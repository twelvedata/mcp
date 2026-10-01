# Working in this repository

Guidance for coding agents. `CLAUDE.md` points here, so whichever name an agent looks for, it
finds the same file.

This is the Twelve Data MCP server as a **single-tenant local server**: one operator, one
Twelve Data account, on their own machine. See `README.md` for running it.

## Commands

```bash
make install          # create .venv (Python 3.10+) and install pinned deps
make run              # streamable-http on :8000/mcp
make run-stdio        # stdio transport — used by Claude Desktop and Claude Code
make run-sse          # SSE on :8000/sse (legacy)
make inspect          # MCP Inspector UI at http://localhost:5173 (requires Node)
make configure CLIENT_ID=x CLIENT_SECRET=y   # write .env from .env.example (overwrites it)
make check            # syntax-check every .py file under src/
make help             # every target
```

`make check` is a syntax check only. There is no `make test`: the test suite is not published.

## Modules

- `src/server.py` — entry point: the ASGI app, `/callback`, `/health`, transport selection.
- `src/state.py` — the FastMCP instance, `td_tool`, credential resolution (`_token_from_ctx`).
- `src/auth.py` — the local OAuth login against Twelve Data's Passport; loads `.env` at import.
- `src/client.py` — the `httpx` wrapper every tool call goes through; sends an api_token as
  `Authorization: apikey`.
- `src/store.py` — the account→api_token map, in `~/.twelvedata_mcp/sessions.json`.
- `src/tools/` — the tools, one module per area. `oauth_login`, `oauth_configure` and
  `auth_status` live in `tools/account.py`.
- `src/views.py` — the HTML of the callback page. Escape anything untrusted before passing it.

## Where a tool call's credential comes from

In order, first that answers (`src/state.py`, `_token_from_ctx`):

1. a raw `Authorization: Bearer <key>` on the request, taken as an api_token;
2. the single stored account, if exactly one has logged in through `oauth_login`;
3. `TWELVE_DATA_API_KEY` from the environment or `.env`.

## Hosted mode is not in this copy

The branches on `LOCAL_MODE` and `src/exchange.py` belong to the multi-user deployment Twelve
Data runs. They are present but inactive here. `src/verifier.py` is absent on purpose: with
`MCP_DATA_PUBLIC_URL` set the server refuses to start. Do not try to make hosted mode work.

## Security

`make run` and Docker serve `/mcp` with no authentication, on `0.0.0.0` by default, and every
call is served under the operator's credential. Anyone who reaches the port can call
`auth_status` and `oauth_configure` — including a web page the operator opens, through DNS
rebinding, because the default bind checks neither Host nor Origin. `MCP_HOST=127.0.0.1 make
run` keeps it local and turns on the SDK's Host and Origin check; ngrok then works only with
`--host-header=rewrite`.
