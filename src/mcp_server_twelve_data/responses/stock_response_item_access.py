from pydantic import BaseModel, Field


class StocksResponseItemAccess(BaseModel):
    global_: str = Field(
        ...,
        alias="global",
        description="Global access level",
        examples=["full"],
    )
    plan: str = Field(
        ...,
        description="Subscription plan",
        examples=["basic"],
    )
