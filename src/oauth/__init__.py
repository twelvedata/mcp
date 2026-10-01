"""Resource-Server wiring for the Twelve Data MCP server.

Public surface:
  build_auth(exchanger) -> (TokenVerifier, AuthSettings) | (None, None)
  ENABLED      -> whether tokens are verified
  LOCAL_MODE   -> whether this process serves one operator on their own machine

This server issues no tokens, and verifies none by itself: the Twelve Data Authorization
Server's token exchange is the verification, and that server is the only entry in the
protected-resource document this one serves.
"""

from __future__ import annotations

import logging

from oauth.config import (
    API_RESOURCE,
    AUTH_ISSUER_URL,
    ENABLED,
    EXCHANGE_CLIENT_ID,
    EXCHANGE_CLIENT_SECRET,
    LOCAL_MODE,
    NEGATIVE_CACHE_MAX,
    SCOPE,
    resource_url,
)

# What this package re-exports, and LOCAL_MODE is here because nothing below reads it: the
# docstring calls it public surface, and __all__ is what makes that true.
__all__ = ["ENABLED", "LOCAL_MODE", "build_auth"]

log = logging.getLogger("oauth")


def build_auth(exchanger=None):
    """Build the token verifier and the SDK's auth settings, or (None, None) when off.

    Verification is off for stdio / local Claude Desktop, which authenticates through the
    oauth_login tool instead. The exchanger is the verification; everything before it is
    checked first, so a refusal names what is missing without one.
    """
    if not ENABLED:
        return None, None

    try:
        from verifier import TwelveDataTokenVerifier
    except ImportError as exc:
        # Imported here and not at module scope so that a checkout without it can
        # still serve local mode, which reaches this function only to return above. Checked
        # first: without the verifier none of the values below would help.
        raise RuntimeError(  # noqa: TRY003 — the operator reads this at boot
            "MCP_DATA_PUBLIC_URL is set, so this server would verify tokens — but this "
            "checkout does not carry the verifier. The published distribution is the local "
            "one; a hosted deployment is run by Twelve Data."
        ) from exc

    missing = [
        name
        for name, value in (
            ("MCP_DATA_AUTH_ISSUER_URL", AUTH_ISSUER_URL),
            ("MCP_DATA_EXCHANGE_CLIENT_ID", EXCHANGE_CLIENT_ID),
            ("MCP_DATA_EXCHANGE_CLIENT_SECRET", EXCHANGE_CLIENT_SECRET),
            ("MCP_DATA_API_RESOURCE", API_RESOURCE),
        )
        if not value
    ]
    if missing:
        # Loud at boot rather than per request: without these every request carrying a new
        # token is refused — 503, or 401 when it is the issuer that is blank — which from
        # outside looks like a fault in this server.
        raise RuntimeError(
            "MCP_DATA_PUBLIC_URL is set, so this server runs as a Resource Server, but "
            + ", ".join(missing)
            + (" is" if len(missing) == 1 else " are")
            + " missing. It has every token verified by exchanging it at the Authorization "
            "Server for a data-plane credential, and neither half works without these."
        )

    from mcp.server.auth.settings import AuthSettings

    if exchanger is None:
        raise RuntimeError("build_auth needs the exchanger: it is the verification")  # noqa: TRY003 — a wiring error
    verifier = TwelveDataTokenVerifier(
        exchanger,
        issuer=AUTH_ISSUER_URL,
        audience=resource_url(),
        api_resource=API_RESOURCE,
        negative_cache_max=NEGATIVE_CACHE_MAX,
    )
    settings = AuthSettings(
        # The single value the SDK copies into the protected-resource document's
        # authorization_servers: this server names the Authorization Server and never itself.
        issuer_url=AUTH_ISSUER_URL,
        resource_server_url=resource_url(),
        required_scopes=[SCOPE],
        # Explicit: with resource_server_url set and this unset the SDK warns and behaves as
        # False, so no audience is checked at its layer. It is the second gate and
        # deliberately the weaker one — it compares parsed URLs, byte-exactness is ours.
        validate_token_resource=True,
    )
    log.info("oauth: resource server enabled (issuer=%s resource=%s)", AUTH_ISSUER_URL, resource_url())
    return verifier, settings
