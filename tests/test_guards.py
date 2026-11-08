"""Reproduction case for the context-budget truncation guard.

A deeply nested API payload — a dense time-series where every row carries a whole
block of technical indicators — is not bounded by the upstream ``outputsize``
cap alone: the serialized JSON can still exceed the caller's context window and
blow memory once it reaches the LLM. These tests pin the guard's behavior on
exactly that shape.
"""

from __future__ import annotations

import json

from guards import (
    CONTEXT_BUDGET_BYTES,
    CONTEXT_BUDGET_MAX_ROWS,
    TRUNCATION_REASON,
    enforce_budget,
)

# One row dense enough to blow the budget quickly: an OHLCV block plus the
# battery of indicators a technical-indicator response carries per item.
_INDICATORS = {
    "open": 100.0,
    "high": 102.5,
    "low": 99.0,
    "close": 101.25,
    "volume": 1234567,
    "rsi": 57.31,
    "macd": 0.42,
    "macd_signal": 0.38,
    "macd_hist": 0.04,
    "sma_20": 100.9,
    "sma_50": 98.7,
    "ema_12": 100.6,
    "bb_upper": 103.1,
    "bb_lower": 97.9,
    "atr": 1.4,
    "stoch_k": 71.2,
    "stoch_d": 66.8,
    "adx": 28.4,
    "cci": 112.0,
}


def _nested_payload(items: int = 250) -> dict:
    """A nested, indicator-dense response shaped like a raw Twelve Data payload."""
    return {
        "meta": {"symbol": "AAPL", "interval": "1day", "items": items},
        "values": [
            {"datetime": f"2024-01-{i % 28 + 1:02d}", **_INDICATORS, "note": None}
            for i in range(items)
        ],
    }


def test_nested_payload_exceeding_budget_is_truncated() -> None:
    payload = _nested_payload()

    # The premise: outputsize does not save us — the nested shape still exceeds
    # the context budget once serialized.
    assert len(json.dumps(payload).encode("utf-8")) > CONTEXT_BUDGET_BYTES

    out = enforce_budget(payload)
    envelope = json.loads(out)  # must still be valid JSON

    assert envelope["_truncated"] is True
    assert envelope["reason"] == TRUNCATION_REASON
    assert isinstance(envelope["data"], dict)

    rows = envelope["data"].get("values", [])
    # Rows were trimmed, but a useful slice survived.
    assert 0 < len(rows) < len(payload["values"])
    assert len(rows) <= CONTEXT_BUDGET_MAX_ROWS

    # The guard's promise: the delivered envelope fits the context budget.
    assert len(out.encode("utf-8")) <= CONTEXT_BUDGET_BYTES

    # Redundant null fields are dropped rather than shipped to the model.
    assert all(value is not None for row in rows for value in row.values())


def test_small_payload_passes_through_untouched() -> None:
    small = {"meta": {"symbol": "AAPL"}, "values": [{"datetime": "2024-01-01", "close": 101.25}]}
    assert enforce_budget(small) == json.dumps(small)
