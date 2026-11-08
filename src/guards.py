"""Context & Rate Safety Layer.

Two guards that sit on the boundary between the Twelve Data data plane and the
LLM caller, so a single oversized financial response cannot blow the caller's
context window and an upstream failure cannot leak a traceback into the
conversation:

- ``enforce_budget`` caps JSON tool payloads. When a serialized response exceeds
  the context budget it is reduced — redundant null fields dropped, then list
  rows truncated — and wrapped in a truncation envelope so the truncation is
  explicit rather than a silent loss of data.

- ``error_envelope`` renders upstream failures (rate limits, 500s, anything
  unexpected) as clean, machine-readable JSON carrying the standard fields
  ``code``, ``status`` and ``retry_after``, instead of a raw traceback.

Both are pure standard-library and configurable through the environment, so the
layer adds no dependency and stays out of the way until a payload or a refusal
actually crosses the line.
"""

from __future__ import annotations

import json
import os
from typing import Any

# Context budget, in bytes of the serialized JSON payload. 16 KiB is comfortably
# under the window of any current model while still carrying a useful slice of a
# time-series or indicator response. Read once at import, like the rest of the
# environment-derived configuration in this repository.
CONTEXT_BUDGET_BYTES = int(os.environ.get("MCP_CONTEXT_BUDGET_BYTES", "16384") or "16384")

# Largest number of rows kept in any list when a payload must be truncated.
CONTEXT_BUDGET_MAX_ROWS = int(os.environ.get("MCP_CONTEXT_BUDGET_MAX_ROWS", "100") or "100")

TRUNCATION_REASON = "payload_exceeds_context_budget"


def enforce_budget(data: Any) -> str:
    """Serialize ``data``, truncating JSON payloads that exceed the context budget.

    Strings are CSV (or already-formatted text) and pass through untouched; the
    row cap for those is applied at the call site. Dicts and lists are the JSON
    tools' output, and it is those the budget guards.

    Returns a JSON string. When the payload fits it is returned verbatim; when it
    does not, the payload is reduced and wrapped in ``{"_truncated": true,
    "reason": "payload_exceeds_context_budget", "data": ...}`` so the caller can
    tell truncation apart from a genuinely short answer.
    """
    if isinstance(data, str):
        return data

    text = json.dumps(data)
    if _size(text) <= CONTEXT_BUDGET_BYTES:
        return text

    reduced = _drop_nulls(data)
    rows = CONTEXT_BUDGET_MAX_ROWS
    while rows >= 1:
        candidate = _truncate_rows(reduced, rows)
        envelope = {"_truncated": True, "reason": TRUNCATION_REASON, "data": candidate}
        text = json.dumps(envelope)
        if _size(text) <= CONTEXT_BUDGET_BYTES:
            return text
        rows //= 2

    # Fail-safe: nothing above fits, so keep the signal and drop the rows. The
    # caller still learns the budget was exceeded instead of receiving a giant,
    # unusable blob or an unhandled error.
    return json.dumps({"_truncated": True, "reason": TRUNCATION_REASON, "data": []})


def error_envelope(code: str, status: int, message: str, retry_after: Any = None) -> str:
    """Render an upstream failure as a clean, machine-readable JSON envelope.

    ``retry_after`` is normalized to an integer when the upstream sent a numeric
    value; otherwise it is kept as-is (or omitted when absent).
    """
    envelope: dict = {"code": code, "status": status, "message": message}
    if retry_after not in (None, ""):
        try:
            envelope["retry_after"] = int(retry_after)
        except (TypeError, ValueError):
            envelope["retry_after"] = retry_after
    return json.dumps(envelope)


def _size(text: str) -> int:
    return len(text.encode("utf-8"))


def _drop_nulls(value: Any) -> Any:
    """Recursively drop dict keys whose value is None (redundant null fields)."""
    if isinstance(value, dict):
        return {k: _drop_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_drop_nulls(v) for v in value]
    return value


def _truncate_rows(value: Any, max_rows: int) -> Any:
    """Recursively cap every list to its first ``max_rows`` elements."""
    if isinstance(value, list):
        return [_truncate_rows(v, max_rows) for v in value[:max_rows]]
    if isinstance(value, dict):
        return {k: _truncate_rows(v, max_rows) for k, v in value.items()}
    return value
