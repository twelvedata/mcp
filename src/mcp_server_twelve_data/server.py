import logging
from typing import Literal, TypeVar, Type

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from .requests.get_cryptocurrencies_params import GetCryptocurrenciesParams
from .requests.get_forex_pairs_params import GetForexPairsParams
from .requests.get_price_params import GetPriceParams
from .requests.get_stocks_params import GetStocksParams
from .requests.get_time_series_params import GetTimeSeriesParams
from .responses.get_cryptocurrencies_response import GetCryptocurrenciesResponse
from .responses.get_forex_pairs_response import GetForexPairsResponse
from .responses.get_price_response import GetPriceResponse
from .responses.get_stock_response import GetStocksResponse
from .responses.get_time_series_response import GetTimeSeriesResponse


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

    # @server.tool()
    # def add(a: int, b: int) -> int:
    #    """Add two numbers"""
    #    return a + b

    P = TypeVar('P', bound=BaseModel)
    R = TypeVar('R', bound=BaseModel)

    async def _call_endpoint(
        endpoint: str,
        params: P,
        response_model: Type[R]
    ) -> R:
        # override apikey unless it's blank
        if apikey:
            params.apikey = apikey

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{api_base}/{endpoint}",
                params=params.model_dump(exclude_none=True)
            )
            resp.raise_for_status()
            return response_model.model_validate(resp.json())

    @server.tool(name="GetTimeSeries", description="Time series tool calling /time_series endpoint")
    async def get_time_series(params: GetTimeSeriesParams) -> GetTimeSeriesResponse:
        return await _call_endpoint("time_series", params, GetTimeSeriesResponse)

    @server.tool(name="GetPrice", description="Real-time price tool calling /price endpoint")
    async def get_price(params: GetPriceParams) -> GetPriceResponse:
        return await _call_endpoint("price", params, GetPriceResponse)

    @server.tool(name="GetStocks", description="Stocks list tool calling /stocks endpoint")
    async def get_stocks(params: GetStocksParams) -> GetStocksResponse:
        return await _call_endpoint("stocks", params, GetStocksResponse)

    @server.tool(name="GetForexPairs", description="Forex pairs list tool calling /forex_pairs endpoint")
    async def get_forex_pairs(params: GetForexPairsParams) -> GetForexPairsResponse:
        return await _call_endpoint("forex_pairs", params, GetForexPairsResponse)

    @server.tool(
        name="GetCryptocurrencies",
        description="Cryptocurrencies list tool calling /cryptocurrencies endpoint"
    )
    async def get_cryptocurrencies(params: GetCryptocurrenciesParams) -> GetCryptocurrenciesResponse:
        return await _call_endpoint("cryptocurrencies", params, GetCryptocurrenciesResponse)

    server.run(transport=transport)

