from typing import Optional, Literal, cast

import openai
from openai.types.chat import ChatCompletionSystemMessageParam
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp.server.fastmcp import FastMCP, Context
from mcp_server_twelve_data.common import (
    create_dummy_request_context, LANCE_DB_DOCS_PATH,
)
from mcp_server_twelve_data.doc_tool_response import DocToolResponse, doctool_func_type
from mcp_server_twelve_data.key_provider import extract_open_ai_apikey
from mcp_server_twelve_data.prompts import doctool_doc_string


def register_doc_tool(
    server: FastMCP,
    open_ai_api_key_from_args: Optional[str],
    transport: Literal["stdio", "sse", "streamable-http"],
) -> doctool_func_type:
    embedding_model = "text-embedding-3-large"
    llm_model = "gpt-4.1-mini"
    # llm_model = "gpt-4o-mini"
    # llm_model = "gpt-4.1-nano"

    db_path = LANCE_DB_DOCS_PATH
    top_k = 15

    import lancedb
    db = lancedb.connect(db_path)
    table = db.open_table("docs")

    @server.tool(name="doc-tool")
    async def doc_tool(query: str, ctx: Context) -> DocToolResponse:
        openai_key, error = extract_open_ai_apikey(
            transport=transport,
            open_ai_api_key=open_ai_api_key_from_args,
            ctx=ctx,
        )
        if error is not None:
            return DocToolResponse(query=query, error=error)

        client = openai.OpenAI(api_key=openai_key)

        try:
            embedding = client.embeddings.create(
                model=embedding_model,
                input=[query],
            ).data[0].embedding

            results = table.search(embedding).metric("cosine").limit(top_k).to_list()
            matches = [r["title"] for r in results]
            combined_text = "\n\n---\n\n".join([r["content"] for r in results])

        except Exception as e:
            return DocToolResponse(query=query, top_candidates=[], error=f"Vector search failed: {e}")

        try:
            prompt = (
                "You are a documentation assistant. Given a user query and relevant documentation sections, "
                "generate a helpful, accurate, and Markdown-formatted answer.\n\n"
                "Use:\n"
                "- Headings\n"
                "- Bullet points\n"
                "- Short paragraphs\n"
                "- Code blocks if applicable\n\n"
                "Do not repeat the full documentation — summarize only what's relevant to the query.\n\n"
                "If the user asks how to perform an action "
                "(e.g., 'how to get', 'ways to retrieve', 'methods for', etc.), "
                "and there are multiple suitable API endpoints, provide "
                "a list of the most relevant ones with a brief description of each.\n"
                "Highlight when to use which endpoint and what kind of data they return."
            )

            llm_response = client.chat.completions.create(
                model=llm_model,
                messages=[
                    cast(ChatCompletionSystemMessageParam, {"role": "system", "content": prompt}),
                    cast(ChatCompletionSystemMessageParam, {"role": "user", "content": f"User query:\n{query}"}),
                    cast(ChatCompletionSystemMessageParam,
                         {"role": "user", "content": f"Documentation:\n{combined_text}"}),
                ],
                temperature=0.2,
            )

            markdown = llm_response.choices[0].message.content.strip()
            return DocToolResponse(
                query=query,
                top_candidates=matches,
                result=markdown,
            )

        except Exception as e:
            return DocToolResponse(query=query, top_candidates=matches, error=f"LLM summarization failed: {e}")

    doc_tool.__doc__ = doctool_doc_string
    return doc_tool


def register_http_doctool(
    transport: str,
    server: FastMCP,
    doc_tool,
):
    if transport == "streamable-http":
        @server.custom_route("/doctool", ["GET"])
        async def doc_tool_http(request: Request):
            query = request.query_params.get("query")
            if not query:
                return JSONResponse({"error": "Missing 'query' query parameter"}, status_code=400)

            ctx = Context(request_context=create_dummy_request_context(request))
            result = await doc_tool(query=query, ctx=ctx)
            return JSONResponse(content=result.model_dump())
