"""ASGI middleware that injects the Auth.md `agent_auth` block into the
OAuth Authorization Server metadata response.

The MCP SDK builds /.well-known/oauth-authorization-server from a fixed
pydantic model with no extension hook, and custom_route handlers are mounted
after the SDK routes (first match wins), so the JSON is patched at the ASGI
layer instead. Every standard field stays SDK-generated; only `agent_auth`
is added on top.
"""

from __future__ import annotations

import json

from oauth.config import agent_auth_metadata

METADATA_PATH = "/.well-known/oauth-authorization-server"


class AgentAuthMetadataMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != METADATA_PATH:
            await self.app(scope, receive, send)
            return

        start_message = None
        body = b""

        async def capture_send(message):
            nonlocal start_message, body
            if message["type"] == "http.response.start":
                start_message = message
            elif message["type"] == "http.response.body":
                body += message.get("body", b"")
                if not message.get("more_body"):
                    await self._send_patched(send, start_message, body)
            else:
                await send(message)

        await self.app(scope, receive, capture_send)

    async def _send_patched(self, send, start_message, body):
        if start_message is None:  # malformed upstream response — pass through
            await send({"type": "http.response.body", "body": body})
            return

        patched = False
        if start_message["status"] == 200 and body:
            try:
                metadata = json.loads(body)
                metadata["agent_auth"] = agent_auth_metadata()
                body = json.dumps(metadata).encode()
                patched = True
            except ValueError:
                pass  # not JSON — leave the original response untouched

        # Rewrite content-length only when the body actually changed, so
        # non-JSON, error, and HEAD responses stay byte-identical.
        if patched:
            headers = [
                (name, value)
                for name, value in (start_message.get("headers") or [])
                if name.lower() != b"content-length"
            ]
            headers.append((b"content-length", str(len(body)).encode()))
            start_message = {**start_message, "headers": headers}

        await send(start_message)
        await send({"type": "http.response.body", "body": body})
