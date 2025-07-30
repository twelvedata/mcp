from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP, Context

from mcp_server_twelve_data.common import mcp_server_base_url
from mcp_server_twelve_data.key_provider import extract_open_ai_apikey, extract_twelve_data_apikey
from mcp_server_twelve_data.prompts import utool_doc_string
from mcp_server_twelve_data.u_tool_response import UToolResponse, utool_func_type


def register_u_tool_remote(
    server: FastMCP,
    transport: str,
    open_ai_api_key_from_args: Optional[str],
    twelve_data_apikey: Optional[str],
) -> utool_func_type:

    @server.tool(name="u-tool")
    async def u_tool(
        query: str,
        ctx: Context,
        format: Optional[str] = None,
        plan: Optional[str] = None,
    ) -> UToolResponse:
        o_ai_api_key_to_use, error = extract_open_ai_apikey(
            transport=transport,
            open_ai_api_key=open_ai_api_key_from_args,
            ctx=ctx,
        )
        if error is not None:
            return UToolResponse(error=error)

        td_key_to_use = extract_twelve_data_apikey(
            transport=transport,
            twelve_data_apikey=twelve_data_apikey,
            ctx=ctx,
        )

        async with httpx.AsyncClient(
            trust_env=False,
            headers={
                "accept": "application/json",
                "user-agent": "python-httpx/0.24.0",
                "x-openapi-key": o_ai_api_key_to_use,
                "Authorization": f'apikey {td_key_to_use}',
            },
            timeout=30,
        ) as client:
            resp = await client.get(
                f"{mcp_server_base_url}/utool",
                params={
                    "query": query,
                    "format": format,
                    "plan": plan,
                }
            )
            resp.raise_for_status()
            resp_json = resp.json()
            return UToolResponse.model_validate(resp_json)

    u_tool.__doc__ = utool_doc_string
    return u_tool
