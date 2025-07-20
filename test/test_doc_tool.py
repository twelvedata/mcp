import json

import pytest
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

from test.common import TD_API_KEY, OPENAI_API_KEY, MCP_URL, run_server


@pytest.mark.asyncio
@pytest.mark.parametrize("query, expected_title_keyword", [
    ("what does the macd indicator do?", "MACD"),
    ("how to fetch time series data?", "Time Series"),
    ("supported intervals for time_series?", "interval"),
])
async def test_doc_tool_async(query, expected_title_keyword, run_server):
    headers = {
        "Authorization": f"apikey {TD_API_KEY}",
        "x-openapi-key": OPENAI_API_KEY
    }

    async with streamablehttp_client(MCP_URL, headers=headers) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            call_result = await session.call_tool("doc-tool", arguments={"query": query})
        await read_stream.aclose()
        await write_stream.aclose()

    assert not call_result.isError, f"doc-tool error: {call_result.content}"
    raw = call_result.content[0].text
    payload = json.loads(raw)

    assert payload["error"] is None
    assert payload["result"] is not None
    assert expected_title_keyword.lower() in payload["result"].lower(), (
        f"Expected '{expected_title_keyword}' in result Markdown:\n{payload['result']}"
    )
    assert len(payload["top_candidates"]) > 0
