"""
Twelve Data MCP Server

Environment variables:
  TWELVE_DATA_API_KEY                – API key (alternative to OAuth)
  MCP_DATA_TWELVE_DATA_CLIENT_ID     – OAuth client ID
  MCP_DATA_TWELVE_DATA_CLIENT_SECRET – OAuth client secret

Claude Desktop config (~/.claude/claude_desktop_config.json):
{
  "mcpServers": {
    "twelvedata": {
      "command": "/path/to/twelve-data-mcp/.venv/bin/python",
      "args": ["/path/to/twelve-data-mcp/server.py"]
    }
  }
}
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from starlette.routing import Route

from views import callback_page
from state import mcp, _oauth_pending, _persist_user_token, _session_user_ids, _session_tokens, _persisted_sessions, _oauth_provider
from oauth import storage as _oauth_storage

_access_log = logging.getLogger("access")
_access_handler = logging.StreamHandler()
_access_handler.setFormatter(logging.Formatter(
    fmt="[%(asctime)s] %(levelname)-8s %(message)s",
    datefmt="%m/%d/%y %H:%M:%S",
))
_access_log.addHandler(_access_handler)
_access_log.setLevel(logging.INFO)
_access_log.propagate = False


class AccessLogMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers    = dict(scope.get("headers", []))
        session_id = headers.get(b"mcp-session-id", b"").decode()
        client_ip  = (scope.get("client") or ("",))[0]
        method     = scope.get("method", "")
        path       = scope.get("path", "")
        status     = 0

        async def capture_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        await self.app(scope, receive, capture_send)

        user = _session_user_ids.get(session_id)
        if not user:
            token = _session_tokens.get(session_id, "")
            user  = next((uid for uid, t in _persisted_sessions.items() if t == token), "-") if token else "-"

        _access_log.info("%s | %s | %s %s | %s", client_ip, user, method, path, status)

# Register all tools by importing their modules (side-effect: @mcp.tool() decorators run)
import tools.account       # noqa: F401
import tools.market        # noqa: F401
import tools.fundamentals  # noqa: F401
import tools.analysis      # noqa: F401
import tools.regulatory    # noqa: F401
import tools.mutual_funds  # noqa: F401
import tools.reference     # noqa: F401


_FAVICON = Path(__file__).parent / "favicon.png"  # ships next to server.py (also in the Docker image)


@mcp.custom_route("/favicon.ico", methods=["GET"])
@mcp.custom_route("/favicon.png", methods=["GET"])
async def favicon(_: Request) -> FileResponse:
    return FileResponse(_FAVICON, media_type="image/png")


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@mcp.custom_route("/callback", methods=["GET"])
async def oauth_callback(request: Request) -> HTMLResponse:
    """OAuth redirect URI handler — receives the code from Twelve Data after user authorizes."""
    code  = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    # OAuth Authorization Server flow: TD redirected here for a connector login.
    # Distinguished from the legacy oauth_login tool flow by the state owning an
    # AS authorize request. Complete the exchange and bounce back to the client.
    if _oauth_provider is not None and state and _oauth_storage.is_authreq(state):
        if error or not code:
            return callback_page(
                "Authorization failed",
                f'<p class="subtitle">{error or "missing code"}</p>',
                kind="error",
                status=400,
            )
        try:
            redirect_url = await _oauth_provider.complete_td_login(state, code)
            return RedirectResponse(redirect_url, status_code=302)
        except Exception as exc:
            return callback_page(
                "Authorization failed",
                f'<p class="subtitle">{exc}</p>',
                kind="error",
                status=400,
            )

    if error or not code:
        _oauth_pending.pop(state, None)
        msg = error or "missing code"
        return callback_page(
            "Authorization failed",
            f'<p class="subtitle">{msg}</p>',
            kind="error",
            status=400,
        )

    pending = _oauth_pending.pop(state, None)
    if pending is None:
        return callback_page(
            "Link expired",
            '<p class="subtitle">This authorization link has already been used or expired.<br>Please call <code>oauth_login</code> again.</p>',
            kind="error",
            status=400,
        )

    auth       = pending["auth"]
    session_id = pending.get("session_id", "")

    try:
        data      = await auth._exchange(code)
        api_token = data.get("api_token", "")
        _persist_user_token(api_token, data.get("_profile_response", {}), session_id)
        suffix = f"…{api_token[-6:]}" if api_token else "not found"
        return callback_page(
            "Authorization successful",
            f'<p class="subtitle">Your API token has been saved and is ready to use.</p>'
            f'<div class="token">'
            f'<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
            f' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
            f'<rect x="3" y="11" width="18" height="11" rx="2"/>'
            f'<path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>'
            f'API token {suffix}</div>',
        )
    except Exception as exc:
        return callback_page(
            "Token exchange failed",
            f'<p class="subtitle">{exc}</p>',
            kind="error",
            status=500,
        )


def main():
    logging.getLogger("httpx").setLevel(logging.WARNING)

    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport in ("streamable-http", "sse"):
        import asyncio
        import uvicorn

        app_fn = mcp.streamable_http_app if transport == "streamable-http" else mcp.sse_app

        async def serve():
            cfg = uvicorn.Config(
                AccessLogMiddleware(app_fn()),
                host=os.environ.get("MCP_HOST", "0.0.0.0"),
                port=8000,
                access_log=False,
                log_config={
                    "version": 1,
                    "disable_existing_loggers": False,
                    "formatters": {
                        "default": {
                            "()": "uvicorn.logging.DefaultFormatter",
                            "fmt": "[%(asctime)s] %(levelprefix)s %(message)s",
                            "datefmt": "%m/%d/%y %H:%M:%S",
                            "use_colors": None,
                        },
                    },
                    "handlers": {
                        "default": {
                            "formatter": "default",
                            "class": "logging.StreamHandler",
                            "stream": "ext://sys.stderr",
                        },
                    },
                    "loggers": {
                        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
                        "uvicorn.error": {"level": "INFO"},
                    },
                },
            )
            await uvicorn.Server(cfg).serve()

        asyncio.run(serve())
    else:
        mcp.run(transport=transport)


if __name__ == "__main__":
    main()
