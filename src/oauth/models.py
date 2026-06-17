"""Token/code models extended with the Twelve Data user_id.

The MCP SDK's OAuthAuthorizationServerProvider is generic over the
authorization-code / refresh-token / access-token types, so we subclass the
base models to carry the ``user_id`` of the Twelve Data account the token was
issued for. Because ``get_access_token()`` returns the very object our
``load_access_token`` produced, the request handler can read ``.user_id``
directly and resolve the user's api_token — no extra lookup, no reliance on the
volatile MCP session id.
"""

from __future__ import annotations

from mcp.server.auth.provider import AccessToken, AuthorizationCode, RefreshToken


class TDAuthorizationCode(AuthorizationCode):
    user_id: str


class TDAccessToken(AccessToken):
    user_id: str


class TDRefreshToken(RefreshToken):
    user_id: str
