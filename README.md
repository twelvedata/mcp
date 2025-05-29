
# mcp-server-twelve-data

![Repository Illustration](./favicon.ico)


## Overview

A Model Context Protocol server for the Twelve Data API.
This server provides tools to fetch market data—historical time series, latest quotes, and instrument lists—for stocks, forex pairs, and cryptocurrencies.
Please note that **mcp-server-twelve-data** is in early development; functionality and available tools may change as the Twelve Data API evolves.

## Tools

1. **`time_series`**
   Fetch historical price data for a symbol.

   * **Inputs:**

     * `symbol` (string): Ticker, e.g. `AAPL`
     * `interval` (string): Data interval, e.g. `1min`, `1day`
     * `start_date` (string, optional): ISO-8601 start timestamp
     * `end_date` (string, optional): ISO-8601 end timestamp
   * **Returns:** Array of OHLCV bars

2. **`price`**
   Get the latest price for a symbol.

   * **Inputs:**

     * `symbol` (string)
   * **Returns:** Latest price quote

3. **`stocks`**
   List available stock instruments.

   * **Inputs:**

     * `exchange` (string, optional): Exchange code to filter by
   * **Returns:** Array of stock metadata

4. **`forex_pairs`**
   List available forex pairs.

   * **Inputs:** none
   * **Returns:** Array of forex pair metadata

5. **`cryptocurrencies`**
   List available cryptocurrencies.

   * **Inputs:** none
   * **Returns:** Array of cryptocurrency metadata

## Installation

### Using **uv** (recommended)

No local install required—use [`uvx`](https://docs.astral.sh/uv/guides/tools/) to run directly:

```bash
uvx mcp-server-twelve-data --help
```

### Using **pip**

```bash
pip install mcp-server-twelve-data
python -m mcp_server_twelve_data --help
```

## Configuration

### Usage with Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "twelvedata": {
      "command": "uvx",
      "args": ["mcp-server-twelve-data", "--apikey", "YOUR_API_KEY"]
    }
  }
}
```

### Usage with VS Code

#### Install with UV in VS Code

[![Install with UV in VS Code](https://img.shields.io/badge/VS_Code-UV-0098FF?style=flat-square\&logo=visualstudiocode\&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=twelvedata&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22mcp-server-twelve-data%22%2C%22--apikey%22%2C%22YOUR_API_KEY%22%5D%7D)

For manual configuration, add to your **User Settings (JSON)**:

```json
{
  "mcp": {
    "servers": {
      "twelvedata": {
        "command": "uvx",
        "args": ["mcp-server-twelve-data", "-t", "streamable-http"]
      }
    }
  }
}
```

## Debugging

Use the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector uvx mcp-server-twelve-data
```

## Development

1. **Local testing** via MCP Inspector (see **Debugging**).
2. **Claude Desktop**: update `claude_desktop_config.json` to point at your local source.

## Docker run

```bash
docker build -t mcp-server-twelve-data .
docker run --rm mcp-server-twelve-data --apikey YOUR_API_KEY
```

## License

This MCP server is licensed under the MIT License. See the [LICENSE](../../LICENSE) file for details.
