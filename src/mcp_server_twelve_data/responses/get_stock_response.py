from typing import List
from pydantic import BaseModel, Field

from .stock_response_item import StocksResponseItem


class GetStocksResponse(BaseModel):
    data: List[StocksResponseItem] = Field(
        ...,
        description="List of stocks metadata",
    )