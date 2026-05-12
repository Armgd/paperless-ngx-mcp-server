"""PaperlessClient unit tests using httpx MockTransport."""
from __future__ import annotations

import httpx
import pytest

from paperless_mcp.client import PaperlessAPIError, PaperlessClient
from paperless_mcp.config import Settings


def _settings() -> Settings:
    return Settings(
        base_url="http://x.invalid",
        token="t",
        timeout=5.0,
        verify_ssl=True,
        download_dir=None,
    )


def _make_client(handler) -> PaperlessClient:
    c = PaperlessClient(_settings())
    c._client = httpx.AsyncClient(
        base_url="http://x.invalid",
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Token t"},
    )
    return c


async def test_get_returns_json() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hello": "world"})

    c = _make_client(handler)
    assert await c.get("/api/x/") == {"hello": "world"}
    await c.aclose()


async def test_get_raises_on_4xx() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    c = _make_client(handler)
    with pytest.raises(PaperlessAPIError) as exc:
        await c.get("/api/missing/")
    assert exc.value.status == 404
    # body is retained on the exception object but redacted from the message.
    assert "not found" not in str(exc.value)
    assert exc.value.body == "not found"
    await c.aclose()


async def test_paginate_walks_pages() -> None:
    pages = {
        1: {"results": [{"id": 1}, {"id": 2}], "next": "http://x/?page=2", "count": 3},
        2: {"results": [{"id": 3}], "next": None, "count": 3},
    }

    def handler(req: httpx.Request) -> httpx.Response:
        page = int(req.url.params.get("page", "1"))
        return httpx.Response(200, json=pages[page])

    c = _make_client(handler)
    items, total, has_more = await c.paginate("/api/list/")
    assert [i["id"] for i in items] == [1, 2, 3]
    assert total == 3
    assert has_more is False
    await c.aclose()


async def test_paginate_respects_max_items() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [{"id": i} for i in range(10)],
                "next": "http://x/?page=2",
                "count": 20,
            },
        )

    c = _make_client(handler)
    items, total, has_more = await c.paginate("/api/list/", max_items=5)
    assert len(items) == 5
    assert total == 20
    assert has_more is True
    await c.aclose()


async def test_paginate_handles_plain_list() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": 1}, {"id": 2}])

    c = _make_client(handler)
    items, total, has_more = await c.paginate("/api/list/")
    assert items == [{"id": 1}, {"id": 2}]
    assert total is None
    assert has_more is False
    await c.aclose()


async def test_paginate_caps_plain_list_with_max_items() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": i} for i in range(10)])

    c = _make_client(handler)
    items, total, has_more = await c.paginate("/api/list/", max_items=3)
    assert len(items) == 3
    assert total is None
    assert has_more is True
    await c.aclose()


async def test_get_binary() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"PDFBLOB", headers={"content-type": "application/pdf"}
        )

    c = _make_client(handler)
    assert await c.get_binary("/api/file/") == b"PDFBLOB"
    await c.aclose()


async def test_request_strips_none_params() -> None:
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["params"] = dict(req.url.params)
        return httpx.Response(200, json={})

    c = _make_client(handler)
    await c.get("/api/x/", params={"a": 1, "b": None, "c": "x"})
    assert "b" not in captured["params"]
    assert captured["params"]["a"] == "1"
    await c.aclose()


async def test_paginate_invokes_progress_cb() -> None:
    pages = {
        1: {
            "count": 3,
            "next": "http://x/?page=2",
            "results": [{"id": 1}, {"id": 2}],
        },
        2: {"count": 3, "next": None, "results": [{"id": 3}]},
    }

    def handler(req: httpx.Request) -> httpx.Response:
        page = int(req.url.params.get("page", "1"))
        return httpx.Response(200, json=pages[page])

    c = _make_client(handler)
    calls: list[tuple[int, int | None]] = []

    async def record(seen: int, total: int | None) -> None:
        calls.append((seen, total))

    items, total, has_more = await c.paginate("/api/documents/", progress_cb=record)
    await c.aclose()
    assert items == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert total == 3
    assert has_more is False
    assert calls == [(2, 3), (3, 3)]


async def test_paginate_progress_cb_on_truncation() -> None:
    pages = {
        1: {
            "count": 5,
            "next": "http://x/?page=2",
            "results": [{"id": 1}, {"id": 2}, {"id": 3}],
        },
        2: {"count": 5, "next": None, "results": [{"id": 4}, {"id": 5}]},
    }

    def handler(req: httpx.Request) -> httpx.Response:
        page = int(req.url.params.get("page", "1"))
        return httpx.Response(200, json=pages[page])

    c = _make_client(handler)
    calls: list[tuple[int, int | None]] = []

    async def record(seen: int, total: int | None) -> None:
        calls.append((seen, total))

    items, total, has_more = await c.paginate("/api/documents/", max_items=2, progress_cb=record)
    await c.aclose()
    assert items == [{"id": 1}, {"id": 2}]
    assert total == 5
    assert has_more is True
    assert calls == [(2, 5)]


async def test_request_expect_headers_returns_tuple() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"PNGDATA", headers={"content-type": "image/png"}
        )

    c = _make_client(handler)
    body, headers = await c.request(
        "GET",
        "/api/documents/1/thumb/",
        expect_binary=True,
        expect_headers=True,
    )
    assert body == b"PNGDATA"
    assert headers["content-type"] == "image/png"
    await c.aclose()
