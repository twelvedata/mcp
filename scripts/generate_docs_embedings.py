import os
import uuid
import httpx
import openai
import pandas as pd
import lancedb
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tqdm import tqdm

# === CONFIG ===
load_dotenv('../.env')

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_PATH = os.getenv("LANCEDB_PATH", '../data/docs.lancedb')
OPENAI_MODEL = 'text-embedding-3-small'
DOCS_URL = 'https://twelvedata.com/docs'

client = openai.OpenAI(api_key=OPENAI_API_KEY)


def download_docs(url: str) -> str:
    print(f"Downloading documentation from: {url}")
    response = httpx.get(url, timeout=10)
    response.raise_for_status()
    print("HTML download complete.")
    return response.text


def parse_sections(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    sections = soup.select("section[id]")

    records = []
    for idx, section in enumerate(sections, start=1):
        section_id = section["id"]
        title_el = section.find("h2") or section.find("h3") or section.find("h1")
        title = title_el.get_text(strip=True) if title_el else section_id
        content = section.get_text(separator="\n", strip=True)
        print(f"[{idx}/{len(sections)}] Parsed section: {title}")
        records.append({
            "id": str(uuid.uuid4()),
            "section_id": section_id,
            "title": title,
            "content": content
        })
    return records


def generate_embedding(text: str) -> list[float]:
    response = client.embeddings.create(
        model=OPENAI_MODEL,
        input=[text]
    )
    return response.data[0].embedding


def build_lancedb(records: list[dict], db_path: str):
    df = pd.DataFrame(records)

    print(f"Generating embeddings for {len(df)} sections...")
    vectors = []
    for content in tqdm(df["content"], desc="Embedding"):
        vectors.append(generate_embedding(content))
    df["vector"] = vectors

    db = lancedb.connect(db_path)
    db.create_table("docs", data=df, mode="overwrite")

    print(f"Saved {len(df)} sections to LanceDB at: {db_path}")
    print("Section titles:")
    for title in df["title"]:
        print(f" - {title}")


def main():
    print("Step 1: Downloading HTML")
    html = download_docs(DOCS_URL)

    print("Step 2: Parsing sections")
    records = parse_sections(html)

    print("Step 3: Building LanceDB")
    build_lancedb(records, DB_PATH)


if __name__ == '__main__':
    main()
