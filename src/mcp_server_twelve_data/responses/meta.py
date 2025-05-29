from pydantic import BaseModel, Field


class Meta(BaseModel):
    symbol: str = Field(
        ...,
        description="Instrument symbol",
        examples=["AAPL"],
    )
    interval: str = Field(
        ...,
        description="Interval of the time series",
        examples=["1h"],
    )
    currency: str = Field(
        ...,
        description="Instrument currency",
        examples=["USD"],
    )
    exchange_timezone: str = Field(
        ...,
        description="Exchange timezone",
        examples=["America/New_York"],
    )
    exchange: str = Field(
        ...,
        description="Exchange name",
        examples=["NASDAQ"],
    )
    mic_code: str = Field(
        ...,
        description="Market Identifier Code",
        examples=["XNAS"],
    )
    type: str = Field(
        ...,
        description="Instrument type",
        examples=["Equity"],
    )