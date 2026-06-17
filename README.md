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

---

## Option 2 — Run it locally with your API key

Prefer to run the server on your own machine (e.g. for Claude Desktop over stdio)? You only need your **Twelve Data API key** — no OAuth setup.

### 1. Get your API key

Log in at [twelvedata.com](https://twelvedata.com) → your dashboard → **API Keys**. Copy your key.

### 2. Install

Requires **Python 3.10+** (3.12 recommended; on macOS `brew install python@3.12` or `make python-install`).

```bash
make install
```

### 3. Add your API key

Create a `.env` file in the project root with your key:

```bash
TWELVE_DATA_API_KEY=your_api_key_here
```

### 4. Connect to Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

Use the `.venv/bin/python` path (not the system Python — macOS ships 3.9, and this server needs 3.10+). Restart Claude Desktop after editing the config.

That's all — the server reads your API key from `.env` and every request uses it. No login step needed.

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
