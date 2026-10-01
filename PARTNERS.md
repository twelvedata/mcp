<!-- robots: noindex, nofollow -->
<meta name="robots" content="noindex, nofollow">

# Twelve Data MCP Server — Self-Hosting & Partner Guide

> **Internal / partners only.** This page is intentionally **not linked** from the
> public README so it stays out of search results. Regular users never need it —
> they use our cloud server or run locally with an API key (see the README).

## What this distribution is

This repository is the Twelve Data MCP server as a **self-hosted, single-tenant**
service: one operator, one Twelve Data account, on your own machine or your own host.
It exposes the same tools the cloud server does, plus `oauth_configure`, which is
registered only where there is one operator to configure.

**The multi-user server at `https://mcp.twelvedata.com/mcp` is run by Twelve Data and is not
part of this distribution.** That deployment verifies OAuth tokens issued by Twelve Data's
Authorization Server. Do not drop the `/mcp` path: the host root answers 404.
The published distribution does not carry the verifier: with
`MCP_DATA_PUBLIC_URL` set it refuses to start and says so. If you want your
users signing in with their own Twelve Data accounts, point them at the cloud server; if
you need something else, talk to us before building it.

## Two ways to authenticate

**A static API key** is the simpler one and covers most self-hosting: the server presents
your key on every request, and there is no login step. Get the key at
[twelvedata.com](https://twelvedata.com) → dashboard → **API Keys**.

**An OAuth login** lets the operator sign in through a browser instead of pasting a key —
the server then fetches that account's API key and stores it. It needs an **OAuth
application** registered on Twelve Data, which yields a `Client ID` and a `Client Secret`
identifying *the app*, not a user. **We register these by hand, per partner** — they are
not self-service, and a user cannot register their own.

The app must have every redirect URI you will log in through registered on it, or Passport
answers `invalid_client`:

- `http://localhost:8765/callback` — the login over stdio, and over `make run` on localhost;
- `https://<your-ngrok-domain>/callback` — the login over HTTP behind ngrok. Use a static
  ngrok domain, or the registered redirect breaks between runs.

Write `localhost`, never `127.0.0.1` — both in the registered redirect and in
`MCP_DATA_TWELVE_DATA_REDIRECT_URI` if you set it. Passport matches `localhost` exactly, and
the server treats any host other than `localhost` as public.

Either way the data requests are billed to the account behind the key.

## Requirements

- **Python 3.10+** (3.12 recommended) — macOS: `brew install python@3.12`, or `make python-install`
- **Node.js** — only for the interactive inspector (`make inspect`)

## Setup

**1. Install**

```bash
make install
```

**2. Configure**

With a static API key, create `.env` in the project root:

```bash
TWELVE_DATA_API_KEY=your_api_key_here
```

With an OAuth login, write the credentials we issued you instead:

```bash
make configure CLIENT_ID=your_client_id CLIENT_SECRET=your_client_secret
```

That writes `.env` from `.env.example` with mode `600`. **It overwrites an existing `.env`**,
so copy anything you need out of it first. `.env` is read at import from the project root,
and real environment variables win over it.

**3. Run**

```bash
make run           # Streamable HTTP → http://localhost:8000/mcp
make run-stdio     # stdio — for Claude Desktop
make run-sse       # SSE → http://localhost:8000/sse (legacy)
```

## Which account serves a request

The server resolves the credential for each tool call in this order, and stops at the first
that answers:

1. a raw `Authorization: Bearer <key>` on the request, taken as an API key;
2. the single signed-in account, if exactly one has logged in through `oauth_login`;
3. `TWELVE_DATA_API_KEY` from the environment.

All three are single-tenant by construction — rung 2 answers only while there is exactly
one stored account. Nothing here authenticates a caller, which is what the next section is
about.

## Security

- `make run` and Docker serve `/mcp` with **no authentication**, on `0.0.0.0` by default.
- Every call is served under **your** credential.
- Anyone who reaches the port can call `auth_status` and `oauth_configure`. That includes a
  web page you open, through DNS rebinding, because the default bind checks neither the
  `Host` nor the `Origin` header.
- `MCP_HOST=127.0.0.1 make run` keeps the server local and turns on the MCP SDK's `Host` and
  `Origin` check.
- With `MCP_HOST=127.0.0.1`, ngrok works only when started with `--host-header=rewrite`.

Keep it on a private network, or put authentication in front of it. Shut a tunnel down when
you are done with it.

## OAuth login, path A: stdio

```bash
make configure CLIENT_ID=your_client_id CLIENT_SECRET=your_client_secret
claude mcp add twelvedata -- /path/to/mcp/.venv/bin/python /path/to/mcp/src/server.py
```

In Claude Code, call `oauth_login`. A browser window opens on Twelve Data; after you
authorize, the redirect lands on `http://localhost:8765/callback`, which the server listens on
for the duration of the login, and the account's API key is stored. Call `auth_status` to
check, then ask for data.

`make run` on localhost logs in the same way, through the same redirect:

```bash
make run
claude mcp add --transport http twelvedata http://localhost:8000/mcp
```

## OAuth login, path B: HTTP behind ngrok

```bash
make configure CLIENT_ID=your_client_id CLIENT_SECRET=your_client_secret
make run
ngrok http --domain=<your-ngrok-domain> 8000
claude mcp add --transport http twelvedata https://<your-ngrok-domain>/mcp
```

Call `oauth_login`. It returns a link to open in your browser; after you authorize, the
redirect lands on `https://<your-ngrok-domain>/callback` and the page says "Authorization
successful". The server derives that redirect from the request headers, so leave
`MCP_DATA_TWELVE_DATA_REDIRECT_URI` unset.

## Claude Desktop (stdio)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "twelvedata": {
      "command": "/path/to/mcp/.venv/bin/python",
      "args": ["/path/to/mcp/src/server.py"]
    }
  }
}
```

Use the `.venv/bin/python` path, not the system Python (macOS ships 3.9; this needs 3.10+).
Restart Claude Desktop after editing. Without an API key in `.env`, call `oauth_login` from
the client and a browser window opens.

## Other commands

```bash
make inspect       # MCP Inspector UI at http://localhost:5173 — call tools by hand
make check         # syntax-check all Python files
make help          # every target, with what it does
```

## Debugging auth

Call `auth_status` from the client first. On a self-hosted instance it reports the
configured credentials, the stored token, the detected host, the redirect URI that will be
used, and how many accounts are stored — which is usually enough to see what is missing.

- **The login link points at a domain that does not exist.** An older `.env.example` carried
  `MCP_DATA_TWELVE_DATA_REDIRECT_URI=https://xxxx.ngrok-free.dev/callback`, and
  `make configure` copied it into `.env`. Delete that line from `.env` and restart the server.
  `auth_status` shows the value in use.
- **A localhost login after an ngrok one goes to the ngrok domain.** `oauth_login` writes the
  redirect it detects into the server's environment, and it stays there for the life of the
  process. Restart the server before logging in over localhost.
