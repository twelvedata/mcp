"""Which scope each tool needs, and the refusal when a token does not carry it.

Every tool declares the one scope the catalogue holds, so the table refuses nothing today:
what it buys is the machinery and the test, so that widening the catalogue is an edit to
declarations rather than the introduction of a mechanism. The declaration rides on the
tool's own `_meta`, which is what makes the registry walk possible.
"""

from __future__ import annotations

from typing import Iterable, Optional

from failures import AuthorizationFailure

META_KEY = "twelvedata/scope"


def declare(scope: str) -> dict:
    """The `_meta` a registered tool carries."""
    return {META_KEY: scope}


def scope_of(tool) -> Optional[str]:
    meta = getattr(tool, "meta", None) or {}
    declared = meta.get(META_KEY)
    return declared if isinstance(declared, str) and declared else None


def tools_without_scope(tools: Iterable) -> list[str]:
    """The registered tools that declare no scope. A non-empty answer fails the suite."""
    return [tool.name for tool in tools if scope_of(tool) is None]


def check(tool_name: str, required: str, granted: Iterable[str]) -> None:
    """Refuse a call whose token does not carry the tool's scope.

    Named `insufficient_scope` because that is the word a client acts on; it arrives inside
    a 200 as a tool error, the endpoint-level refusal being the SDK's and already past.
    """
    if required in set(granted):
        return
    raise AuthorizationFailure(  # noqa: TRY003 — the client acts on this message
        f"insufficient_scope: {tool_name} requires the {required!r} scope"
    )
