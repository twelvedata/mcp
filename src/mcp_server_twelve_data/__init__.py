from typing import Literal

import click
import logging
import sys
from .server import serve


@click.command()
@click.option("-v", "--verbose", count=True)
@click.option("-t", "--transport", default="stdio", help="stdio, streamable-http")
@click.option("-k", "--apikey", default="", help="if set, then override a query parameter")
@click.option(
    "-n", "--number-of-tools", default=35,
    help="limit number of tools to prevent problems with mcp clients, max n value is 193, default is 35"
)
@click.option(
    "-u", "--u-tool-open-ai-api-key", default=None,
    help=(
        "If set, activates a unified 'u-tool' that uses OpenAI "
        "to select and call the appropriate Twelve Data endpoint."
    ),
)
def main(
    verbose: bool,
    transport: Literal["stdio", "sse", "streamable-http"] = "stdio",
    apikey: str = "",
    number_of_tools: int = 30,
    u_tool_open_ai_api_key: str = None,
) -> None:
    """MCP Git Server - Git functionality for MCP"""
    logging_level = logging.WARN
    if verbose == 1:
        logging_level = logging.INFO
    elif verbose >= 2:
        logging_level = logging.DEBUG

    logging.basicConfig(level=logging_level, stream=sys.stderr)
    serve(
        api_base="https://api.twelvedata.com",
        transport=transport,
        apikey=apikey,
        number_of_tools=number_of_tools,
        u_tool_open_ai_api_key=u_tool_open_ai_api_key,
    )


if __name__ == "__main__":
    main()
