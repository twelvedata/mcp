import json
import lancedb
import openai
from pathlib import Path


def patch_one_vector(
    operation_id: str,
    db_path: str = "../src/mcp_server_twelve_data/resources/endpoints.lancedb",
    table_name: str = "endpoints",
    desc_path: str = "../extra/full_descriptions.json",
    verbose: bool = True
):
    desc_file = Path(desc_path)
    if not desc_file.exists():
        raise FileNotFoundError(f"{desc_path} not found")

    with desc_file.open("r", encoding="utf-8") as f:
        full_descriptions = json.load(f)

    if operation_id not in full_descriptions:
        raise ValueError(f"No description found for operation_id '{operation_id}'")

    new_description = full_descriptions[operation_id]

    embedding = openai.OpenAI().embeddings.create(
        model="text-embedding-3-small",
        input=[new_description]
    ).data[0].embedding

    db = lancedb.connect(db_path)
    table = db.open_table(table_name)

    matches = table.to_arrow().to_pylist()
    record = next((row for row in matches if row["id"] == operation_id), None)

    if not record:
        raise ValueError(f"operation_id '{operation_id}' not found in LanceDB")

    if verbose:
        print(f"Updating vector for operation_id: {operation_id}")
        print(f"Old description:\n{record['description']}\n")
        print(f"New description:\n{new_description}\n")

    table.update(
        where=f"id == '{operation_id}'",
        values={
            "description": new_description,
            "vector": embedding
        }
    )

    if verbose:
        print("Update complete.")


if __name__ == "__main__":
    patch_one_vector("GetETFsList")
