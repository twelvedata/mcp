"""Shared MCP instance, global state, and helper functions."""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.fastmcp import FastMCP, Context

from auth import TwelveDataAuth, load_config
from client import Credential, Refusal, TwelveDataClient
from exchange import Exchanger
from failures import ToolFailure
from lru import LRUDict as _LRUDict
from scopes import declare as _declare_scope
from store import store
from oauth import build_auth
from oauth.config import (
    EXCHANGE_CACHE_MAX,
    EXCHANGE_CLIENT_ID,
    EXCHANGE_CLIENT_SECRET,
    LOCAL_MODE,
    token_endpoint,
)

# One exchanger for the process. Its connection pool and its cache are opened and closed
# with the application lifespan, never at import: a socket created at import leaks one per
# reload the test harness performs.
exchanger = Exchanger(
    token_endpoint=token_endpoint(),
    client_id=EXCHANGE_CLIENT_ID,
    client_secret=EXCHANGE_CLIENT_SECRET,
    cache_max=EXCHANGE_CACHE_MAX,
)

# The token verifier and the SDK's auth settings. (None, None) for stdio / local. Built after
# the exchanger, which is what it verifies with.
_token_verifier, _auth_settings = build_auth(exchanger)

_dataplane_log = logging.getLogger("dataplane")

# The five log slugs the data plane's refusals are read through. Each names a different
# branch of ours, and a slug that means two things means nothing.
LOG_CREDENTIAL_REFUSED = "dataplane: credential refused"
LOG_BRANCH_DID_NOT_RUN = "dataplane: bearer branch did not run"
LOG_TRANSIENT_UPSTREAM = "dataplane: transient upstream"
LOG_UPSTREAM_INTERNAL = "dataplane: upstream internal error"
LOG_DATAPLANE_UNREACHABLE = "dataplane: unreachable"

# The body the data plane answers a request its Bearer branch never reached. It is one
# constant on that side, rendered by one function, so matching its leading words is enough
# — and copying the rest of it in is what would make the match brittle. The asterisks are
# part of it: the message is rendered as markdown to the user.
_MISSING_APIKEY_BODY = "**apikey** parameter is incorrect or not specified"

# Pending OAuth logins for the local browser flow: state → {"auth", "session_id", "created_at"}
_oauth_pending: dict = {}
_OAUTH_PENDING_TTL = 600  # 10 minutes

# Largest number of Mcp-Session-Id entries kept in the hot caches below.
_SESSION_CACHE_MAX = int(os.environ.get("MCP_SESSION_CACHE_MAX", "5000") or "5000")

# Hot caches for the local login flow; the user map is warmed from `store` at startup. Local
# only: on a hosted deployment identity comes from the verified token, and warming would pull
# every legacy user's permanent api_token into this process for nothing to read.
#
# session_id → api_token
_session_tokens: dict[str, str] = _LRUDict(_SESSION_CACHE_MAX)
# session_id → user_id (for access logs)
_session_user_ids: dict[str, str] = _LRUDict(_SESSION_CACHE_MAX)
# user_id → api_token  (stable identity that survives restarts)
_persisted_sessions: dict[str, str] = {}

if LOCAL_MODE:
    store.warm(_persisted_sessions)

mcp = FastMCP(
    "Twelve Data",
    instructions="""Financial data assistant powered by Twelve Data.

Capabilities:
- Real-time & historical prices — stocks, ETFs, forex, crypto, commodities
- 60+ technical indicators (RSI, MACD, SMA, BBANDS, ATR, etc.)
- Fundamentals — financial statements, earnings, dividends, splits, company profiles, market cap & key stats, IPO calendar
- Funds — ETF & mutual fund profiles, performance, holdings, risk
- Company news & press releases — recent announcements per company
- Market intelligence — movers, exchange rates, analyst ratings, price targets
- Regulatory — SEC/EDGAR filings, insider transactions, institutional holdings

NOT available — do not claim these are supported:
- Market indices themselves (e.g. S&P 500 / SPX, NASDAQ Composite / IXIC,
  NASDAQ-100 / NDX, Dow Jones / DJI). Use an index ETF as a proxy instead:
    S&P 500       → SPY  (also IVV, VOO)
    NASDAQ-100    → QQQ
    Dow Jones     → DIA
    Russell 2000  → IWM
    Total market  → VTI
  When a user asks for an index, tell them the index itself isn't covered and
  offer the matching ETF proxy.
- Options (calls/puts, option chains).
- Bonds / fixed income.

Symbol formats:
  Stocks  → AAPL, MSFT, TSLA
  Crypto  → BTC/USD, ETH/USD
  Forex   → EUR/USD, GBP/JPY
""" + (
    "\nAuthentication is handled automatically via OAuth when you connect — no auth tool to call."
    if _auth_settings is not None else
    "\nAuthentication: call oauth_login, or set TWELVE_DATA_API_KEY in the server environment."
),
    host=os.environ.get("MCP_HOST", "0.0.0.0"),  # noqa: S104 — a container reaches its port through the bridge
    token_verifier=_token_verifier,
    auth=_auth_settings,
)


def td_tool(*, scope: str, **kwargs):
    """Register a tool, declaring the scope a caller's token must carry for it.

    The SDK's own decorator has no argument for a scope, so the declaration rides on the
    tool's `_meta`, where the registry walk can read it back. A tool registered through
    `mcp.tool` directly declares none and fails that walk.
    """
    return mcp.tool(meta=_declare_scope(scope), **kwargs)


_UNSET = object()
_shared_auth: object = _UNSET  # TwelveDataAuth | None once loaded


def _get_shared_auth() -> Optional[TwelveDataAuth]:
    global _shared_auth
    if _shared_auth is _UNSET:
        cfg  = load_config()
        cid  = cfg.get("client_id", "")
        csec = cfg.get("client_secret", "")
        _shared_auth = TwelveDataAuth(cid, csec) if (cid and csec) else None
    return _shared_auth  # type: ignore[return-value]


def _reset_shared_auth() -> None:
    """Force re-read of config on next _get_shared_auth() call."""
    global _shared_auth
    _shared_auth = _UNSET


def _persist_user_token(api_token: str, profile: dict, session_id: str = "") -> None:
    """Persist api_token to the durable store (sessions.json) and warm caches."""
    if not api_token:
        return
    user_id = store.save_user_from_profile(api_token, profile)
    _persisted_sessions[user_id] = api_token
    if session_id:
        _session_tokens[session_id] = api_token
        _session_user_ids[session_id] = user_id


def _get_client(credential: Optional[Credential] = None) -> TwelveDataClient:
    return TwelveDataClient(credential, exchanger)


def request_user(ctx: Context) -> Optional[AuthenticatedUser]:
    """The principal of THIS request, off the ASGI scope.

    Never `get_access_token()`: a tool body does not run in its own request's task. The
    session manager starts one task per session inside the *initialize* POST, and anyio
    copies the caller's context into it — so the contextvar every later call reads holds the
    token presented when the connector connected, which is expired from the sixteenth minute
    of a session on.
    """
    try:
        request = ctx.request_context.request
    except Exception:  # noqa: BLE001 — a guard on the request path; it must never be what fails a call
        return None
    return user_from_scope(getattr(request, "scope", None))


def user_from_scope(scope) -> Optional[AuthenticatedUser]:
    """The principal on an ASGI scope, guarded both ways.

    `scope.get` and never `scope["user"]`: the SDK installs its authentication middleware
    only when auth is configured, so a local HTTP deployment has no such key at all. And an
    isinstance check and never `.access_token`: an unauthenticated request carries
    Starlette's own UnauthenticatedUser, which has no such attribute.
    """
    if not isinstance(scope, dict):
        return None
    user = scope.get("user")
    return user if isinstance(user, AuthenticatedUser) else None


def _token_from_ctx(ctx: Context) -> Optional[Credential]:
    """The credential this request may spend at the data plane, or nothing.

    On a hosted deployment there is one source: the token this request presented and the
    verifier accepted. It is a subject token, which the seam exchanges — an identity, not
    something the data plane would take.

    Local mode keeps three rungs, and what they yield is an api_token: the Bearer a laptop
    passes as its own key, the single stored user, who on a single-tenant process is by
    definition the caller, and TWELVE_DATA_API_KEY. All three are gated on the local signal
    rather than on whether verification is on, because a hosted box with verification
    switched off would otherwise answer every caller with one tenant's key.
    """
    user = request_user(ctx)
    if user is not None:
        name = (user.access_token.claims or {}).get("td_client_name")
        return Credential.subject_token(
            user.access_token.token,
            # A claim of any other type is dropped rather than refused: it names nothing but
            # an analytics bucket, so a bad one costs attribution and never a tool call.
            client_name=name if isinstance(name, str) and name else None,
        )

    if not LOCAL_MODE:
        return None

    session_id = ""
    try:
        req = ctx.request_context.request
        session_id = req.headers.get("mcp-session-id", "")
        auth_header = req.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            raw = auth_header[7:].strip()
            if raw:
                return Credential.api_token(raw)
    except Exception:
        pass

    if len(_persisted_sessions) == 1:
        user_id, api_token = next(iter(_persisted_sessions.items()))
        if session_id:
            _session_tokens[session_id] = api_token
            _session_user_ids[session_id] = user_id
        return Credential.api_token(api_token)

    # The documented way to run this server without logging in at all. It used to live at
    # the seam, where it applied to every deployment: with the variable set on a host, a
    # request whose credential did not resolve was served under the server's own key.
    own_key = os.environ.get("TWELVE_DATA_API_KEY", "")
    if own_key:
        return Credential.api_token(own_key)
    return None


def _err(data) -> Optional[str]:
    """Turn a refusal from the data plane into what the agent should read.

    A returned string is `isError=False` — a successful call whose content says "error" —
    so it is what a refusal the user can act on gets. A failure of ours is raised instead,
    which is the only thing an agent can tell apart and the thing that decides whether it
    retries.

    The discriminator is the status line first, then WWW-Authenticate, then the body. The
    order is what keeps the one refusal that carries no challenge out of the arm that is
    about challenges.
    """
    if isinstance(data, Refusal):
        return _map_refusal(data)
    if isinstance(data, dict) and data.get("status") == "error":
        # A 200 carrying an error envelope: some upstreams answer this way, and so do the
        # endpoints that report in-band.
        return _plan_aware(str(data.get("message", "Unknown error from Twelve Data")), str(data.get("code")))
    return None


def _map_refusal(refusal: Refusal) -> str:
    status = refusal.status
    message = refusal.message

    if status is None:
        # The request never completed, so nothing was refused and nobody said anything about
        # the credential: this is ours. It is the one input of the default arm with a shape
        # known in advance, and leaving it there answered a connection failure with a string
        # — a successful call whose content says "error", which is the one thing an agent
        # cannot tell from data. The message is logged and not relayed: it is httpx's, and
        # the agent's move is the same whichever socket failed.
        _dataplane_log.error("%s: %s", LOG_DATAPLANE_UNREACHABLE, message)
        raise ToolFailure(  # noqa: TRY003 — the agent reads this message
            "Twelve Data could not be reached. The call is worth repeating."
        )

    if status == 503 and refusal.retry_after:
        # It says "ask again" and carries a machine-readable when. A keyset it could not
        # consult is the interesting cause and not the only one — an edge attaches this
        # header as a matter of course — so the slug names the class and not the cause.
        _dataplane_log.error("%s: retry_after=%s", LOG_TRANSIENT_UPSTREAM, refusal.retry_after)
        raise ToolFailure(  # noqa: TRY003 — the agent reads this message
            f"Twelve Data is briefly unavailable and suggested retrying in {refusal.retry_after} "
            "seconds. The call is worth repeating."
        )

    if status == 401:
        if refusal.www_authenticate:
            # Never passed through as a 401: the agent's own token is valid, so telling it
            # to authorize sends it through a flow that succeeds and returns it here.
            _dataplane_log.error("%s: %s", LOG_CREDENTIAL_REFUSED, refusal.www_authenticate)
            raise ToolFailure(  # noqa: TRY003 — the agent reads this message
                "Twelve Data refused this server's own credential for this account. Signing in "
                "again will not change it; try again shortly."
            )
        if message.lower().startswith(_MISSING_APIKEY_BODY):
            # The node is serving without its Bearer branch. What this repository owes is
            # not relaying Twelve Data's API-key sales copy to a user who already has an
            # account.
            _dataplane_log.error("%s", LOG_BRANCH_DID_NOT_RUN)
            raise ToolFailure(  # noqa: TRY003 — the agent reads this message
                "Twelve Data did not accept this server's credential on the node that answered. "
                "Try again shortly."
            )
        return f"Error: {message}"

    if status == 402:
        # A lapsed subscription, and the link in the message is a BILLING link: the user's
        # action is paying an invoice rather than upgrading a plan, which is why this arm
        # does not share the plan-gate sentence.
        return (
            f"{message}\n\n"
            "(The user's Twelve Data subscription has lapsed. Relay the message and the billing "
            "link above to the user; the action is paying the outstanding invoice.)"
        )

    if status == 500:
        # The account lookup or the quota service failed inside the data plane. Two
        # different bodies arrive here and nothing branches on which, so neither is relayed.
        _dataplane_log.error("%s: status=500", LOG_UPSTREAM_INTERNAL)
        raise ToolFailure(  # noqa: TRY003 — the agent reads this message
            "Twelve Data could not complete the request. Try again shortly."
        )

    return _plan_aware(message, str(status) if status is not None else refusal.code)


def _plan_aware(message: str, code: Optional[str]) -> str:
    """The plan-gate arm, unchanged, and the default that makes the rule total.

    Plan gating comes as 403 or 404 — the code alone is not enough, a 404 also being a
    genuine "symbol not found" — so the message has to name a plan or a pricing link.
    """
    lower = message.lower()
    is_plan = code in ("403", "404") and (
        "twelvedata.com/pricing" in lower or "upgrad" in lower or "plan" in lower
    )
    if is_plan:
        # Lead with Twelve Data's own message (it carries the plan + pricing link); append a
        # short steer so the model surfaces it instead of falling back to web search.
        return (
            f"{message}\n\n"
            "(This data requires upgrading the user's Twelve Data plan. Relay "
            "the message and pricing link above to the user; do not fall back "
            "to web search or prior knowledge.)"
        )
    return f"Error: {message}"


def _raw(data) -> str:
    """Return API response as a string: CSV text as-is, JSON dicts serialized."""
    return data if isinstance(data, str) else json.dumps(data)
