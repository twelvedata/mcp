from typing import List
from pydantic import BaseModel, Field

from .cryptocurrency_response_item import CryptocurrencyResponseItem


class GetCryptocurrenciesResponse(BaseModel):
    data: List[CryptocurrencyResponseItem] = Field(
        ...,
        description="List of cryptocurrencies data",
    )