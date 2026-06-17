<!-- robots: noindex, nofollow -->
<meta name="robots" content="noindex, nofollow">

# Twelve Data MCP Server — Self-Hosting & Partner Guide

> **Internal / partners only.** This page is intentionally **not linked** from the
> public README so it stays out of search results. Regular users never need it —
> they use our cloud server or run locally with an API key (see the README).
>
> This guide covers running your own public instance and wiring up a dedicated
> OAuth login. That requires Twelve Data OAuth client credentials, which we issue
> **manually, per partner** — they are not self-service.

## OAuth credentials (`CLIENT_ID` / `CLIENT_SECRET`)

A partner deployment that offers OAuth login needs an **OAuth application**
registered on Twelve Data. It yields a `Client ID` and
`Client Secret` that identify *the app*, not an individual user. When a user logs
in through OAuth, the server fetches that user's personal `api_token` and uses it
for all data requests — the OAuth credentials only drive the login flow.

These credentials belong to the operator, **not** to end users: a user cannot and
should not register their own app. For each partner we register a separate OAuth
client by hand and share its `CLIENT_ID` / `CLIENT_SECRET`. The redirect URI on
that app must include `<your-public-url>/callback`.

> If you only want a single-tenant deployment with a static key, skip OAuth
> entirely and set `TWELVE_DATA_API_KEY` in `.env` — no `CLIENT_ID`/`CLIENT_SECRET`
> needed.

## Requirements

- Python 3.10+ (3.12 recommended) — macOS: `brew install python@3.12` (`make python-install`)
- Redis — required for any public multi-user deployment (stores OAuth clients, codes, tokens, sessions)
- Node.js — only for the interactive inspector (`make node-install`)

## Setup

**1. Install**

```bash
make install
```

**2. Configure OAuth credentials**

```bash
make configure CLIENT_ID=your_client_id CLIENT_SECRET=your_client_secret
```

This creates `.env` from `.env.example`. Edit it to fill in the rest (see below).

**3. Run**

```bash
make run           # Streamable HTTP transport → http://localhost:8000/mcp
make run-stdio     # stdio transport (only for a local Claude Desktop smoke test)
make run-sse       # SSE transport → http://localhost:8000/sse (legacy)
```

## Public multi-user deployment (ChatGPT / Claude connectors)

This is the mode that powers the hosted cloud server. Set the externally reachable
base URL — this turns the server into its **own OAuth Authorization Server** (with
Dynamic Client Registration + discovery metadata), so connectors can log in over
standard OAuth and identity rides in a Bearer token on every request (survives
restarts and per-call session churn).

In `.env`:

```bash
MCP_DATA_PUBLIC_URL=https://mcp.twelvedata.com   # externally reachable base URL
REDIS_URL=redis://localhost:6379                 # required when PUBLIC_URL is set
# MCP_OAUTH_ACCESS_TTL=3600                       # optional token lifetimes
# MCP_OAUTH_REFRESH_TTL=2592000
```

The upstream login reuses the existing `/callback` redirect URI, so **no extra
redirect URI** needs registering on the Twelve Data OAuth app — just ensure
`<MCP_DATA_PUBLIC_URL>/callback` is among its allowed URIs.

## Quick remote test via ngrok

```bash
make run
ngrok http 8000
```

Point the client to `https://<your-ngrok-domain>/mcp`. The OAuth redirect URI is
detected automatically from request headers — no extra config. Register
`https://<your-ngrok-domain>/callback` as a redirect URI on the Twelve Data OAuth app.

## Local Claude Desktop test (stdio)

For a quick local check without a public URL, point Claude Desktop straight at the
server. Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "twelvedata": {
      "command": "/path/to/twelve-data-mcp/.venv/bin/python",
      "args": ["/path/to/twelve-data-mcp/src/server.py"]
    }
  }
}
```

Use the `.venv/bin/python` path, not the system Python (macOS ships 3.9; this needs
3.10+). Without `MCP_DATA_PUBLIC_URL`, login uses the `oauth_login` tool (browser
opens, `api_token` saved to `~/.twelvedata_mcp/tokens.json`), or set
`TWELVE_DATA_API_KEY` in `.env` to skip OAuth. Restart Claude Desktop after editing.

## Other commands

```bash
make inspect       # MCP Inspector UI at http://localhost:5173
make check         # syntax-check all Python files
make clean         # remove .venv
```

## Debugging auth

Call `auth_status` from the client — it reports configured credentials, stored
tokens, detected host, the redirect URI that will be used for OAuth, and the active
session-store backend. Check it first when login misbehaves.
