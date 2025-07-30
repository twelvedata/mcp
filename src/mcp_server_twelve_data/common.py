import os
import importlib.util
from pathlib import Path
from typing import Optional, List, Tuple
from starlette.requests import Request
from mcp.client.streamable_http import RequestContext


mcp_server_base_url = "https://mcp.twelvedata.com"
spec = importlib.util.find_spec("mcp_server_twelve_data")
MODULE_PATH = Path(spec.origin).resolve()
PACKAGE_ROOT = MODULE_PATH.parent  # src/mcp_server_twelve_data
LANCE_DB_ENDPOINTS_PATH = str(PACKAGE_ROOT / ".." / "resources" / "endpoints.lancedb")
LANCE_DB_DOCS_PATH = str(PACKAGE_ROOT / ".." / "resources" / "docs.lancedb")


def vector_db_exists():
    return os.path.isdir(LANCE_DB_ENDPOINTS_PATH)


def create_dummy_request_context(request: Request) -> RequestContext:
    return RequestContext(
        client=object(),
        headers=dict(request.headers),
        session_id="generated-session-id",
        session_message=object(),
        metadata=object(),
        read_stream_writer=object(),
        sse_read_timeout=10.0,
    )


class ToolPlanMap:
    def __init__(self, df):
        self.df = df
        self.plan_to_int = {
            'basic': 0,
            'grow': 1,
            'pro': 2,
            'ultra': 3,
            'enterprise': 4,
        }

    def split(self, user_plan: Optional[str], tool_operation_ids: List[str]) -> Tuple[List[str], List[str]]:
        if user_plan is None:
            # if user plan param was not specified, then we have no restrictions for function calling
            return tool_operation_ids, []
        user_plan_key = user_plan.lower()
        user_plan_int = self.plan_to_int.get(user_plan_key)
        if user_plan_int is None:
            raise ValueError(f"Wrong user_plan: '{user_plan}'")

        tools_df = self.df[self.df["id"].isin(tool_operation_ids)]

        candidates = []
        premium_only_candidates = []

        for _, row in tools_df.iterrows():
            tool_id = row["id"]
            tool_plan_raw = row["x-starting-plan"]
            if tool_plan_raw is None:
                tool_plan_raw = 'basic'

            tool_plan_key = tool_plan_raw.lower()
            tool_plan_int = self.plan_to_int.get(tool_plan_key)
            if tool_plan_int is None:
                raise ValueError(f"Wrong tool_starting_plan: '{tool_plan_key}'")

            if user_plan_int >= tool_plan_int:
                candidates.append(tool_id)
            else:
                premium_only_candidates.append(tool_id)

        return candidates, premium_only_candidates


def build_openai_tools_subset(tool_list):
    def expand_parameters(params):
        if (
            "properties" in params and
            "params" in params["properties"] and
            "$ref" in params["properties"]["params"] and
            "$defs" in params
        ):
            ref_path = params["properties"]["params"]["$ref"]
            ref_name = ref_path.split("/")[-1]
            schema = params["$defs"].get(ref_name, {})
            return {
                "type": "object",
                "properties": {
                    "params": {
                        "type": "object",
                        "properties": schema.get("properties", {}),
                        "required": schema.get("required", []),
                        "description": schema.get("description", "")
                    }
                },
                "required": ["params"]
            }
        else:
            return params

    tools = []
    for tool in tool_list:
        expanded_parameters = expand_parameters(tool.parameters)
        tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "No description provided.",
                "parameters": expanded_parameters
            }
        })
    # [t for t in tools if t["function"]["name"] in ["GetTimeSeriesAdd", "GetTimeSeriesAd"]]
    return tools
