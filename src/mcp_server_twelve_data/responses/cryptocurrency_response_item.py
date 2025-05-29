from typing import List
from pydantic import BaseModel, Field


class CryptocurrencyResponseItem(BaseModel):
    symbol: str = Field(
        ...,
        description="Cryptocurrency symbol",
        examples=["BTC/USD"],
    )
    available_exchanges: List[str] = Field(
        ...,
        description="Exchanges where the cryptocurrency is traded",
        examples=[["Binance", "Coinbase"]],
    )
    currency_base: str = Field(
        ...,
        description="Base currency",
        examples=["BTC"],
    )
    currency_quote: str = Field(
        ...,
        description="Quote currency",
        examples=["USD"],
    )