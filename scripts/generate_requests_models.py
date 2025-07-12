import json
from pathlib import Path
import keyword
from typing import Any, List, Optional

OPENAPI_PATH = "../extra/openapi_clean.json"
REQUESTS_FILE = "../data/request_models.py"

PRIMITIVES = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "object": "dict",
    "array": "list",
}


def canonical_class_name(opid: str, suffix: str) -> str:
    if not opid:
        return ""
    return opid[0].upper() + opid[1:] + suffix


def safe_field_name(name: str) -> str:
    # Append underscore if name is a Python keyword
    if keyword.iskeyword(name):
        return name + "_"
    return name


def python_type(schema: dict, components: dict) -> str:
    # Resolve $ref to the corresponding model class name
    if "$ref" in schema:
        ref_name = schema["$ref"].split("/")[-1]
        return canonical_class_name(ref_name, "")
    # Handle allOf by delegating to the first subschema
    if "allOf" in schema:
        for subschema in schema["allOf"]:
            return python_type(subschema, components)
    t = schema.get("type", "string")
    if t == "array":
        # Construct type for lists recursively
        return f"list[{python_type(schema.get('items', {}), components)}]"
    return PRIMITIVES.get(t, "Any")


def resolve_schema(schema: dict, components: dict) -> dict:
    # Fully resolve $ref and allOf compositions into a merged schema
    if "$ref" in schema:
        ref = schema["$ref"].split("/")[-1]
        return resolve_schema(components.get(ref, {}), components)
    if "allOf" in schema:
        merged = {"properties": {}, "required": [], "description": ""}
        for subschema in schema["allOf"]:
            sub = resolve_schema(subschema, components)
            merged["properties"].update(sub.get("properties", {}))
            merged["required"].extend(sub.get("required", []))
            if sub.get("description"):
                merged["description"] += sub["description"] + "\n"
        merged["required"] = list(set(merged["required"]))
        merged["description"] = merged["description"].strip() or None
        return merged
    return schema


def collect_examples(param: dict, sch: dict) -> List[Any]:
    # Collect all examples from parameter, schema, and enums without deduplication
    examples: List[Any] = []
    if "example" in param:
        examples.append(param["example"])
    if "examples" in param:
        exs = param["examples"]
        if isinstance(exs, dict):
            for v in exs.values():
                examples.append(v["value"] if isinstance(v, dict) and "value" in v else v)
        elif isinstance(exs, list):
            examples.extend(exs)
    if "example" in sch:
        examples.append(sch["example"])
    if "examples" in sch:
        exs = sch["examples"]
        if isinstance(exs, dict):
            for v in exs.values():
                examples.append(v["value"] if isinstance(v, dict) and "value" in v else v)
        elif isinstance(exs, list):
            examples.extend(exs)
    # Include enum values as examples if present
    if "enum" in sch and isinstance(sch["enum"], list):
        examples.extend(sch["enum"])
    return [e for e in examples if e is not None]


def gen_field(name: str, typ: str, required: bool, desc: Optional[str],
              examples: List[Any], default: Any) -> str:
    name = safe_field_name(name)
    # Wrap in Optional[...] if default is None and field is not required
    if default is None and not required:
        typ = f"Optional[{typ}]"
    args: List[str] = []
    if required:
        args.append("...")
    else:
        args.append(f"default={repr(default)}")
    if desc:
        args.append(f"description={repr(desc)}")
    if examples:
        args.append(f"examples={repr(examples)}")
    return f"    {name}: {typ} = Field({', '.join(args)})"


def gen_class(name: str, props: dict, desc: Optional[str]) -> str:
    lines = [f"class {name}(BaseModel):"]
    if desc:
        # Add class docstring if description is present
        lines.append(f'    """{desc.replace(chr(34)*3, "")}"""')
    if not props:
        lines.append("    pass")
    else:
        for pname, fdict in props.items():
            lines.append(gen_field(
                pname,
                fdict["type"],
                fdict["required"],
                fdict["description"],
                fdict["examples"],
                fdict["default"]
            ))
    return "\n".join(lines)


def main():
    # Load the OpenAPI specification
    with open(OPENAPI_PATH, "r", encoding="utf-8") as f:
        spec = json.load(f)

    components = spec.get("components", {}).get("schemas", {})
    request_models: List[str] = []
    request_names: set = set()

    for path, methods in spec.get("paths", {}).items():
        for http_method, op in methods.items():
            opid = op.get("operationId")
            if not opid:
                continue
            class_name = canonical_class_name(opid, "Request")

            # Collect parameters from path, query, header, etc.
            props: dict = {}
            for param in op.get("parameters", []):
                name = param["name"]
                sch = param.get("schema", {"type": "string"})
                typ = python_type(sch, components)
                required = param.get("required", False)
                desc = param.get("description") or sch.get("description")
                examples = collect_examples(param, sch)
                default = sch.get("default", None)
                props[name] = {
                    "type": typ,
                    "required": required,
                    "description": desc,
                    "examples": examples,
                    "default": default,
                }

            # Collect JSON body properties
            body = op.get("requestBody", {}) \
                     .get("content", {}) \
                     .get("application/json", {}) \
                     .get("schema")
            if body:
                body_sch = resolve_schema(body, components)
                for name, sch in body_sch.get("properties", {}).items():
                    typ = python_type(sch, components)
                    required = name in body_sch.get("required", [])
                    desc = sch.get("description")
                    examples = collect_examples({}, sch)
                    default = sch.get("default", None)
                    props[name] = {
                        "type": typ,
                        "required": required,
                        "description": desc,
                        "examples": examples,
                        "default": default,
                    }

            # Add outputsize with detailed description and default=10
            props["outputsize"] = {
                "type": "int",
                "required": False,
                "description": (
                    "Number of data points to retrieve. Supports values in the range from `1` to `5000`. "
                    "Default `10` when no date parameters are set, otherwise set to maximum"
                ),
                "examples": [10],
                "default": 10,
            }

            # Add apikey with default="demo"
            props["apikey"] = {
                "type": "str",
                "required": False,
                "description": "API key",
                "examples": ["demo"],
                "default": "demo",
            }

            if "interval" in props:
                props["interval"]["required"] = False
                props["interval"]["default"] = "1day"

            code = gen_class(class_name, props, op.get("description"))
            if class_name not in request_names:
                request_models.append(code)
                request_names.add(class_name)

    # Write all generated models to the target file
    header = (
        "from pydantic import BaseModel, Field\n"
        "from typing import Any, List, Optional\n\n"
    )
    Path(REQUESTS_FILE).write_text(header + "\n\n".join(request_models), encoding="utf-8")
    print(f"Generated request models: {REQUESTS_FILE}")


if __name__ == "__main__":
    main()
