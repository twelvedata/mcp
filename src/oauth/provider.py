"""Twelve Data Authorization Server provider.

Implements the MCP SDK's OAuthAuthorizationServerProvider by storing all OAuth
state in Redis and delegating the user-authentication step to Twelve Data's
upstream OAuth. The SDK handles client registration, redirect_uri validation
and PKCE verification; this provider only persists and issues artifacts.

The storage layer (oauth/storage.py) uses the shared *synchronous* redis client.
Provider methods run on the ASGI event loop and several are awaited per request
(notably load_access_token, on every authenticated call), so every Redis touch
is offloaded with asyncio.to_thread to avoid blocking the loop. redis-py's sync
client is connection-pooled and thread-safe, so this is safe.

Flow (see authorize() / complete_td_login()):

    client --/authorize--> us --redirect--> Twelve Data /oauth/authorize
                                                  |
    client <--?code&state-- us <--/callback (we mint OUR code)
    client --/token(code+verifier)--> us  ==> access_token (bound to user_id)
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from typing import Optional

from mcp.server.auth.provider import (
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from auth import TwelveDataAuth, load_config
from store import store
from oauth import storage
from oauth.config import ACCESS_TTL, REFRESH_TTL, CODE_TTL, SCOPE, td_callback_url
from oauth.models import TDAccessToken, TDAuthorizationCode, TDRefreshToken

log = logging.getLogger("oauth.provider")


class TwelveDataASProvider(
    OAuthAuthorizationServerProvider[TDAuthorizationCode, TDRefreshToken, TDAccessToken]
):
    def __init__(self) -> None:
        cfg = load_config()
        self._td = TwelveDataAuth(cfg.get("client_id", ""), cfg.get("client_secret", ""))

    # -- client registration (DCR) --------------------------------------------

    async def get_client(self, client_id: str) -> Optional[OAuthClientInformationFull]:
        return await asyncio.to_thread(storage.get_client, client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        await asyncio.to_thread(storage.save_client, client_info)

    # -- authorize: hand the browser off to Twelve Data -----------------------

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        td_state = secrets.token_urlsafe(32)
        await asyncio.to_thread(storage.save_authreq, td_state, {
            "client_id":                        client.client_id,
            "redirect_uri":                     str(params.redirect_uri),
            "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
            "code_challenge":                   params.code_challenge,
            "scopes":                           params.scopes or [SCOPE],
            "state":                            params.state,
            "resource":                         params.resource,
        })
        # Redirect to the upstream IdP; it returns to /callback.
        return self._td.get_auth_url(state=td_state, redirect_uri=td_callback_url())

    async def complete_td_login(self, td_state: str, td_code: str) -> str:
        """Finish the upstream exchange and return the client redirect URL.

        Called by the shared /callback route. Exchanges the Twelve Data code for
        the user's api_token, persists user→apikey, mints OUR authorization code,
        and returns the URL to send the browser back to the MCP client.
        """
        req = await asyncio.to_thread(storage.pop_authreq, td_state)
        if req is None:
            raise ValueError("authorization request expired or already used")

        data      = await self._td._exchange(td_code, redirect_uri=td_callback_url())
        api_token = data.get("api_token")
        if not api_token:
            raise ValueError("Twelve Data did not return an api_token for this account")

        user_id = await asyncio.to_thread(
            store.save_user_from_profile, api_token, data.get("_profile_response", {})
        )

        code = secrets.token_urlsafe(32)
        await asyncio.to_thread(storage.save_code, TDAuthorizationCode(
            code=code,
            scopes=req["scopes"],
            expires_at=time.time() + CODE_TTL,
            client_id=req["client_id"],
            code_challenge=req["code_challenge"],
            redirect_uri=req["redirect_uri"],
            redirect_uri_provided_explicitly=req["redirect_uri_provided_explicitly"],
            resource=req.get("resource"),
            user_id=user_id,
        ))
        return construct_redirect_uri(req["redirect_uri"], code=code, state=req.get("state"))

    # -- token endpoint --------------------------------------------------------

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> Optional[TDAuthorizationCode]:
        ac = await asyncio.to_thread(storage.get_code, authorization_code)
        if ac is None or ac.client_id != client.client_id:
            return None
        return ac

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: TDAuthorizationCode
    ) -> OAuthToken:
        await asyncio.to_thread(storage.delete_code, authorization_code.code)  # single-use
        return await self._issue(authorization_code.user_id, client.client_id, authorization_code.scopes)

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> Optional[TDRefreshToken]:
        rt = await asyncio.to_thread(storage.get_refresh, refresh_token)
        if rt is None or rt.client_id != client.client_id:
            return None
        return rt

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: TDRefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        # Rotate: invalidate the presented refresh token, issue a fresh pair.
        await asyncio.to_thread(storage.delete_refresh, refresh_token.token)
        return await self._issue(refresh_token.user_id, client.client_id, scopes or refresh_token.scopes)

    async def load_access_token(self, token: str) -> Optional[TDAccessToken]:
        at = await asyncio.to_thread(storage.get_access, token)
        if at is None:
            return None
        if at.expires_at and at.expires_at < int(time.time()):
            await asyncio.to_thread(storage.delete_access, token)
            return None
        return at

    async def revoke_token(self, token) -> None:
        # token is a TDAccessToken or TDRefreshToken; revoke both sides.
        await asyncio.to_thread(storage.delete_access, token.token)
        await asyncio.to_thread(storage.delete_refresh, token.token)

    # -- helpers ---------------------------------------------------------------

    async def _issue(self, user_id: str, client_id: str, scopes: list[str]) -> OAuthToken:
        now     = int(time.time())
        access  = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(32)
        await asyncio.to_thread(storage.save_access, TDAccessToken(
            token=access, client_id=client_id, scopes=scopes,
            expires_at=now + ACCESS_TTL, user_id=user_id,
        ))
        await asyncio.to_thread(storage.save_refresh, TDRefreshToken(
            token=refresh, client_id=client_id, scopes=scopes,
            expires_at=now + REFRESH_TTL, user_id=user_id,
        ))
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=ACCESS_TTL,
            scope=" ".join(scopes),
            refresh_token=refresh,
        )
