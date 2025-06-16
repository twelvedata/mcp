import os
import lancedb
import openai

# Константы
EMBEDDING_MODEL = "text-embedding-3-small"

def generate_embedding(text: str) -> list[float]:
    client = openai.OpenAI()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[text]
    )
    return response.data[0].embedding

def evaluate_queries(query_target_pairs: list[tuple[str, str]]):
    db_path = os.getenv('LANCEDB_PATH', '../extra/endpoints.lancedb')
    db = lancedb.connect(db_path)
    table = db.open_table("endpoints")

    results_summary = []

    for user_query, target_endpoint in query_target_pairs:
        query_vec = generate_embedding(user_query)
        results = table.search(query_vec).metric("cosine").limit(30).to_list()

        top_endpoint = results[0]['path'] if results else None
        target_position = next((i for i, r in enumerate(results) if r['path'] == target_endpoint), None)

        print(f"Query: {user_query}")
        print(f"Target endpoint: {target_endpoint}")
        print(f"Top 1 endpoint: {top_endpoint}")
        print(f"Target position in top 30: {target_position}\n")

        results_summary.append((user_query, target_endpoint, top_endpoint, target_position))

    return results_summary


def main():
    query_target_pairs = [
        ("Show me intraday stock prices for Tesla (TSLA) with 1-minute intervals for the past 3 hours.", "/time_series"),
        ("What is the current exchange rate between USD and EUR?", "/price"),
        ("Get the RSI indicator for Apple (AAPL) over the last 14 days.", "/rsi"),
        ("When did Amazon last split its stock?", "/splits"),
        ("Give me daily closing prices for Bitcoin in the past 6 months.", "/time_series"),
        ("Show the MACD for Microsoft.", "/macd"),
        ("Get Google earnings reports for the last year.", "/earnings"),
        ("Fetch dividend history for Johnson & Johnson.", "/dividends"),
        ("Give me fundamentals for Netflix including P/E ratio.", "/fundamentals"),
        ("What is the latest stock quote for Nvidia?", "/quote"),
        ("Retrieve the Bollinger Bands for Apple.", "/bbands"),
        ("What is the VWAP for Tesla?", "/vwap"),
        ("Get ATR indicator for Amazon.", "/atr"),
        ("What is the stochastic oscillator for MSFT?", "/stoch"),
        ("Show me the EMA for S&P 500.", "/ema"),
        ("Retrieve the ADX indicator for crude oil.", "/adx"),
        ("Get the OBV for Bitcoin.", "/obv"),
        ("What is the highest stock price of Apple in the last 30 days?", "/max"),
        ("Give me the minimum price for TSLA in January 2024.", "/min"),
        ("Get the ROC indicator for Ethereum.", "/roc"),
    ]

    results = evaluate_queries(query_target_pairs)

    print("\nSummary:")
    for row in results:
        print(row)


if __name__ == "__main__":
    main()
