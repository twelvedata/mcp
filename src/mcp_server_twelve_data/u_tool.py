import os
from pathlib import Path

import openai
import lancedb
import json

from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
from typing import Any, Optional, List, cast
from openai.types.chat import ChatCompletionSystemMessageParam


def register_u_tool(server: FastMCP, u_tool_open_ai_api_key: str):
    # LLM_MODEL = "gpt-4o"
    LLM_MODEL = "gpt-4-turbo"

    EMBEDDING_MODEL = "text-embedding-3-small"
    BASE_DIR = Path(__file__).resolve().parents[2]
    DB_PATH = str(BASE_DIR / "extra" / "endpoints.lancedb")
    TOP_N = 35

    class UToolResponse(BaseModel):
        """Response object returned by the u-tool."""

        top_candidates: List[str] = Field(
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
        motivation: Optional[str] = Field(
            None, description="Brief explanation why the LLM chose this tool."
        )

    def build_openai_tools_subset(tool_list):
        tools = []
        for tool in tool_list:
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "No description provided.",
                    "parameters": tool.parameters
                }
            })
        return tools

    os.environ["OPENAI_API_KEY"] = u_tool_open_ai_api_key
    all_tools = server._tool_manager._tools
    server._tool_manager._tools = {}  # leave only u-tool

    db = lancedb.connect(DB_PATH)
    table = db.open_table("endpoints")

    @server.tool(name="u-tool")
    async def u_tool(query: str, ctx: Context) -> UToolResponse:
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
        client = openai.OpenAI()
        candidate_ids: List[str]

        try:
            embedding = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=[query]
            ).data[0].embedding

            results = table.search(embedding).metric("cosine").limit(TOP_N).to_list()  # type: ignore[attr-defined]
            candidate_ids = [r["id"] for r in results]

        except Exception as e:
            return UToolResponse(
                top_candidates=[],
                selected_tool=None,
                param=None,
                response=None,
                error=f"Embedding or vector search failed: {e}",
                motivation=None,
            )

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
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    cast(ChatCompletionSystemMessageParam, {"role": "system", "content": prompt}),
                    cast(ChatCompletionSystemMessageParam, {"role": "user", "content": query})
                ],
                tools=openai_tools,
                tool_choice="required",
                temperature=0,
            )

            call = response.choices[0].message.tool_calls[0]
            name = call.function.name
            arguments = json.loads(call.function.arguments)
            choice = response.choices[0].message
            motivation_text = choice.content.strip() if choice.content else None

        except Exception as e:
            return UToolResponse(
                top_candidates=candidate_ids,
                selected_tool=None,
                param=None,
                response=None,
                error=f"LLM did not return valid tool call: {e}",
                motivation=None,
            )

        tool = all_tools.get(name)
        if not tool:
            return UToolResponse(
                top_candidates=candidate_ids,
                selected_tool=name,
                param=arguments,
                response=None,
                error=f"Tool '{name}' not found in MCP",
                motivation=None,
            )

        try:
            params_type = tool.fn_metadata.arg_model.model_fields["params"].annotation
            arguments['params'] = params_type(**arguments['params'])
            arguments['ctx'] = ctx

            result = await tool.fn(**arguments)
            return UToolResponse(
                top_candidates=candidate_ids,
                selected_tool=name,
                param=arguments,
                response=result,
                error=None,
                motivation=motivation_text,
            )
        except Exception as e:
            return UToolResponse(
                top_candidates=candidate_ids,
                selected_tool=name,
                param=arguments,
                response=None,
                error=str(e),
                motivation=None,
            )
