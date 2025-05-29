from typing import List
from pydantic import BaseModel, Field

from .forex_response_item import ForexResponseItem


class GetForexPairsResponse(BaseModel):
    data: List[ForexResponseItem] = Field(
        ...,
        description="List of forex currency pairs",
    )
