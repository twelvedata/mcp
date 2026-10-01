"""
Twelve Data MCP Server

Environment variables:
  TWELVE_DATA_API_KEY                – API key (local/stdio only)
  MCP_DATA_TWELVE_DATA_CLIENT_ID     – upstream Passport OAuth client ID (local login)
  MCP_DATA_TWELVE_DATA_CLIENT_SECRET – upstream Passport OAuth client secret (local login)
  MCP_DATA_OPENAI_APPS_CHALLENGE     – OpenAI domain verification token (hosted only)
  MCP_DATA_PUBLIC_URL                – set by the hosted deployment; local runs leave it unset

Claude Desktop config (~/Library/Application Support/Claude/claude_desktop_config.json):
{
  "mcpServers": {
    "twelvedata": {
      "command": "/path/to/mcp/.venv/bin/python",
      "args": ["/path/to/mcp/src/server.py"]
    }
  }
}
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import mcp.types as types
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, FileResponse, PlainTextResponse, Response

from failures import AuthorizationFailure, ToolFailure
from scopes import scope_of, check as check_scope
from views import callback_page
from state import (
    mcp, exchanger, request_user, user_from_scope,
    _oauth_pending, _persist_user_token, _token_verifier,
    _session_user_ids, _session_tokens, _persisted_sessions,
)
from oauth.config import (
    AUTH_ISSUER_URL, LOCAL_MODE, SCOPE, as_metadata_url, authorize_url, register_url, resource_url,
    revocation_url, token_endpoint,
)

# Register all tools by importing their modules (side-effect: decorators run)
import tools.account
import tools.market
import tools.fundamentals
import tools.analysis
import tools.regulatory
import tools.mutual_funds
import tools.reference  # noqa: F401 — every `import tools.*` binds one name, `tools`, and ruff counts only its last binding

# Idle MCP sessions are the dominant source of unbounded memory growth on the
# public deployment. In stateful streamable-http mode the SDK keeps every
# session alive in StreamableHTTPSessionManager._server_instances — a transport,
# a running anyio task with its ServerSession, and the per-request memory object
# streams — until the client sends `DELETE /mcp`. Real clients (ChatGPT, Claude,
# Cursor) almost never do; they just drop the connection and re-initialise with
# a fresh session id, so every reconnect strands another live session for the
# lifetime of the process. FastMCP does not surface the SDK's idle reaper, so
# arm it directly on the manager. 0 disables (back to the old, leaking default).
_SESSION_IDLE_TIMEOUT = float(os.environ.get("MCP_SESSION_IDLE_TIMEOUT", "1800") or "0")

_access_log = logging.getLogger("access")
_access_handler = logging.StreamHandler()
_access_handler.setFormatter(logging.Formatter(
    fmt="[%(asctime)s] %(levelname)-8s %(message)s",
    datefmt="%m/%d/%y %H:%M:%S",
))
_access_log.addHandler(_access_handler)
_access_log.setLevel(logging.INFO)
_access_log.propagate = False

# One record, one line. FastMCP puts rich's RichHandler on the root logger whenever rich is
# importable, which through typer it always is: without a terminal it wraps at 80 columns, so a
# log driver shipping each line as a message splits one event across several, and rendering
# each record as a table was a sixth of what a flood of forged tokens costs the event loop.
def _one_line_per_record(root: logging.Logger) -> None:
    for handler in [h for h in root.handlers if type(h).__module__.startswith("rich.")]:
        root.removeHandler(handler)
        plain = logging.StreamHandler()
        plain.setFormatter(logging.Formatter(
            fmt="[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
            datefmt="%m/%d/%y %H:%M:%S",
        ))
        root.addHandler(plain)


_one_line_per_record(logging.getLogger())

# The SDK writes an INFO line per JSON-RPC request and three per session; the access log
# carries the request's method and tool itself, and a WARNING from these still gets through.
_SDK_CHATTY_LOGGERS = ("mcp.server.lowlevel.server", "mcp.server.streamable_http_manager", "mcp.server.streamable_http")
for _name in _SDK_CHATTY_LOGGERS:
    logging.getLogger(_name).setLevel(logging.WARNING)

# Only a body this size is parsed for its method; larger ones are logged without it.
_RPC_BODY_MAX = 64 * 1024
# What a logged method or tool name may contain: both come from the caller, and a newline or a
# ` | ` in one would forge a line or a column.
_RPC_NAME = re.compile(r"[A-Za-z0-9_./-]{1,64}")


def _quiet(path: str, status: int, sent_credential: bool) -> bool:
    """Requests whose line says nothing a reader acts on.

    Polled documents and the probe on success; a 404, which only a path nothing serves gets;
    and a 401 to a request that carried no credential at all, which is the first step of
    every client's discovery rather than a refusal.
    """
    if status == 404:
        return True
    if status == 401 and not sent_credential:
        return True
    return status < 400 and (path.startswith("/.well-known/") or path in ("/health", "/favicon.ico", "/favicon.png"))


def _rpc_of(body: bytes) -> str:
    """The JSON-RPC method, and the tool for a call — never its arguments."""
    try:
        message = json.loads(body)
    except ValueError:
        return ""
    if not isinstance(message, dict):
        return ""
    method = message.get("method")
    if not isinstance(method, str) or not _RPC_NAME.fullmatch(method):
        return ""
    params = message.get("params")
    tool = params.get("name") if method == "tools/call" and isinstance(params, dict) else None
    if tool is None:
        return f"rpc={method}"
    return f"rpc={method} tool={tool if isinstance(tool, str) and _RPC_NAME.fullmatch(tool) else '?'}"


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
        # Read before the app runs: the verification layer strips the header on the way in.
        sent_credential = b"authorization" in headers
        body = bytearray()
        body_whole = method == "POST"

        async def capture_receive():
            nonlocal body_whole
            message = await receive()
            if body_whole and message["type"] == "http.request":
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > _RPC_BODY_MAX:
                    body_whole = False
                    body.clear()
                else:
                    body.extend(chunk)
            return message

        async def capture_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        await self.app(scope, receive if method != "POST" else capture_receive, capture_send)

        if _quiet(path, status, sent_credential):
            return

        # The verified subject, read off the scope the authentication middleware wrote it
        # on — not get_access_token(), whose contextvar is reset in a `finally` before this
        # line runs, and which therefore logs a dash with nothing saying why.
        user = ""
        principal = user_from_scope(scope)
        if principal is not None:
            user = principal.access_token.subject or ""
        # Hosted: an unverified request is logged as nobody, whatever session id it carries.
        if not user and LOCAL_MODE:
            user = _session_user_ids.get(session_id, "")
            if not user:
                token = _session_tokens.get(session_id, "")
                user  = next((uid for uid, t in _persisted_sessions.items() if t == token), "") if token else ""
        user = user or "-"

        rpc = _rpc_of(bytes(body)) if body_whole and body else ""
        if rpc:
            _access_log.info("%s | %s | %s %s | %s | %s", client_ip, user, method, path, status, rpc)
        else:
            _access_log.info("%s | %s | %s %s | %s", client_ip, user, method, path, status)

class ByteExactIssuerMiddleware:
    """Spells the Authorization Server in the protected-resource document the way it spells
    itself.

    pydantic's AnyHttpUrl appends a trailing slash to an authority-only URL, so the SDK
    serializes `https://auth.example.com/` into `authorization_servers` while `iss` on every
    token — and the `issuer` field of the document a client fetches next — carries none.
    RFC 8414 §3.3 has a conformant client compare those two and refuse on a mismatch, with
    nothing anywhere reporting it. Only that one value is rewritten; the document stays the
    SDK's.
    """

    def __init__(self, app, path: str):
        self.app = app
        self.path = path

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != self.path:
            await self.app(scope, receive, send)
            return

        start_message = None
        body = b""

        async def capture_send(message):
            nonlocal start_message, body
            if message["type"] == "http.response.start":
                start_message = message
            elif message["type"] == "http.response.body":
                body += message.get("body", b"")
                if not message.get("more_body"):
                    await self._send_respelled(send, start_message, body)
            else:
                await send(message)

        await self.app(scope, receive, capture_send)

    async def _send_respelled(self, send, start_message, body):
        if start_message is None:  # pragma: no cover - malformed upstream response
            await send({"type": "http.response.body", "body": body})
            return

        rewritten = False
        if start_message["status"] == 200 and body:
            try:
                document = json.loads(body)
                document["authorization_servers"] = [AUTH_ISSUER_URL]
                body = json.dumps(document).encode()
                rewritten = True
            except ValueError:  # pragma: no cover - not JSON, leave it alone
                pass

        if rewritten:
            headers = [
                (name, value)
                for name, value in (start_message.get("headers") or [])
                if name.lower() != b"content-length"
            ]
            headers.append((b"content-length", str(len(body)).encode()))
            start_message = {**start_message, "headers": headers}

        await send(start_message)
        await send({"type": "http.response.body", "body": body})


_FAVICON = Path(__file__).parent / "favicon.png"  # ships next to server.py (also in the Docker image)

# OpenAI domain verification token, from the deployment's environment.
_OPENAI_APPS_CHALLENGE = os.environ.get("MCP_DATA_OPENAI_APPS_CHALLENGE", "")


# ── the tool-descriptor and tool-result escape hatches ────────────────────────
#
# FastMCP builds each descriptor from a fixed argument list and converts whatever a tool
# body returned, so neither a top-level descriptor field nor a `_meta` on a result can come
# from a tool. Both are reachable one level up: the low-level handler's first branch on a
# result is "already a CallToolResult? return it untouched". So these two wrap FastMCP's own
# handlers rather than replacing them — reading them as a reimplementation buys a second
# copy of the SDK's input, output-schema and content-normalisation behaviour, which stops
# matching at the next pin bump.

def _security_schemes(scope: str) -> list[dict]:
    """What a client needs to call this tool, on the descriptor itself.

    ChatGPT's in-conversation linking path reads it here; the same requirement reaches an
    install-time flow through the protected-resource document instead.
    """
    return [{"type": "oauth2", "scopes": [scope]}]


def _challenge(error: str = "insufficient_scope") -> str:
    if not resource_url().startswith("http"):
        return f'Bearer error="{error}", scope="{SCOPE}"'
    metadata_url = _resource_metadata_url()
    return f'Bearer error="{error}", scope="{SCOPE}", resource_metadata="{metadata_url}"'


def _resource_metadata_url() -> str:
    from mcp.server.auth.routes import build_resource_metadata_url

    return str(build_resource_metadata_url(AnyHttpUrl(resource_url())))


@mcp._mcp_server.list_tools()
async def list_tools() -> list[types.Tool]:
    tools = await mcp.list_tools()
    for tool in tools:
        declared = (tool.meta or {}).get("twelvedata/scope")
        if isinstance(declared, str) and declared:
            tool.securitySchemes = _security_schemes(declared)
    return tools


@mcp._mcp_server.call_tool(validate_input=False)
async def call_tool(name: str, arguments: dict):
    try:
        _refuse_uncovered_tool(name)
        return await mcp.call_tool(name, arguments)
    except Exception as exc:
        failure = _our_failure(exc)
        if failure is None:
            raise
        meta = {"mcp/www_authenticate": failure.challenge or _challenge(failure.error)} if isinstance(
            failure, AuthorizationFailure
        ) else None
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=str(failure))],
            isError=True,
            _meta=meta,
        )


def _refuse_uncovered_tool(name: str) -> None:
    """Refuse a call whose token does not carry the tool's scope.

    While the catalogue holds one entry the endpoint has already refused every token this
    would, so nothing here fires in production — which is why the table is what a test
    reaches, not the wire.
    """
    if _token_verifier is None:  # verification off: no token, and so no granted scopes
        return
    tool = mcp._tool_manager.get_tool(name)
    required = scope_of(tool) if tool is not None else None
    if required is None:
        return
    principal = request_user(mcp.get_context())
    check_scope(name, required, principal.scopes if principal is not None else [])


def _our_failure(exc: BaseException):
    """Our own failure anywhere in the chain.

    The SDK wraps whatever a tool body raised in a ToolError, so the type is only reachable
    through __cause__.
    """
    seen: BaseException | None = exc
    while seen is not None:
        if isinstance(seen, ToolFailure):
            return seen
        seen = seen.__cause__
    return None


@mcp.custom_route("/favicon.ico", methods=["GET"])
@mcp.custom_route("/favicon.png", methods=["GET"])
async def favicon(_: Request) -> FileResponse:
    return FileResponse(_FAVICON, media_type="image/png")


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    """That the process serves, and nothing about what it depends on.

    Liveness only: a supervisor that restarts the process when it exits is all this needs,
    and nothing waits on this process being ready. The signal for the Authorization Server
    being out of reach is the exchange's own `exchange failed` log event.
    """
    return JSONResponse({"status": "ok"})


def _hosted_only_route(path: str, methods: list[str]):
    """Serve a route only on a hosted deployment.

    These answer for the hosted Authorization Server and the apps registered against it; on a
    local run their targets are empty and each would redirect to itself. Gated on the local
    signal, as `_local_only_tool` is, and never on whether verification is on.
    """
    if LOCAL_MODE:
        return lambda fn: fn
    return mcp.custom_route(path, methods=methods)


@_hosted_only_route("/.well-known/openai-apps-challenge", methods=["GET"])
async def openai_apps_challenge(_: Request) -> PlainTextResponse:
    if not _OPENAI_APPS_CHALLENGE:
        return PlainTextResponse("Not Found", status_code=404)
    return PlainTextResponse(_OPENAI_APPS_CHALLENGE)


# ── the retired Authorization Server paths ────────────────────────────────────
#
# Unopposed in Resource-Server mode: the SDK mounts its own /register and metadata routes
# only when it is given an authorization server provider.

_RETIRED_BODY = (
    "This host no longer issues tokens; {target} does.\n\n"
    "Following this redirect returns that server's own metadata, whose `issuer` names it "
    "and not this host — RFC 8414 requires the two to match, so a conformant client will "
    "refuse it. Ask {target} directly instead. This redirect is a signpost for a reader of "
    "our documentation, not a compatibility shim for a client.\n"
)


def _retired(target: str, status: int) -> Response:
    # no-store, and not a short max-age: both codes are heuristically cacheable, and the
    # retirement is meant to stay reversible for everyone at once rather than for whoever
    # has not fetched it yet.
    return Response(
        content=_RETIRED_BODY.format(target=target),
        status_code=status,
        media_type="text/plain",
        headers={"Location": target, "Cache-Control": "no-store"},
    )


@_hosted_only_route("/.well-known/oauth-authorization-server", methods=["GET"])
async def retired_metadata(_: Request) -> Response:
    return _retired(as_metadata_url(), 301)


@_hosted_only_route("/register", methods=["POST"])
async def retired_registration(_: Request) -> Response:
    # 308 and not 301: a user agent may turn a redirected POST into a GET, and 308 is the
    # code that forbids it.
    return _retired(register_url(), 308)


# ── the legacy Authorization Server's flow endpoints, forwarded ───────────────
#
# Unlike the two above, these ARE a compatibility shim. A client registered against the
# legacy server keeps its endpoints pinned in its own configuration — an app published
# against it does — and without these it meets a 404 on every authorization and every refresh.
# Temporary: remove once no such client is left.

def _forwarded(target: str, status: int) -> Response:
    return Response(status_code=status, headers={"Location": target, "Cache-Control": "no-store"})


@_hosted_only_route("/authorize", methods=["GET"])
async def forwarded_authorize(request: Request) -> Response:
    # The query goes through byte for byte: PKCE, state and redirect_uri are all in it.
    query = request.url.query
    return _forwarded(f"{authorize_url()}?{query}" if query else authorize_url(), 302)


@_hosted_only_route("/token", methods=["POST"])
async def forwarded_token(_: Request) -> Response:
    return _forwarded(token_endpoint(), 308)


@_hosted_only_route("/revoke", methods=["POST"])
async def forwarded_revocation(_: Request) -> Response:
    return _forwarded(revocation_url(), 308)


@mcp.custom_route("/callback", methods=["GET"])
async def oauth_callback(request: Request) -> HTMLResponse:
    """Upstream redirect URI for the local oauth_login flow."""
    code  = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    if error or not code:
        _oauth_pending.pop(state, None)
        msg = error or "missing code"
        return callback_page(
            "Authorization failed",
            f'<p class="subtitle">{html.escape(msg)}</p>',
            kind="error",
            status=400,
        )

    pending = _oauth_pending.pop(state, None)
    if pending is None:
        # On a hosted deployment nothing sends a browser here any more, and the tool this
        # page used to name answers "already authenticated" there — so it says what such a
        # reader can actually do instead.
        retry = (
            'Please call <code>oauth_login</code> again.'
            if LOCAL_MODE else
            'This server no longer signs users in. Reconnect the Twelve Data integration in your client.'
        )
        return callback_page(
            "Link expired",
            f'<p class="subtitle">This authorization link has already been used or expired.<br>{retry}</p>',
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
    except Exception as exc:  # noqa: BLE001 — the browser is owed a page, never a bare 500
        return callback_page(
            "Token exchange failed",
            f'<p class="subtitle">{html.escape(str(exc))}</p>',
            kind="error",
            status=500,
        )


def build_app():
    """The ASGI application, with the long-lived object bound to its lifespan.

    A connection pool created at import leaks one per reload, and the test harness reloads.
    The exchanger's is started and stopped here, composed with the lifespan FastMCP already
    installs for the session manager rather than replacing it.
    """
    app = mcp.streamable_http_app()

    if _SESSION_IDLE_TIMEOUT > 0:
        # Set after streamable_http_app(), which is what creates the session manager.
        sm = mcp._session_manager
        if sm is not None and not sm.stateless:
            sm.session_idle_timeout = _SESSION_IDLE_TIMEOUT
            logging.getLogger("mcp").info("session idle timeout: %.0fs", _SESSION_IDLE_TIMEOUT)

    inner = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(scoped_app):
        if _token_verifier is not None:
            await exchanger.start()
        try:
            async with inner(scoped_app):
                yield
        finally:
            if _token_verifier is not None:
                await exchanger.close()

    app.router.lifespan_context = lifespan
    # Under the condition the verifier exists and never unconditionally: local HTTP mode also
    # serves /mcp with a Bearer — a laptop's api_token — and the layer would send it to an
    # exchanger with no client and answer 503.
    if _token_verifier is not None:
        from verifier import VerdictLayer

        app = VerdictLayer(app, _token_verifier, mcp.settings.streamable_http_path)
        app = ByteExactIssuerMiddleware(app, urlparse(_resource_metadata_url()).path)
    return AccessLogMiddleware(app)


def main():
    logging.getLogger("httpx").setLevel(logging.WARNING)

    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport in ("streamable-http", "sse"):
        import asyncio
        import uvicorn

        app = build_app() if transport == "streamable-http" else AccessLogMiddleware(mcp.sse_app())

        async def serve():
            cfg = uvicorn.Config(
                app,
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
