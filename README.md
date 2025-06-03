
# Twelve Data MCP Server

## Overview

The Twelve Data MCP Server provides a seamless integration with the Twelve Data API to access financial market data. It enables retrieval of historical time series, real-time quotes, and instrument metadata for stocks, forex pairs, and cryptocurrencies.

> Note: This server is currently in early-stage development; features and tools may evolve alongside updates to the Twelve Data API.

## Obtaining Your API Key

To use Twelve Data MCP Server, you must first obtain an API key from Twelve Data:

1. Visit [Twelve Data Sign Up](https://twelvedata.com/register?utm_source=github&utm_medium=repository&utm_campaign=mcp_repo).
2. Create an account or log in if you already have one.
3. Navigate to your Dashboard and copy your API key.

Important: Access to specific endpoints or markets may vary depending on your Twelve Data subscription plan.

## Tools

1. **`time_series`**
   Fetch historical price data for a symbol.

   * **Inputs:**

     * `symbol` (string): Ticker, e.g. `AAPL`
     * `interval` (string): Data interval, e.g. `1min`, `1day`
     * `start_date` (string, optional): ISO-8601 start timestamp
     * `end_date` (string, optional): ISO-8601 end timestamp
   * **Returns:** Array of OHLCV bars.

2. **`price`**
   Get the latest price for a symbol.

   * **Inputs:**

     * `symbol` (string)
   * **Returns:** Latest price quote.

3. **`stocks`**
   List available stock instruments.

   * **Inputs:**

     * `exchange` (string, optional): Exchange code to filter by
   * **Returns:** Array of stock metadata.

4. **`forex_pairs`**
   List available forex pairs.

   * **Inputs:** none
   * **Returns:** Array of forex pair metadata.

5. **`cryptocurrencies`**
   List available cryptocurrencies.

   * **Inputs:** none
   * **Returns:** Array of cryptocurrency metadata.

## Installation

### Using **UV** (recommended)

Directly run without local installation using [`uvx`](https://docs.astral.sh/uv/guides/tools/):

```bash
uvx mcp-server-twelve-data --help
```

### Using **pip**

Install the server via pip:

```bash
pip install mcp-server-twelve-data
python -m mcp_server_twelve_data --help
```

## Configuration

### Claude Desktop integration

Add the following snippet to your `claude_desktop_config.json`:

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

### VS Code integration

#### Automatic setup (with UV)

[![Install with UV in VS Code](https://img.shields.io/badge/VS_Code-UV-0098FF?style=flat-square\&logo=visualstudiocode\&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=twelvedata&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22mcp-server-twelve-data%22%2C%22--apikey%22%2C%22YOUR_API_KEY%22%5D%7D)

#### Manual setup

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

Use the MCP Inspector for troubleshooting:

```bash
npx @modelcontextprotocol/inspector uvx mcp-server-twelve-data
```

## Development guide

1. **Local testing:** Utilize the MCP Inspector as described in **Debugging**.
2. **Claude Desktop:**: Update `claude_desktop_config.json` to reference local source paths.

## Docker usage

Build and run the server using Docker:

```bash
docker build -t mcp-server-twelve-data .
docker run --rm mcp-server-twelve-data --apikey YOUR_API_KEY
```

## License

This MCP server is licensed under the MIT License. See the [LICENSE](../../LICENSE) file for details.
