
utool_doc_string = """
A universal tool router for the MCP system, designed for the Twelve Data API.

This tool accepts a natural language query in English and performs the following:
1. Uses vector search to retrieve the top-N relevant Twelve Data endpoints.
2. Sends the query and tool descriptions to OpenAI's gpt-4o with function calling.
3. The model selects the most appropriate tool and generates the input parameters.
4. The selected endpoint (tool) is executed and its response is returned.

Supported endpoint categories (from Twelve Data docs):
- Market & Reference: price, quote, symbol_search, stocks, exchanges, market_state
- Time Series: time_series, eod, splits, dividends, etc.
- Technical Indicators: rsi, macd, ema, bbands, atr, vwap, and 100+ others
- Fundamentals & Reports: earnings, earnings_estimate, income_statement,
  balance_sheet, cash_flow, statistics, profile, ipo_calendar, analyst_ratings
- Currency & Crypto: currency_conversion, exchange_rate, price_target
- Mutual Funds / ETFs: funds, mutual_funds/type, mutual_funds/world
- Misc Utilities: logo, calendar endpoints, time_series_calendar, etc.
"""

doctool_doc_string = """
Search Twelve Data documentation and return a Markdown summary of the most relevant sections.
"""