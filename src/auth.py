"""OAuth 2.0 flow and token management for Twelve Data."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from dotenv import load_dotenv

# Load .env at import time so all env vars are available before any method is called
load_dotenv(Path(__file__).parent.parent / ".env", override=False)

import httpx
from views import callback_page

OAUTH_BASE     = "https://twelvedata.com"
CALLBACK_PORT  = 8765
CONFIG_DIR     = Path.home() / ".twelvedata_mcp"
CONFIG_FILE    = CONFIG_DIR / "config.json"
SESSIONS_FILE  = CONFIG_DIR / "sessions.json"


def load_config() -> dict:
    """Load credentials with the following priority (highest → lowest):

    1. Real env vars already in the process (Docker, systemd, Claude Desktop config)
    2. .env file in the project directory          ← server deployments
    3. ~/.twelvedata_mcp/config.json               ← personal Claude Desktop use
    """
    cfg: dict = {}

    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass

    if os.environ.get("MCP_DATA_TWELVE_DATA_CLIENT_ID"):
        cfg["client_id"] = os.environ["MCP_DATA_TWELVE_DATA_CLIENT_ID"]
    if os.environ.get("MCP_DATA_TWELVE_DATA_CLIENT_SECRET"):
        cfg["client_secret"] = os.environ["MCP_DATA_TWELVE_DATA_CLIENT_SECRET"]
    if os.environ.get("TWELVE_DATA_API_KEY"):
        cfg["api_key"] = os.environ["TWELVE_DATA_API_KEY"]

    return cfg


def load_session_tokens() -> dict[str, str]:
    """Load persisted {user_id: api_token} map from sessions.json."""
    if SESSIONS_FILE.exists():
        try:
            return json.loads(SESSIONS_FILE.read_text())
        except Exception:
            pass
    return {}


def write_sessions(sessions: dict[str, str]) -> None:
    """Write the complete {user_id: api_token} map to sessions.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_FILE.write_text(json.dumps(sessions, indent=2))
    SESSIONS_FILE.chmod(0o600)


def save_config(client_id: str, client_secret: str) -> None:
    """Persist OAuth credentials to ~/.twelvedata_mcp/config.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if CONFIG_FILE.exists():
        try:
            existing = json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    existing.update({"client_id": client_id, "client_secret": client_secret})
    CONFIG_FILE.write_text(json.dumps(existing, indent=2))
    CONFIG_FILE.chmod(0o600)


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/callback":
            params = parse_qs(parsed.query)
            self.server._code = params.get("code", [None])[0]
            self.server._state = params.get("state", [None])[0]
            page = callback_page(
                "Authorization successful",
                '<p class="subtitle">Your API token has been saved and is ready to use.</p>',
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(page.body)
            self.server._event.set()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass  # suppress server access logs


class TwelveDataAuth:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id     = client_id
        self.client_secret = client_secret
        self._token_data: dict | None = None  # in-memory only, set after exchange

    def _redirect_uri(self) -> str:
        override = os.environ.get("MCP_DATA_TWELVE_DATA_REDIRECT_URI", "").strip()
        return override or f"http://localhost:{CALLBACK_PORT}/callback"

    def get_auth_url(self, state: str, redirect_uri: str | None = None) -> str:
        params = urlencode({
            "client_id":     self.client_id,
            "redirect_uri":  redirect_uri or self._redirect_uri(),
            "response_type": "code",
            "state":         state,
        })
        return f"{OAUTH_BASE}/oauth/authorize?{params}"

    async def fetch_user_profile(self, access_token: str) -> dict:
        """Call /api/v1/user/user with the OAuth Bearer token."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{OAUTH_BASE}/api/v1/user/user",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            return {"error": str(exc)}

    async def _exchange(self, code: str, redirect_uri: str | None = None) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{OAUTH_BASE}/oauth/token",
                data={
                    "grant_type":    "authorization_code",
                    "client_id":     self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri":  redirect_uri or self._redirect_uri(),
                    "code":          code,
                },
            )
            resp.raise_for_status()
            data    = resp.json()
            profile = await self.fetch_user_profile(data["access_token"])
            api_token = profile.get("data", profile).get("api_token")
            if api_token:
                data["api_token"] = api_token
            data["_profile_response"] = profile
            self._token_data = data  # in-memory only
            return data

    async def login(self) -> str:
        """stdio transport: open a local HTTP server to receive the OAuth callback."""
        state = secrets.token_urlsafe(16)
        auth_url = self.get_auth_url(state)

        httpd = HTTPServer(("localhost", CALLBACK_PORT), _CallbackHandler)
        httpd._code  = None
        httpd._state = None
        httpd._event = threading.Event()

        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        webbrowser.open(auth_url)

        loop     = asyncio.get_running_loop()
        received = await loop.run_in_executor(None, lambda: httpd._event.wait(120.0))
        httpd.shutdown()

        if not received or not httpd._code:
            return (
                "Timed out waiting for authorization (120 s).\n"
                f"Open this URL manually if needed:\n{auth_url}"
            )

        if httpd._state != state:
            return "State mismatch — possible CSRF. Please try oauth_login again."

        try:
            data      = await self._exchange(httpd._code)
            api_token = data.get("api_token")
            profile   = data.get("_profile_response", {})

            if api_token:
                return (
                    f"Authenticated! api_token saved (…{api_token[-6:]}).\n"
                    f"All API calls will now use this key."
                )

            return (
                "OAuth exchange succeeded but api_token was not found in the user profile.\n"
                f"Profile response: {profile}\n\n"
                "Check that the field name is 'api_token' in the response above, "
                "then update fetch_user_profile() in auth.py if needed."
            )
        except Exception as exc:
            return f"Token exchange failed: {exc}"
