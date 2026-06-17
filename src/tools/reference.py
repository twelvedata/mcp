"""Reference data tools: exchanges, schedules, countries, instrument types."""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import Context

from state import mcp, _get_client, _token_from_ctx, _err, _raw


@mcp.tool()
async def get_reference_data(
    ctx: Context,
    data_type: str,
    exchange: Optional[str] = None,
    mic_code: Optional[str] = None,
    country: Optional[str] = None,
    date: Optional[str] = None,
    instrument_type: Optional[str] = None,
    fund_type: Optional[str] = None,
) -> str:
    """Get reference and dictionary data — exchanges, countries, instrument types, and more.

    data_type:
      'exchanges'         – list of stock/ETF/forex exchanges with MIC codes
      'exchange_schedule' – trading hours and holiday schedule for an exchange
      'crypto_exchanges'  – list of supported cryptocurrency exchanges
      'countries'         – list of all supported countries with ISO codes
      'instrument_types'  – list of all supported instrument types
      'etf_types'         – ETF category/type classifications
      'fund_types'        – mutual fund category/type classifications

    Filters (not all apply to every data_type):
      exchange        – exchange name, e.g. 'NASDAQ' (for exchange_schedule)
      mic_code        – ISO 10383 MIC code, e.g. 'XNGS'
      country         – country name or ISO code, e.g. 'United States' or 'US'
      date            – specific date YYYY-MM-DD (for exchange_schedule)
      instrument_type – asset class filter for exchanges, e.g. 'ETF', 'Stock'
      fund_type       – fund category filter, e.g. 'Large Blend' (for etf_types/fund_types)

    Use for: 'list all exchanges', 'NYSE trading hours', 'what countries are supported?',
    'what instrument types exist?', 'ETF categories', 'is NASDAQ open on Friday?'
    """
    client = _get_client(_token_from_ctx(ctx))

    key = data_type.lower().replace(" ", "_")

    if key in ("exchanges", "exchange"):
        data = await client.get(
            "exchanges",
            type=instrument_type,
            name=exchange,
            code=mic_code,
            country=country,
        )
    elif key in ("exchange_schedule", "schedule"):
        data = await client.get(
            "exchange_schedule",
            mic_name=exchange,
            mic_code=mic_code,
            country=country,
            date=date,
        )
    elif key in ("crypto_exchanges", "crypto_exchange", "cryptocurrency_exchanges"):
        data = await client.get("cryptocurrency_exchanges")
    elif key in ("countries", "country"):
        data = await client.get("countries")
    elif key in ("instrument_types", "instrument_type"):
        data = await client.get("instrument_type")
    elif key in ("etf_types", "etf_type"):
        data = await client.get("etfs/type", country=country, fund_type=fund_type)
    elif key in ("fund_types", "fund_type", "mutual_fund_types"):
        data = await client.get("mutual_funds/type", country=country, fund_type=fund_type)
    else:
        return f"Error: unknown data_type '{data_type}'"

    if e := _err(data):
        return e
    return _raw(data)
