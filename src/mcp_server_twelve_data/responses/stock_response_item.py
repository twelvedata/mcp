from pydantic import BaseModel, Field

from .stock_response_item_access import StocksResponseItemAccess


class StocksResponseItem(BaseModel):
    symbol: str = Field(
        ...,
        description="Ticker symbol",
        examples=["AAPL"],
    )
    name: str = Field(
        ...,
        description="Company name",
        examples=["Apple Inc."],
    )
    currency: str = Field(
        ...,
        description="Trading currency",
        examples=["USD"],
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
    country: str = Field(
        ...,
        description="Country code",
        examples=["US"],
    )
    type: str = Field(
        ...,
        description="Instrument type",
        examples=["Common Stock"],
    )
    figi_code: str = Field(
        ...,
        description="Financial Instrument Global Identifier",
        examples=["BBG000B9XRY4"],
    )
    cfi_code: str = Field(
        ...,
        description="Classification of Financial Instrument code",
        examples=["ESXXXX"],
    )
    isin: str = Field(
        ...,
        description="International Securities Identification Number",
        examples=["US0378331005"],
    )
    access: StocksResponseItemAccess = Field(
        ...,
        description="Access details for the stock instrument",
    )
