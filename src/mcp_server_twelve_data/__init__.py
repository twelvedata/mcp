from typing import Literal, Optional

import click
import logging
import sys
from .server import serve


@click.command()
@click.option("-v", "--verbose", count=True)
@click.option("-t", "--transport", default="stdio", help="stdio, streamable-http")
@click.option(
    "-k",
    "--twelve-data-apikey",
    default=None,
    help=(
        "This parameter is required for 'stdio' transport. "
        "For 'streamable-http', you have three options: "
        "1. Use the -k option to set a predefined API key. "
        "2. Use the -ua option to retrieve the API key from the Twelve Data server. "
        "3. Provide the API key in the 'Authorization' header as: 'apikey <your-apikey>'."
    )
)
@click.option(
    "-n", "--number-of-tools", default=35,
    help="limit number of tools to prevent problems with mcp clients, max n value is 193, default is 35"
)
@click.option(
    "-u", "--u-tool-open-ai-api-key", default=None,
    help=(
        "If set, activates a unified 'u-tool' powered by OpenAI "
        "to select and call the appropriate Twelve Data endpoint."
    ),
)
@click.option(
    "-ua", "--u-tool-oauth2", default=False, is_flag=True,
    help=(
        "If set, activates the unified 'u-tool' powered by OpenAI, "
        "and fetches Twelve Data and OpenAI API keys directly from the Twelve Data server."
    )
)
def main(
    verbose: bool,
    transport: Literal["stdio", "sse", "streamable-http"] = "stdio",
    twelve_data_apikey: Optional[str] = None,
    number_of_tools: int = 30,
    u_tool_open_ai_api_key: Optional[str] = None,
    u_tool_oauth2: bool = False,
) -> None:
    logging_level = logging.WARN
    if verbose == 1:
        logging_level = logging.INFO
    elif verbose >= 2:
        logging_level = logging.DEBUG

    logging.basicConfig(level=logging_level, stream=sys.stderr)

    if u_tool_oauth2 and u_tool_open_ai_api_key is not None:
        RuntimeError("Set either u_tool_open_ai_api_key or u_tool_oauth2")
    if u_tool_oauth2 and transport != "streamable-http":
        RuntimeError("Set transport to streamable-http if you want to use -ua option")
    if transport == "stdio" and twelve_data_apikey is None:
        RuntimeError("Set -k to use stdio transport")

    serve(
        api_base="https://api.twelvedata.com",
        transport=transport,
        twelve_data_apikey=twelve_data_apikey,
        number_of_tools=number_of_tools,
        u_tool_open_ai_api_key=u_tool_open_ai_api_key,
        u_tool_oauth2=u_tool_oauth2,
    )


if __name__ == "__main__":
    main()
