from typing import Type, TypeVar, Literal, Optional
import httpx
from mcp.client.streamable_http import RequestContext
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP, Context
from starlette.requests import Request
from starlette.responses import JSONResponse

from .tools import register_all_tools
from .u_tool import register_u_tool, get_tokens_from_rc


def serve(
    api_base: str,
    transport: Literal["stdio", "sse", "streamable-http"],
    twelve_data_apikey: Optional[str],
    number_of_tools: int,
    u_tool_open_ai_api_key: Optional[str],
    u_tool_oauth2: bool
) -> None:
    # logger = logging.getLogger(__name__)

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
        if transport == 'stdio' and twelve_data_apikey:
            params.apikey = twelve_data_apikey
        elif transport == "streamable-http" and twelve_data_apikey:
            params.apikey = twelve_data_apikey
        else:
            rc: RequestContext = ctx.request_context
            tokens = get_tokens_from_rc(rc=rc)
            params.apikey = tokens.twelve_data_api_key

        async with httpx.AsyncClient(
            trust_env=False,
            headers={
                "accept": "application/json",
                "user-agent": "python-httpx/0.24.0"
            },
        ) as client:
            resp = await client.get(
                f"{api_base}/{endpoint}",
                params=params.model_dump(exclude_none=True)
            )
            resp.raise_for_status()
            return response_model.model_validate(resp.json())

    register_all_tools(server=server, _call_endpoint=_call_endpoint)

    if u_tool_oauth2 or u_tool_open_ai_api_key is not None:
        # if u_tool_oauth2 is True, then u_tool_open_ai_api_key is None and will be received via Twelve data server
        register_u_tool(
            server=server,
            u_tool_open_ai_api_key=u_tool_open_ai_api_key,
            transport=transport
        )
    else:
        all_tools = server._tool_manager._tools
        server._tool_manager._tools = dict(list(all_tools.items())[:number_of_tools])

    @server.custom_route("/health", ["GET"])
    async def health(request: Request):
        return JSONResponse({"status": "ok"})

    server.run(transport=transport)
