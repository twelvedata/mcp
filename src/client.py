"""Twelve Data API HTTP client."""

from __future__ import annotations

import os
from typing import Any

import httpx

API_BASE = "https://api.twelvedata.com"


class TwelveDataClient:
    def __init__(self, api_key: str = ""):
        self._api_key = api_key or os.environ.get("TWELVE_DATA_API_KEY", "")

    async def get(self, endpoint: str, **params: Any) -> "dict | str":
        if not self._api_key:
            return {
                "status": "error",
                "message": (
                    "Not authenticated. Run oauth_login or set the "
                    "TWELVE_DATA_API_KEY environment variable."
                ),
            }
        clean = {k: str(v) for k, v in params.items() if v is not None}
        clean["format"] = "CSV"
        try:
            async with httpx.AsyncClient(timeout=30.0) as http:
                resp = await http.get(
                    f"{API_BASE}/{endpoint}",
                    headers={"Authorization": f"apikey {self._api_key}"},
                    params=clean,
                )
                try:
                    body = resp.json()  # error envelope or JSON-only endpoints
                except Exception:
                    body = None

                if resp.is_success:
                    return body if body is not None else resp.text  # CSV response

                # HTTP error (plan gating comes as 403 or 404). Twelve Data
                # usually carries details in a JSON envelope; keep them but
                # always stamp the HTTP status into `code` so downstream still
                # has it when the body lacks it or isn't JSON.
                if isinstance(body, dict):
                    body.setdefault("status", "error")
                    body.setdefault("code", resp.status_code)
                    return body
                return {
                    "status": "error",
                    "code": resp.status_code,
                    "message": f"HTTP {resp.status_code}: {resp.text[:300]}",
                }
        except httpx.RequestError as exc:
            return {"status": "error", "message": f"Request failed: {exc}"}
