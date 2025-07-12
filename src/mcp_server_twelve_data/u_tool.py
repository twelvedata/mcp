import importlib.util
from pathlib import Path

from mcp.client.streamable_http import RequestContext
from starlette.requests import Request

import openai
import lancedb
import json

from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
from typing import Any, Optional, List, cast, Literal, Callable, Awaitable
from openai.types.chat import ChatCompletionSystemMessageParam
from starlette.responses import JSONResponse


def create_dummy_request_context(request: Request) -> RequestContext:
    """Returns a valid RequestContext with Starlette request injected manually."""

    rctx = RequestContext(
        client=object(),
        headers=dict(request.headers),
        session_id="dummy-session-id",
        session_message=object(),
        metadata=object(),
        read_stream_writer=object(),
        sse_read_timeout=10.0
    )

    return rctx


class TwelvedataTokens:
    def __init__(
        self, twelve_data_api_key: Optional[str] = None,
        open_ai_api_key: Optional[str] = None,
        error: Optional[str] = None,
    ):
        self.twelve_data_api_key = twelve_data_api_key
        self.open_ai_api_key = open_ai_api_key
        self.error = error


def get_tokens_from_rc(rc: RequestContext) -> TwelvedataTokens:
    if hasattr(rc, "headers"):
        headers = rc.headers
    elif hasattr(rc, "request"):
        headers = rc.request.headers
    else:
        return TwelvedataTokens(error="Headers were not found in a request context.")
    auth_header = headers.get('authorization')
    split_header = auth_header.split(' ') if auth_header else []
    if len(split_header) == 2:
        access_token = split_header[1]
        open_ai_api_key=headers.get('x-openapi-key')
        # in this case user provide both api keys via headers
        return TwelvedataTokens(
            twelve_data_api_key=access_token,
            open_ai_api_key=open_ai_api_key
        )
    return TwelvedataTokens(error=f"Bad authorization header: {auth_header}.")


def get_md_response(
    client: openai.OpenAI,
    llm_model: str,
    query: str,
    result: BaseModel
) -> str:
    prompt = """
    You are a Markdown report generator.
    
    Your task is to generate a clear, well-structured and readable response in Markdown format based on:
    1. A user query
    2. A JSON object containing the data relevant to the query
    
    Instructions:
    - Do NOT include raw JSON.
    - Instead, extract relevant information and present it using Markdown structure: headings, bullet points, tables,
      bold/italic text, etc.
    - Be concise, accurate, and helpful.
    - If the data is insufficient to fully answer the query, say so clearly.
    
    Respond only with Markdown. Do not explain or include extra commentary outside of the Markdown response.
    """

    llm_response = client.chat.completions.create(
        model=llm_model,
        messages=[
            cast(ChatCompletionSystemMessageParam, {"role": "system", "content": prompt}),
            cast(ChatCompletionSystemMessageParam, {"role": "user", "content": f"User query:\n{query}"}),
            cast(ChatCompletionSystemMessageParam, {"role": "user", "content": f"Data:\n{result.model_dump_json(indent=2)}"}),
        ],
        temperature=0,
    )

    return llm_response.choices[0].message.content.strip()


def register_u_tool(
    server: FastMCP,
    u_tool_open_ai_api_key: Optional[str],
    transport: Literal["stdio", "sse", "streamable-http"],
):
    # llm_model = "gpt-4o"         # Input $2.5,   Output $10
    # llm_model = "gpt-4-turbo"    # Input $10.00, Output $30
    llm_model = "gpt-4o-mini"      # Input $0.15,  Output $0.60

    EMBEDDING_MODEL = "text-embedding-3-small"
    spec = importlib.util.find_spec("mcp_server_twelve_data")
    MODULE_PATH = Path(spec.origin).resolve()
    PACKAGE_ROOT = MODULE_PATH.parent  # src/mcp_server_twelve_data
    DB_PATH = str(PACKAGE_ROOT / "resources" / "endpoints.lancedb")
    TOP_N = 30

    class UToolResponse(BaseModel):
        """Response object returned by the u-tool."""

        top_candidates: Optional[List[str]] = Field(
            ..., description="List of tool operationIds considered by the vector search."
        )
        selected_tool: Optional[str] = Field(
            None, description="Name (operationId) of the tool selected by the LLM."
        )
        param: Optional[dict] = Field(
            None, description="Parameters passed to the selected tool."
        )
        response: Optional[Any] = Field(
            None, description="Result returned by the selected tool."
        )
        error: Optional[str] = Field(
            None, description="Error message, if tool resolution or execution fails."
        )

    def constructor_for_utool(
        top_candidates=None,
        selected_tool=None,
        param=None,
        response=None,
        error=None,
    ):
        return UToolResponse(
            top_candidates=top_candidates,
            selected_tool=selected_tool,
            param=param,
            response=response,
            error=error,
        )

    def build_openai_tools_subset(tool_list):
        def expand_parameters(params):
            if (
                "properties" in params and
                "params" in params["properties"] and
                "$ref" in params["properties"]["params"] and
                "$defs" in params
            ):
                ref_path = params["properties"]["params"]["$ref"]
                ref_name = ref_path.split("/")[-1]
                schema = params["$defs"].get(ref_name, {})
                return {
                    "type": "object",
                    "properties": {
                        "params": {
                            "type": "object",
                            "properties": schema.get("properties", {}),
                            "required": schema.get("required", []),
                            "description": schema.get("description", "")
                        }
                    },
                    "required": ["params"]
                }
            else:
                return params

        tools = []
        for tool in tool_list:
            expanded_parameters = expand_parameters(tool.parameters)
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "No description provided.",
                    "parameters": expanded_parameters
                }
            })
        # [t for t in tools if t["function"]["name"] in ["GetTimeSeriesAdd", "GetTimeSeriesAd"]]
        return tools

    all_tools = server._tool_manager._tools
    server._tool_manager._tools = {}  # leave only u-tool

    db = lancedb.connect(DB_PATH)
    table = db.open_table("endpoints")

    @server.tool(name="u-tool")
    async def u_tool(query: str, ctx: Context, format_param: Optional[str] = None) -> UToolResponse:
        """
        A universal tool router for the MCP system, designed for the Twelve Data API.

        This tool accepts a natural language query in English and performs the following:
        1. Uses vector search to retrieve the top-N relevant Twelve Data endpoints.
        2. Sends the query and tool descriptions to OpenAI's gpt-4o with function calling.
        3. The model selects the most appropriate tool and generates the input parameters.
        4. The selected endpoint (tool) is executed and its response is returned.

        Supported endpoint categories (from Twelve Data docs):
        - Market & Reference: price, quote, symbol_search, stocks, exchanges, market_state
        - Time Series: time_series, eod, splits, dividends, etc.
        - Technical Indicators: rsi, macd, ema, bbands, atr, vwap, and 100+ others
        - Fundamentals & Reports: earnings, earnings_estimate, income_statement,
          balance_sheet, cash_flow, statistics, profile, ipo_calendar, analyst_ratings
        - Currency & Crypto: currency_conversion, exchange_rate, price_target
        - Mutual Funds / ETFs: funds, mutual_funds/type, mutual_funds/world
        - Misc Utilities: logo, calendar endpoints, time_series_calendar, etc.
        """
        o_ai_api_key_to_use: Optional[str]
        if transport == 'stdio':
            if u_tool_open_ai_api_key is not None:
                o_ai_api_key_to_use = u_tool_open_ai_api_key
            else:
                # It's not a possible case
                return constructor_for_utool(
                    error=(
                        f"Transport is stdio and u_tool_open_ai_api_key is None. "
                        f"Something goes wrong. Please contact support."
                    ),
                )
        elif transport == "streamable-http":
            if u_tool_open_ai_api_key is not None:
                o_ai_api_key_to_use=u_tool_open_ai_api_key
            else:
                rc: RequestContext = ctx.request_context
                token_from_rc = get_tokens_from_rc(rc=rc)
                if token_from_rc.error is not None:
                    return constructor_for_utool(error=token_from_rc.error)
                elif token_from_rc.twelve_data_api_key and token_from_rc.open_ai_api_key:
                    o_ai_api_key_to_use = token_from_rc.open_ai_api_key
                else:
                    return constructor_for_utool(error=f"Either OPEN API KEY or TWELVE Data API key is not provided.")
        else:
            return constructor_for_utool(error=f"This transport is not supported")

        client = openai.OpenAI(api_key=o_ai_api_key_to_use)
        candidate_ids: List[str]

        try:
            embedding = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=[query]
            ).data[0].embedding

            results = table.search(embedding).metric("cosine").limit(TOP_N).to_list()  # type: ignore[attr-defined]
            candidate_ids = [r["id"] for r in results]
            if "GetTimeSeries" not in candidate_ids:
                candidate_ids.append('GetTimeSeries')

        except Exception as e:
            return constructor_for_utool(error=f"Embedding or vector search failed: {e}")

        filtered_tools = [tool for tool in all_tools.values() if tool.name in candidate_ids]  # type: ignore
        openai_tools = build_openai_tools_subset(filtered_tools)

        prompt = (
            "You are a function-calling assistant. Based on the user query, "
            "you must select the most appropriate function from the provided tools and return "
            "a valid tool call with all required parameters. "
            "Before the function call, provide a brief plain-text explanation (1–2 sentences) of "
            "why you chose that function, based on the user's intent and tool descriptions."
        )

        try:
            llm_response = client.chat.completions.create(
                model=llm_model,
                messages=[
                    cast(ChatCompletionSystemMessageParam, {"role": "system", "content": prompt}),
                    cast(ChatCompletionSystemMessageParam, {"role": "user", "content": query}),
                ],
                tools=openai_tools,
                tool_choice="required",
                temperature=0,
            )

            call = llm_response.choices[0].message.tool_calls[0]
            name = call.function.name
            arguments = json.loads(call.function.arguments)
            # all tools require single parameter with nested attributes, but sometimes LLM flattens it
            if "params" not in arguments:
                arguments = {"params": arguments}

        except Exception as e:
            return constructor_for_utool(
                top_candidates=candidate_ids,
                error=f"LLM did not return valid tool call: {e}",
            )

        tool = all_tools.get(name)
        if not tool:
            return constructor_for_utool(
                top_candidates=candidate_ids,
                selected_tool=name,
                param=arguments,
                error=f"Tool '{name}' not found in MCP",
            )

        try:
            params_type = tool.fn_metadata.arg_model.model_fields["params"].annotation
            arguments['params'] = params_type(**arguments['params'])
            arguments['ctx'] = ctx

            result = await tool.fn(**arguments)

            if format_param == "md":
                result = get_md_response(
                    client=client,
                    llm_model=llm_model,
                    query=query,
                    result=result,
                )

            return constructor_for_utool(
                top_candidates=candidate_ids,
                selected_tool=name,
                param=arguments,
                response=result,
            )
        except Exception as e:
            return constructor_for_utool(
                top_candidates=candidate_ids,
                selected_tool=name,
                param=arguments,
                error=str(e),
            )

    if transport == "streamable-http":
        @server.custom_route("/utool", ["GET"])
        async def u_tool_http(request: Request):
            query = request.query_params.get("query")
            format_param = request.query_params.get("format", default="json").lower()
            if not query:
                return JSONResponse({"error": "Missing 'query' query parameter"}, status_code=400)

            request_context = create_dummy_request_context(request)
            ctx = Context(request_context=request_context)
            result = await u_tool(query=query, ctx=ctx, format_param=format_param, )

            return JSONResponse(content=result.model_dump())
