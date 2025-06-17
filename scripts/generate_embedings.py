import os
import json
from typing import cast

import yaml
import openai
import lancedb
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam

def load_spec(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) if path.lower().endswith(('.yaml', '.yml')) else json.load(f)

def extract_endpoints(spec: dict) -> list[dict]:
    paths = spec.get('paths', {})
    components = spec.get('components', {})

    def resolve_ref(obj):
        if isinstance(obj, dict):
            if '$ref' in obj:
                ref_path = obj['$ref'].lstrip('#/').split('/')
                resolved = spec
                for part in ref_path:
                    resolved = resolved.get(part, {})
                return resolve_ref(resolved)
            else:
                return {k: resolve_ref(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [resolve_ref(item) for item in obj]
        return obj

    endpoints = []
    for path, methods in paths.items():
        for method, op in methods.items():
            if not isinstance(op, dict):
                continue

            parameters = op.get('parameters', [])
            request_body = op.get('requestBody', {})
            responses = []

            for code, raw_resp in op.get('responses', {}).items():
                resolved_resp = resolve_ref(raw_resp)
                content = resolved_resp.get('content', {})
                resolved_content = {}

                for mime_type, mime_obj in content.items():
                    schema = mime_obj.get('schema', {})
                    resolved_schema = resolve_ref(schema)
                    resolved_content[mime_type] = {
                        'schema': resolved_schema
                    }

                responses.append({
                    'code': code,
                    'description': resolved_resp.get('description', ''),
                    'content': resolved_content
                })

            endpoints.append({
                'path': path,
                'method': method.upper(),
                'summary': op.get('summary', ''),
                'description': op.get('description', ''),
                'parameters': parameters,
                'requestBody': request_body,
                'responses': responses,
                'operationId': op.get('operationId', f'{method}_{path}')
            })

    return endpoints

def generate_llm_description(info: dict) -> str:
    prompt = (
        "You are an OpenAPI endpoint explainer. Your goal is to produce a clear, concise, and "
        "natural-language explanation of the given API endpoint based on its metadata. "
        "This description will be embedded into a vector space for solving a top-N retrieval task. "
        "Given a user query, the system will compare it semantically to these embeddings to find "
        "the most relevant endpoints. Therefore, the output must reflect both the purpose of the "
        "endpoint and its parameter semantics using natural language.\n\n"
        "Please summarize the endpoint's purpose, its key input parameters and their roles, and "
        "what the endpoint returns. You may include short usage context or constraints to help clarify its behavior. "
        "Do not echo raw JSON. Avoid listing all optional or less relevant fields unless necessary for understanding.\n"
        "Instead of showing URL-style query examples, include two or three natural-language questions "
        "a user might ask that this endpoint could satisfy. These examples will help optimize the embedding "
        "for semantic search over user queries."
    )
    client = openai.OpenAI()
    messages = [
        cast(ChatCompletionSystemMessageParam, {"role": "system", "content": prompt}),
        cast(ChatCompletionUserMessageParam, {"role": "user", "content": json.dumps(info, indent=2)})
    ]

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.3
    )

    return response.choices[0].message.content.strip()

def generate_embedding(text: str) -> list[float]:
    response = openai.OpenAI().embeddings.create(
        model="text-embedding-3-small",
        input=[text]
    )
    return response.data[0].embedding

def load_existing_descriptions(path: str) -> dict:
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_descriptions(path: str, data: dict):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    spec_path = os.getenv('OPENAPI_SPEC', '../extra/openapi_clean.json')
    db_path = os.getenv('LANCEDB_PATH', '../data/endpoints.lancedb')
    desc_path = os.getenv('DESC_JSON_PATH', '../extra/full_descriptions.json')

    spec = load_spec(spec_path)
    endpoints = extract_endpoints(spec)

    full_descriptions = load_existing_descriptions(desc_path)
    records = []

    for info in endpoints:
        try:
            operation_id = info.get('operationId', f"{info['method']}_{info['path']}")
            if operation_id in full_descriptions:
                description = full_descriptions[operation_id]
            else:
                description = generate_llm_description(info)
                full_descriptions[operation_id] = description
                save_descriptions(desc_path, full_descriptions)  # Save on each iteration

            print(f"\n--- LLM Description for {info['method']} {info['path']} ---\n{description}\n")
            vector = generate_embedding(description)

            records.append({
                'id': operation_id,
                'vector': vector,
                'path': info['path'],
                'method': info['method'],
                'summary': info['summary'],
                'description': info['description'],
            })
        except Exception as e:
            print(f"Error processing {info['method']} {info['path']}: {e}")

    db = lancedb.connect(db_path)
    db.create_table(name='endpoints', data=records, mode='overwrite')

    save_descriptions(desc_path, full_descriptions)
    print(f"Indexed {len(records)} endpoints into '{db_path}' and saved LLM descriptions to '{desc_path}'.")

if __name__ == '__main__':
    main()
