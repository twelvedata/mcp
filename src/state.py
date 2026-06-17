"""Shared MCP instance, global state, and helper functions."""

from __future__ import annotations

import json
import os
import time
from typing import Optional

from mcp.server.fastmcp import FastMCP, Context

from auth import TwelveDataAuth, load_config
from client import TwelveDataClient
from store import store
from oauth import build_auth, resolve_apikey

# OAuth Authorization Server (HTTP / multi-user). (None, None) for stdio.
_oauth_provider, _auth_settings = build_auth()

# Pending OAuth logins: state → {"auth": TwelveDataAuth, "session_id": str, "created_at": float}
_oauth_pending: dict = {}
_OAUTH_PENDING_TTL = 600  # 10 minutes

# Hot, request-path caches. The durable source of truth is `store` (Redis, with
# a sessions.json fallback); these are warmed from it at startup and written
# through on login / session-resolve so data-request lookups stay I/O-free.
#
# session_id → api_token
_session_tokens: dict[str, str] = {}
# session_id → user_id (for access logs)
_session_user_ids: dict[str, str] = {}
# user_id → api_token  (stable identity that survives restarts)
_persisted_sessions: dict[str, str] = {}

store.warm(_persisted_sessions, _session_tokens, _session_user_ids)

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
    host=os.environ.get("MCP_HOST", "0.0.0.0"),
    auth_server_provider=_oauth_provider,
    auth=_auth_settings,
)

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
    """Persist api_token to the durable store (Redis/file) and warm caches."""
    if not api_token:
        return
    user_id = store.save_user_from_profile(api_token, profile)
    _persisted_sessions[user_id] = api_token
    if session_id:
        _session_tokens[session_id] = api_token
        _session_user_ids[session_id] = user_id
        store.save_session(session_id, user_id, api_token)


def _get_client(request_api_token: Optional[str] = None) -> TwelveDataClient:
    return TwelveDataClient(request_api_token or "")


def _token_from_ctx(ctx: Context) -> Optional[str]:
    """Return the api_token for the current request, checking in order:

    1. In-memory session map (keyed by Mcp-Session-Id)
    2. Per-request Bearer header
    3. Auto-restore: if exactly one user in sessions.json, use their token
    """
    # OAuth (HTTP, multi-user): identity is the access token the SDK validated.
    # Resolve the bound user → their Twelve Data api_token. This is the path
    # used by ChatGPT / Claude connectors and survives restarts.
    apikey = resolve_apikey()
    if apikey:
        return apikey

    session_id = ""
    try:
        req        = ctx.request_context.request
        session_id = req.headers.get("mcp-session-id", "")
        if session_id and session_id in _session_tokens:
            return _session_tokens[session_id]
        # Cache miss: a session created by another worker (or before a restart
        # where the id is still alive) may live in the durable store.
        if session_id:
            rec = store.get_session(session_id)
            if rec and rec.get("api_token"):
                _session_tokens[session_id] = rec["api_token"]
                if rec.get("user_id"):
                    _session_user_ids[session_id] = rec["user_id"]
                return rec["api_token"]
        auth_header = req.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            return auth_header[7:].strip() or None
    except Exception:
        pass
    if len(_persisted_sessions) == 1:
        user_id, api_token = next(iter(_persisted_sessions.items()))
        if session_id:
            _session_tokens[session_id] = api_token
            _session_user_ids[session_id] = user_id
            store.save_session(session_id, user_id, api_token)
        return api_token
    return None


def _err(data) -> Optional[str]:
    if isinstance(data, dict) and data.get("status") == "error":
        msg = data.get("message", "Unknown error from Twelve Data")
        # Plan gating comes as 403 or 404 — gate on the code first, then confirm
        # via the message (a 404 is also a genuine "symbol not found", so the
        # code alone isn't enough). The plan message names a plan / pricing link.
        code = str(data.get("code"))
        lower = msg.lower()
        is_plan = code in ("403", "404") and (
            "twelvedata.com/pricing" in lower or "upgrad" in lower or "plan" in lower
        )
        if is_plan:
            # Lead with Twelve Data's own message (it carries the plan + pricing
            # link); append a short steer so the model surfaces it instead of
            # silently falling back to web search.
            return (
                f"{msg}\n\n"
                "(This data requires upgrading the user's Twelve Data plan. Relay "
                "the message and pricing link above to the user; do not fall back "
                "to web search or prior knowledge.)"
            )
        return f"Error: {msg}"
    return None


def _raw(data) -> str:
    """Return API response as a string: CSV text as-is, JSON dicts serialized."""
    return data if isinstance(data, str) else json.dumps(data)


