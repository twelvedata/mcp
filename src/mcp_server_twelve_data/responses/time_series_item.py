from pydantic import BaseModel, Field


class TimeSeriesItem(BaseModel):
    open: str = Field(
        ...,
        description="Price at the opening of current bar",
        examples=["123.45"],
    )
    high: str = Field(
        ...,
        description="Highest price which occurred during the current bar.",
        examples=["125.00"],
    )
    low: str = Field(
        ...,
        description="Lowest price which occurred during the current bar.",
        examples=["122.50"],
    )
    close: str = Field(
        ...,
        description="Close price at the end of the bar.",
        examples=["124.75"],
    )
    volume: str = Field(
        ...,
        description="Trading volume which occurred during the current bar",
        examples=["1000000"],
    )
    datetime: str = Field(
        ...,
        description="Datetime at local exchange time referring to when the bar with specified interval was opened.",
        examples=["2025-05-28 19:00:00"],
    )
