"""Mutual fund data tools."""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import Context

from state import mcp, _get_client, _token_from_ctx, _err, _raw


@mcp.tool()
async def get_mutual_fund_data(
    ctx: Context,
    symbol: str,
    figi: Optional[str] = None,
    isin: Optional[str] = None,
    cusip: Optional[str] = None,
    country: Optional[str] = None,
    data_type: str = "summary",
) -> str:
    """Get mutual fund data — summary, performance, risk, ratings, holdings, and more.

    data_type:
      'summary'       – name, AUM, expense ratio, NAV, category, inception date
      'performance'   – returns over 1M/3M/6M/YTD/1Y/3Y/5Y/10Y
      'risk'          – Sharpe, Sortino, standard deviation, beta, alpha
      'ratings'       – Morningstar star ratings and analyst ratings for the fund
      'composition'   – top holdings and sector/asset-class weights
      'purchase_info' – minimum investment, load fees, availability
      'sustainability' – ESG scores and controversy metrics
      'full'          – all of the above in one response

    Note: 'ratings' here are fund quality ratings (Morningstar stars, analyst grades),
    NOT analyst buy/sell recommendations — use get_analyst_data for those.

    Use for: 'expense ratio of VFIAX', 'top holdings of FXAIX', 'Morningstar rating of X',
    'ESG score of Y fund', 'performance of Z mutual fund', 'minimum investment for X'
    """
    client = _get_client(_token_from_ctx(ctx))

    endpoint_map = {
        "summary":      "mutual_funds/world/summary",
        "performance":  "mutual_funds/world/performance",
        "risk":         "mutual_funds/world/risk",
        "ratings":      "mutual_funds/world/ratings",
        "composition":  "mutual_funds/world/composition",
        "holdings":     "mutual_funds/world/composition",
        "purchase_info": "mutual_funds/world/purchase_info",
        "purchase":     "mutual_funds/world/purchase_info",
        "sustainability": "mutual_funds/world/sustainability",
        "esg":          "mutual_funds/world/sustainability",
        "full":         "mutual_funds/world",
    }
    endpoint = endpoint_map.get(data_type.lower(), data_type.lower())

    params: dict = dict(
        symbol=symbol,
        figi=figi,
        isin=isin,
        cusip=cusip,
        country=country,
    )
    data = await client.get(endpoint, **params)
    if e := _err(data):
        return e
    return _raw(data)
