from typing import Optional
from pydantic import BaseModel, Field


class GetCryptocurrenciesParams(BaseModel):
    apikey: str = Field(
        ...,
        description="Your API key",
        examples=["demo"],
    )
    symbol: Optional[str] = Field(
        None,
        description="Filter by cryptocurrency symbol",
        examples=["BTC/USD"],
    )
    exchange: Optional[str] = Field(
        None,
        description="Filter by exchange",
        examples=["Binance"],
    )
    currency_base: Optional[str] = Field(
        None,
        description="Base currency",
        examples=["BTC"],
    )
    currency_quote: Optional[str] = Field(
        None,
        description="Quote currency",
        examples=["USD"],
    )
    format: Optional[str] = Field(
        None,
        description="Output format",
        examples=["JSON"],
    )
    delimiter: Optional[str] = Field(
        None,
        description="CSV delimiter",
        examples=[","],
    )
