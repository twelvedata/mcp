"""Twelve Data API HTTP client, and the credential it is handed.

The seam every tool call passes through. What flows through it is a typed credential rather
than a bare string, because the two kinds have different destinations and nothing at the
call sites says which one it is holding: a subject token is exchanged and sent as a Bearer,
an api_token is sent as `apikey`, and a value whose meaning is inferred from the mode a
reader has to remember is the defect this seam exists to avoid.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

import httpx

from exchange import Exchanger
from failures import AuthorizationFailure
from oauth.config import API_RESOURCE, LOCAL_MODE

# Where the data plane is. It is configuration and not a constant because this seam is the
# one part of a tool call that cannot otherwise be exercised against anything but the public
# API — a test environment verifying the Bearer hop has to name its own. What it decides is
# where a live data-plane credential is SENT, which is why it has a working default and
# nothing but a deployment's own environment can move it; MCP_DATA_API_RESOURCE is the
# audience that credential is minted for and answers a different question.
DEFAULT_API_BASE = "https://api.twelvedata.com"


def _api_base() -> str:
    # `or` and not a default argument: an empty assignment is what a compose file writes for
    # a key nothing set, and it would otherwise defeat the default rather than fall back to it.
    return (os.environ.get("MCP_DATA_API_BASE") or DEFAULT_API_BASE).rstrip("/")


API_BASE = _api_base()


@dataclass(frozen=True)
class Credential:
    """What the caller proved, and which kind of proof it is.

    `client_name` is the agent's name as its token states it, for attributing traffic to
    the agent product. It is attribution and not proof: a self-registered client chose it.
    """

    kind: Literal["subject_token", "api_token"]
    value: str
    # Outside equality, so two credentials holding the same token stay the same credential.
    client_name: Optional[str] = field(default=None, compare=False)

    @staticmethod
    def subject_token(value: str, client_name: Optional[str] = None) -> "Credential":
        return Credential("subject_token", value, client_name)

    @staticmethod
    def api_token(value: str) -> "Credential":
        return Credential("api_token", value)


@dataclass(frozen=True)
class Refusal:
    """A refusal from the data plane, with the two headers the mapping discriminates on.

    `TwelveDataClient.get` used to return the decoded body alone, and the status line and
    both headers were thrown away one layer below the code that has to branch on them.
    """

    status: Optional[int]
    message: str
    code: Optional[str] = None
    www_authenticate: str = ""
    retry_after: str = ""


class TwelveDataClient:
    def __init__(self, credential: Optional[Credential] = None, exchanger: Optional[Exchanger] = None):
        self._credential = credential
        self._exchanger = exchanger

    async def get(self, endpoint: str, **params: Any) -> "dict | str | Refusal":
        headers = await self._authorization()
        clean = {k: str(v) for k, v in params.items() if v is not None}
        clean["format"] = "CSV"
        clean["source"] = _source(self._credential.client_name if self._credential else None)
        try:
            async with httpx.AsyncClient(timeout=30.0) as http:
                resp = await http.get(f"{API_BASE}/{endpoint}", headers=headers, params=clean)
                try:
                    body = resp.json()  # error envelope or JSON-only endpoints
                except Exception:  # noqa: BLE001 — a body that will not decode is one refusal: there is none
                    body = None

                if resp.is_success:
                    return body if body is not None else resp.text  # CSV response

                message, code = _refusal_body(body, resp)
                return Refusal(
                    status=resp.status_code,
                    message=message,
                    code=code,
                    www_authenticate=resp.headers.get("www-authenticate", ""),
                    retry_after=resp.headers.get("retry-after", ""),
                )
        except httpx.RequestError as exc:
            # No status line at all, which is what the mapping's first arm reads: a request
            # that never completed is ours rather than a refusal the user can act on.
            return Refusal(status=None, message=f"Request failed: {exc}")

    async def _authorization(self) -> dict[str, str]:
        if self._credential is None or not self._credential.value:
            raise AuthorizationFailure(
                "Not authenticated. Run oauth_login or set the TWELVE_DATA_API_KEY "
                "environment variable."
                if LOCAL_MODE
                else "Not authenticated — reconnect the Twelve Data integration to authorize again."
            )
        if self._credential.kind == "api_token":
            return {"Authorization": f"apikey {self._credential.value}"}
        if self._exchanger is None:  # pragma: no cover - wiring error, not a request outcome
            raise AuthorizationFailure(  # noqa: TRY003 — the agent reads this message
                "Not authenticated — this server cannot obtain a data credential."
            )
        exchanged = await self._exchanger.token_for(self._credential.value, API_RESOURCE)
        return {"Authorization": f"Bearer {exchanged}"}


_SLUG_MAX = 32
_NOT_SLUG = re.compile(r"[^a-z0-9]")


def _source(client_name: Optional[str]) -> str:
    """`mcp`, or `mcp-<slug>` of the agent's name, for the data plane's traffic analytics.

    One dash per character outside `[a-z0-9]`, with no collapsing and no trimming, so a name
    maps to exactly one value that the analytics side can predict from the name alone.
    """
    if not client_name:
        return "mcp"
    return "mcp-" + _NOT_SLUG.sub("-", client_name.lower())[:_SLUG_MAX]


def _refusal_body(body: object, resp: httpx.Response) -> tuple[str, Optional[str]]:
    """The message and Twelve Data's own `code`, which is the status line on this branch.

    The status is NOT stamped into `code` here. It used to be, with a comment promising it
    always would, while `CreateErrorMap` on the other side always writes one — so the
    fallback never fired and a reader relied on it for a refusal that arrives with no JSON
    envelope at all.
    """
    if isinstance(body, dict):
        message = str(body.get("message", "")) or f"HTTP {resp.status_code}"
        code = body.get("code")
        return message, str(code) if code is not None else None
    return f"HTTP {resp.status_code}: {resp.text[:300]}", None
