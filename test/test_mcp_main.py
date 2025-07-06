import json
import os
import signal

import httpx
import pytest
import asyncio
import urllib.parse


import pytest_asyncio
from dotenv import load_dotenv
from mcp import stdio_client, ClientSession, StdioServerParameters

dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)
server_url = os.environ['SERVER_URL']
td_api_key = os.environ['TWELVE_DATA_API_KEY']
open_api_key = os.environ['OPEN_API_KEY']
test_oauth2_access_token = os.environ['TEST_OAUTH2_ACCESS_TOKEN']


@pytest_asyncio.fixture
def run_server_factory():
    async def _start_server(*args):
        proc = await asyncio.create_subprocess_exec(
            "python", "-m", "mcp_server_twelve_data",
            *args,
            # stdout=asyncio.subprocess.DEVNULL,
            # stderr=asyncio.subprocess.DEVNULL,
        )

        # healthcheck
        for _ in range(30):
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(f"{server_url}/health")
                    if r.status_code == 200:
                        break
            except Exception:
                await asyncio.sleep(1)
        else:
            proc.terminate()
            raise RuntimeError("Server did not start")

        async def stop():
            proc.send_signal(signal.SIGINT)
            await proc.wait()

        return stop

    return _start_server


@pytest.mark.asyncio
async def test_call_utool(run_server_factory):
    stop_server = await run_server_factory(
        "-t", "streamable-http",
        "-k", td_api_key,
        "-u", open_api_key,
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{server_url}/utool?query={urllib.parse.quote('show me RSI for AAPL')}",
                timeout=30,
            )
        assert response.status_code == 200
        data = response.json()
        response = data.get("response")
        assert response
        assert "values" in response
        assert len(response["values"]) > 0
    finally:
        await stop_server()


@pytest.mark.asyncio
async def test_call_utool_both_keys_in_header(run_server_factory):
    stop_server = await run_server_factory(
        "-t", "streamable-http", "-ua"
    )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{server_url}/utool?query={urllib.parse.quote('show me RSI for AAPL')}",
                timeout=30,
                headers={
                    'Authorization': f'apikey {td_api_key}',
                    'X-OpenAPI-Key': open_api_key,
                }
            )
        assert response.status_code == 200
        data = response.json()
        response = data.get("response")
        assert response
        assert "values" in response
        assert len(response["values"]) > 0
    finally:
        await stop_server()


@pytest.mark.asyncio
async def test_call_utool_stdio():
    server_params = StdioServerParameters(
        command="python",
        args=[
            "-m", "mcp_server_twelve_data",
            "-t", "stdio",
            "-k", td_api_key,
            "-u", open_api_key
        ],
    )

    async with stdio_client(server_params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            result = await session.call_tool("u-tool", arguments={"query": "show me RSI for AAPL"})
            data = json.loads(result.content[0].text)
            response = data.get("response")
            assert response
            assert "values" in response
            assert len(response["values"]) > 0


@pytest.mark.asyncio
async def test_call_time_series_stdio():
    server_params = StdioServerParameters(
        command="python",
        args=[
            "-m", "mcp_server_twelve_data",
            "-t", "stdio",
            "-k", td_api_key,
        ],
    )

    async with stdio_client(server_params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            arguments = {
                "params": {
                    "symbol": "AAPL",
                    "interval": "1day",
                }
            }

            result = await session.call_tool("GetTimeSeries", arguments=arguments)
            data = json.loads(result.content[0].text)

            assert "values" in data
            assert len(data["values"]) > 0
