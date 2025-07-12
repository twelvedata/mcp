import os
import json
import sys
import asyncio
import signal

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
from test.endpoint_pairs import pairs


def _ignore_unraisable(unraisable):
    """prevent pycharm errors in debug mode"""
    pass

sys.unraisablehook = _ignore_unraisable

dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)

SERVER_URL = os.environ["SERVER_URL"]
MCP_URL = SERVER_URL + '/mcp/'
TD_API_KEY = os.environ["TWELVE_DATA_API_KEY"]
OPEN_API_KEY = os.environ["OPEN_API_KEY"]


@pytest_asyncio.fixture(scope="function")
async def run_server():
    proc = await asyncio.create_subprocess_exec(
        "python", "-m", "mcp_server_twelve_data",
        "-t", "streamable-http",
        "-k", TD_API_KEY,
        "-u", OPEN_API_KEY,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )

    for _ in range(40):
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{SERVER_URL}/health")
                if r.status_code == 200:
                    break
        except Exception:
            await asyncio.sleep(1)
    else:
        proc.terminate()
        raise RuntimeError("Server did not start")

    yield

    proc.send_signal(signal.SIGINT)
    await proc.wait()


@pytest.mark.asyncio
@pytest.mark.parametrize("user_query,expected_op_id", pairs)
async def test_embedding_and_utool_async(user_query, expected_op_id, run_server):
    headers = {"Authorization": f"apikey {TD_API_KEY}"}

    async with streamablehttp_client(MCP_URL, headers=headers) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            call_result = await session.call_tool("u-tool", arguments={"query": user_query})
        await read_stream.aclose()
        await write_stream.aclose()

    assert not call_result.isError, f"u-tool error: {call_result.content}"
    raw = call_result.content[0].text
    payload = json.loads(raw)
    top_cands = payload.get("top_candidates", [])
    error = payload.get("error")
    selected_tool = payload.get("selected_tool")
    response = payload.get("response")
    assert expected_op_id in top_cands, f"{expected_op_id!r} not in {top_cands!r}"
    assert error is None, f"u-tool error: {error}"
    assert selected_tool == expected_op_id, (
        f"selected_tool {payload.get('selected_tool')!r} != expected {expected_op_id!r}"
    )
    assert response is not None
    if "GetTimeSeries" in selected_tool:
        values = response['values']
        assert values is not None and len(values) > 0
