"""Deployment mode, and the values a Resource Server needs, read from the environment.

Two questions get two answers here. ENABLED says whether this process verifies tokens;
LOCAL_MODE says whether it serves one operator on their own machine. One boolean answering
both is what let a hosted deployment with verification switched off report itself "local"
and hand a multi-tenant diagnostic dump — and one tenant's api_token — to any caller.

Hosted mode is turned on by MCP_DATA_PUBLIC_URL, e.g.
    MCP_DATA_PUBLIC_URL=https://mcp.twelvedata.com
"""

from __future__ import annotations

import os

# Public base URL of this server (no trailing slash). Empty => stdio / local Claude
# Desktop, which authenticates through the oauth_login tool.
PUBLIC_URL = os.environ.get("MCP_DATA_PUBLIC_URL", "").rstrip("/")

# "Am I one operator's own process?" Derived from PUBLIC_URL alone and never from ENABLED:
# a signal built on ENABLED answers "local" on a hosted box with MCP_OAUTH_ENABLED=0.
LOCAL_MODE = not PUBLIC_URL

# "Are tokens verified?" A hosted deployment verifies unless explicitly told not to.
# MCP_OAUTH_ENABLED is a local and testing switch and must never be passed to a deployed
# process: on a public deployment it would turn verification off while leaving the
# deployment public.
ENABLED = bool(PUBLIC_URL) and os.environ.get("MCP_OAUTH_ENABLED", "1") not in ("0", "false", "no")

# Single scope representing "access Twelve Data on the user's behalf".
SCOPE = "twelvedata"

# The Authorization Server. One value because three things are derived from it — the `iss`
# every accepted token must carry, the only entry in the protected-resource document's
# authorization_servers, and the exchange endpoint — and a second key would be a second place
# for them to disagree.
AUTH_ISSUER_URL = os.environ.get("MCP_DATA_AUTH_ISSUER_URL", "").rstrip("/")

# What this server authenticates as at the Authorization Server's token endpoint.
# Deliberately not spelled near MCP_DATA_TWELVE_DATA_CLIENT_ID/_SECRET, which are the
# upstream Passport application's credentials: adjacent names are the ones an operator
# pastes into the wrong slot.
EXCHANGE_CLIENT_ID     = os.environ.get("MCP_DATA_EXCHANGE_CLIENT_ID", "")
EXCHANGE_CLIENT_SECRET = os.environ.get("MCP_DATA_EXCHANGE_CLIENT_SECRET", "")

# The resource identifier presented to the data plane, byte-exact: it is the `aud` of the
# exchanged token and api compares it as a string.
API_RESOURCE = os.environ.get("MCP_DATA_API_RESOURCE", "https://api.twelvedata.com")

# Ceiling on resident exchange-cache entries, and — the sweep running at the ceiling rather
# than per insert — also what the cache costs once it has filled, dead entries accumulating
# up to it before one pass drops them. Measured at about 1.1 kB an entry — the subject
# token's digest, the resource, the exchanged RS256 JWT and a timestamp — so ~36 MB, small
# beside a process's working set. What bounds the value is not
# that memory but the sweep: it is O(map), so a ceiling the live-grant population actually
# FILLS costs an event-loop share rising faster than its square, and one process serves
# from that loop.
EXCHANGE_CACHE_MAX = int(os.environ.get("MCP_DATA_EXCHANGE_CACHE_MAX", "32768") or "32768")


# Ceiling on remembered `invalid_grant` refusals. A constant and not a knob: an entry is a
# digest, the resource and a deadline, measured at about 250 B, so the ceiling costs ~16 MB;
# and under a flood of forged tokens the map churns whatever its size, which costs one grant
# read at the Authorization Server per retry of a revoked token while the bound holds.
NEGATIVE_CACHE_MAX = 65536


def resource_url() -> str:
    """Canonical resource identifier = the MCP endpoint clients POST to."""
    return f"{PUBLIC_URL}/mcp"


def token_endpoint() -> str:
    return f"{AUTH_ISSUER_URL}/token"


def as_metadata_url() -> str:
    return f"{AUTH_ISSUER_URL}/.well-known/oauth-authorization-server"


def register_url() -> str:
    return f"{AUTH_ISSUER_URL}/register"


def authorize_url() -> str:
    return f"{AUTH_ISSUER_URL}/authorize"


def revocation_url() -> str:
    return f"{AUTH_ISSUER_URL}/revoke"
