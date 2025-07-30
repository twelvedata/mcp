from typing import Optional

from mcp.server.fastmcp import Context
from mcp.client.streamable_http import RequestContext


def extract_open_ai_apikey(
    transport: str,
    open_ai_api_key: str,
    ctx: Context,
) -> (Optional[str], Optional[str]):
    """Returns optional key and optional error"""
    if transport == 'stdio':
        if open_ai_api_key is not None:
            return (open_ai_api_key, None)
        else:
            # It's not a possible case
            error = (
                f"Transport is stdio and u_tool_open_ai_api_key is None. "
                f"Something goes wrong. Please contact support."
            )
            return None, error
    elif transport == "streamable-http":
        if open_ai_api_key is not None:
            return open_ai_api_key, None
        else:
            rc: RequestContext = ctx.request_context
            token_from_rc = get_tokens_from_rc(rc=rc)
            if token_from_rc.error is not None:
                return None, token_from_rc.error
            elif token_from_rc.twelve_data_api_key and token_from_rc.open_ai_api_key:
                o_ai_api_key_to_use = token_from_rc.open_ai_api_key
                return o_ai_api_key_to_use, None
            else:
                return None, "Either OPEN API KEY or TWELVE Data API key is not provided."
    else:
        return None, "This transport is not supported"


def extract_twelve_data_apikey(
    transport: str,
    twelve_data_apikey: Optional[str],
    ctx: Context,
):
    if transport in {'stdio', 'streamable-http'} and twelve_data_apikey:
        return twelve_data_apikey
    else:
        rc: RequestContext = ctx.request_context
        tokens = get_tokens_from_rc(rc=rc)
        return tokens.twelve_data_api_key


class ToolTokens:
    def __init__(
        self,
        twelve_data_api_key: Optional[str] = None,
        open_ai_api_key: Optional[str] = None,
        error: Optional[str] = None,
    ):
        self.twelve_data_api_key = twelve_data_api_key
        self.open_ai_api_key = open_ai_api_key
        self.error = error


def get_tokens_from_rc(rc: RequestContext) -> ToolTokens:
    if hasattr(rc, "headers"):
        headers = rc.headers
    elif hasattr(rc, "request"):
        headers = rc.request.headers
    else:
        return ToolTokens(error="Headers were not found in a request context.")
    auth_header = headers.get("authorization")
    split = auth_header.split(" ") if auth_header else []
    if len(split) == 2:
        access_token = split[1]
        openai_key = headers.get("x-openapi-key")
        return ToolTokens(
            twelve_data_api_key=access_token,
            open_ai_api_key=openai_key,
        )
    return ToolTokens(error=f"Bad or missing authorization header: {auth_header}")