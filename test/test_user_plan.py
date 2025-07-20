import json

import pytest
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

from test.common import TD_API_KEY, MCP_URL, run_server


@pytest.mark.asyncio
@pytest.mark.parametrize("user_query, expected_operation_id", [
    ("Show me market movers", "GetMarketMovers"),
    ("Show me earnings estimates for AAPL", "GetEarningsEstimate"),
    ("Show me price targets for TSLA", "GetPriceTarget"),
])
async def test_utool_basic_plan_restrictions(user_query, expected_operation_id, run_server):
    """
    Users on Basic plan should be denied access to endpoints that require higher plans.
    Error message must include required operationId.
    """
    headers = {"Authorization": f"apikey {TD_API_KEY}"}
    user_plan = "Basic"

    async with streamablehttp_client(MCP_URL, headers=headers) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool("u-tool", arguments={
                "query": user_query,
                "user_plan_param": user_plan
            })
        await read_stream.aclose()
        await write_stream.aclose()

    assert not result.isError, f"u-tool error: {result.content}"
    payload = json.loads(result.content[0].text)
    error = payload.get("error")
    selected_tool = payload.get("selected_tool")
    response = payload.get("response")

    assert error is not None, f"Expected error for query: '{user_query}'"
    assert "at least" in error, f"Unexpected error format: {error}"
    assert expected_operation_id in error, (
        f"Expected operationId '{expected_operation_id}' to appear in error message: {error}"
    )
    assert selected_tool == expected_operation_id
    assert response is None, "No response should be returned if access is denied"
