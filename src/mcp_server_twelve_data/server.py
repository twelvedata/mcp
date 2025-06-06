import logging
from typing import Type, TypeVar, Literal
import httpx
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP, Context

from mcp_server_twelve_data.request_models import GetTimeSeriesRequest, GetPriceRequest, GetEodRequest, GetQuoteRequest, \
    GetMarketStateRequest, GetEarningsRequest, GetTimeSeriesRsiRequest, GetStocksRequest, GetTimeSeriesMacdRequest, \
    GetExchangeRateRequest, GetProfileRequest, GetStatisticsRequest, GetSymbolSearchRequest, GetTimeSeriesAvgRequest, \
    GetTimeSeriesSmaRequest, GetLogoRequest, GetApiUsageRequest, GetTimeSeriesEmaRequest, GetExchangeScheduleRequest, \
    GetTimeSeriesAtrRequest, GetMutualFundsWorldSummaryRequest, GetMutualFundsWorldRequest, GetTimeSeriesVwapRequest, \
    GetTimeSeriesCrsiRequest, GetEarliestTimestampRequest, GetPriceTargetRequest, GetIncomeStatementRequest, \
    GetDividendsRequest, GetCashFlowRequest, GetBalanceSheetRequest, GetTimeSeriesBBandsRequest, \
    GetRecommendationsRequest, GetCurrencyConversionRequest, GetEtfRequest, GetSplitsRequest, \
    GetEarningsEstimateRequest, GetTimeSeriesStochRequest, GetRevenueEstimateRequest, \
    GetAnalystRatingsUsEquitiesRequest, GetInsiderTransactionsRequest, GetGrowthEstimatesRequest, \
    GetInstitutionalHoldersRequest, GetTimeSeriesSarRequest, GetTimeSeriesHtTrendlineRequest, GetEpsRevisionsRequest, \
    GetEpsTrendRequest, GetKeyExecutivesRequest, GetAnalystRatingsLightRequest, GetTimeSeriesWmaRequest, \
    GetCrossListingsRequest, GetTimeSeriesCciRequest, GetTimeSeriesAdxRequest, GetFundHoldersRequest, \
    GetTimeSeriesObvRequest, GetTimeSeriesMaRequest, GetTimeSeriesPercent_BRequest, GetExchangesRequest, \
    GetIncomeStatementConsolidatedRequest, GetDividendsCalendarRequest, GetTimeSeriesSuperTrendRequest, \
    GetETFsWorldRequest, GetTimeSeriesIchimokuRequest, GetTimeSeriesRvolRequest, GetMutualFundsListRequest, \
    GetDirectHoldersRequest, GetTimeSeriesMfiRequest, GetMarketMoversRequest, GetTimeSeriesDemaRequest, \
    GetForexPairsRequest, GetTimeSeriesPlusDIRequest, GetTimeSeriesKeltnerRequest, GetTechnicalIndicatorsRequest, \
    GetTimeSeriesHtTrendModeRequest, GetMutualFundsWorldPerformanceRequest, GetETFsWorldCompositionRequest, \
    GetMutualFundsWorldPurchaseInfoRequest, GetTimeSeriesPivotPointsHLRequest, GetTimeSeriesMinusDIRequest, \
    GetMutualFundsWorldCompositionRequest, GetTimeSeriesAdxrRequest, GetETFsWorldRiskRequest, \
    GetMutualFundsWorldRiskRequest, GetMutualFundsWorldSustainabilityRequest, GetETFsWorldPerformanceRequest, \
    GetTimeSeriesMaxRequest, GetTimeSeriesWillRRequest, GetETFsListRequest, GetTimeSeriesHeikinashiCandlesRequest, \
    GetTimeSeriesTemaRequest, GetTimeSeriesPpoRequest
from mcp_server_twelve_data.response_models import GetTimeSeries200Response, GetPrice200Response, GetEod200Response, \
    GetQuote200Response, GetMarketState200Response, GetEarnings200Response, GetTimeSeriesRsi200Response, \
    GetStocks200Response, GetTimeSeriesMacd200Response, GetExchangeRate200Response, GetProfile200Response, \
    GetStatistics200Response, GetSymbolSearch200Response, GetTimeSeriesAvg200Response, GetTimeSeriesSma200Response, \
    GetLogo200Response, GetApiUsage200Response, GetTimeSeriesEma200Response, GetExchangeSchedule200Response, \
    GetTimeSeriesAtr200Response, GetMutualFundsWorldSummary200Response, GetMutualFundsWorld200Response, \
    GetTimeSeriesVwap200Response, GetTimeSeriesCrsi200Response, GetEarliestTimestamp200Response, \
    GetPriceTarget200Response, GetIncomeStatement200Response, GetDividends200Response, GetCashFlow200Response, \
    GetBalanceSheet200Response, GetTimeSeriesBBands200Response, GetRecommendations200Response, \
    GetCurrencyConversion200Response, GetEtf200Response, GetSplits200Response, GetEarningsEstimate200Response, \
    GetTimeSeriesStoch200Response, GetRevenueEstimate200Response, GetAnalystRatingsUsEquities200Response, \
    GetInsiderTransactions200Response, GetGrowthEstimates200Response, GetInstitutionalHolders200Response, \
    GetTimeSeriesSar200Response, GetTimeSeriesHtTrendline200Response, GetEpsRevisions200Response, \
    GetEpsTrend200Response, GetKeyExecutives200Response, GetAnalystRatingsLight200Response, GetTimeSeriesWma200Response, \
    GetCrossListings200Response, GetTimeSeriesCci200Response, GetTimeSeriesAdx200Response, GetFundHolders200Response, \
    GetTimeSeriesObv200Response, GetTimeSeriesMa200Response, GetTimeSeriesPercent_B200Response, GetExchanges200Response, \
    GetIncomeStatementConsolidated200Response, GetDividendsCalendar200Response, GetTimeSeriesSuperTrend200Response, \
    GetETFsWorld200Response, GetTimeSeriesIchimoku200Response, GetTimeSeriesRvol200Response, \
    GetMutualFundsList200Response, GetDirectHolders200Response, GetTimeSeriesMfi200Response, GetMarketMovers200Response, \
    GetTimeSeriesDema200Response, GetForexPairs200Response, GetTimeSeriesPlusDI200Response, \
    GetTimeSeriesKeltner200Response, GetTechnicalIndicators200Response, GetTimeSeriesHtTrendMode200Response, \
    GetMutualFundsWorldPerformance200Response, GetETFsWorldComposition200Response, \
    GetMutualFundsWorldPurchaseInfo200Response, GetTimeSeriesPivotPointsHL200Response, GetTimeSeriesMinusDI200Response, \
    GetTimeSeriesAdxr200Response, GetETFsWorldRisk200Response, GetMutualFundsWorldRisk200Response, \
    GetMutualFundsWorldSustainability200Response, GetETFsWorldPerformance200Response, GetTimeSeriesMax200Response, \
    GetTimeSeriesWillR200Response, GetETFsList200Response, GetTimeSeriesHeikinashiCandles200Response, \
    GetMutualFundsWorldComposition200Response, GetTimeSeriesTema200Response, GetTimeSeriesPpo200Response


def serve(
    api_base: str,
    transport: Literal["stdio", "sse", "streamable-http"],
    apikey: str,
) -> None:
    logger = logging.getLogger(__name__)

    server = FastMCP(
        "mcp-twelve-data",
        host="0.0.0.0",
        port="8000",
    )

    P = TypeVar('P', bound=BaseModel)
    R = TypeVar('R', bound=BaseModel)

    async def _call_endpoint(
        endpoint: str,
        params: P,
        response_model: Type[R],
        ctx: Context
    ) -> R:
        if transport == 'stdio' and apikey:
            params.apikey = apikey
        elif transport == "streamable-http":
            apikey_header = ctx.request_context.request.headers.get('Authorization')
            split_header = apikey_header.split(' ')
            if len(split_header) == 2:
                params.apikey = apikey_header.split(' ')[1]

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{api_base}/{endpoint}",
                params=params.model_dump(exclude_none=True)
            )
            resp.raise_for_status()
            return response_model.model_validate(resp.json())

    @server.tool(name="GetTimeSeries", description="This API call returns meta and time series for the requested instrument. Metaobject consists of general information about the requested symbol. Time series is the array of objects ordered by time descending with Open, High, Low, Close prices. Non-currency instruments also include volume information.")
    async def GetTimeSeries(params: GetTimeSeriesRequest,  ctx: Context) -> GetTimeSeries200Response:
        return await _call_endpoint("time_series", params, GetTimeSeries200Response, ctx)

    @server.tool(name="GetPrice", description="This endpoint is a lightweight method that allows retrieving only the real-time price of the selected instrument.")
    async def GetPrice(params: GetPriceRequest,  ctx: Context) -> GetPrice200Response:
        return await _call_endpoint("price", params, GetPrice200Response, ctx)

    @server.tool(name="GetEod", description="This endpoint returns the latest End of Day (EOD) price of an instrument.")
    async def GetEod(params: GetEodRequest,  ctx: Context) -> GetEod200Response:
        return await _call_endpoint("eod", params, GetEod200Response, ctx)

    @server.tool(name="GetQuote", description="Quote endpoint is an efficient method to retrieve the latest quote of the selected instrument.")
    async def GetQuote(params: GetQuoteRequest,  ctx: Context) -> GetQuote200Response:
        return await _call_endpoint("quote", params, GetQuote200Response, ctx)

    @server.tool(name="GetMarketState", description="Check the state of all available exchanges, time to open, and time to close. Returns all available stock exchanges by default.")
    async def GetMarketState(params: GetMarketStateRequest,  ctx: Context) -> GetMarketState200Response:
        return await _call_endpoint("market_state", params, GetMarketState200Response, ctx)

    @server.tool(name="GetEarnings", description="This API call returns earnings data for a given company, including EPS estimate and EPS actual. Earnings are available for complete company history.")
    async def GetEarnings(params: GetEarningsRequest,  ctx: Context) -> GetEarnings200Response:
        return await _call_endpoint("earnings", params, GetEarnings200Response, ctx)

    @server.tool(name="GetTimeSeriesRsi", description="The Relative Strength Index (RSI) is a momentum oscillator that measures the speed and change of price movements, helping traders identify potential overbought or oversold conditions and trend reversals.")
    async def GetTimeSeriesRsi(params: GetTimeSeriesRsiRequest,  ctx: Context) -> GetTimeSeriesRsi200Response:
        return await _call_endpoint("rsi", params, GetTimeSeriesRsi200Response, ctx)

    @server.tool(name="GetStocks", description="This API call returns an array of symbols available at Twelve Data API. This list is updated daily.")
    async def GetStocks(params: GetStocksRequest,  ctx: Context) -> GetStocks200Response:
        return await _call_endpoint("stocks", params, GetStocks200Response, ctx)

    @server.tool(name="GetTimeSeriesMacd", description="The Moving Average Convergence Divergence (MACD) is a momentum indicator that measures the difference between two moving averages, with a signal line used to identify potential trend reversals and trading opportunities.")
    async def GetTimeSeriesMacd(params: GetTimeSeriesMacdRequest,  ctx: Context) -> GetTimeSeriesMacd200Response:
        return await _call_endpoint("macd", params, GetTimeSeriesMacd200Response, ctx)

    @server.tool(name="GetExchangeRate", description="This API call returns real-time exchange rate for currency pair. Works with forex and cryptocurrency.")
    async def GetExchangeRate(params: GetExchangeRateRequest,  ctx: Context) -> GetExchangeRate200Response:
        return await _call_endpoint("exchange_rate", params, GetExchangeRate200Response, ctx)

    @server.tool(name="GetProfile", description="Returns general information about the company.")
    async def GetProfile(params: GetProfileRequest,  ctx: Context) -> GetProfile200Response:
        return await _call_endpoint("profile", params, GetProfile200Response, ctx)

    @server.tool(name="GetStatistics",
                 description="Returns current overview of companys main statistics including valuation metrics and financials.")
    async def GetStatistics(params: GetStatisticsRequest,  ctx: Context) -> GetStatistics200Response:
        return await _call_endpoint("statistics", params, GetStatistics200Response, ctx)

    @server.tool(name="GetSymbolSearch", description="This method helps to find the best matching symbol. It can be used as the base for custom lookups. The response is returned in descending order, with the most relevant instrument at the beginning.")
    async def GetSymbolSearch(params: GetSymbolSearchRequest,  ctx: Context) -> GetSymbolSearch200Response:
        return await _call_endpoint("symbol_search", params, GetSymbolSearch200Response, ctx)

    @server.tool(name="GetTimeSeriesAvg", description="The Average (AVG) indicator calculates the arithmetic mean of a data series over a specified period, often used to smooth out data fluctuations.")
    async def GetTimeSeriesAvg(params: GetTimeSeriesAvgRequest,  ctx: Context) -> GetTimeSeriesAvg200Response:
        return await _call_endpoint("avg", params, GetTimeSeriesAvg200Response, ctx)

    @server.tool(name="GetTimeSeriesSma",
                 description="The Simple Moving Average (SMA) is a smoothing indicator that calculates the average price of a security over a specified period, helping traders identify trends and potential support or resistance levels.")
    async def GetTimeSeriesSma(params: GetTimeSeriesSmaRequest,  ctx: Context) -> GetTimeSeriesSma200Response:
        return await _call_endpoint("sma", params, GetTimeSeriesSma200Response, ctx)

    @server.tool(name="GetLogo", description="Returns a logo of company, cryptocurrency, or forex pair.")
    async def GetLogo(params: GetLogoRequest,  ctx: Context) -> GetLogo200Response:
        return await _call_endpoint("logo", params, GetLogo200Response, ctx)

    @server.tool(name="GetApiUsage", description="This endpoint will provide information on the current usage of Twelve Data API.")
    async def GetApiUsage(params: GetApiUsageRequest,  ctx: Context) -> GetApiUsage200Response:
        return await _call_endpoint("api_usage", params, GetApiUsage200Response, ctx)

    @server.tool(name="GetTimeSeriesEma", description="The Exponential Moving Average (EMA) is a weighted moving average that gives more importance to recent price data, making it more responsive to new information and helping traders identify trends and potential entry or exit points.")
    async def GetTimeSeriesEma(params: GetTimeSeriesEmaRequest,  ctx: Context) -> GetTimeSeriesEma200Response:
        return await _call_endpoint("ema", params, GetTimeSeriesEma200Response, ctx)

    @server.tool(name="GetExchangeSchedule", description="This API call return exchanges details and trading hours.")
    async def GetExchangeSchedule(params: GetExchangeScheduleRequest,  ctx: Context) -> GetExchangeSchedule200Response:
        return await _call_endpoint("exchange_schedule", params, GetExchangeSchedule200Response, ctx)

    @server.tool(name="GetTimeSeriesAtr", description="The Average True Range (ATR) is a volatility indicator that measures the average range of price movement over a specified period, helping traders assess market volatility.")
    async def GetTimeSeriesAtr(params: GetTimeSeriesAtrRequest,  ctx: Context) -> GetTimeSeriesAtr200Response:
        return await _call_endpoint("atr", params, GetTimeSeriesAtr200Response, ctx)

    @server.tool(name="GetMutualFundsWorldSummary", description="This API request returns a brief summary of a mutual fund.")
    async def GetMutualFundsWorldSummary(params: GetMutualFundsWorldSummaryRequest,  ctx: Context) -> GetMutualFundsWorldSummary200Response:
        return await _call_endpoint("mutual_funds/world/summary", params, GetMutualFundsWorldSummary200Response, ctx)

    @server.tool(name="GetMutualFundsWorld", description="This API request returns a complete breakdown of a mutual fund, including summary, performance, risk, ratings, composition, purchase_info, and sustainability.")
    async def GetMutualFundsWorld(params: GetMutualFundsWorldRequest,  ctx: Context) -> GetMutualFundsWorld200Response:
        return await _call_endpoint("mutual_funds/world", params, GetMutualFundsWorld200Response, ctx)

    @server.tool(name="GetTimeSeriesVwap", description="The Volume Weighted Average Price (VWAP) indicator offers an insightful measure of the average trading price weighted by volume, commonly used for trading analysis and execution evaluation.")
    async def GetTimeSeriesVwap(params: GetTimeSeriesVwapRequest,  ctx: Context) -> GetTimeSeriesVwap200Response:
        return await _call_endpoint("vwap", params, GetTimeSeriesVwap200Response, ctx)

    @server.tool(name="GetTimeSeriesCrsi", description="The Connors RSI is a composite indicator combining the Relative Strength Index (RSI), the Rate of Change (ROC), and the Up/Down Length, providing a more comprehensive view of momentum and potential trend reversals.")
    async def GetTimeSeriesCrsi(params: GetTimeSeriesCrsiRequest,  ctx: Context) -> GetTimeSeriesCrsi200Response:
        return await _call_endpoint("crsi", params, GetTimeSeriesCrsi200Response, ctx)

    @server.tool(name="GetEarliestTimestamp", description="This method returns the first available DateTime for a given instrument at the specific interval.")
    async def GetEarliestTimestamp(params: GetEarliestTimestampRequest,  ctx: Context) -> GetEarliestTimestamp200Response:
        return await _call_endpoint("earliest_timestamp", params, GetEarliestTimestamp200Response, ctx)

    @server.tool(name="GetPriceTarget", description="This API endpoint returns the analysts' projection of a security's future price.")
    async def GetPriceTarget(params: GetPriceTargetRequest,  ctx: Context) -> GetPriceTarget200Response:
        return await _call_endpoint("price_target", params, GetPriceTarget200Response, ctx)

    @server.tool(name="GetIncomeStatement", description="Returns complete income statement of a company and shows the companys revenues and expenses during a period (annual or quarter).")
    async def GetIncomeStatement(params: GetIncomeStatementRequest,  ctx: Context) -> GetIncomeStatement200Response:
        return await _call_endpoint("income_statement", params, GetIncomeStatement200Response, ctx)

    @server.tool(name="GetDividends", description="Returns the amount of dividends paid out for the last 10+ years.")
    async def GetDividends(params: GetDividendsRequest,  ctx: Context) -> GetDividends200Response:
        return await _call_endpoint("dividends", params, GetDividends200Response, ctx)

    @server.tool(name="GetCashFlow", description="Returns complete cash flow of a company showing the net amount of cash and cash equivalents being transferred into and out of business.")
    async def GetCashFlow(params: GetCashFlowRequest,  ctx: Context) -> GetCashFlow200Response:
        return await _call_endpoint("cash_flow", params, GetCashFlow200Response, ctx)

    @server.tool(name="GetBalanceSheet", description="Returns complete balance sheet of a company showing the summary of assets, liabilities, and shareholders equity.")
    async def GetBalanceSheet(params: GetBalanceSheetRequest,  ctx: Context) -> GetBalanceSheet200Response:
        return await _call_endpoint("balance_sheet", params, GetBalanceSheet200Response, ctx)

    @server.tool(name="GetTimeSeriesBBands", description="Bollinger Bands (BBANDS) are volatility bands placed above and below a moving average, measuring price volatility and helping traders identify potential overbought or oversold conditions.")
    async def GetTimeSeriesBBands(params: GetTimeSeriesBBandsRequest,  ctx: Context) -> GetTimeSeriesBBands200Response:
        return await _call_endpoint("bbands", params, GetTimeSeriesBBands200Response, ctx)

    @server.tool(name="GetRecommendations", description="This API endpoint returns the average of all analyst recommendations and classifies them as Strong Buy, Buy, Hold, or Sell. Also, it returns a recommendation score.")
    async def GetRecommendations(params: GetRecommendationsRequest,  ctx: Context) -> GetRecommendations200Response:
        return await _call_endpoint("recommendations", params, GetRecommendations200Response, ctx)

    @server.tool(name="GetCurrencyConversion", description="This API call returns real-time exchange rate and converted amount for currency pair. Works with forex and cryptocurrency.")
    async def GetCurrencyConversion(params: GetCurrencyConversionRequest,  ctx: Context) -> GetCurrencyConversion200Response:
        return await _call_endpoint("currency_conversion", params, GetCurrencyConversion200Response, ctx)

    @server.tool(name="GetEtf", description="This API call returns an array of ETFs available at Twelve Data API. This list is updated daily.")
    async def GetEtf(params: GetEtfRequest,  ctx: Context) -> GetEtf200Response:
        return await _call_endpoint("etfs", params, GetEtf200Response, ctx)

    @server.tool(name="GetSplits", description="Returns the date and the split factor of shares of the company for the last 10+ years.")
    async def GetSplits(params: GetSplitsRequest,  ctx: Context) -> GetSplits200Response:
        return await _call_endpoint("splits", params, GetSplits200Response, ctx)

    @server.tool(name="GetEarningsEstimate", description="This API endpoint returns analysts' estimate for a company's future quarterly and annual earnings per share (EPS).")
    async def GetEarningsEstimate(params: GetEarningsEstimateRequest,  ctx: Context) -> GetEarningsEstimate200Response:
        return await _call_endpoint("earnings_estimate", params, GetEarningsEstimate200Response, ctx)

    @server.tool(name="GetTimeSeriesStoch", description="The Stochastic Oscillator (STOCH) is a momentum indicator that compares a security's closing price to its price range over a specified period, helping traders identify potential overbought or oversold conditions and trend reversals.")
    async def GetTimeSeriesStoch(params: GetTimeSeriesStochRequest,  ctx: Context) -> GetTimeSeriesStoch200Response:
        return await _call_endpoint("stoch", params, GetTimeSeriesStoch200Response, ctx)

    @server.tool(name="GetRevenueEstimate", description="This API endpoint returns analysts' estimate for a company's future quarterly and annual sales (total revenue).")
    async def GetRevenueEstimate(params: GetRevenueEstimateRequest,  ctx: Context) -> GetRevenueEstimate200Response:
        return await _call_endpoint("revenue_estimate", params, GetRevenueEstimate200Response, ctx)

    @server.tool(name="GetAnalystRatingsUsEquities", description="This API endpoint returns complete information on ratings issued by analyst firms. Works only for US equities.")
    async def GetAnalystRatingsUsEquities(params: GetAnalystRatingsUsEquitiesRequest,  ctx: Context) -> GetAnalystRatingsUsEquities200Response:
        return await _call_endpoint("analyst_ratings/us_equities", params, GetAnalystRatingsUsEquities200Response, ctx)

    @server.tool(name="GetInsiderTransactions", description="Returns trading information performed by insiders.")
    async def GetInsiderTransactions(params: GetInsiderTransactionsRequest,  ctx: Context) -> GetInsiderTransactions200Response:
        return await _call_endpoint("insider_transactions", params, GetInsiderTransactions200Response, ctx)

    @server.tool(name="GetGrowthEstimates", description="This API endpoint returns consensus analyst estimates over the company's growth rates for various periods. Calculation averages projections of numerous analysts, taking arbitrary parameters, such as earnings per share, revenue, etc.")
    async def GetGrowthEstimates(params: GetGrowthEstimatesRequest,  ctx: Context) -> GetGrowthEstimates200Response:
        return await _call_endpoint("growth_estimates", params, GetGrowthEstimates200Response, ctx)

    @server.tool(name="GetInstitutionalHolders", description="Returns the amount of the companys available stock owned by institutions (pension funds, insurance companies, investment firms, private foundations, endowments, or other large entities that manage funds on behalf of others).")
    async def GetInstitutionalHolders(params: GetInstitutionalHoldersRequest,  ctx: Context) -> GetInstitutionalHolders200Response:
        return await _call_endpoint("institutional_holders", params, GetInstitutionalHolders200Response, ctx)

    @server.tool(name="GetTimeSeriesSar", description="The Parabolic SAR (SAR) is a trend-following indicator that calculates potential support and resistance levels based on a security's price and time, helping traders identify potential entry and exit points.")
    async def GetTimeSeriesSar(params: GetTimeSeriesSarRequest,  ctx: Context) -> GetTimeSeriesSar200Response:
        return await _call_endpoint("sar", params, GetTimeSeriesSar200Response, ctx)

    @server.tool(name="GetTimeSeriesHtTrendline", description="The Hilbert Transform Instantaneous Trendline (HT_TRENDLINE) is a smoothed moving average that follows the dominant market cycle, helping traders identify trends and potential entry or exit points.\n\nYou can read more about it in the Rocket Science for Traders book by John F. Ehlers.")
    async def GetTimeSeriesHtTrendline(params: GetTimeSeriesHtTrendlineRequest,  ctx: Context) -> GetTimeSeriesHtTrendline200Response:
        return await _call_endpoint("ht_trendline", params, GetTimeSeriesHtTrendline200Response, ctx)

    @server.tool(name="GetEpsRevisions", description="This API endpoint returns analysts revisions of a company's future quarterly and annual earnings per share (EPS) over the last week and month.")
    async def GetEpsRevisions(params: GetEpsRevisionsRequest,  ctx: Context) -> GetEpsRevisions200Response:
        return await _call_endpoint("eps_revisions", params, GetEpsRevisions200Response, ctx)

    @server.tool(name="GetEpsTrend", description="This API endpoint returns a breakdown of the estimated historical EPS changes at a given period.")
    async def GetEpsTrend(params: GetEpsTrendRequest,  ctx: Context) -> GetEpsTrend200Response:
        return await _call_endpoint("eps_trend", params, GetEpsTrend200Response, ctx)

    @server.tool(name="GetKeyExecutives", description="Returns key executive information for a specified symbol.")
    async def GetKeyExecutives(params: GetKeyExecutivesRequest,  ctx: Context) -> GetKeyExecutives200Response:
        return await _call_endpoint("key_executives", params, GetKeyExecutives200Response, ctx)

    @server.tool(name="GetAnalystRatingsLight", description="This API endpoint returns a lightweight version of ratings issued by analyst firms. Works for US and international markets.")
    async def GetAnalystRatingsLight(params: GetAnalystRatingsLightRequest,  ctx: Context) -> GetAnalystRatingsLight200Response:
        return await _call_endpoint("analyst_ratings/light", params, GetAnalystRatingsLight200Response, ctx)

    @server.tool(name="GetTimeSeriesWma", description="The Weighted Moving Average (WMA) is a smoothing indicator that calculates the average price of a security over a specified period, with more weight given to recent prices, providing a more responsive view of price action.")
    async def GetTimeSeriesWma(params: GetTimeSeriesWmaRequest,  ctx: Context) -> GetTimeSeriesWma200Response:
        return await _call_endpoint("wma", params, GetTimeSeriesWma200Response, ctx)

    @server.tool(name="GetTechnicalIndicators", description="This API call returns an array of objects with available technical indicators. This endpoint might be used to build an abstract interface to make more convenient API calls from the application.")
    async def GetTechnicalIndicators(params: GetTechnicalIndicatorsRequest,  ctx: Context) -> GetTechnicalIndicators200Response:
        return await _call_endpoint("technical_indicators", params, GetTechnicalIndicators200Response, ctx)

    @server.tool(name="GetCrossListings", description="This API call returns an array of cross listed symbols for a specified instrument. Cross listings are the same securities listed on different exchanges.")
    async def GetCrossListings(params: GetCrossListingsRequest,  ctx: Context) -> GetCrossListings200Response:
        return await _call_endpoint("cross_listings", params, GetCrossListings200Response, ctx)

    @server.tool(name="GetTimeSeriesCci", description="The Commodity Channel Index (CCI) is a momentum oscillator that measures the deviation of a security's price from its average relative to its typical price range, helping traders identify overbought or oversold conditions.")
    async def GetTimeSeriesCci(params: GetTimeSeriesCciRequest,  ctx: Context) -> GetTimeSeriesCci200Response:
        return await _call_endpoint("cci", params, GetTimeSeriesCci200Response, ctx)

    @server.tool(name="GetTimeSeriesAdx", description="The Average Directional Index (ADX) measures the strength of a trend, regardless of direction, helping traders determine if a market is trending or ranging.")
    async def GetTimeSeriesAdx(params: GetTimeSeriesAdxRequest,  ctx: Context) -> GetTimeSeriesAdx200Response:
        return await _call_endpoint("adx", params, GetTimeSeriesAdx200Response, ctx)

    @server.tool(name="GetFundHolders", description="Returns the amount of the companys available stock owned by mutual fund holders.")
    async def GetFundHolders(params: GetFundHoldersRequest,  ctx: Context) -> GetFundHolders200Response:
        return await _call_endpoint("fund_holders", params, GetFundHolders200Response, ctx)

    @server.tool(name="GetTimeSeriesObv", description="The On Balance Volume (OBV) indicator is a cumulative volume-based tool used to measure buying and selling pressure, helping traders identify potential price trends and reversals.")
    async def GetTimeSeriesObv(params: GetTimeSeriesObvRequest,  ctx: Context) -> GetTimeSeriesObv200Response:
        return await _call_endpoint("obv", params, GetTimeSeriesObv200Response, ctx)

    @server.tool(name="GetTimeSeriesMa", description="The Moving Average (MA) is a smoothing indicator that calculates the average price of a security over a specified period, helping traders identify trends and potential support or resistance levels.")
    async def GetTimeSeriesMa(params: GetTimeSeriesMaRequest,  ctx: Context) -> GetTimeSeriesMa200Response:
        return await _call_endpoint("ma", params, GetTimeSeriesMa200Response, ctx)

    @server.tool(name="GetTimeSeriesPercent_B", description="The Percent B (%B) is a component of the Bollinger Bands indicator, measuring the position of a security's price relative to the bands, helping traders identify potential overbought or oversold conditions.")
    async def GetTimeSeriesPercent_B(params: GetTimeSeriesPercent_BRequest,  ctx: Context) -> GetTimeSeriesPercent_B200Response:
        return await _call_endpoint("percent_b", params, GetTimeSeriesPercent_B200Response, ctx)

    @server.tool(name="GetExchanges", description="This API call returns an array of stock or ETF exchanges available at Twelve Data API. This list is updated daily.")
    async def GetExchanges(params: GetExchangesRequest,  ctx: Context) -> GetExchanges200Response:
        return await _call_endpoint("exchanges", params, GetExchanges200Response, ctx)

    @server.tool(name="GetIncomeStatementConsolidated", description="Returns consolidated income statement of a company and expenses during a period (annual or quarter).")
    async def GetIncomeStatementConsolidated(params: GetIncomeStatementConsolidatedRequest,  ctx: Context) -> GetIncomeStatementConsolidated200Response:
        return await _call_endpoint("income_statement/consolidated", params, GetIncomeStatementConsolidated200Response, ctx)

    @server.tool(name="GetDividendsCalendar", description="This API method returns dividend data as a calendar for a given date range. To call custom period, use start_date and end_date parameters.")
    async def GetDividendsCalendar(params: GetDividendsCalendarRequest,  ctx: Context) -> GetDividendsCalendar200Response:
        return await _call_endpoint("dividends_calendar", params, GetDividendsCalendar200Response, ctx)

    @server.tool(name="GetTimeSeriesSuperTrend", description="The Supertrend indicator is a trend-following tool that uses a combination of price, time, and volatility to generate potential entry and exit points in trending markets.")
    async def GetTimeSeriesSuperTrend(params: GetTimeSeriesSuperTrendRequest,  ctx: Context) -> GetTimeSeriesSuperTrend200Response:
        return await _call_endpoint("supertrend", params, GetTimeSeriesSuperTrend200Response, ctx)

    @server.tool(name="GetETFsWorld", description="This API request returns a complete breakdown of a etf, including summary, performance, risk and composition.")
    async def GetETFsWorld(params: GetETFsWorldRequest,  ctx: Context) -> GetETFsWorld200Response:
        return await _call_endpoint("etfs/world", params, GetETFsWorld200Response, ctx)

    @server.tool(name="GetTimeSeriesIchimoku", description="The Ichimoku Cloud (ICHIMOKU) is a comprehensive trend-following indicator that combines multiple moving averages and support/resistance levels to help traders identify potential entry and exit points, trend direction, and momentum.")
    async def GetTimeSeriesIchimoku(params: GetTimeSeriesIchimokuRequest,  ctx: Context) -> GetTimeSeriesIchimoku200Response:
        return await _call_endpoint("ichimoku", params, GetTimeSeriesIchimoku200Response, ctx)

    @server.tool(name="GetTimeSeriesRvol", description="The Relative Volume (RVOL) is a ratio that compares a security's current trading volume to its average trading volume over a specified period. By measuring volume activity relative to its historical norm, RVOL helps traders identify unusual market activity, potential breakouts, and the strength of price movements.")
    async def GetTimeSeriesRvol(params: GetTimeSeriesRvolRequest,  ctx: Context) -> GetTimeSeriesRvol200Response:
        return await _call_endpoint("rvol", params, GetTimeSeriesRvol200Response, ctx)

    @server.tool(name="GetMutualFundsList", description="This API request returns a list of mutual funds available at Twelve Data. Sorting is in descending order by total assets value. The list is updated daily.")
    async def GetMutualFundsList(params: GetMutualFundsListRequest,  ctx: Context) -> GetMutualFundsList200Response:
        return await _call_endpoint("mutual_funds/list", params, GetMutualFundsList200Response, ctx)

    @server.tool(name="GetDirectHolders", description="Returns the amount of the stocks owned directly and recorded in the company's share registry.")
    async def GetDirectHolders(params: GetDirectHoldersRequest,  ctx: Context) -> GetDirectHolders200Response:
        return await _call_endpoint("direct_holders", params, GetDirectHolders200Response, ctx)

    @server.tool(name="GetTimeSeriesMfi", description="The Money Flow Index (MFI) is a volume-weighted momentum oscillator that measures buying and selling pressure by comparing positive and negative money flow, helping traders identify overbought or oversold conditions.")
    async def GetTimeSeriesMfi(params: GetTimeSeriesMfiRequest,  ctx: Context) -> GetTimeSeriesMfi200Response:
        return await _call_endpoint("mfi", params, GetTimeSeriesMfi200Response, ctx)

    @server.tool(name="GetMarketMovers", description="Get the list of the top gaining or losing stocks today.\n\nTop gainers are ordered by the highest rate of price increase since the previous day''s close. Top losers are ordered by the highest percentage of price decrease since the last day.\n\nData is available for all international equities, forex, crypto.")
    async def GetMarketMovers(params: GetMarketMoversRequest,  ctx: Context) -> GetMarketMovers200Response:
        return await _call_endpoint("market_movers/{market}", params, GetMarketMovers200Response, ctx)

    @server.tool(name="GetTimeSeriesDema", description="The Double Exponential Moving Average (DEMA) is a more responsive moving average that reduces lag by giving more weight to recent price data, helping traders identify trends and potential entry or exit points.")
    async def GetTimeSeriesDema(params: GetTimeSeriesDemaRequest,  ctx: Context) -> GetTimeSeriesDema200Response:
        return await _call_endpoint("dema", params, GetTimeSeriesDema200Response, ctx)

    @server.tool(name="GetForexPairs", description="This API call returns an array of forex pairs available at Twelve Data API. This list is updated daily.")
    async def GetForexPairs(params: GetForexPairsRequest,  ctx: Context) -> GetForexPairs200Response:
        return await _call_endpoint("forex_pairs", params, GetForexPairs200Response, ctx)

    @server.tool(name="GetTimeSeriesPlusDI",
                 description="The Plus Directional Indicator (PLUS_DI) is a component of the ADX indicator, measuring the strength of a security's upward price movement.")
    async def GetTimeSeriesPlusDI(params: GetTimeSeriesPlusDIRequest,  ctx: Context) -> GetTimeSeriesPlusDI200Response:
        return await _call_endpoint("plus_di", params, GetTimeSeriesPlusDI200Response, ctx)

    @server.tool(name="GetTimeSeriesKeltner", description="The Keltner Channel (KELTNER) is a volatility-based indicator that uses a combination of EMA and the ATR to create a channel around a security's price. The channel helps traders identify potential overbought or oversold conditions, as well as trend direction and potential price breakouts.")
    async def GetTimeSeriesKeltner(params: GetTimeSeriesKeltnerRequest,  ctx: Context) -> GetTimeSeriesKeltner200Response:
        return await _call_endpoint("keltner", params, GetTimeSeriesKeltner200Response, ctx)

    @server.tool(name="GetTimeSeriesHtTrendMode", description="The Hilbert Transform Trend vs Cycle Mode (HT_TRENDMODE) distinguishes between trending and cyclical market phases, helping traders adapt their strategies accordingly.\n\nYou can read more about it in the Rocket Science for Traders book by John F. Ehlers.")
    async def GetTimeSeriesHtTrendMode(params: GetTimeSeriesHtTrendModeRequest,  ctx: Context) -> GetTimeSeriesHtTrendMode200Response:
        return await _call_endpoint("ht_trendmode", params, GetTimeSeriesHtTrendMode200Response, ctx)

    @server.tool(name="GetMutualFundsWorldPerformance", description="This API request returns detailed performance of a mutual fund, including trailing, annual, quarterly, and load-adjusted returns.")
    async def GetMutualFundsWorldPerformance(params: GetMutualFundsWorldPerformanceRequest,  ctx: Context) -> GetMutualFundsWorldPerformance200Response:
        return await _call_endpoint("mutual_funds/world/performance", params, GetMutualFundsWorldPerformance200Response, ctx)

    @server.tool(name="GetETFsWorldComposition", description="This API request returns portfolio composition of a etf, including sectors, holding details, weighted exposure, and others.")
    async def GetETFsWorldComposition(params: GetETFsWorldCompositionRequest,  ctx: Context) -> GetETFsWorldComposition200Response:
        return await _call_endpoint("etfs/world/composition", params, GetETFsWorldComposition200Response, ctx)

    @server.tool(name="GetMutualFundsWorldPurchaseInfo", description="This API request returns essential information on purchasing a mutual fund, including minimums, pricing, and available brokerages.")
    async def GetMutualFundsWorldPurchaseInfo(params: GetMutualFundsWorldPurchaseInfoRequest,  ctx: Context) -> GetMutualFundsWorldPurchaseInfo200Response:
        return await _call_endpoint("mutual_funds/world/purchase_info", params, GetMutualFundsWorldPurchaseInfo200Response, ctx)

    @server.tool(name="GetTimeSeriesPivotPointsHL", description="The Pivot Points High Low (PIVOT_POINTS_HL) indicator calculates support and resistance levels based on the highest high and lowest low of a security's price over a specified period, providing potential entry and exit points.")
    async def GetTimeSeriesPivotPointsHL(params: GetTimeSeriesPivotPointsHLRequest,  ctx: Context) -> GetTimeSeriesPivotPointsHL200Response:
        return await _call_endpoint("pivot_points_hl", params, GetTimeSeriesPivotPointsHL200Response, ctx)

    @server.tool(name="GetTimeSeriesMinusDI", description="The Minus Directional Indicator (MINUS_DI) is a component of the ADX indicator, measuring the strength of a security's downward price movement.")
    async def GetTimeSeriesMinusDI(params: GetTimeSeriesMinusDIRequest,  ctx: Context) -> GetTimeSeriesMinusDI200Response:
        return await _call_endpoint("minus_di", params, GetTimeSeriesMinusDI200Response, ctx)

    @server.tool(name="GetMutualFundsWorldComposition", description="This API request returns portfolio composition of a mutual fund, including sectors, holding details, weighted exposure, and others.")
    async def GetMutualFundsWorldComposition(params: GetMutualFundsWorldCompositionRequest,  ctx: Context) -> GetMutualFundsWorldComposition200Response:
        return await _call_endpoint("mutual_funds/world/composition", params, GetMutualFundsWorldComposition200Response, ctx)

    @server.tool(name="GetTimeSeriesAdxr", description="The Average Directional Movement Index Rating (ADXR) is a smoothed version of ADX, providing a more stable measure of trend strength over time.")
    async def GetTimeSeriesAdxr(params: GetTimeSeriesAdxrRequest,  ctx: Context) -> GetTimeSeriesAdxr200Response:
        return await _call_endpoint("adxr", params, GetTimeSeriesAdxr200Response, ctx)

    @server.tool(name="GetETFsWorldRisk", description="This API request returns core metrics to measure the risk of investing in a etf.")
    async def GetETFsWorldRisk(params: GetETFsWorldRiskRequest,  ctx: Context) -> GetETFsWorldRisk200Response:
        return await _call_endpoint("etfs/world/risk", params, GetETFsWorldRisk200Response, ctx)

    @server.tool(name="GetMutualFundsWorldRisk", description="This API request returns core metrics to measure the risk of investing in a mutual fund.")
    async def GetMutualFundsWorldRisk(params: GetMutualFundsWorldRiskRequest,  ctx: Context) -> GetMutualFundsWorldRisk200Response:
        return await _call_endpoint("mutual_funds/world/risk", params, GetMutualFundsWorldRisk200Response, ctx)

    @server.tool(name="GetMutualFundsWorldSustainability", description="This API request returns brief information on mutual fund sustainability and ESG.")
    async def GetMutualFundsWorldSustainability(params: GetMutualFundsWorldSustainabilityRequest,  ctx: Context) -> GetMutualFundsWorldSustainability200Response:
        return await _call_endpoint("mutual_funds/world/sustainability", params, GetMutualFundsWorldSustainability200Response, ctx)

    @server.tool(name="GetETFsWorldPerformance", description="This API request returns detailed performance of a etf, including trailing and annual returns.")
    async def GetETFsWorldPerformance(params: GetETFsWorldPerformanceRequest,  ctx: Context) -> GetETFsWorldPerformance200Response:
        return await _call_endpoint("etfs/world/performance", params, GetETFsWorldPerformance200Response, ctx)

    @server.tool(name="GetTimeSeriesMax", description="The Maximum (MAX) indicator calculates the highest value of a data series over a specified period, often used to identify potential resistance levels or extreme price movements.")
    async def GetTimeSeriesMax(params: GetTimeSeriesMaxRequest,  ctx: Context) -> GetTimeSeriesMax200Response:
        return await _call_endpoint("max", params, GetTimeSeriesMax200Response, ctx)

    @server.tool(name="GetTimeSeriesWillR", description="The Williams %R (WILLR) is a momentum oscillator that measures the level of a security's closing price in relation to the high and low range over a specified period, helping traders identify potential overbought or oversold conditions and trend reversals.")
    async def GetTimeSeriesWillR(params: GetTimeSeriesWillRRequest,  ctx: Context) -> GetTimeSeriesWillR200Response:
        return await _call_endpoint("willr", params, GetTimeSeriesWillR200Response, ctx)

    @server.tool(name="GetETFsList", description="This API request returns a list of exchange traded funds available at Twelve Data. Sorting is in descending order by total assets value. The list is updated daily.")
    async def GetETFsList(params: GetETFsListRequest,  ctx: Context) -> GetETFsList200Response:
        return await _call_endpoint("etfs/list", params, GetETFsList200Response, ctx)

    @server.tool(name="GetTimeSeriesHeikinashiCandles", description="Heikin Ashi Candles are a modified form of Japanese candlestick charts, using averaged price data to smooth out noise and better highlight trends and potential trend reversals.")
    async def GetTimeSeriesHeikinashiCandles(params: GetTimeSeriesHeikinashiCandlesRequest,  ctx: Context) -> GetTimeSeriesHeikinashiCandles200Response:
        return await _call_endpoint("heikinashicandles", params, GetTimeSeriesHeikinashiCandles200Response, ctx)

    @server.tool(name="GetTimeSeriesTema", description="The Triple Exponential Moving Average (TEMA) is a smoothing indicator that applies three exponential moving averages to price data, reducing lag and providing a more accurate representation of trends.")
    async def GetTimeSeriesTema(params: GetTimeSeriesTemaRequest,  ctx: Context) -> GetTimeSeriesTema200Response:
        return await _call_endpoint("tema", params, GetTimeSeriesTema200Response, ctx)

    @server.tool(name="GetTimeSeriesPpo", description="The Percentage Price Oscillator (PPO) is a momentum oscillator that measures the percentage difference between two moving averages, helping traders identify potential trend reversals and trading opportunities.")
    async def GetTimeSeriesPpo(params: GetTimeSeriesPpoRequest,  ctx: Context) -> GetTimeSeriesPpo200Response:
        return await _call_endpoint("ppo", params, GetTimeSeriesPpo200Response, ctx)


    server.run(transport=transport)
