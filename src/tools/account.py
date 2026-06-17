"""Account and authentication tools."""

from __future__ import annotations

import json
import os
import time
from typing import Optional

from mcp.server.fastmcp import Context

from auth import load_config, save_config, CALLBACK_PORT
from state import (
    mcp,
    _get_shared_auth, _reset_shared_auth, _persist_user_token,
    _get_client, _token_from_ctx, _err, _raw,
    _oauth_pending, _OAUTH_PENDING_TTL, _session_tokens, _persisted_sessions,
)
from store import store
from oauth.config import ENABLED as _OAUTH_AS_ENABLED


@mcp.tool()
async def oauth_login(ctx: Context) -> str:
    """Authenticate with Twelve Data via OAuth 2.0.

    Opens a browser window for the user to authorize access.
    After login the api_token is fetched from the user profile and saved locally.
    Requires MCP_DATA_TWELVE_DATA_CLIENT_ID and MCP_DATA_TWELVE_DATA_CLIENT_SECRET environment variables.
    Alternatively, set TWELVE_DATA_API_KEY to skip OAuth entirely.
    """
    # When the Authorization Server is active (remote multi-user: ChatGPT /
    # Claude connectors), login already happened when the integration connected.
    # Short-circuit so the model gets a clear signal instead of running the
    # legacy browser flow.
    if _OAUTH_AS_ENABLED:
        return (
            "Already authenticated — this connection uses OAuth, so no separate login "
            "step is needed. Just ask for data (e.g. 'price of AAPL'). If a request "
            "reports 'Not authenticated', reconnect the integration to re-run OAuth."
        )
    auth = _get_shared_auth()
    if auth is None:
        return (
            "OAuth not configured — MCP_DATA_TWELVE_DATA_CLIENT_ID / MCP_DATA_TWELVE_DATA_CLIENT_SECRET not set.\n"
            "Call oauth_configure first, or set them in .env and restart the server."
        )

    try:
        req   = ctx.request_context.request
        host  = (
            req.headers.get("x-forwarded-host")
            or req.headers.get("host", "")
        ).split(":")[0]
        proto = req.headers.get("x-forwarded-proto", "https")
        if host and "localhost" not in host and "127.0.0.1" not in host:
            os.environ["MCP_DATA_TWELVE_DATA_REDIRECT_URI"] = f"{proto}://{host}/callback"
    except Exception:
        pass

    redirect_uri = auth._redirect_uri()
    is_public    = not redirect_uri.startswith("http://localhost")

    if is_public:
        import secrets as _secrets
        state    = _secrets.token_urlsafe(16)
        auth_url = auth.get_auth_url(state)
        try:
            session_id = ctx.request_context.request.headers.get("mcp-session-id", "")
        except Exception:
            session_id = ""
        now   = time.time()
        stale = [s for s, v in _oauth_pending.items() if now - v["created_at"] > _OAUTH_PENDING_TTL]
        for s in stale:
            del _oauth_pending[s]
        _oauth_pending[state] = {"auth": auth, "session_id": session_id, "created_at": now}
        return (
            f"Open this URL in your browser to authorize:\n\n{auth_url}\n\n"
            "After you authorize, the page will confirm and tokens will be saved automatically.\n"
            "Then call auth_status to verify."
        )
    else:
        result = await auth.login()
        if auth._token_data:
            _persist_user_token(
                auth._token_data.get("api_token", ""),
                auth._token_data.get("_profile_response", {}),
            )
        return result


@mcp.tool()
async def auth_status(ctx: Context) -> str:
    """Show current authentication state — useful for debugging.

    Reports: which credentials are configured, whether OAuth tokens exist,
    whether api_token was successfully fetched from the user profile.
    """
    cfg  = load_config()
    auth = _get_shared_auth()

    has_client_id     = bool(cfg.get("client_id"))
    has_client_secret = bool(cfg.get("client_secret"))
    has_env_api_key   = bool(cfg.get("api_key"))

    detected_host = None
    try:
        req           = ctx.request_context.request
        detected_host = req.headers.get("x-forwarded-host") or req.headers.get("host", "")
    except Exception:
        pass

    redirect_uri = auth._redirect_uri() if auth else f"http://localhost:{CALLBACK_PORT}/callback"

    session_id    = ""
    session_token = ""
    try:
        session_id    = ctx.request_context.request.headers.get("mcp-session-id", "")
        session_token = _session_tokens.get(session_id, "")
    except Exception:
        pass

    lines = [
        "Twelve Data MCP — Auth Status\n",
        f"CLIENT_ID configured              : {'yes' if has_client_id else 'NO'}",
        f"CLIENT_SECRET configured          : {'yes' if has_client_secret else 'NO'}",
        f"API_KEY (env/file)                : {'yes' if has_env_api_key else 'no'}",
        f"Detected request host             : {detected_host or '(stdio — no HTTP context)'}",
        f"Redirect URI                      : {redirect_uri}",
        f"MCP_DATA_TWELVE_DATA_REDIRECT_URI : {os.environ.get('MCP_DATA_TWELVE_DATA_REDIRECT_URI', '(not set)')}",
        f"Mcp-Session-Id                    : {session_id or '(not present)'}",
        f"Session token                     : {'…' + session_token[-6:] if session_token else 'none — call oauth_login'}",
        f"Session store backend             : {store.backend}",
        f"Persisted users ({store.backend:<6})           : {len(_persisted_sessions)} "
        + (f"[{', '.join(_persisted_sessions.keys())}]" if _persisted_sessions else "(empty)"),
    ]

    if not auth:
        lines += ["", "OAuth not configured — set CLIENT_ID + CLIENT_SECRET in .env or call oauth_configure."]

    return "\n".join(lines)


@mcp.tool()
async def oauth_configure(ctx: Context, client_id: str, client_secret: str) -> str:
    """Save Twelve Data OAuth credentials to ~/.twelvedata_mcp/config.json.

    Run this once before oauth_login if credentials are not yet configured.
    The file is stored with chmod 600 (owner-readable only).
    After saving, call oauth_login to complete the authorization flow.
    """
    save_config(client_id, client_secret)
    _reset_shared_auth()
    return (
        f"Credentials saved to ~/.twelvedata_mcp/config.json\n"
        f"client_id: {client_id}\n"
        f"Now call oauth_login to authorize."
    )


@mcp.tool()
async def get_api_usage(ctx: Context) -> str:
    """Check Twelve Data API credit consumption and plan limits.

    Useful to verify authentication is working and to monitor quota.
    """
    client = _get_client(_token_from_ctx(ctx))
    data = await client.get("api_usage")

    if e := _err(data):
        return e

    if isinstance(data, str):
        return data

    return (
        "plan_category,current_usage,plan_limit,timestamp\n"
        f"{data.get('plan_category','')},{data.get('current_usage','')},{data.get('plan_limit','')},{data.get('timestamp','')}"
    )


@mcp.tool()
async def search_symbol(
    ctx: Context,
    symbol: str,
    outputsize: int = 10,
    instrument_type: Optional[str] = None,
    cross_listings: bool = False,
    exchange: Optional[str] = None,
    mic_code: Optional[str] = None,
    country: Optional[str] = None,
) -> str:
    """Search for financial instruments by name or partial ticker, or find cross-listings.

    - cross_listings=False (default) – search by name or partial ticker
      instrument_type filter: Stock | ETF | Mutual Fund | Forex | Cryptocurrency | Commodity
      (indices, options and bonds are not supported — for an index use its ETF
       proxy, e.g. SPY for the S&P 500, QQQ for the NASDAQ-100, DIA for the Dow)

    - cross_listings=True – find all exchanges where a symbol is listed
      exchange / mic_code / country – optional filters to narrow results

    Use for: 'find ticker for Apple', 'search AAPL', 'where else is ASML listed?',
    'cross-listings of BP', 'which exchanges trade TSLA?'
    """
    client = _get_client(_token_from_ctx(ctx))

    if cross_listings:
        data = await client.get(
            "cross_listings",
            symbol=symbol,
            exchange=exchange,
            mic_code=mic_code,
            country=country,
        )
        if e := _err(data):
            return e
        return _raw(data)

    data = await client.get("symbol_search", symbol=symbol, outputsize=outputsize, type=instrument_type)

    if e := _err(data):
        return e

    results = data.get("data", [])
    if not results:
        return f"No instruments found matching '{symbol}'"

    return json.dumps(results)
