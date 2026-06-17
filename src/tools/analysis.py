"""Analysis tools: technical indicators and analyst data."""

from __future__ import annotations

import json
from typing import Annotated, Optional
from pydantic import BeforeValidator

from mcp.server.fastmcp import Context

from state import mcp, _get_client, _token_from_ctx, _err, _raw


@mcp.tool()
async def get_technical_indicator(
    ctx: Context,
    indicator: str,
    symbol: str,
    figi: Optional[str] = None,
    isin: Optional[str] = None,
    cusip: Optional[str] = None,
    mic_code: Optional[str] = None,
    exchange: Optional[str] = None,
    country: Optional[str] = None,
    interval: str = "1day",
    outputsize: int = 30,
    prepost: bool = False,
    time_period: Optional[int] = None,
    series_type: Optional[str] = None,
    fast_period: Optional[int] = None,
    slow_period: Optional[int] = None,
    signal_period: Optional[int] = None,
    nbdevup: Optional[float] = None,
    nbdevdn: Optional[float] = None,
    symbol_2: Optional[str] = None,
    extra: Optional[Annotated[str, BeforeValidator(lambda v: json.dumps(v) if isinstance(v, dict) else v)]] = None,
) -> str:
    """Calculate any technical indicator for a symbol.

    indicator (case-insensitive) — available indicators:

    Trend/Overlap:
      SMA, EMA, WMA, DEMA, TEMA, TRIMA, KAMA, MAMA, T3MA, HT_TRENDLINE,
      VWAP, BBANDS, MIDPOINT, MIDPRICE, SAR, SAREXT, ICHIMOKU, KELTNER,
      PIVOT_POINTS_HL, MA, MCGINLEY_DYNAMIC

    Momentum:
      RSI, MACD, MACDEXT, MACD_SLOPE, STOCH, STOCHF, STOCHRSI, ADX, ADXR,
      APO, AROON, AROONOSC, BOP, CCI, CMO, COPPOCK, CRSI, DPO, DX, KST,
      MFI, MINUS_DI, MINUS_DM, MOM, PERCENT_B, PLUS_DI, PLUS_DM, PPO,
      ROC, ROCP, ROCR, ROCR100, STOCH, ULTOSC, WILLR

    Volume:   OBV, AD, ADOSC, RVOL
    Volatility: ATR, NATR, TRANGE, SUPERTREND
    Statistics: CORREL, BETA, STDDEV, VAR, LINEARREG, LINEARREGSLOPE, TSF, MAX, MIN
    Price Transform: AVGPRICE, MEDPRICE, TYPPRICE, WCLPRICE, HLC3, HEIKINASHICANDLES

    Instrument identifiers (use any one):
      symbol, figi, isin, cusip
    For multiple symbols pass a comma-separated string: 'AAPL,MSFT,BTC/USD'

    Key parameters:
      exchange  – exchange name (e.g. 'NASDAQ')
      mic_code  – MIC code (e.g. 'XNGS')
      country   – country name or ISO code (e.g. 'United States', 'US')
      prepost   – include pre/post-market price (default False)
      time_period        – lookback window (e.g. 14 for RSI, 20 for SMA/BBANDS)
      series_type        – close | open | high | low
      fast/slow/signal_period – for MACD
      nbdevup / nbdevdn  – std-dev multipliers for BBANDS
      symbol_2           – second symbol for CORREL / BETA
      extra              – JSON string for any other indicator-specific params
                           e.g. "{\"fast_k_period\":5,\"slow_k_period\":3}" for STOCH
    """
    client = _get_client(_token_from_ctx(ctx))

    params: dict = dict(
        symbol=symbol,
        figi=figi,
        isin=isin,
        cusip=cusip,
        mic_code=mic_code,
        exchange=exchange,
        country=country,
        interval=interval,
        outputsize=outputsize,
        prepost=prepost,
        time_period=time_period,
        series_type=series_type,
        fast_period=fast_period,
        slow_period=slow_period,
        signal_period=signal_period,
        nbdevup=nbdevup,
        nbdevdn=nbdevdn,
        symbol_2=symbol_2,
    )

    if extra:
        try:
            params.update(json.loads(extra))
        except json.JSONDecodeError:
            return "Error: `extra` must be a JSON object, e.g. {\"time_period\": 200}"

    data = await client.get(indicator.lower(), **params)
    if e := _err(data):
        return e
    return _raw(data)


@mcp.tool()
async def get_analyst_data(
    ctx: Context,
    symbol: str,
    figi: Optional[str] = None,
    isin: Optional[str] = None,
    cusip: Optional[str] = None,
    mic_code: Optional[str] = None,
    exchange: Optional[str] = None,
    country: Optional[str] = None,
    data_type: str = "ratings",
) -> str:
    """Get analyst ratings, consensus price targets, and forward estimates for stocks and ETFs.

    data_type:
      'ratings'           – buy/sell/hold counts + consensus rating + target price
      'price_target'      – mean/high/low analyst price targets
      'recommendations'   – historical recommendation trend (buy/hold/sell over time)
      'earnings_estimate' – quarterly & annual EPS estimates
      'revenue_estimate'  – quarterly & annual revenue estimates
      'eps_trend'         – how EPS estimates have shifted (current/7d/30d/60d ago)
      'eps_revisions'     – upward/downward estimate revision counts
      'growth_estimates'  – next-quarter/year/5-year growth rate consensus

    Note: this tool is for stocks and ETFs only. For mutual fund ratings (Morningstar stars,
    fund grades) use get_mutual_fund_data with data_type='ratings'.

    Use for: 'analyst opinion on AAPL', 'price target for TSLA', 'EPS estimate for MSFT',
    'buy/sell/hold for X stock'
    """
    client = _get_client(_token_from_ctx(ctx))

    endpoint_map = {
        "ratings":           "analyst_ratings/us_equities",
        "price_target":      "price_target",
        "recommendations":   "recommendations",
        "earnings_estimate": "earnings_estimate",
        "revenue_estimate":  "revenue_estimate",
        "eps_trend":         "eps_trend",
        "eps_revisions":     "eps_revisions",
        "growth_estimates":  "growth_estimates",
    }
    endpoint = endpoint_map.get(data_type.lower(), data_type.lower())

    params: dict = dict(
        symbol=symbol,
        figi=figi,
        isin=isin,
        cusip=cusip,
        mic_code=mic_code,
        exchange=exchange,
        country=country,
    )

    data = await client.get(endpoint, **params)
    if e := _err(data):
        return e

    if data_type.lower() == "ratings" and isinstance(data, dict):
        for rating in data.get("ratings", []):
            if rating.get("time") == "00:00:00":
                rating.pop("time", None)
            for key in [k for k, v in list(rating.items()) if v is None]:
                del rating[key]

    return _raw(data)
