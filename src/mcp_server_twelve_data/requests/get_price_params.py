from typing import Optional
from pydantic import BaseModel, Field


class GetPriceParams(BaseModel):
    symbol: str = Field(
        ...,
        description="Instrument symbol",
        examples=["AAPL"],
    )
    apikey: str = Field(
        ...,
        description="Your API key",
        examples=["demo"],
    )
    figi: Optional[str] = Field(
        None,
        description="Financial Instrument Global Identifier",
        examples=["BBG000B9XRY4"],
    )
    isin: Optional[str] = Field(
        None,
        description="ISSN International Securities Identification Number",
        examples=["US0378331005"],
    )
    cusip: Optional[str] = Field(
        None,
        description="CUSIP number",
        examples=["037833100"],
    )
    exchange: Optional[str] = Field(
        None,
        description="Exchange code",
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
        examples=["Equity"],
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
    prepost: Optional[bool] = Field(
        None,
        description="Include pre/post market data",
        examples=[False],
    )
    dp: Optional[int] = Field(
        None,
        description="Number of decimal places",
        examples=[2],
    )
