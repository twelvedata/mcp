# Twelve Data MCP Server

Connect Claude, ChatGPT, and other AI assistants to the [Twelve Data](https://twelvedata.com) financial API — real-time and historical prices, 60+ technical indicators, fundamentals, earnings, dividends, ETFs, company news, market movers, and more.

You need a Twelve Data account. Sign up at [twelvedata.com](https://twelvedata.com).

There are two ways to use it. **Most people should use the cloud server (Option 1)** — there is nothing to install.

---

## Option 1 — Use our cloud server (recommended)

Connect your AI assistant to our hosted server:

```
https://mcp.twelvedata.com/mcp
```

That's it. No installation, no API key to copy and paste. When you connect, a browser window opens and you log in with your Twelve Data account — your personal API key is linked automatically and stays tied to your account.

### How to add it

**Claude (Desktop / Web) and ChatGPT** support custom connectors / MCP servers:

1. Open your assistant's **Connectors** (or **Integrations** / **MCP servers**) settings.
2. Add a new connector with the URL `https://mcp.twelvedata.com/mcp`.
3. When prompted, click **Connect / Log in** — a Twelve Data login page opens in your browser.
4. Authorize, and you're done. Ask things like *"What's the RSI for AAPL?"* or *"Show me TSLA's latest earnings."*

> The exact menu names differ between apps and versions, but the flow is always the same: add the URL, then log in via the browser popup.

The MCP host does not issue tokens. The connector URL is `https://mcp.twelvedata.com/mcp`. The client must follow that URL's protected-resource metadata to the authorization server named there. Do not point a connector at the host root (it answers 404), or at this host's `/register` or `/.well-known/oauth-authorization-server`.

### Perplexity (custom remote connector)

Perplexity Pro, Max, and Enterprise users can add the hosted server as a custom remote connector. That is a per-account setup, not a listing in Perplexity's public curated directory.

1. In Perplexity, open **Account settings → Connectors → + Custom connector** and select **Remote**. On Enterprise, an admin may need to allow custom connectors first.
2. Set **Name** to `Twelve Data` and **MCP Server URL** to `https://mcp.twelvedata.com/mcp`.
3. Choose **OAuth** for authentication and **Streamable HTTP** for transport. Leave the Client ID and Client Secret blank so Perplexity can use dynamic client registration on the authorization server named in the server's protected-resource metadata.
4. Accept Perplexity's custom connector acknowledgement and click **Add**. Then click the Twelve Data connector card to start authentication, sign in to your Twelve Data account, and authorize access.
5. Once the connector is enabled, try these prompts:
   - "Use Twelve Data to find the AAPL symbol."
   - "Use Twelve Data to get the latest quote for AAPL, including price and volume."
   - "Use Twelve Data to show the last five daily closing prices for AAPL."
   - "Use Twelve Data to show AAPL RSI."

Each person signs in with their own Twelve Data account. If an Enterprise admin shares the connector, require individual authentication for each member. Do not paste a Twelve Data API key into the connector's API Key authentication field.

If the OAuth window is blocked, login fails, or tools stop after idle time, open the Twelve Data connector, disable it, enable it again, and sign in. Reconnect this way rather than switching the connector to API Key auth. Confirm the URL is exactly `https://mcp.twelvedata.com/mcp` with no trailing slash, and that the Twelve Data plan includes the requested data. See [Perplexity's custom remote connector guide](https://www.perplexity.ai/help-center/en/articles/13915507-adding-custom-remote-connectors) for the current settings screens.

### Codex (CLI, desktop, and IDE)

Add the hosted MCP server to Codex without installing this repository or copying an API key:

```bash
codex mcp add twelvedata --url https://mcp.twelvedata.com/mcp
codex mcp list
```

The `add` command starts OAuth: complete the Twelve Data sign-in in your browser. If you need to authorize again later, run `codex mcp login twelvedata`. In Codex, use `/mcp` to check the connection, then ask: *"Use Twelve Data to get the latest quote for AAPL."* and *"Use Twelve Data to show AAPL RSI."* To disconnect, run `codex mcp remove twelvedata`.

The public plugin repository is https://github.com/MazeBraker/twelvedata-skills. It installs the skills and the same hosted MCP:

```bash
codex plugin marketplace add https://github.com/MazeBraker/twelvedata-skills
codex plugin add twelvedata@twelvedata-skills
```

---

## Option 2 — Run it yourself with an API key

Prefer to run the server on your own machine? You only need your **Twelve Data API key** — no OAuth setup. Get it at [twelvedata.com](https://twelvedata.com) → your dashboard → **API Keys**.

### 1. Install

Requires **Python 3.10+** (3.12 recommended; on macOS `brew install python@3.12` or `make python-install`).

```bash
make install
```

### 2. Add your API key

Create a `.env` file in the project root with your key, readable only by you:

```bash
echo 'TWELVE_DATA_API_KEY=your_api_key_here' > .env
chmod 600 .env
```

The server reads the key from `.env` and every request uses it. No login step needed.

### 3. Connect over stdio

**Claude Desktop** — add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

Use the `.venv/bin/python` path (not the system Python — macOS ships 3.9, and this server needs 3.10+). Restart Claude Desktop after editing the config.

**Claude Code**:

```bash
claude mcp add twelvedata -- /path/to/mcp/.venv/bin/python /path/to/mcp/src/server.py
```

### 4. Connect over HTTP

```bash
make run           # serves http://localhost:8000/mcp
```

```bash
claude mcp add --transport http twelvedata http://localhost:8000/mcp
```

### 5. Run it in Docker

```bash
docker build -t twelvedata-mcp .
docker run --rm --env-file .env -p 127.0.0.1:8000:8000 twelvedata-mcp
```

`--env-file` keeps the key out of your shell history. Connect to `http://localhost:8000/mcp` as in step 4. OAuth login is not supported in Docker.

### 6. Security

- `make run` and Docker serve `/mcp` with **no authentication**, on `0.0.0.0` by default.
- Every call is served under **your** credential.
- Anyone who reaches the port can call `auth_status` and `oauth_configure`. That includes a web page you open, through DNS rebinding, because the default bind checks neither the `Host` nor the `Origin` header.
- `MCP_HOST=127.0.0.1 make run` keeps the server local and turns on the MCP SDK's `Host` and `Origin` check.
- With `MCP_HOST=127.0.0.1`, ngrok works only when started with `--host-header=rewrite`.

### 7. Troubleshooting

Call `auth_status` from your client first. It shows whether an API key is configured, the stored token, the detected host and the redirect URI — usually enough to see what is missing.

---

## What you can ask

- **Prices** — stocks, ETFs, forex, crypto, commodities (real-time & historical)
- **Technical indicators** — RSI, MACD, SMA, BBANDS, ATR, and 60+ more
- **Fundamentals** — financial statements, earnings, dividends, splits, company profiles, market cap, key stats, IPO calendar
- **Funds** — ETF & mutual fund profiles, performance, holdings, risk
- **News** — company news & press releases
- **Market intelligence** — movers, exchange rates, analyst ratings, price targets
- **Regulatory** — SEC/EDGAR filings, insider transactions, institutional holdings

Symbol formats: stocks `AAPL`, crypto `BTC/USD`, forex `EUR/USD`.

---

## Partners

Running your own public instance or setting up a dedicated OAuth login? That's a
partner arrangement — reach out to us at [twelvedata.com](https://twelvedata.com)
and we'll provide the setup guide and OAuth credentials.
