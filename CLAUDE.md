# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is MCP server for local usage and for public usage for thousands users. 
This MCP server provide access to Twelve Data API. For access we have to use personal
user's apikeys. We can not write Twelve Data apikey to .env file because users 
buy their keys. This MCP server is for usage from Claude Desktop, Chatgpt, 
and other systems. Therefore this MCP server must support all needed authorization interfaces for different systems.

## Commands

```bash
make install                                    # create .venv (Python 3.10+) and install deps
make run                                        # stdio transport — used by Claude Desktop
make run-http                                   # streamable-http on :8000/mcp — used with ngrok
make run-sse                                    # SSE on :8000/sse (legacy)
make inspect                                    # MCP Inspector UI at http://localhost:5173 (requires Node)
make check                                      # syntax-check all .py files
make configure CLIENT_ID=x CLIENT_SECRET=y     # write .env from template
make python-install                             # brew install python@3.12 if needed
```

## Architecture

Three files; no framework beyond FastMCP:

**`auth.py`** — OAuth 2.0 (Laravel Passport) + token persistence  
- `load_dotenv` runs at **import time** from `Path(__file__).parent / ".env"` so env vars are available before any method is called  
- `load_config()` merges `~/.twelvedata_mcp/config.json` (personal) with env vars (env wins)  
- `TwelveDataAuth` stores tokens at `~/.twelvedata_mcp/tokens.json`  
- After OAuth exchange, calls `GET https://twelvedata.com/api/v1/user/user` (Bearer token) and extracts `data.api_token` — this is the actual API key used for all data requests  
- Two login paths: `login()` spins up a standalone `HTTPServer` on port 8765 (stdio/Claude Desktop), `login_via_queue()` awaits an `asyncio.Queue` fed by the `/callback` route (HTTP transport)

**`client.py`** — thin `httpx` wrapper  
- `_headers()` priority: `api_token` from stored profile → re-fetch via Bearer if missing → `TWELVE_DATA_API_KEY` env var  
- All API calls go to `https://api.twelvedata.com/{endpoint}` with `Authorization: apikey {token}`  
- OAuth Bearer tokens are **never** sent to `api.twelvedata.com` — only used to fetch the user profile

**`server.py`** — FastMCP server with 20 tools  
- `_get_shared_auth()` is a lazy singleton (reads config once); `_get_client(token)` is per-request — creates a fresh `TwelveDataClient` each call, passing a per-request token from the MCP `Authorization` header if present (multi-user HTTP deployments)  
- `oauth_login` auto-detects transport: reads `x-forwarded-host` / `host` from the request context to build the redirect URI dynamically — no `MCP_DATA_TWELVE_DATA_REDIRECT_URI` env var needed when running behind ngrok  
- `/callback` is a custom Starlette route on the same server; it puts `{code, state}` into `_oauth_queue` (capacity 1, drains stale entries before each login)  
- `get_technical_indicator` dispatches to 60+ endpoints by lowercasing the `indicator` param; `get_correlation` wraps `/correl` directly  
- `auth_status` tool shows full diagnostic state including detected host and redirect URI (plus the active session-store backend) — use it first when debugging auth issues

**`store.py`** — durable session / user / payment store (Redis, with file fallback)
- Source of truth is Redis (`REDIS_URL`); degrades to `~/.twelvedata_mcp/sessions.json` + in-memory when Redis is down — stdio/local works with no Redis running
- Keyed by **user identity**, not the volatile `Mcp-Session-Id`: `td:user:<uid>:api_token` / `:profile` / `:meta` (a `td:users` set), plus `td:session:<sid>` → `{user_id, api_token}` (optional `MCP_SESSION_TTL`)
- `store.warm()` runs at startup in `state.py` to repopulate the in-memory caches (`_session_tokens`, `_session_user_ids`, `_persisted_sessions`) — this is what makes a server restart seamless
- The MCP transport `Mcp-Session-Id` lives only in the SDK's in-memory `StreamableHTTPSessionManager` and **cannot** be serialised; on restart the client re-initialises with a new id. Continuity comes from keying durable state to the user. Payments/subscriptions belong in per-user meta (`store.set_user_field` / `get_user_field` / `get_user_meta`)
- Request-path reads stay in-memory; Redis is touched only on login, on session cache-miss, and at startup — so sync `redis` calls never block the data hot path

**`oauth/` package** — the server's own OAuth 2.1 Authorization Server (for remote multi-user clients: ChatGPT, Claude connectors, Cursor…)
- Enabled only when `MCP_DATA_PUBLIC_URL` is set (stdio / local Claude Desktop stays OAuth-off and uses the `oauth_login` tool). Requires Redis.
- The MCP server is its own AS and **delegates the actual login to Twelve Data's OAuth** (the upstream IdP) — because TD's Passport has no RFC 8414 metadata and no Dynamic Client Registration, clients can't talk to it directly.
- FastMCP auto-mounts `/authorize`, `/token`, `/register` (DCR) and discovery metadata once given `auth_server_provider` + `AuthSettings` (built in `state.py` via `oauth.build_auth()`). Unauthenticated `/mcp` → `401` + `WWW-Authenticate` advertising `/.well-known/oauth-protected-resource/mcp`.
- `oauth/provider.py` `TwelveDataASProvider`: `authorize()` stores a pending request and redirects the browser to TD; the shared `/callback` route in `server.py` (dispatched by `state` via `storage.is_authreq`) finishes the TD exchange, persists `user_id→td_apikey` (via `store.save_user_from_profile`), mints **our** auth code, and bounces the browser back to the client. SDK does PKCE verification and redirect_uri validation.
- The upstream redirect URI reuses the existing `/callback` (`oauth/config.py` `TD_CALLBACK_PATH`), so **no new redirect URI needs registering** on the Twelve Data OAuth app — `<MCP_DATA_PUBLIC_URL>/callback` must just be among its allowed URIs (Passport returns `invalid_client` if not). The legacy `oauth_login`/`oauth_configure` tools are not registered while the AS is enabled (they're auth-gated and irrelevant).
- Tokens carry the `user_id` (`oauth/models.py` subclasses), so `resolve_apikey()` reads the validated access token from the request, takes `user_id`, and looks up the api_token in the store. This is checked **first** in `_token_from_ctx`. Identity lives in the Bearer on every request — immune to `Mcp-Session-Id` churn and restarts.
- Redis (under `td:oauth:*`): registered client apps, pending authorize requests, auth codes, access/refresh tokens (TTL'd). Separate from the `td:user:*`/`td:session:*` data in `store.py`, same connection.

## Credential priority (highest → lowest)

1. Env vars already in the process (Docker, systemd, Claude Desktop `env` block)  
2. `.env` in project root (loaded at import time)  
3. `~/.twelvedata_mcp/config.json` (written by `oauth_configure` tool or `make configure`)

## Claude Desktop config

```json
{
  "mcpServers": {
    "twelvedata": {
      "command": "/path/to/twelve-data-mcp/.venv/bin/python",
      "args": ["/path/to/twelve-data-mcp/server.py"]
    }
  }
}
```

Use the venv Python (not system `python3`) — system Python on macOS is 3.9, `mcp` requires 3.10+. After changing config, restart Claude Desktop (the server process is spawned once at startup).

## First-time OAuth setup

```
1. Register an OAuth app on Twelve Data with redirect URI:
   - Local:  http://localhost:8765/callback
   - ngrok:  https://<your-domain>/callback  (auto-detected from request headers)

2. make configure CLIENT_ID=xxx CLIENT_SECRET=yyy

3. In Claude: call oauth_login
   → browser opens → user authorizes → api_token saved to tokens.json
```
