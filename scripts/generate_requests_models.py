import json
from pathlib import Path
import keyword

OPENAPI_PATH = "../data/openapi_clean.json"
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

def safe_field_name(name):
    if keyword.iskeyword(name):
        return name + "_"
    return name

def python_type(schema, components):
    if "$ref" in schema:
        ref_name = schema["$ref"].split("/")[-1]
        return canonical_class_name(ref_name, "")
    if "allOf" in schema:
        for subschema in schema["allOf"]:
            return python_type(subschema, components)
    t = schema.get("type", "string")
    if t == "array":
        return f"list[{python_type(schema.get('items', {}), components)}]"
    return PRIMITIVES.get(t, "Any")

def resolve_schema(schema, components):
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

def collect_examples(param, sch):
    examples = []
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
    return [e for i, e in enumerate(examples) if e is not None and e not in examples[:i]]

def gen_field(name, typ, required, desc, examples, default):
    name = safe_field_name(name)
    field_args = []
    if required:
        field_args.append("...")
    else:
        field_args.append(f"default={repr(default)}")
    if desc:
        field_args.append(f'description={repr(desc)}')
    if examples:
        field_args.append(f'examples={repr(examples)}')
    args = ", ".join(field_args)
    return f"    {name}: {typ} = Field({args})"

def gen_class(name, props, desc):
    lines = [f"class {name}(BaseModel):"]
    if desc:
        lines.append(f'    """{desc.replace(chr(34)*3, "")}"""')
    if not props:
        lines.append("    pass")
    else:
        for pname, fdict in props.items():
            typ = fdict["type"]
            required = fdict["required"]
            dsc = fdict["description"]
            exs = fdict["examples"]
            default = fdict["default"]
            lines.append(gen_field(pname, typ, required, dsc, exs, default))
    return "\n".join(lines)

def main():
    with open(OPENAPI_PATH, "r", encoding="utf-8") as f:
        spec = json.load(f)

    components = spec.get("components", {}).get("schemas", {})

    request_models = []
    request_names = set()
    for path, methods in spec["paths"].items():
        for http_method, op in methods.items():
            opid = op.get("operationId")
            if not opid:
                continue
            class_name = canonical_class_name(opid, "Request")
            params = op.get("parameters", [])
            body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
            props = {}
            for param in params:
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
            desc = op.get("description", None)
            # ДОБАВЛЯЕМ apikey:
            props["apikey"] = {
                "type": "str",
                "required": True,
                "description": "API key",
                "examples": ["demo"],
                "default": "demo"
            }
            code = gen_class(class_name, props, desc)
            if class_name not in request_names:
                request_models.append(code)
                request_names.add(class_name)

    Path(REQUESTS_FILE).write_text(
        "from pydantic import BaseModel, Field\nfrom typing import Any, List\n\n"
        + "\n\n".join(request_models),
        encoding="utf-8"
    )
    print(f"Сгенерированы модели запросов: {REQUESTS_FILE}")

if __name__ == "__main__":
    main()
