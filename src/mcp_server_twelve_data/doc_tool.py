import importlib.util
from pathlib import Path
from typing import Optional, List, Literal, cast

import openai
import lancedb
from openai.types.chat import ChatCompletionSystemMessageParam
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp.server.fastmcp import FastMCP, Context
from mcp_server_twelve_data.common import (
    get_tokens_from_rc,
    create_dummy_request_context,
)


def register_doc_tool(
    server: FastMCP,
    doc_tool_open_ai_api_key: Optional[str],
    transport: Literal["stdio", "sse", "streamable-http"],
):
    EMBEDDING_MODEL = "text-embedding-3-small"
    LLM_MODEL = "gpt-4o-mini"

    spec = importlib.util.find_spec("mcp_server_twelve_data")
    module_path = Path(spec.origin).resolve()
    db_path = str(module_path.parent / "resources" / "docs.lancedb")
    top_k = 5

    class DocToolResponse(BaseModel):
        query: str
        top_candidates: List[str]
        result: Optional[str] = None
        error: Optional[str] = None

    @server.tool(name="doc-tool")
    async def doc_tool(query: str, ctx: Context) -> DocToolResponse:
        """Search Twelve Data documentation and return a Markdown summary of the most relevant sections."""
        if transport == "stdio":
            if not doc_tool_open_ai_api_key:
                return DocToolResponse(query=query, top_candidates=[], error="Missing OpenAI API key.")
            openai_key = doc_tool_open_ai_api_key
        elif transport == "streamable-http":
            rc = ctx.request_context
            tokens = get_tokens_from_rc(rc)
            openai_key = tokens.open_ai_api_key
            if not openai_key:
                return DocToolResponse(query=query, top_candidates=[], error=tokens.error)
        else:
            return DocToolResponse(query=query, top_candidates=[], error="Unsupported transport.")

        client = openai.OpenAI(api_key=openai_key)

        try:
            embedding = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=[query],
            ).data[0].embedding

            db = lancedb.connect(db_path)
            table = db.open_table("docs")
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
                "Do not repeat the full documentation — summarize only what's relevant to the query."
            )

            llm_response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    cast(ChatCompletionSystemMessageParam, {"role": "system", "content": prompt}),
                    cast(ChatCompletionSystemMessageParam, {"role": "user", "content": f"User query:\n{query}"}),
                    cast(ChatCompletionSystemMessageParam, {"role": "user", "content": f"Documentation:\n{combined_text}"}),
                ],
                temperature=0.2,
            )

            markdown = llm_response.choices[0].message.content.strip()

        except Exception as e:
            return DocToolResponse(query=query, top_candidates=matches, error=f"LLM summarization failed: {e}")

        return DocToolResponse(
            query=query,
            top_candidates=matches,
            result=markdown,
        )

    if transport == "streamable-http":
        @server.custom_route("/doctool", ["GET"])
        async def doc_tool_http(request: Request):
            query = request.query_params.get("query")
            if not query:
                return JSONResponse({"error": "Missing 'query' query parameter"}, status_code=400)

            ctx = Context(request_context=create_dummy_request_context(request))
            result = await doc_tool(query=query, ctx=ctx)
            return JSONResponse(content=result.model_dump())
