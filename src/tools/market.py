"""Market data tools: prices, quotes, time series, movers, rates, state."""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import Context

from state import mcp, _get_client, _token_from_ctx, _err, _raw


@mcp.tool()
async def get_price(
    ctx: Context,
    symbol: Optional[str] = None,
    figi: Optional[str] = None,
    isin: Optional[str] = None,
    cusip: Optional[str] = None,
    mic_code: Optional[str] = None,
    exchange: Optional[str] = None,
    country: Optional[str] = None,
    prepost: bool = False,
) -> str:
    """Get the current real-time price for one or more symbols.

    Instrument identifiers (use any one):
      symbol, figi, isin, cusip
    For multiple symbols pass a comma-separated string: 'AAPL,MSFT,BTC/USD'

    Filters:
      exchange  – exchange name (e.g. 'NASDAQ')
      mic_code  – MIC code (e.g. 'XNGS')
      country   – country name or ISO code (e.g. 'United States', 'US')
      prepost   – include pre/post-market price (default False)

    Use this for: 'what is X trading at?', 'current price of Y', 'how much is Z?'

    Not supported: market indices (S&P 500/SPX, NASDAQ/IXIC, Dow/DJI), options,
    and bonds. For an index, use its ETF proxy — SPY (S&P 500), QQQ (NASDAQ-100),
    DIA (Dow), IWM (Russell 2000).
    """
    client = _get_client(_token_from_ctx(ctx))
    data = await client.get(
        "price",
        symbol=symbol,
        figi=figi,
        isin=isin,
        cusip=cusip,
        mic_code=mic_code,
        exchange=exchange,
        country=country,
        prepost=prepost if prepost else None,
    )
    if e := _err(data):
        return e
    return _raw(data)


@mcp.tool()
async def get_quote(
    ctx: Context,
    symbol: Optional[str] = None,
    figi: Optional[str] = None,
    isin: Optional[str] = None,
    cusip: Optional[str] = None,
    mic_code: Optional[str] = None,
    exchange: Optional[str] = None,
    country: Optional[str] = None,
    prepost: bool = False,
) -> str:
    """Get a full real-time quote: open, high, low, close, volume, change %, 52-week range.

    Instrument identifiers (use any one):
      symbol, figi, isin, cusip

    Filters:
      exchange  – exchange name (e.g. 'NASDAQ')
      mic_code  – MIC code (e.g. 'XNGS')
      country   – country name or ISO code (e.g. 'United States', 'US')
      prepost   – include pre/post-market data (default False)

    Use for detailed current market snapshot of a stock, ETF, forex pair, or crypto.

    Not supported: market indices (S&P 500/SPX, NASDAQ/IXIC, Dow/DJI), options,
    and bonds. For an index, use its ETF proxy — SPY (S&P 500), QQQ (NASDAQ-100),
    DIA (Dow), IWM (Russell 2000).
    """
    client = _get_client(_token_from_ctx(ctx))
    data = await client.get(
        "quote",
        symbol=symbol,
        figi=figi,
        isin=isin,
        cusip=cusip,
        mic_code=mic_code,
        exchange=exchange,
        country=country,
        prepost=prepost if prepost else None,
    )
    if e := _err(data):
        return e
    return _raw(data)


@mcp.tool()
async def get_time_series(
    ctx: Context,
    symbol: Optional[str] = None,
    figi: Optional[str] = None,
    isin: Optional[str] = None,
    cusip: Optional[str] = None,
    mic_code: Optional[str] = None,
    exchange: Optional[str] = None,
    country: Optional[str] = None,
    interval: str = "1day",
    outputsize: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    prepost: bool = False,
) -> str:
    """Get historical OHLCV (Open, High, Low, Close, Volume) time series data.

    Instrument identifiers (use any one):
      symbol, figi, isin, cusip

    Filters:
      exchange  – exchange name (e.g. 'NASDAQ')
      mic_code  – MIC code (e.g. 'XNGS')
      country   – country name or ISO code (e.g. 'United States', 'US')

    interval: 1min | 5min | 15min | 30min | 45min | 1h | 2h | 4h | 1day | 1week | 1month
    outputsize: number of data points (default 30, max 5000)
    start_date / end_date: YYYY-MM-DD (optional, overrides outputsize window)
    prepost: include pre-market and post-market data (default False)

    Use for: historical prices, trend analysis, price performance over time.
    To find how far back data goes (the earliest valid start_date) without
    fetching the series, use get_earliest_timestamp instead.

    Not supported: market indices (S&P 500/SPX, NASDAQ/IXIC, Dow/DJI), options,
    and bonds. For an index, use its ETF proxy — SPY (S&P 500), QQQ (NASDAQ-100),
    DIA (Dow), IWM (Russell 2000).
    """
    client = _get_client(_token_from_ctx(ctx))
    data = await client.get(
        "time_series",
        symbol=symbol,
        figi=figi,
        isin=isin,
        cusip=cusip,
        mic_code=mic_code,
        exchange=exchange,
        country=country,
        interval=interval,
        outputsize=outputsize,
        start_date=start_date,
        end_date=end_date,
        prepost=prepost if prepost else None,
    )
    if e := _err(data):
        return e
    return _raw(data)


@mcp.tool()
async def get_earliest_timestamp(
    ctx: Context,
    interval: str = "1day",
    symbol: Optional[str] = None,
    figi: Optional[str] = None,
    isin: Optional[str] = None,
    cusip: Optional[str] = None,
    mic_code: Optional[str] = None,
    exchange: Optional[str] = None,
) -> str:
    """Get the earliest available datetime for an instrument at a given interval.

    Returns the first date/time for which historical data exists (with its UNIX
    timestamp) — i.e. how far back the history goes. This is metadata about data
    availability, NOT the price data itself; use get_time_series to fetch actual
    OHLCV, and use this tool to discover the valid start_date for that call.

    Instrument identifiers (use any one):
      symbol, figi, isin, cusip

    interval: 1min | 5min | 15min | 30min | 45min | 1h | 2h | 4h | 1day | 1week | 1month

    Filters:
      exchange  – exchange name (e.g. 'NASDAQ')
      mic_code  – MIC code (e.g. 'XNGS')

    Use for: 'how far back does data go for X?', 'earliest available date for Y',
    'when does Z's history start?'
    """
    client = _get_client(_token_from_ctx(ctx))
    data = await client.get(
        "earliest_timestamp",
        symbol=symbol,
        figi=figi,
        isin=isin,
        cusip=cusip,
        mic_code=mic_code,
        exchange=exchange,
        interval=interval,
    )
    if e := _err(data):
        return e
    return _raw(data)


@mcp.tool()
async def get_market_state(
    ctx: Context,
    exchange: Optional[str] = None,
    mic_code: Optional[str] = None,
    country: Optional[str] = None,
) -> str:
    """Get current trading status and hours for exchanges.

    Leave all filters blank for all major markets.
      exchange  – exchange name (e.g. 'NYSE', 'NASDAQ', 'LSE', 'BINANCE')
      mic_code  – MIC code (e.g. 'XNYS')
      country   – country name or ISO code (e.g. 'United States', 'US')

    Use for: 'is the market open?', 'NYSE hours', 'when does NASDAQ close?'
    """
    client = _get_client(_token_from_ctx(ctx))
    data = await client.get("market_state", exchange=exchange, code=mic_code, country=country)
    if e := _err(data):
        return e
    return _raw(data)


@mcp.tool()
async def get_market_movers(
    ctx: Context,
    market: str = "stocks",
    direction: str = "gainers",
    country: str = "United States",
    outputsize: int = 10,
) -> str:
    """Get top market movers — biggest gainers, losers, or most-active instruments.

    market   : stocks | etfs | mutual_funds | forex | crypto | commodities
    direction: gainers | losers | most_active  (most_active only for stocks)
    country  : e.g. 'United States', 'United Kingdom', 'Germany' (for stocks/etfs)

    Use for: 'top gainers today', 'biggest crypto losers', 'most active stocks'
    """
    client = _get_client(_token_from_ctx(ctx))

    path_map = {
        "stocks": "stocks", "stock": "stocks",
        "etfs": "etfs", "etf": "etfs",
        "mutual_funds": "mutual_funds", "funds": "mutual_funds",
        "forex": "forex", "fx": "forex",
        "crypto": "crypto", "cryptocurrencies": "crypto", "cryptocurrency": "crypto",
        "commodities": "commodities", "commodity": "commodities",
    }
    path = path_map.get(market.lower(), market.lower())

    data = await client.get(
        f"market_movers/{path}",
        direction=direction,
        country=country,
        outputsize=outputsize,
    )
    if e := _err(data):
        return e
    return _raw(data)


@mcp.tool()
async def currency_conversion(
    ctx: Context,
    symbol: str,
    amount: Optional[float] = None,
    date: Optional[str] = None,
) -> str:
    """Get exchange rate or convert an amount between currencies (fiat or crypto).

    symbol: currency pair, e.g. 'EUR/USD', 'BTC/USD', 'GBP/JPY'
    amount: if provided, returns the converted value for that amount
    date:   historical rate for a specific date (YYYY-MM-DD); omit for real-time

    Use for: 'EUR to USD', 'convert 1000 JPY to GBP', 'BTC price in EUR'
    """
    client = _get_client(_token_from_ctx(ctx))

    if amount is not None:
        data = await client.get("currency_conversion", symbol=symbol, amount=amount, date=date)
    else:
        data = await client.get("exchange_rate", symbol=symbol, date=date)

    if e := _err(data):
        return e
    return _raw(data)
