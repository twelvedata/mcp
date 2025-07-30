from typing import Optional, List, Callable, Awaitable
from mcp.server.fastmcp import Context
from pydantic import BaseModel


class DocToolResponse(BaseModel):
    query: str
    top_candidates: Optional[List[str]] = None
    result: Optional[str] = None
    error: Optional[str] = None


doctool_func_type = Callable[[str, Context], Awaitable[DocToolResponse]]
