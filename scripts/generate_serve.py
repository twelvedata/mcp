import json
from pathlib import Path
import re
import csv

OPENAPI_PATH = "../extra/openapi_clean.json"
ENDPOINTS_PATH = "../extra/endpoints_spec_en.csv"
OUTPUT_PATH = "../data/serve_autogen.py"
REQUESTS_MODULE = "request_models"
RESPONSES_MODULE = "response_models"

def canonical_class_name(opid: str, suffix: str) -> str:
    if not opid:
        return ""
    return opid[0].upper() + opid[1:] + suffix

def make_tool_desc(path: str, op: dict) -> str:
    desc = op.get("description", "").strip()
    if desc:
        desc = desc.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return desc
    clean = path.strip("/").replace("_", " ").replace("-", " ")
    if not clean:
        clean = "resource"
    if clean.endswith("s"):
        return f"Get list of {clean}."
    return f"Get {clean}."

def load_endpoint_list(path):
    endpoints = []
    with open(path, encoding='utf-8') as f:
        for row in csv.reader(f, delimiter=","):
            ep = row[0].strip()
            if ep:
                endpoints.append(ep)
    return endpoints

def gen_serve(openapi: dict, endpoints_order: list) -> str:
    paths = openapi.get("paths", {})
    request_types = set()
    response_types = set()
    endpoint_blocks = []

    # Соберём все get-эндпоинты из спецификации
    path_map = {}
    for path, ops in paths.items():
        for method, op in ops.items():
            if method.lower() != "get":
                continue
            path_map[path] = (method, op)

    # Эндпоинты, которых нет в списке из файла, добавим в конец (отсортированы)
    specified = set(endpoints_order)
    rest_endpoints = [ep for ep in path_map if ep not in specified]
    rest_endpoints.sort()
    final_endpoints = endpoints_order + rest_endpoints

    for endpoint in final_endpoints:
        if endpoint in path_map:
            method, op = path_map[endpoint]
            opid = op.get("operationId")
            if not opid:
                parts = [p for p in re.split(r'[-_/]', endpoint.strip("/").replace('/', '_').replace('-', '_')) if p]
                opid = parts[0][0].upper() + parts[0][1:] + ''.join(p.capitalize() for p in parts[1:])
            class_req = canonical_class_name(opid, "Request")
            request_types.add(class_req)
            responses = op.get("responses", {})
            status_code = None
            for code in responses:
                if code.startswith("2"):
                    status_code = code
                    break
            if not status_code:
                status_code = next(iter(responses.keys()))
            class_resp = canonical_class_name(opid, f"{status_code}Response")
            response_types.add(class_resp)
            tool_name = opid
            tool_desc = make_tool_desc(endpoint, op)
            endpoint_blocks.append(
                f'    @server.tool(name="{tool_name}", description="{tool_desc}")\n'
                f'    async def {tool_name}(params: {class_req}, ctx: Context) -> {class_resp}:\n'
                f'        return await _call_endpoint("{endpoint.lstrip("/")}", params, {class_resp}, ctx)\n\n'
            )

    import_requests = "\n".join(f"from .{REQUESTS_MODULE} import {t}" for t in sorted(request_types))
    import_responses = "\n".join(f"from .{RESPONSES_MODULE} import {t}" for t in sorted(response_types))

    code = (
        "import logging\n"
        "from typing import Type, TypeVar, Literal\n"
        "import httpx\n"
        "from pydantic import BaseModel\n"
        "from mcp.server.fastmcp import FastMCP, Context\n"
        f"{import_requests}\n"
        f"{import_responses}\n\n"
        "def serve(\n"
        "    api_base: str,\n"
        "    transport: Literal[\"stdio\", \"sse\", \"streamable-http\"],\n"
        "    apikey: str,\n"
        "    number_of_tools: int,\n"
        ") -> None:\n"
        "    logger = logging.getLogger(__name__)\n\n"
        "    server = FastMCP(\n"
        "        \"mcp-twelve-data\",\n"
        "        host=\"0.0.0.0\",\n"
        "        port=\"8000\",\n"
        "    )\n\n"
        "    P = TypeVar('P', bound=BaseModel)\n"
        "    R = TypeVar('R', bound=BaseModel)\n\n"
        "    async def _call_endpoint(\n"
        "        endpoint: str,\n"
        "        params: P,\n"
        "        response_model: Type[R],\n"
        "        ctx: Context\n"
        "    ) -> R:\n"
        "        if transport == 'stdio' and apikey:\n"
        "            params.apikey = apikey\n"
        "        elif transport == \"streamable-http\":\n"
        "            apikey_header = ctx.request_context.request.headers.get('Authorization')\n"
        "            split_header = apikey_header.split(' ') if apikey_header else []\n"
        "            if len(split_header) == 2:\n"
        "                params.apikey = split_header[1]\n"
        "        async with httpx.AsyncClient() as client:\n"
        "            resp = await client.get(\n"
        "                f\"{api_base}/{endpoint}\",\n"
        "                params=params.model_dump(exclude_none=True)\n"
        "            )\n"
        "            resp.raise_for_status()\n"
        "            return response_model.model_validate(resp.json())\n\n"
        f"{''.join(endpoint_blocks)}"
        "    all_tools = server._tool_manager._tools\n"
        "    server._tool_manager._tools = dict(list(all_tools.items())[:number_of_tools])\n"
        "    server.run(transport=transport)\n"
    )
    return code

def main():
    with open(OPENAPI_PATH, "r", encoding="utf-8") as f:
        spec = json.load(f)
    endpoints = load_endpoint_list(ENDPOINTS_PATH)
    code = gen_serve(spec, endpoints)
    Path(OUTPUT_PATH).write_text(code, encoding="utf-8")
    print(f"Готово: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
