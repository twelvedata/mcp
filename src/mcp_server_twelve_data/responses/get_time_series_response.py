from typing import List
from pydantic import BaseModel, Field

from .meta import Meta
from .time_series_item import TimeSeriesItem


class GetTimeSeriesResponse(BaseModel):
    meta: Meta = Field(
        ...,
        description="Metadata for the time series",
    )
    values: List[TimeSeriesItem] = Field(
        ...,
        description="List of time series bars",
    )