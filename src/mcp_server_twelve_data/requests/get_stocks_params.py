from typing import Optional
from pydantic import BaseModel, Field


class GetStocksParams(BaseModel):
    apikey: str = Field(
        ...,
        description="Your API key",
        examples=["demo"],
    )
    symbol: Optional[str] = Field(
        None,
        description="Filter by ticker symbol",
        examples=["AAPL"],
    )
    figi: Optional[str] = Field(
        None,
        description="Financial Instrument Global Identifier",
        examples=["BBG000B9XRY4"],
    )
    isin: Optional[str] = Field(
        None,
        description="International Securities Identification Number",
        examples=["US0378331005"],
    )
    cusip: Optional[str] = Field(
        None,
        description="CUSIP number",
        examples=["037833100"],
    )
    exchange: Optional[str] = Field(
        None,
        description="Filter by exchange",
        examples=["NASDAQ"],
    )
    mic_code: Optional[str] = Field(
        None,
        description="Market Identifier Code",
        examples=["XNAS"],
    )
    country: Optional[str] = Field(
        None,
        description="Country code",
        examples=["US"],
    )
    type: Optional[str] = Field(
        None,
        description="Instrument type",
        examples=["Common Stock"],
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
    show_plan: Optional[bool] = Field(
        None,
        description="Include subscription plan details",
        examples=[True],
    )
    include_delisted: Optional[bool] = Field(
        None,
        description="Include delisted instruments",
        examples=[False],
    )
