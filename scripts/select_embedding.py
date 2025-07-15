import os
from dotenv import load_dotenv
from lancedb import connect
from openai import OpenAI
import numpy as np
from numpy.linalg import norm

load_dotenv('../.env')
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

query = "Show me tax information for AAPL."
query_vector = np.array(
    client.embeddings.create(input=query, model="text-embedding-3-large").data[0].embedding
)

db = connect("../src/mcp_server_twelve_data/resources/endpoints.lancedb")
tbl = db.open_table("endpoints")
df = tbl.to_pandas()

tax_vector = np.array(df.query("id == 'GetTaxInfo'").iloc[0]["vector"])
balance_vector = np.array(df.query("id == 'GetBalanceSheetConsolidated'").iloc[0]["vector"])


def cosine_similarity(a, b):
    return np.dot(a, b) / (norm(a) * norm(b))


print(f"GetTaxInfo: {cosine_similarity(query_vector, tax_vector):.4f}")
print(f"GetBalanceSheetConsolidated: {cosine_similarity(query_vector, balance_vector):.4f}")
