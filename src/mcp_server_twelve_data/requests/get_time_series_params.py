from typing import Optional
from pydantic import BaseModel, Field


class GetTimeSeriesParams(BaseModel):
    symbol: str = Field(
        ...,
        description="Instrument symbol",
        examples=["AAPL"],
    )
    interval: str = Field(
        ...,
        description="Data interval",
        examples=["1h"],
    )
    apikey: str = Field(
        ...,
        description="Your API key",
        examples=["demo"],
    )
    isin: Optional[str] = Field(
        None,
        description="International Securities Identification Number",
        examples=["US0378331005"],
    )
    figi: Optional[str] = Field(
        None,
        description="Financial Instrument Global Identifier",
        examples=["BBG000B9XRY4"],
    )
    cusip: Optional[str] = Field(
        None,
        description="Committee on Uniform Securities Identification Procedures number",
        examples=["037833100"],
    )
    outputsize: Optional[int] = Field(
        None,
        description="Number of data points to return",
        examples=[100],
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
    timezone: Optional[str] = Field(
        None,
        description="Timezone for returned data",
        examples=["America/New_York"],
    )
    start_date: Optional[str] = Field(
        None,
        description="Start date (YYYY-MM-DD)",
        examples=["2025-01-01"],
    )
    end_date: Optional[str] = Field(
        None,
        description="End date (YYYY-MM-DD)",
        examples=["2025-05-27"],
    )
    date: Optional[str] = Field(
        None,
        description="Specific date (YYYY-MM-DD)",
        examples=["2025-05-27"],
    )
    order: Optional[str] = Field(
        None,
        description="Order of data (asc or desc)",
        examples=["asc"],
    )
    prepost: Optional[bool] = Field(
        None,
        description="Include pre/post market data",
        examples=[False],
    )
    format: Optional[str] = Field(
        None,
        description="Output format (JSON or CSV)",
        examples=["JSON"],
    )
    delimiter: Optional[str] = Field(
        None,
        description="Delimiter for CSV output",
        examples=[","],
    )
    dp: Optional[int] = Field(
        None,
        description="Number of decimal places",
        examples=[2],
    )
    previous_close: Optional[bool] = Field(
        None,
        description="Include previous close price",
        examples=[True],
    )
    adjust: Optional[str] = Field(
        None,
        description="Adjustment type",
        examples=["split"],
    )
