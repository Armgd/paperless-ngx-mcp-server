"""OriginAllowlistMiddleware unit tests — drive ASGI scope directly."""
from __future__ import annotations

import pytest

from paperless_mcp._origin_check import (
    OriginAllowlistMiddleware,
    parse_allowed_origins,
)


class _RecordingApp:
    def __init__(self) -> None:
        self.called = False

    async def __call__(self, scope, receive, send) -> None:
        self.called = True


def _scope(origin: bytes | None) -> dict:
    headers: list[tuple[bytes, bytes]] = []
    if origin is not None:
        headers.append((b"origin", origin))
    return {"type": "http", "headers": headers}


async def _noop_receive() -> dict:
    return {"type": "http.request", "body": b""}


async def test_allows_when_allowlist_empty() -> None:
    app = _RecordingApp()
    mw = OriginAllowlistMiddleware(app, allowed=set())
    sent: list[dict] = []

    async def send(message: dict) -> None:
        sent.append(message)

    await mw(_scope(b"http://evil.example"), _noop_receive, send)
    assert app.called is True
    assert sent == []


async def test_allows_when_origin_in_allowlist() -> None:
    app = _RecordingApp()
    mw = OriginAllowlistMiddleware(app, allowed={"http://localhost:5173"})
    sent: list[dict] = []

    async def send(message: dict) -> None:
        sent.append(message)

    await mw(_scope(b"http://localhost:5173"), _noop_receive, send)
    assert app.called is True


async def test_blocks_when_origin_not_in_allowlist() -> None:
    app = _RecordingApp()
    mw = OriginAllowlistMiddleware(app, allowed={"http://localhost:5173"})
    sent: list[dict] = []

    async def send(message: dict) -> None:
        sent.append(message)

    await mw(_scope(b"http://evil.example"), _noop_receive, send)
    assert app.called is False
    assert sent[0]["status"] == 403


async def test_allows_when_no_origin_header() -> None:
    """Non-browser clients (curl, MCP CLIs) usually have no Origin header."""
    app = _RecordingApp()
    mw = OriginAllowlistMiddleware(app, allowed={"http://localhost:5173"})
    sent: list[dict] = []

    async def send(message: dict) -> None:
        sent.append(message)

    await mw(_scope(None), _noop_receive, send)
    assert app.called is True


async def test_skips_non_http_scope() -> None:
    app = _RecordingApp()
    mw = OriginAllowlistMiddleware(app, allowed={"http://localhost:5173"})
    sent: list[dict] = []

    async def send(message: dict) -> None:
        sent.append(message)

    await mw({"type": "lifespan", "headers": []}, _noop_receive, send)
    assert app.called is True


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, set()),
        ("", set()),
        ("http://a", {"http://a"}),
        ("http://a, http://b", {"http://a", "http://b"}),
        ("  http://a  ,,  http://b ,", {"http://a", "http://b"}),
    ],
)
def test_parse_allowed_origins(raw: str | None, expected: set[str]) -> None:
    assert parse_allowed_origins(raw) == expected
