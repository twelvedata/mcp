import logging
from typing import Type, TypeVar, Literal
import httpx
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP, Context

from .tools import register_all_tools
from .u_tool import register_u_tool


def serve(
    api_base: str,
    transport: Literal["stdio", "sse", "streamable-http"],
    apikey: str,
    number_of_tools: int,
    u_tool_open_ai_api_key: str,
) -> None:
    logger = logging.getLogger(__name__)

    server = FastMCP(
        "mcp-twelve-data",
        host="0.0.0.0",
        port="8000",
    )

    P = TypeVar('P', bound=BaseModel)
    R = TypeVar('R', bound=BaseModel)

    async def _call_endpoint(
        endpoint: str,
        params: P,
        response_model: Type[R],
        ctx: Context
    ) -> R:
        if transport == 'stdio' and apikey:
            params.apikey = apikey
        elif transport == "streamable-http":
            apikey_header = ctx.request_context.request.headers.get('Authorization')
            split_header = apikey_header.split(' ') if apikey_header else []
            if len(split_header) == 2:
                params.apikey = split_header[1]
        async with httpx.AsyncClient(
            trust_env=False,
            headers={
                "Accept": "application/json",
                "User-Agent": "python-httpx/0.24.0"
            },
        ) as client:
            resp = await client.get(
                f"{api_base}/{endpoint}",
                params=params.model_dump(exclude_none=True)
            )
            resp.raise_for_status()
            return response_model.model_validate(resp.json())

    register_all_tools(server=server, _call_endpoint=_call_endpoint)

    if u_tool_open_ai_api_key is None:
        all_tools = server._tool_manager._tools
        server._tool_manager._tools = dict(list(all_tools.items())[:number_of_tools])
    else:
        register_u_tool(server=server, u_tool_open_ai_api_key=u_tool_open_ai_api_key)

    server.run(transport=transport)
