from typing import Literal

import click
import logging
import sys

from pygments.lexer import default

from .server import serve


@click.command()
@click.option("-v", "--verbose", count=True)
@click.option("-t", "--transport", default="stdio", help="stdio, streamable-http")
@click.option("-k", "--apikey", default="", help="if set, then override a query parameter")
@click.option(
    "-n", "--number-of-tools", default=30,
    help="limit number of tools to prevent problems with mcp clients, max n value is 100, default is 30"
)
def main(
    verbose: bool,
    transport: Literal["stdio", "sse", "streamable-http"] = "stdio",
    apikey: str = "",
    number_of_tools: int = 30,
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
        number_of_tools=number_of_tools
    )


if __name__ == "__main__":
    main()
