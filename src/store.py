"""Durable session / user / payment store.

Source of truth is Redis (REDIS_URL). When Redis is unavailable the store
degrades gracefully to the on-disk ``sessions.json`` (user→token map) plus the
in-memory caches in ``state.py`` — so stdio / local use keeps working without a
Redis server running.

Why identity, not session-id, is the durable key
------------------------------------------------
The MCP ``Mcp-Session-Id`` is issued by the SDK's StreamableHTTPSessionManager
and lives only in an in-memory dict of *live* transport objects. On restart that
dict is empty, the old id gets a 404, and the client re-initialises with a new
id — there is nothing serialisable to restore. So everything that must survive a
restart (api_token, and your future payment / subscription state) is keyed by
**user_id**, which is stable across reconnects. session_id→user is stored too,
which lets a session resolve across multiple workers sharing one Redis while the
id is still alive.

Redis key layout
----------------
  td:users                       SET  of user_ids
  td:user:<uid>:api_token        STR  Twelve Data api_token
  td:user:<uid>:profile          STR  json profile blob
  td:user:<uid>:meta             HASH free-form per-user state (payments live here)
  td:session:<sid>               HASH {user_id, api_token}  (optional TTL)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from auth import load_session_tokens, write_sessions

log = logging.getLogger("store")

_K_USERS         = "td:users"
_K_USER_TOKEN    = "td:user:{uid}:api_token"
_K_USER_PROFILE  = "td:user:{uid}:profile"
_K_USER_META     = "td:user:{uid}:meta"
_K_SESSION       = "td:session:{sid}"

# Optional TTL (seconds) for session_id→user records. 0/unset = no expiry.
_SESSION_TTL = int(os.environ.get("MCP_SESSION_TTL", "0") or "0") or None


class Store:
    def __init__(self) -> None:
        self._r = None
        url = os.environ.get("REDIS_URL", "").strip()
        if url:
            try:
                import redis  # sync client; touched only on login/startup, not per data request

                r = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
                r.ping()
                self._r = r
                log.info("store: connected to Redis (%s)", url)
            except Exception as exc:  # pragma: no cover - depends on environment
                log.warning("store: Redis unavailable (%s) — falling back to %s", exc, "sessions.json")
                self._r = None

    @property
    def backend(self) -> str:
        return "redis" if self._r is not None else "file"

    @property
    def redis(self):
        """The shared sync Redis client (or None on file fallback).

        The OAuth Authorization Server (src/oauth) reuses this connection so
        there is a single Redis client and one consistent fallback behaviour.
        """
        return self._r

    # -- startup ---------------------------------------------------------------

    def warm(
        self,
        persisted_sessions: dict[str, str],
        session_tokens: dict[str, str],
        session_user_ids: dict[str, str],
    ) -> None:
        """Populate the in-memory caches from the durable store at startup."""
        if self._r is None:
            persisted_sessions.update(load_session_tokens())  # user_id → api_token
            return

        try:
            for uid in self._r.smembers(_K_USERS):
                tok = self._r.get(_K_USER_TOKEN.format(uid=uid))
                if tok:
                    persisted_sessions[uid] = tok
            for key in self._r.scan_iter(match="td:session:*"):
                rec = self._r.hgetall(key)
                sid = key.split("td:session:", 1)[-1]
                if rec.get("api_token"):
                    session_tokens[sid] = rec["api_token"]
                if rec.get("user_id"):
                    session_user_ids[sid] = rec["user_id"]
            log.info(
                "store: warmed %d user(s), %d session(s) from Redis",
                len(persisted_sessions), len(session_tokens),
            )
        except Exception as exc:  # pragma: no cover
            log.warning("store: warm from Redis failed (%s)", exc)

    # -- users -----------------------------------------------------------------

    def save_user(self, user_id: str, api_token: str, profile: dict) -> None:
        if self._r is None:
            sessions = load_session_tokens()
            sessions[user_id] = api_token
            write_sessions(sessions)
            return
        try:
            pipe = self._r.pipeline()
            pipe.sadd(_K_USERS, user_id)
            pipe.set(_K_USER_TOKEN.format(uid=user_id), api_token)
            pipe.set(_K_USER_PROFILE.format(uid=user_id), json.dumps(profile))
            pipe.execute()
        except Exception as exc:  # pragma: no cover
            log.warning("store: save_user(%s) failed (%s)", user_id, exc)

    def save_user_from_profile(self, api_token: str, profile: dict) -> str:
        """Derive a stable user_id from a Twelve Data profile and persist the
        user→api_token mapping. Returns the user_id. Single source of the
        user_id derivation rule, shared by the OAuth callback and oauth_login."""
        inner   = profile.get("data", profile)
        user_id = str(inner.get("id") or inner.get("email") or api_token[:16])
        self.save_user(user_id, api_token, inner)
        return user_id

    def get_user_token(self, user_id: str) -> Optional[str]:
        """Return the api_token for a user_id (Redis, or file fallback)."""
        if not user_id:
            return None
        if self._r is None:
            return load_session_tokens().get(user_id)
        try:
            return self._r.get(_K_USER_TOKEN.format(uid=user_id))
        except Exception as exc:  # pragma: no cover
            log.warning("store: get_user_token(%s) failed (%s)", user_id, exc)
            return None

    def users(self) -> dict[str, str]:
        """Return {user_id: api_token} for all known users."""
        if self._r is None:
            return load_session_tokens()
        try:
            out: dict[str, str] = {}
            for uid in self._r.smembers(_K_USERS):
                tok = self._r.get(_K_USER_TOKEN.format(uid=uid))
                if tok:
                    out[uid] = tok
            return out
        except Exception as exc:  # pragma: no cover
            log.warning("store: users() failed (%s)", exc)
            return {}

    # -- sessions --------------------------------------------------------------

    def save_session(self, session_id: str, user_id: str, api_token: str) -> None:
        if self._r is None or not session_id:
            return
        try:
            key = _K_SESSION.format(sid=session_id)
            self._r.hset(key, mapping={"user_id": user_id, "api_token": api_token})
            if _SESSION_TTL:
                self._r.expire(key, _SESSION_TTL)
        except Exception as exc:  # pragma: no cover
            log.warning("store: save_session(%s) failed (%s)", session_id, exc)

    def get_session(self, session_id: str) -> Optional[dict]:
        if self._r is None or not session_id:
            return None
        try:
            rec = self._r.hgetall(_K_SESSION.format(sid=session_id))
            return rec or None
        except Exception as exc:  # pragma: no cover
            log.warning("store: get_session(%s) failed (%s)", session_id, exc)
            return None

    # -- per-user meta (payments / subscriptions live here) --------------------

    def set_user_field(self, user_id: str, field: str, value: str) -> None:
        if self._r is None:
            return
        try:
            self._r.hset(_K_USER_META.format(uid=user_id), field, value)
        except Exception as exc:  # pragma: no cover
            log.warning("store: set_user_field(%s,%s) failed (%s)", user_id, field, exc)

    def get_user_field(self, user_id: str, field: str) -> Optional[str]:
        if self._r is None:
            return None
        try:
            return self._r.hget(_K_USER_META.format(uid=user_id), field)
        except Exception as exc:  # pragma: no cover
            log.warning("store: get_user_field(%s,%s) failed (%s)", user_id, field, exc)
            return None

    def get_user_meta(self, user_id: str) -> dict:
        if self._r is None:
            return {}
        try:
            return self._r.hgetall(_K_USER_META.format(uid=user_id)) or {}
        except Exception as exc:  # pragma: no cover
            log.warning("store: get_user_meta(%s) failed (%s)", user_id, exc)
            return {}


store = Store()
