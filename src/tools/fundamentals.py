"""Fundamental data tools: financials, earnings, dividends, profiles, stats, ETFs, IPOs."""

from __future__ import annotations

import json
import re
from datetime import date
from html import unescape
from html.parser import HTMLParser
from typing import Optional

from mcp.server.fastmcp import Context

from state import mcp, _get_client, _token_from_ctx, _err, _raw


def _truncate_csv(data, max_rows: int) -> str:
    """Keep the header + first max_rows data rows of a CSV response.

    Non-CSV (JSON) responses and already-short results pass through unchanged.
    """
    text = _raw(data)
    if max_rows <= 0 or "\n" not in text:
        return text
    lines = text.splitlines()
    total = len(lines) - 1  # excluding header
    if total <= max_rows:
        return text
    kept = "\n".join(lines[: max_rows + 1])
    return (
        f"{kept}\n"
        f"... showing {max_rows} of {total} rows. "
        f"Pass a larger outputsize or filter by country/exchange to narrow the list."
    )


_NEWS_BODY_PREVIEW = 500  # chars of press-release body to keep, after HTML→markdown


class _MarkdownExtractor(HTMLParser):
    """Minimal HTML→markdown for press-release bodies (no extra dependency).

    Covers the tags TD press releases actually use — headings, paragraphs,
    links, lists, emphasis. Content of <script>/<style> is dropped entirely.
    """

    _BLOCK = {"p", "div", "section", "article", "header", "footer",
              "ul", "ol", "table", "tr", "blockquote", "br"}
    _SKIP = {"script", "style", "head"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0
        self._href = None

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
        elif self._skip:
            return
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.parts.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in ("strong", "b"):
            self.parts.append("**")
        elif tag in ("em", "i"):
            self.parts.append("_")
        elif tag == "a":
            self._href = dict(attrs).get("href")
            self.parts.append("[")
        elif tag in self._BLOCK:
            self.parts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP:
            self._skip = max(0, self._skip - 1)
        elif self._skip:
            return
        elif tag in ("strong", "b"):
            self.parts.append("**")
        elif tag in ("em", "i"):
            self.parts.append("_")
        elif tag == "a":
            href, self._href = self._href, None
            self.parts.append(f"]({href})" if href else "]")
        elif tag[0] == "h" or tag in self._BLOCK:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _html_to_markdown(html: str) -> str:
    """Convert an HTML fragment to whitespace-collapsed markdown."""
    parser = _MarkdownExtractor()
    parser.feed(html)
    md = unescape("".join(parser.parts))
    md = re.sub(r"[ \t]+", " ", md)      # collapse runs of spaces/tabs
    md = re.sub(r" *\n *", "\n", md)     # strip spaces around newlines
    md = re.sub(r"\n{3,}", "\n\n", md)   # at most one blank line
    return md.strip()


def _shape_press_releases(data):
    """Trim a press_releases payload for the model: drop the heavy CSS `style`
    field and render each HTML `body` to a short markdown preview.
    """
    if not isinstance(data, dict):
        return data
    releases = data.get("press_releases")
    if isinstance(releases, list):
        for item in releases:
            if not isinstance(item, dict):
                continue
            item.pop("style", None)
            body = item.get("body")
            if isinstance(body, str) and body:
                md = _html_to_markdown(body)
                if len(md) > _NEWS_BODY_PREVIEW:
                    # extend forward to the next whitespace so we never cut a word
                    # (or a markdown link — URLs have no spaces) mid-token
                    nxt = re.search(r"\s", md[_NEWS_BODY_PREVIEW:])
                    cut = _NEWS_BODY_PREVIEW + nxt.start() if nxt else len(md)
                    if cut < len(md):
                        md = md[:cut].rstrip() + "… [trimmed]"
                item["body"] = md
    return data


@mcp.tool()
async def get_market_cap(
    ctx: Context,
    symbol: str,
    figi: Optional[str] = None,
    isin: Optional[str] = None,
    cusip: Optional[str] = None,
    mic_code: Optional[str] = None,
    exchange: Optional[str] = None,
    country: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    outputsize: Optional[int] = None,
) -> str:
    """Get market capitalization for a company.

    - No date params → current market cap from /statistics (available on lower plans)
    - start_date / end_date → historical market cap time series from /market_cap

    outputsize: records per page for historical data (default 10)

    Use for: 'market cap of X', 'what is Y worth?', 'historical market cap of Z',
    'how has X market cap changed over time?'
    """
    client = _get_client(_token_from_ctx(ctx))
    params = dict(
        symbol=symbol,
        figi=figi,
        isin=isin,
        cusip=cusip,
        mic_code=mic_code,
        exchange=exchange,
        country=country,
    )
    if start_date or end_date:
        data = await client.get("market_cap", **params, start_date=start_date, end_date=end_date, outputsize=outputsize)
    else:
        data = await client.get("statistics", **params)
        if e := _err(data):
            return e
        if isinstance(data, dict):
            return json.dumps({
                "meta": data.get("meta", {}),
                "market_cap": [{"date": date.today().isoformat(), "value": data.get("statistics", {}).get("valuations_metrics", {}).get("market_capitalization")}],
            })
    if e := _err(data):
        return e
    return _raw(data)


@mcp.tool()
async def get_statistics(
    ctx: Context,
    symbol: str,
    figi: Optional[str] = None,
    isin: Optional[str] = None,
    cusip: Optional[str] = None,
    mic_code: Optional[str] = None,
    exchange: Optional[str] = None,
    country: Optional[str] = None,
) -> str:
    """Get key fundamental statistics for a stock or ETF.

    Covers: market cap, enterprise value, P/E (trailing & forward), PEG, P/S, P/B,
    revenue, margins, ROA, ROE, EPS, beta, 52-week range, short ratio, dividend yield.

    Use for: 'P/E of X', 'market cap of Y', 'fundamental metrics for Z'
    """
    client = _get_client(_token_from_ctx(ctx))
    params = dict(
        symbol=symbol,
        figi=figi,
        isin=isin,
        cusip=cusip,
        mic_code=mic_code,
        exchange=exchange,
        country=country,
    )
    data = await client.get("statistics", **params)
    if e := _err(data):
        return e
    return _raw(data)


@mcp.tool()
async def get_company_info(
    ctx: Context,
    symbol: str,
    figi: Optional[str] = None,
    isin: Optional[str] = None,
    cusip: Optional[str] = None,
    mic_code: Optional[str] = None,
    exchange: Optional[str] = None,
    country: Optional[str] = None,
    data_type: str = "profile",
) -> str:
    """Get company profile, executives, or logo.

    data_type:
      'profile'         – description, sector, industry, employees, CEO, website
      'executives'      – key executives with name, title, and compensation
      'logo'            – company logo URL

    For press releases / company news, use get_company_news instead.

    Use for: 'tell me about X', 'what does Y do', 'sector of Z', 'who is the CEO of X',
    'key executives at Y', 'management team of Z', 'logo of X'
    """
    client = _get_client(_token_from_ctx(ctx))

    endpoint_map = {
        "profile":         "profile",
        "executives":      "key_executives",
        "management":      "key_executives",
        "logo":            "logo",
    }
    endpoint = endpoint_map.get(data_type.lower(), data_type.lower())

    params = dict(
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


@mcp.tool()
async def get_company_news(
    ctx: Context,
    symbol: str,
    figi: Optional[str] = None,
    isin: Optional[str] = None,
    cusip: Optional[str] = None,
    mic_code: Optional[str] = None,
    exchange: Optional[str] = None,
    country: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    outputsize: Optional[int] = None,
) -> str:
    """Latest news, press releases, and announcements for a company.

    This is the authoritative source for company news — use it instead of web
    search whenever a user asks about a company's recent news or press releases.

    start_date / end_date: datetime filter (e.g. '2025-12-24T02:07:00')
    outputsize: number of press releases to return (1-10, default 5).
    Each release's HTML body is converted to a short markdown preview to keep
    responses compact.

    Use for: 'latest press release for X', 'recent news about Y',
    'announcements from Z', 'what did X announce', 'company news for Y'
    """
    client = _get_client(_token_from_ctx(ctx))

    outputsize = min(max(outputsize or 5, 1), 10)
    params = dict(
        symbol=symbol,
        figi=figi,
        isin=isin,
        cusip=cusip,
        mic_code=mic_code,
        exchange=exchange,
        country=country,
        start_date=start_date,
        end_date=end_date,
        outputsize=outputsize,
    )
    data = await client.get("press_releases", **params)
    if e := _err(data):
        return e
    return _raw(_shape_press_releases(data))


@mcp.tool()
async def get_financials(
    ctx: Context,
    symbol: str,
    figi: Optional[str] = None,
    isin: Optional[str] = None,
    cusip: Optional[str] = None,
    mic_code: Optional[str] = None,
    exchange: Optional[str] = None,
    country: Optional[str] = None,
    statement: str = "income_statement",
    period: str = "annual",
) -> str:
    """Get financial statements for a company.

    statement:
      'income_statement' (or 'income')  – revenue, gross/operating/net income, EPS
      'balance_sheet'    (or 'balance') – assets, liabilities, equity, cash, debt
      'cash_flow'        (or 'cf')      – operating, investing, financing flows, FCF

    period: 'annual' | 'quarterly'

    Use for: 'X revenue', 'Y income statement', 'Z free cash flow', financial analysis.
    """
    client = _get_client(_token_from_ctx(ctx))

    aliases = {
        "income": "income_statement", "p&l": "income_statement",
        "balance": "balance_sheet",
        "cashflow": "cash_flow", "cf": "cash_flow",
    }
    endpoint = aliases.get(statement.lower(), statement.lower())

    params = dict(
        symbol=symbol,
        figi=figi,
        isin=isin,
        cusip=cusip,
        mic_code=mic_code,
        exchange=exchange,
        country=country,
        period=period
    )
    data = await client.get(endpoint, **params)
    if e := _err(data):
        return e
    return _raw(data)


@mcp.tool()
async def get_earnings(
    ctx: Context,
    symbol: Optional[str] = None,
    figi: Optional[str] = None,
    isin: Optional[str] = None,
    cusip: Optional[str] = None,
    mic_code: Optional[str] = None,
    exchange: Optional[str] = None,
    country: Optional[str] = None,
    calendar: bool = False,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    outputsize: Optional[int] = None,
) -> str:
    """Get earnings data or the market-wide earnings calendar.

    - symbol='AAPL'              → AAPL EPS history (actual vs estimate, surprise %)
    - calendar=True              → upcoming earnings events across the market
    - calendar=True + date range → filter the calendar to a window (YYYY-MM-DD)

    Use for: 'when does X report?', 'AAPL earnings history', 'upcoming earnings this week'

    outputsize: max rows for the market-wide calendar. It lists every company
    reporting (1000+ rows for a single day worldwide), so calendar=True caps at
    50 rows by default. Pass a larger number or filter by country/exchange to
    narrow it. Ignored for single-symbol earnings history.
    """
    client = _get_client(_token_from_ctx(ctx))
    params = dict(
        symbol=symbol,
        figi=figi,
        isin=isin,
        cusip=cusip,
        mic_code=mic_code,
        exchange=exchange,
        country=country,
        start_date=start_date,
        end_date=end_date,
    )
    if calendar:
        data = await client.get("earnings_calendar", **params)
        if e := _err(data):
            return e
        # The earnings_calendar endpoint ignores outputsize/date filtering and
        # returns every company reporting (~100k chars). Cap rows on our side.
        return _truncate_csv(data, outputsize if outputsize is not None else 50)
    data = await client.get("earnings", **params)

    if e := _err(data):
        return e
    return _raw(data)


@mcp.tool()
async def get_dividends(
    ctx: Context,
    symbol: Optional[str] = None,
    figi: Optional[str] = None,
    isin: Optional[str] = None,
    cusip: Optional[str] = None,
    mic_code: Optional[str] = None,
    exchange: Optional[str] = None,
    country: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    calendar: bool = False,
) -> str:
    """Get dividend history for a stock or the upcoming dividend calendar.

    - symbol='AAPL'  → AAPL historical dividend payments (full history)
    - calendar=True  → upcoming ex-dividend dates across the market

    Instrument identifiers (use any one to identify the security):
      symbol, figi, isin, cusip

    Filters:
      exchange  – exchange name (e.g. 'NASDAQ')
      mic_code  – MIC code (e.g. 'XNGS')
      country   – country name or ISO code (e.g. 'United States', 'US')

    Use for: 'dividend history of X', 'when is Y ex-date?', 'upcoming dividends'
    """
    client = _get_client(_token_from_ctx(ctx))

    if calendar:
        data = await client.get("dividends_calendar", start_date=start_date, end_date=end_date)
    else:
        data = await client.get(
            "dividends",
            symbol=symbol,
            figi=figi,
            isin=isin,
            cusip=cusip,
            mic_code=mic_code,
            exchange=exchange,
            country=country,
            range="full",
        )

    if e := _err(data):
        return e
    return _raw(data)


@mcp.tool()
async def get_splits(
    ctx: Context,
    symbol: Optional[str] = None,
    figi: Optional[str] = None,
    isin: Optional[str] = None,
    cusip: Optional[str] = None,
    mic_code: Optional[str] = None,
    exchange: Optional[str] = None,
    country: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    calendar: bool = False,
) -> str:
    """Get stock split history for a company or the upcoming splits calendar.

    - symbol='AAPL'  → AAPL historical split events (ratio, date)
    - calendar=True  → upcoming stock splits across the market

    Instrument identifiers (use any one to identify the security):
      symbol, figi, isin, cusip

    Filters:
      exchange   – exchange name (e.g. 'NASDAQ')
      mic_code   – MIC code (e.g. 'XNGS')
      country    – country name or ISO code (e.g. 'United States', 'US')
      start_date / end_date – date window in YYYY-MM-DD format

    Use for: 'split history of X', 'upcoming stock splits', 'has AAPL ever split?'
    """
    client = _get_client(_token_from_ctx(ctx))

    if calendar:
        data = await client.get(
            "splits_calendar",
            symbol=symbol,
            figi=figi,
            isin=isin,
            cusip=cusip,
            mic_code=mic_code,
            exchange=exchange,
            country=country,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        data = await client.get(
            "splits",
            symbol=symbol,
            figi=figi,
            isin=isin,
            cusip=cusip,
            mic_code=mic_code,
            exchange=exchange,
            country=country,
            start_date=start_date,
            end_date=end_date,
            range="full",
        )

    if e := _err(data):
        return e
    return _raw(data)


@mcp.tool()
async def get_ipo_calendar(
    ctx: Context,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    exchange: Optional[str] = None,
    mic_code: Optional[str] = None,
    country: Optional[str] = None,
) -> str:
    """Get the IPO calendar — upcoming and recent initial public offerings.

    Returns IPOs grouped by date, each with symbol, company name, exchange,
    price range, offer price, currency, and share count.

    Filters (all optional):
      start_date / end_date – date window in YYYY-MM-DD format
      exchange              – e.g. 'NASDAQ', 'NYSE'
      mic_code              – ISO 10383 MIC code (e.g. 'XNAS')
      country               – e.g. 'United States'

    Use for: 'what IPOs are coming up?', 'IPOs on NASDAQ this month', 'recent IPOs'
    """
    client = _get_client(_token_from_ctx(ctx))
    params = dict(
        start_date=start_date,
        end_date=end_date,
        exchange=exchange,
        mic_code=mic_code,
        country=country,
    )
    data = await client.get("ipo_calendar", **params)
    if e := _err(data):
        return e
    return _raw(data)


@mcp.tool()
async def get_etf_data(
    ctx: Context,
    symbol: str,
    figi: Optional[str] = None,
    isin: Optional[str] = None,
    cusip: Optional[str] = None,
    # mic_code: Optional[str] = None,
    # exchange: Optional[str] = None,
    country: Optional[str] = None,
    data_type: str = "summary",
) -> str:
    """Get ETF analytics.

    data_type:
      'summary'     – name, AUM, expense ratio, NAV, category, inception date
      'performance' – returns over 1M/3M/6M/YTD/1Y/3Y/5Y/10Y
      'risk'        – Sharpe, Sortino, Treynor, standard deviation, beta, alpha
      'composition' – top holdings and sector/asset-class weights

    Use for: ETF comparison, expense ratios, performance history, what's inside an ETF.
    """
    client = _get_client(_token_from_ctx(ctx))

    endpoint_map = {
        "summary":     "etfs/world/summary",
        "performance": "etfs/world/performance",
        "risk":        "etfs/world/risk",
        "composition": "etfs/world/composition",
        "holdings":    "etfs/world/composition",
    }
    endpoint = endpoint_map.get(data_type.lower(), "etfs/world/summary")

    params: dict = dict(
        symbol=symbol,
        figi=figi,
        isin=isin,
        cusip=cusip,
        # mic_code=mic_code,
        # exchange=exchange,
        country=country,
    )
    data = await client.get(endpoint, **params)
    if e := _err(data):
        return e
    return _raw(data)
