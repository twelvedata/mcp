from typing import Optional, List, Any, Callable, Awaitable
from pydantic import BaseModel, Field

from mcp.server.fastmcp import Context


class UToolResponse(BaseModel):
    """Response object returned by the u-tool."""

    top_candidates: Optional[List[str]] = Field(
        default=None, description="List of tool operationIds considered by the vector search."
    )
    premium_only_candidates: Optional[List[str]] = Field(
        default=None, description="Relevant tool IDs available only in higher-tier plans"
    )
    selected_tool: Optional[str] = Field(
        default=None, description="Name (operationId) of the tool selected by the LLM."
    )
    param: Optional[dict] = Field(
        default=None, description="Parameters passed to the selected tool."
    )
    response: Optional[Any] = Field(
        default=None, description="Result returned by the selected tool."
    )
    error: Optional[str] = Field(
        default=None, description="Error message, if tool resolution or execution fails."
    )


utool_func_type = Callable[[str, Context, Optional[str], Optional[str]], Awaitable[UToolResponse]]
