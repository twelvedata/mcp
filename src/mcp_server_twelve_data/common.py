from typing import Optional
from starlette.requests import Request
from mcp.client.streamable_http import RequestContext


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


def create_dummy_request_context(request: Request) -> RequestContext:
    return RequestContext(
        client=object(),
        headers=dict(request.headers),
        session_id="generated-session-id",
        session_message=object(),
        metadata=object(),
        read_stream_writer=object(),
        sse_read_timeout=10.0,
    )
