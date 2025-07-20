import asyncio
import os
import signal
import sys

import pytest_asyncio
from dotenv import load_dotenv

sys.unraisablehook = lambda unraisable: None

dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)

SERVER_URL = os.environ["SERVER_URL"]
MCP_URL = SERVER_URL + '/mcp/'
TD_API_KEY = os.environ["TWELVE_DATA_API_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]


@pytest_asyncio.fixture(scope="function")
async def run_server():
    proc = await asyncio.create_subprocess_exec(
        "python", "-m", "mcp_server_twelve_data",
        "-t", "streamable-http",
        "-k", TD_API_KEY,
        "-u", OPENAI_API_KEY,
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
