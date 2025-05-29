from pydantic import BaseModel, Field


class ForexResponseItem(BaseModel):
    symbol: str = Field(
        ...,
        description="Currency pair symbol",
        examples=["EUR/USD"],
    )
    currency_group: str = Field(
        ...,
        description="Currency group",
        examples=["Forex"],
    )
    currency_base: str = Field(
        ...,
        description="Base currency",
        examples=["EUR"],
    )
    currency_quote: str = Field(
        ...,
        description="Quote currency",
        examples=["USD"],
    )
