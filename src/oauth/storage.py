"""Redis persistence for OAuth artifacts (the Authorization Server state).

This is deliberately separate from the user/session store in ``src/store.py``:
that one maps ``user_id → td_apikey``; this one holds the OAuth machinery —
registered client *applications*, pending authorize requests, authorization
codes, and issued access/refresh tokens. Both reuse the same Redis connection
(``store.redis``) so there is a single client and one fallback behaviour.

OAuth requires Redis: if it is unavailable the server cannot durably issue or
validate tokens, so the helpers degrade to returning None (the SDK then emits
the appropriate OAuth error) rather than silently using volatile memory.

Key layout
----------
  td:oauth:client:<client_id>   json OAuthClientInformationFull
  td:oauth:authreq:<td_state>   json pending authorize request (TTL = CODE_TTL)
  td:oauth:code:<code>          json TDAuthorizationCode          (TTL = CODE_TTL)
  td:oauth:access:<token>       json TDAccessToken                (TTL = ACCESS_TTL)
  td:oauth:refresh:<token>      json TDRefreshToken               (TTL = REFRESH_TTL)
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from mcp.shared.auth import OAuthClientInformationFull

from store import store
from oauth import models
from oauth.config import ACCESS_TTL, CODE_TTL, REFRESH_TTL

log = logging.getLogger("oauth.storage")

_CLIENT  = "td:oauth:client:{cid}"
_AUTHREQ = "td:oauth:authreq:{st}"
_CODE    = "td:oauth:code:{code}"
_ACCESS  = "td:oauth:access:{tok}"
_REFRESH = "td:oauth:refresh:{tok}"


def _r():
    return store.redis


def available() -> bool:
    return _r() is not None


# -- clients (Dynamic Client Registration) -------------------------------------

def save_client(client: OAuthClientInformationFull) -> None:
    r = _r()
    if r is None or not client.client_id:
        return
    r.set(_CLIENT.format(cid=client.client_id), client.model_dump_json())


def get_client(client_id: str) -> Optional[OAuthClientInformationFull]:
    r = _r()
    if r is None:
        return None
    raw = r.get(_CLIENT.format(cid=client_id))
    if not raw:
        return None
    try:
        return OAuthClientInformationFull.model_validate_json(raw)
    except Exception as exc:  # pragma: no cover
        log.warning("oauth: corrupt client record %s (%s)", client_id, exc)
        return None


# -- pending authorize requests (correlation across the TD upstream hop) -------

def save_authreq(td_state: str, data: dict) -> None:
    r = _r()
    if r is None:
        return
    r.setex(_AUTHREQ.format(st=td_state), CODE_TTL, json.dumps(data))


def is_authreq(td_state: str) -> bool:
    """Non-destructive check: does this state belong to an AS authorize request?
    Used by the shared /callback route to tell the OAuth flow from the legacy one."""
    r = _r()
    if r is None or not td_state:
        return False
    return bool(r.exists(_AUTHREQ.format(st=td_state)))


def pop_authreq(td_state: str) -> Optional[dict]:
    r = _r()
    if r is None or not td_state:
        return None
    key = _AUTHREQ.format(st=td_state)
    raw = r.get(key)
    if raw is None:
        return None
    r.delete(key)  # single-use
    try:
        return json.loads(raw)
    except Exception:  # pragma: no cover
        return None


# -- authorization codes -------------------------------------------------------

def save_code(code: models.TDAuthorizationCode) -> None:
    r = _r()
    if r is None:
        return
    r.setex(_CODE.format(code=code.code), CODE_TTL, code.model_dump_json())


def get_code(code: str) -> Optional[models.TDAuthorizationCode]:
    r = _r()
    if r is None:
        return None
    raw = r.get(_CODE.format(code=code))
    if not raw:
        return None
    try:
        return models.TDAuthorizationCode.model_validate_json(raw)
    except Exception:  # pragma: no cover
        return None


def delete_code(code: str) -> None:
    r = _r()
    if r is not None:
        r.delete(_CODE.format(code=code))


# -- access / refresh tokens ---------------------------------------------------

def save_access(tok: models.TDAccessToken) -> None:
    r = _r()
    if r is None:
        return
    r.setex(_ACCESS.format(tok=tok.token), ACCESS_TTL, tok.model_dump_json())


def get_access(token: str) -> Optional[models.TDAccessToken]:
    r = _r()
    if r is None:
        return None
    raw = r.get(_ACCESS.format(tok=token))
    if not raw:
        return None
    try:
        return models.TDAccessToken.model_validate_json(raw)
    except Exception:  # pragma: no cover
        return None


def delete_access(token: str) -> None:
    r = _r()
    if r is not None:
        r.delete(_ACCESS.format(tok=token))


def save_refresh(tok: models.TDRefreshToken) -> None:
    r = _r()
    if r is None:
        return
    r.setex(_REFRESH.format(tok=tok.token), REFRESH_TTL, tok.model_dump_json())


def get_refresh(token: str) -> Optional[models.TDRefreshToken]:
    r = _r()
    if r is None:
        return None
    raw = r.get(_REFRESH.format(tok=token))
    if not raw:
        return None
    try:
        return models.TDRefreshToken.model_validate_json(raw)
    except Exception:  # pragma: no cover
        return None


def delete_refresh(token: str) -> None:
    r = _r()
    if r is not None:
        r.delete(_REFRESH.format(tok=token))
