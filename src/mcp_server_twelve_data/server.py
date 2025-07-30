from typing import Type, TypeVar, Literal, Optional
import httpx
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP, Context
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
import re

from .common import vector_db_exists
from .doc_tool import register_doc_tool, register_http_doctool
from .doc_tool_remote import register_doc_tool_remote
from .key_provider import extract_twelve_data_apikey
from .tools import register_all_tools
from .u_tool import register_u_tool, register_http_utool
from .u_tool_remote import register_u_tool_remote


def serve(
    api_base: str,
    transport: Literal["stdio", "sse", "streamable-http"],
    twelve_data_apikey: Optional[str],
    number_of_tools: int,
    u_tool_open_ai_api_key: Optional[str],
    u_tool_oauth2: bool
) -> None:
    server = FastMCP(
        "mcp-twelve-data",
        host="0.0.0.0",
        port="8000",
    )

    P = TypeVar('P', bound=BaseModel)
    R = TypeVar('R', bound=BaseModel)

    def resolve_path_params(endpoint: str, params_dict: dict) -> str:
        def replacer(match):
            key = match.group(1)
            if key not in params_dict:
                raise ValueError(f"Missing path parameter: {key}")
            return str(params_dict.pop(key))
        return re.sub(r"{(\w+)}", replacer, endpoint)

    async def _call_endpoint(
        endpoint: str,
        params: P,
        response_model: Type[R],
        ctx: Context
    ) -> R:
        params.apikey = extract_twelve_data_apikey(
            twelve_data_apikey=twelve_data_apikey,
            transport=transport,
            ctx=ctx
        )

        params_dict = params.model_dump(exclude_none=True)
        resolved_endpoint = resolve_path_params(endpoint, params_dict)

        async with httpx.AsyncClient(
            trust_env=False,
            headers={
                "accept": "application/json",
                "user-agent": "python-httpx/0.24.0"
            },
        ) as client:
            resp = await client.get(
                f"{api_base}/{resolved_endpoint}",
                params=params_dict
            )
            resp.raise_for_status()
            resp_json = resp.json()

            if isinstance(resp_json, dict):
                status = resp_json.get("status")
                if status == "error":
                    code = resp_json.get('code')
                    raise HTTPException(
                        status_code=code,
                        detail=f"Failed to perform request,"
                               f" code = {code}, message = {resp_json.get('message')}"
                    )

            return response_model.model_validate(resp_json)

    if u_tool_oauth2 or u_tool_open_ai_api_key is not None:
        # we will not publish large vector db, without it server will work in remote mode
        if vector_db_exists():
            register_all_tools(server=server, _call_endpoint=_call_endpoint)
            u_tool = register_u_tool(
                server=server,
                open_ai_api_key_from_args=u_tool_open_ai_api_key,
                transport=transport
            )
            doc_tool = register_doc_tool(
                server=server,
                open_ai_api_key_from_args=u_tool_open_ai_api_key,
                transport=transport
            )
        else:
            u_tool = register_u_tool_remote(
                server=server,
                twelve_data_apikey=twelve_data_apikey,
                open_ai_api_key_from_args=u_tool_open_ai_api_key,
                transport=transport,
            )
            doc_tool = register_doc_tool_remote(
                server=server,
                twelve_data_apikey=twelve_data_apikey,
                open_ai_api_key_from_args=u_tool_open_ai_api_key,
                transport=transport,
            )
        register_http_utool(
            transport=transport,
            u_tool=u_tool,
            server=server,
        )
        register_http_doctool(
            transport=transport,
            server=server,
            doc_tool=doc_tool,
        )

    else:
        register_all_tools(server=server, _call_endpoint=_call_endpoint)
        all_tools = server._tool_manager._tools
        server._tool_manager._tools = dict(list(all_tools.items())[:number_of_tools])

    @server.custom_route("/health", ["GET"])
    async def health(_: Request):
        return JSONResponse({"status": "ok"})

    server.run(transport=transport)
