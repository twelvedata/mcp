from typing import Optional
from pydantic import BaseModel, Field


class GetForexPairsParams(BaseModel):
    apikey: str = Field(
        ...,
        description="Your API key",
        examples=["demo"],
    )
    symbol: Optional[str] = Field(
        None,
        description="Filter by currency pair symbol",
        examples=["EUR/USD"],
    )
    currency_base: Optional[str] = Field(
        None,
        description="Base currency of pair",
        examples=["EUR"],
    )
    currency_quote: Optional[str] = Field(
        None,
        description="Quote currency of pair",
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
