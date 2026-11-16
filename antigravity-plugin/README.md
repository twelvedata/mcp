# Twelve Data for Antigravity

Market data for stocks, forex, crypto, ETFs and indices inside Antigravity: real-time quotes, historical time series, symbol search, fundamentals and technical indicators such as RSI.

The plugin connects to the hosted Twelve Data MCP server at `https://mcp.twelvedata.com/mcp`. No API key is stored in the plugin. You sign in to your own Twelve Data account, and every request runs under that account and its plan.

## Install

Install Twelve Data from the Antigravity plugin marketplace.

After installation the plugin card shows "Sign in required". Open the Twelve Data plugin, go to the Accounts tab and choose Sign in: Antigravity opens a browser window where you sign in to your Twelve Data account. A free account is enough to start: https://twelvedata.com/register

## Install from source

Clone the repository and install the plugin from its folder:

```bash
git clone --depth 1 https://github.com/twelvedata/mcp.git
cd mcp
agy plugin install ./antigravity-plugin
```

Then sign in on the Accounts tab as above.

Antigravity keeps its own copy of the plugin, so the cloned folder can be deleted after installation. To update, pull or clone again and run the same install command.

## Try

- Find the symbol for Apple and show its latest quote
- Show the last five daily closing prices for NVDA
- What is the 14-day RSI for AAPL?

## Support

- Documentation: https://twelvedata.com/docs
- Support: https://support.twelvedata.com/en/
- Privacy: https://twelvedata.com/privacy
- Terms: https://twelvedata.com/terms
