from starlette.requests import Request

import openai
import json

from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel
from typing import Optional, List, cast, Literal
from openai.types.chat import ChatCompletionSystemMessageParam
from starlette.responses import JSONResponse

from mcp_server_twelve_data.common import create_dummy_request_context, ToolPlanMap, \
    build_openai_tools_subset, LANCE_DB_ENDPOINTS_PATH
from mcp_server_twelve_data.key_provider import extract_open_ai_apikey
from mcp_server_twelve_data.prompts import utool_doc_string
from mcp_server_twelve_data.u_tool_response import UToolResponse, utool_func_type


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
            cast(ChatCompletionSystemMessageParam, {"role": "user", "content": f"Data:\n{result.model_dump_json()}"}),
        ],
        temperature=0,
    )

    return llm_response.choices[0].message.content.strip()


def register_u_tool(
    server: FastMCP,
    open_ai_api_key_from_args: Optional[str],
    transport: Literal["stdio", "sse", "streamable-http"],
) -> utool_func_type:
    # llm_model = "gpt-4o"         # Input $2.5,   Output $10
    # llm_model = "gpt-4-turbo"    # Input $10.00, Output $30
    llm_model = "gpt-4o-mini"    # Input $0.15,  Output $0.60
    # llm_model = "gpt-4.1-nano"     # Input $0.10,  Output $0.40

    embedding_model = "text-embedding-3-large"
    top_n = 30

    all_tools = server._tool_manager._tools
    server._tool_manager._tools = {}  # leave only u-tool

    import lancedb
    db = lancedb.connect(LANCE_DB_ENDPOINTS_PATH)
    table = db.open_table("endpoints")
    table_df = table.to_pandas()
    tool_plan_map = ToolPlanMap(table_df)

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

        client = openai.OpenAI(api_key=o_ai_api_key_to_use)
        all_candidate_ids: List[str]

        try:
            embedding = client.embeddings.create(
                model=embedding_model,
                input=[query]
            ).data[0].embedding

            results = table.search(embedding).metric("cosine").limit(top_n).to_list()  # type: ignore[attr-defined]
            all_candidate_ids = [r["id"] for r in results]
            if "GetTimeSeries" not in all_candidate_ids:
                all_candidate_ids.append('GetTimeSeries')

            candidates, premium_only_candidates = tool_plan_map.split(
                user_plan=plan, tool_operation_ids=all_candidate_ids
            )

        except Exception as e:
            return UToolResponse(error=f"Embedding or vector search failed: {e}")

        filtered_tools = [tool for tool in all_tools.values() if tool.name in candidates]  # type: ignore
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
            return UToolResponse(
                top_candidates=candidates,
                premium_only_candidates=premium_only_candidates,
                error=f"LLM did not return valid tool call: {e}",
            )

        tool = all_tools.get(name)
        if not tool:
            return UToolResponse(
                top_candidates=candidates,
                premium_only_candidates=premium_only_candidates,
                selected_tool=name,
                param=arguments,
                error=f"Tool '{name}' not found in MCP",
            )

        try:
            params_type = tool.fn_metadata.arg_model.model_fields["params"].annotation
            arguments['params'] = params_type(**arguments['params'])
            arguments['ctx'] = ctx

            result = await tool.fn(**arguments)

            if format == "md":
                result = get_md_response(
                    client=client,
                    llm_model=llm_model,
                    query=query,
                    result=result,
                )

            return UToolResponse(
                top_candidates=candidates,
                premium_only_candidates=premium_only_candidates,
                selected_tool=name,
                param=arguments,
                response=result,
            )
        except Exception as e:
            return UToolResponse(
                top_candidates=candidates,
                premium_only_candidates=premium_only_candidates,
                selected_tool=name,
                param=arguments,
                error=str(e),
            )
    u_tool.__doc__ = utool_doc_string
    return u_tool


def register_http_utool(
    transport: str,
    server: FastMCP,
    u_tool,
):
    if transport == "streamable-http":
        @server.custom_route("/utool", ["GET"])
        async def u_tool_http(request: Request):
            query = request.query_params.get("query")
            format_param = request.query_params.get("format", default="json").lower()
            user_plan_param = request.query_params.get("plan", None)
            if not query:
                return JSONResponse({"error": "Missing 'query' query parameter"}, status_code=400)

            request_context = create_dummy_request_context(request)
            ctx = Context(request_context=request_context)
            result = await u_tool(
                query=query, ctx=ctx,
                format=format_param,
                plan=user_plan_param
            )

            return JSONResponse(content=result.model_dump(mode="json"))
