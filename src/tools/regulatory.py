"""Regulatory and ownership data tools."""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import Context

from state import mcp, _get_client, _token_from_ctx, _err, _raw


@mcp.tool()
async def get_regulatory_data(
    ctx: Context,
    symbol: str,
    data_type: str,
    figi: Optional[str] = None,
    isin: Optional[str] = None,
    cusip: Optional[str] = None,
    mic_code: Optional[str] = None,
    exchange: Optional[str] = None,
    country: Optional[str] = None,
) -> str:
    """Get regulatory and ownership data. data_type is required — pick the one
    that matches the question; there is no sensible default for this tool.

    data_type:
      'insider_transactions'  – recent insider buying/selling (officers, directors)
      'institutional_holders' – top institutional shareholders with share counts
      'fund_holders'          – top mutual-fund holders
      'direct_holders'        – direct/registered shareholders
      'edgar_filings'         – recent SEC filings (10-K, 10-Q, 8-K, proxy, etc.)
      'tax_info'              – tax-related data (withholding rates, domicile, etc.)

    Use for: 'insider trades at X', 'who owns Y?', 'institutional ownership of Z',
    'recent SEC filings for AAPL', 'tax info for X', 'direct holders of Y'
    """
    client = _get_client(_token_from_ctx(ctx))

    endpoint_map = {
        "insider_transactions":  "insider_transactions",
        "insider":               "insider_transactions",
        "insiders":              "insider_transactions",
        "institutional_holders": "institutional_holders",
        "institutional":         "institutional_holders",
        "institutions":          "institutional_holders",
        "fund_holders":          "fund_holders",
        "funds":                 "fund_holders",
        "direct_holders":        "direct_holders",
        "direct":                "direct_holders",
        "edgar_filings":         "edgar_filings/archive",
        "edgar":                 "edgar_filings/archive",
        "filings":               "edgar_filings/archive",
        "sec":                   "edgar_filings/archive",
        "tax_info":              "tax_info",
        "tax":                   "tax_info",
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
    return _raw(data)
