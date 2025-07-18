import json
import csv
from pathlib import Path

OPENAPI_PATH = "../extra/openapi_clean.json"
ENDPOINTS_PATH = "../extra/endpoints_spec_en.csv"
OUTPUT_PATH = "../data/tools_autogen.py"


def load_csv_paths(path):
    with open(path, newline='', encoding='utf-8') as f:
        return [row[0] for i, row in enumerate(csv.reader(f)) if i > 0 and row]


def load_openapi_spec(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def collect_operations(paths, spec):
    ops = []
    seen = set()
    for path in paths:
        path_item = spec.get("paths", {}).get(path)
        if not path_item:
            continue
        for method, details in path_item.items():
            op_id = details.get("operationId")
            if not op_id or op_id in seen:
                continue
            seen.add(op_id)
            desc = details.get("description", "").strip().replace('"', '\\"').replace('\n', ' ')
            ops.append((op_id, desc, path.lstrip('/')))
    return ops


def generate_code(ops):
    def fix_case(name: str) -> str:
        return name[0].upper() + name[1:] if name.lower().startswith("advanced") else name

    lines = [
        'from mcp.server import FastMCP',
        'from mcp.server.fastmcp import Context',
        ''
    ]

    # Import request models
    for op, _, _ in ops:
        lines.append(f'from .request_models import {fix_case(op)}Request')
    lines.append('')

    # Import response models
    for op, _, _ in ops:
        lines.append(f'from .response_models import {fix_case(op)}200Response')
    lines.append('')

    # Register tools
    lines.append('def register_all_tools(server: FastMCP, _call_endpoint):')
    for op, desc, key in ops:
        fixed_op = fix_case(op)
        lines += [
            f'    @server.tool(name="{op}",',
            f'                 description="{desc}")',
            f'    async def {op}(params: {fixed_op}Request, ctx: Context) -> {fixed_op}200Response:',
            f'        return await _call_endpoint("{key}", params, {fixed_op}200Response, ctx)',
            ''
        ]
    return '\n'.join(lines)


def main():
    spec = load_openapi_spec(OPENAPI_PATH)
    csv_paths = load_csv_paths(ENDPOINTS_PATH)
    all_spec_paths = list(spec.get("paths", {}).keys())
    extra_paths = sorted(set(all_spec_paths) - set(csv_paths))
    final_paths = csv_paths + extra_paths

    ops = collect_operations(final_paths, spec)
    total = len(ops)
    from_csv = len([op for op in ops if '/' + op[2] in csv_paths])
    from_extra = total - from_csv

    print(f"[INFO] Loaded {len(csv_paths)} paths from CSV.")
    print(f"[INFO] Found {len(all_spec_paths)} paths in OpenAPI spec.")
    print(f"[INFO] Added {from_extra} additional paths not listed in CSV.")
    print(f"[INFO] Generated {total} tools in total.")

    code = '# AUTOGENERATED FILE - DO NOT EDIT MANUALLY\n\n' + generate_code(ops)
    Path(OUTPUT_PATH).write_text(code, encoding='utf-8')
    print(f"[SUCCESS] File written to: {OUTPUT_PATH}")


if __name__ == '__main__':
    main()
