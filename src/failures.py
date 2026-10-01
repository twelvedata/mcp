"""Failures of ours, as distinct from refusals the user can act on.

Every tool here answers a refusal with a string, and a returned string is a successful call
whose content happens to say "error" — which is what an agent reads it as. Only a raised
exception reaches the SDK's wrapper and comes back marked `isError`. So the distinction
these types carry is the one an agent can read, and it is the one that decides whether it
retries.

RAISED IS NOT THE SAME AS OURS. `AuthorizationFailure` is raised too, and deliberately: an
agent that cannot see a failure cannot offer the user the one action that fixes it, so the
refusal a user CAN act on has to reach them marked as a failure and carrying the challenge.
"""

from __future__ import annotations


class ToolFailure(Exception):
    """Something on our side did not work. Rendered to the agent with `isError` set."""


class AuthorizationFailure(ToolFailure):
    """The caller's authorization does not cover this call.

    Carries the challenge that goes on the result's `_meta["mcp/www_authenticate"]`, which
    is what lets a client start a linking flow from inside a conversation rather than only
    at install time.
    """

    def __init__(self, message: str, challenge: str = "", error: str = "insufficient_scope") -> None:
        super().__init__(message)
        self.challenge = challenge
        # The RFC 6750 §3.1 code the default challenge is built with. `insufficient_scope` is
        # the scope refusal's, and a revoked or expired credential is `invalid_token`: a client
        # told the former re-authorizes asking for more scope, which is not what is wrong.
        self.error = error
