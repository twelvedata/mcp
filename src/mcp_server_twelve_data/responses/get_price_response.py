from pydantic import BaseModel, Field


class GetPriceResponse(BaseModel):
    price: str = Field(
        ...,
        description="Real-time or latest available price",
        examples=["173.65"],
    )
