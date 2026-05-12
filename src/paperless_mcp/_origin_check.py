"""ASGI middleware: reject HTTP requests whose Origin header is not allowlisted."""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

_log = logging.getLogger(__name__)

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


class OriginAllowlistMiddleware:
    """Block HTTP requests with an Origin not in `allowed`.

    Empty allowlist disables the check (pass-through). Requests without an
    Origin header are allowed (non-browser clients like curl, MCP CLIs).
    """

    def __init__(self, app: Callable[..., Awaitable[None]], allowed: set[str]) -> None:
        self._app = app
        self._allowed = allowed

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") == "http" and self._allowed:
            origin = _origin_from_scope(scope)
            if origin is not None and origin not in self._allowed:
                _log.warning("rejecting request: Origin=%r not allowed", origin)
                await _send_forbidden(send, origin)
                return
        await self._app(scope, receive, send)


def _origin_from_scope(scope: Scope) -> str | None:
    for name, value in scope.get("headers") or []:
        if name == b"origin":
            return value.decode("latin-1") or None
    return None


async def _send_forbidden(send: Send, origin: str) -> None:
    body = f"Origin {origin!r} not in MCP_ALLOWED_ORIGINS".encode()
    await send(
        {
            "type": "http.response.start",
            "status": 403,
            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
        }
    )
    await send({"type": "http.response.body", "body": body})


def parse_allowed_origins(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {o.strip() for o in raw.split(",") if o.strip()}
