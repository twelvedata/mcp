"""RFC 8693 token exchange against the Twelve Data Authorization Server.

The agent's MCP-audience token is not a credential for the data plane, so it is traded here
for an API-audience one that tool calls send as a Bearer. The trade is also this server's
verification of the token: the first request carrying it performs the exchange, and every
tool call after that reuses the result. The exchange writes nothing at the Authorization
Server, which is what makes caching it a pure saving.

On failure this refuses. There is no apikey to fall back to and no second attempt with
different parameters: a fallback would quietly restore the credential path this phase
exists to remove.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import time
from typing import Callable, Optional
from urllib.parse import quote

import httpx

from failures import AuthorizationFailure, ToolFailure
from lru import LRUDict

log = logging.getLogger("exchange")

GRANT_TYPE = "urn:ietf:params:oauth:grant-type:token-exchange"  # an IANA URN
# The same URN, and the directive is on this one alone: S105 reads the NAME, and only this
# name carries "TOKEN".
SUBJECT_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"  # noqa: S105 — an IANA URN

# The design fixes the client timeout on the Authorization Server's endpoints at ten
# seconds and calls it a hard requirement on this service and on any proxy in front of it.
# It is not a measurement of ours, and a multiple of one taken on the same host as the
# server would fire on a healthy production exchange: that number says how long the server
# computes, not how long a round trip to another host takes.
TIMEOUT_SECONDS = 10.0

# How many exchanges may be on the wire at once, below httpx's default pool of 100 so that
# nothing queues there. Past it a new token is refused at once rather than queued: httpcore 1.0.9
# walks every queued request against every connection on each pool event, so a queue that
# outgrows this process's CPU never drains, even once the load that built it is gone.
MAX_INFLIGHT = 32

# At most one shed line per interval, carrying the count: the refusals arrive at the flooder's
# rate, and a line each would be one more cost per forged token.
SHED_LOG_INTERVAL_SECONDS = 10.0

# The named event an operator greps for: this service has no metric surface.
LOG_EVENT = "exchange failed"

# An `invalid_grant` is the presenter's and arrives at whatever rate the presenter chooses, so
# it is DEBUG under a name of its own. The Authorization Server logs the same refusal with its
# reason and the access line records the 401, so at INFO it would only be one more cost per
# forged token; at ERROR under the event above it would bury the line read for an outage.
LOG_INVALID_GRANT = "exchange refused: invalid_grant"

LOG_SHED = "exchange shed: at capacity"


def cache_key(subject_token: str, resource: str) -> tuple[bytes, str]:
    """The key every map here uses: the whole token's digest, and the resource.

    Never a claim. Once a cache hit is the verification, a key derived from `jti` or `sid` is
    one anyone can reproduce in an unsigned token of their own, and the hit hands them the
    exchanged credential of the user whose claim they copied. A digest rather than the token
    so that no key in a map is a live credential.
    """
    return hashlib.sha256(subject_token.encode()).digest(), resource


def basic_credentials(client_id: str, client_secret: str) -> str:
    """The Authorization header value, both halves form-urlencoded first.

    RFC 6749 §2.3.1 requires that encoding, and a client id that is a URL is what makes it
    load-bearing rather than pedantic: the server splits the decoded pair at the FIRST
    colon, so `https://mcp.example.com/client` sent raw reads back as the client id
    `https` and the exchange is refused `invalid_client`.
    """
    pair = f"{quote(client_id, safe='')}:{quote(client_secret, safe='')}"
    return "Basic " + base64.b64encode(pair.encode()).decode()


class ExchangeFailed(ToolFailure):
    """The Authorization Server did not answer with a credential.

    A failure of ours. On a tool call it is raised rather than returned and reaches the agent
    marked `isError` — the one thing an agent can read to tell "retry" from "the user must
    act"; on the verification of a request it is the 503 the verifier's layer answers.
    """


class Exchanger:
    def __init__(
        self,
        token_endpoint: str,
        client_id: str,
        client_secret: str,
        cache_max: int,
        http: Optional[httpx.AsyncClient] = None,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._token_endpoint = token_endpoint
        # One header for the process rather than the pair: the credentials do not change,
        # and httpx's own `auth=` tuple encodes neither half.
        self._authorization = basic_credentials(client_id, client_secret)
        self._now = now
        self._http = http
        self._owns_http = http is None
        # Keyed by cache_key(): the exchanged token carries the subject token's own exp, so
        # an entry can never outlive the credential it was derived from. The ceiling is what
        # bounds the map, whose insertion rate is one per subject token per fifteen minutes
        # per live grant.
        self._cache_max = max(1, cache_max)
        self._cache: LRUDict = LRUDict(self._cache_max)
        self._inflight: dict[tuple[bytes, str], asyncio.Task] = {}
        self._shed = 0
        self._shed_logged_at: Optional[float] = None

    async def start(self) -> None:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=TIMEOUT_SECONDS)

    async def close(self) -> None:
        if self._http is not None and self._owns_http:
            await self._http.aclose()
        self._http = None

    async def token_for(self, subject_token: str, resource: str) -> str:
        """Exchange this request's subject token for one the data plane accepts.

        Once per subject token while its entry is resident: an entry evicted under pressure
        is exchanged again, which is the price of the bound rather than a defect in it.
        """
        key = cache_key(subject_token, resource)
        cached = self._cache.get(key)
        if cached is not None and cached[1] > self._now():
            return cached[0]

        task = self._inflight.get(key)
        if task is None:
            # Checked only here, so a caller collapsing onto an exchange already running takes
            # no slot, and with no await before the insert the count cannot be overshot.
            if len(self._inflight) >= MAX_INFLIGHT:
                self._shed += 1
                self._log_shed()
                raise ExchangeFailed(  # noqa: TRY003 — the agent reads this message
                    "too many verifications are in progress — retry shortly"
                )
            self._log_shed()
            task = asyncio.create_task(self._exchange(key, subject_token))
            self._inflight[key] = task
        # Shielded: a caller that hangs up must not cancel the exchange the other waiters
        # on this key are collapsed onto.
        return await asyncio.shield(task)

    async def _exchange(self, key: tuple[bytes, str], subject_token: str) -> str:
        # The token travels beside the key: the key holds only its digest.
        resource = key[1]
        try:
            token, expires_in = await self._request(subject_token, resource)
            if expires_in > 0:
                self._store(key, token, expires_in)
            return token
        finally:
            self._inflight.pop(key, None)

    async def _request(self, subject_token: str, resource: str) -> tuple[str, int]:
        if self._http is None:
            raise ExchangeFailed("the exchange client is not open")  # noqa: TRY003 — the agent reads this message
        try:
            # One deadline over the whole request: httpx times connect, write and each read
            # separately, a read between bytes, so without it one slow answer holds a slot for
            # a multiple of the timeout. wait_for and not asyncio.timeout, which needs 3.11.
            resp = await asyncio.wait_for(
                self._http.post(
                    self._token_endpoint,
                    data={
                        "grant_type": GRANT_TYPE,
                        "subject_token": subject_token,
                        "subject_token_type": SUBJECT_TOKEN_TYPE,
                        "resource": resource,
                    },
                    headers={"Authorization": self._authorization},
                ),
                TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as exc:
            log.error("%s: no answer within %.0fs", LOG_EVENT, TIMEOUT_SECONDS)  # noqa: TRY400 — the traceback travels on the raise
            raise ExchangeFailed(  # noqa: TRY003 — the agent reads this message
                "the Authorization Server did not answer in time"
            ) from exc
        except httpx.HTTPError as exc:
            # log.error and not log.exception: the traceback travels on the raise below, and
            # what this line is for is the one greppable event.
            log.error("%s: %s: %s", LOG_EVENT, type(exc).__name__, exc)  # noqa: TRY400 — see above
            raise ExchangeFailed(  # noqa: TRY003 — the agent reads this message
                "the Authorization Server could not be reached"
            ) from exc

        if resp.status_code != 200:
            # The status and the OAuth error code, never the body: one carries the operator
            # the whole way and the other is a response this service did not write.
            code = ""
            try:
                code = str(resp.json().get("error", ""))
            except (ValueError, AttributeError):
                # A body that is not JSON, or is JSON but not an object. The status line
                # below carries the operator either way.
                pass
            if resp.status_code == 400 and code == "invalid_grant":
                # THE ONE REFUSAL RECONNECTING CAN FIX, and it is keyed on the OAuth code AND on
                # the status RFC 6749 §5.2 gives it: `invalid_grant` is a grant that is expired,
                # revoked or issued to someone else — the user's authorization being gone. Every
                # other refusal the exchange can draw is this server's own configuration
                # (`invalid_target`, `invalid_client`, `unauthorized_client`), and a 429 or a 5xx
                # is someone's outage whatever its body names — a proxy's
                # `500 {"error":"invalid_grant"}` would otherwise send every user to reauthorize.
                # Offering a reconnect for any of those sends users round a loop that cannot
                # end. An unparseable body leaves `code` empty and takes the arm below, which is
                # the safe direction: we do not ask a user to act on a refusal we could not read.
                log.debug("%s: status=%d", LOG_INVALID_GRANT, resp.status_code)
                raise AuthorizationFailure(  # noqa: TRY003 — the agent reads this message
                    "Twelve Data no longer accepts this connection's authorization — "
                    "reconnect the integration to authorize again.",
                    error="invalid_token",
                )
            log.error("%s: status=%d error=%s", LOG_EVENT, resp.status_code, code or "-")
            raise ExchangeFailed(  # noqa: TRY003 — the agent reads this message
                f"the Authorization Server refused the exchange ({resp.status_code})"
            )

        # A 200 is a verdict only when it carries a credential: accepting any `access_token`
        # would turn `123` or `""` into an accepted token and a failed tool call. `int()` is
        # not the check — it takes "900", 900.7 and True alike.
        try:
            body = resp.json()
        except ValueError:
            body = None
        token = body.get("access_token") if isinstance(body, dict) else None
        expires_in = body.get("expires_in", 0) if isinstance(body, dict) else None
        if (
            not isinstance(token, str)
            or not token
            or not isinstance(expires_in, int)
            or isinstance(expires_in, bool)
        ):
            log.error("%s: unusable response", LOG_EVENT)
            raise ExchangeFailed(  # noqa: TRY003 — the agent reads this message
                "the Authorization Server answered without a credential"
            )
        return token, expires_in

    def _store(self, key: tuple[bytes, str], token: str, expires_in: int) -> None:
        # Swept at the ceiling rather than on every insert: the scan is O(map) and the
        # insert rate rises with the same population the map does, so per-insert costs an
        # event-loop share rising faster than the square — 0.6 ms over 8k entries, 27 ms
        # over 128k. The ceiling is where it earns that cost, a dead entry being what
        # would otherwise take a live one's slot; nothing SERVES a dead entry either way,
        # token_for checking exp on the way out.
        now = self._now()
        if len(self._cache) >= self._cache_max:
            for dead in [k for k, v in self._cache.items() if v[1] <= now]:
                del self._cache[dead]
        self._cache[key] = (token, now + expires_in)

    def _log_shed(self) -> None:
        # Also called on an admission, so the count of a flood's last interval is written by
        # the next exchange rather than lost.
        if not self._shed:
            return
        now = self._now()
        if self._shed_logged_at is not None and now - self._shed_logged_at < SHED_LOG_INTERVAL_SECONDS:
            return
        log.warning("%s: shed=%d max_inflight=%d", LOG_SHED, self._shed, MAX_INFLIGHT)
        self._shed = 0
        self._shed_logged_at = now

    def now(self) -> float:
        """The clock every deadline here is on — monotonic, and the one a test injects."""
        return self._now()

    # Test seams: what is asserted is the map, not the passage of time.
    def cache_size(self) -> int:
        return len(self._cache)

    def in_flight(self) -> int:
        return len(self._inflight)

    def cached(self, subject_token: str, resource: str) -> Optional[str]:
        entry = self._cache.get(cache_key(subject_token, resource))
        return entry[0] if entry is not None and entry[1] > self._now() else None
