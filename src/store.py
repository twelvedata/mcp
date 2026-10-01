"""The local login's account→api_token map, in ``~/.twelvedata_mcp/sessions.json``.

Keyed by **user_id** and not by ``Mcp-Session-Id``: the SDK keeps session ids only in an
in-memory dict of live transports, so after a restart the client re-initialises with a new
id and nothing keyed by the old one could be resolved again. The user is what survives.

Only the local login writes here. A hosted deployment keeps no user state: identity and the
data-plane credential come from each request's verified token.
"""

from __future__ import annotations

from auth import load_session_tokens, write_sessions


class Store:
    def warm(self, persisted_sessions: dict[str, str]) -> None:
        """Load the stored accounts into the in-memory map at startup."""
        persisted_sessions.update(load_session_tokens())

    def save_user(self, user_id: str, api_token: str) -> None:
        sessions = load_session_tokens()
        sessions[user_id] = api_token
        write_sessions(sessions)

    def save_user_from_profile(self, api_token: str, profile: dict) -> str:
        """Derive a stable user_id from a Twelve Data profile and persist the
        user→api_token mapping. Returns the user_id. Single source of the
        user_id derivation rule, shared by the OAuth callback and oauth_login."""
        inner   = profile.get("data", profile)
        user_id = str(inner.get("id") or inner.get("email") or api_token[:16])
        self.save_user(user_id, api_token)
        return user_id


store = Store()
