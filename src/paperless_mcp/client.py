"""Async HTTP client for Paperless-ngx with auto-pagination."""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, AsyncIterator

import httpx

from .config import Settings

_log = logging.getLogger(__name__)


class PaperlessAPIError(Exception):
    def __init__(self, status: int, body: str, method: str, path: str) -> None:
        super().__init__(f"{method} {path} -> {status}")
        self.status = status
        self.body = body
        self.method = method
        self.path = path
        _log.warning(
            "paperless api error: %s %s -> %s body=%r", method, path, status, body[:500]
        )


class PaperlessClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.base_url,
            headers={
                "Authorization": f"Token {settings.token}",
                "Accept": "application/json; version=6",
            },
            timeout=settings.timeout,
            verify=settings.verify_ssl,
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        expect_binary: bool = False,
        expect_headers: bool = False,
    ) -> Any:
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        resp = await self._client.request(method, path, params=clean, json=json)
        if resp.status_code >= 400:
            raise PaperlessAPIError(resp.status_code, resp.text, method, path)
        if resp.status_code == 204 or not resp.content:
            body: Any = None
        elif expect_binary:
            body = resp.content
        else:
            ctype = resp.headers.get("content-type", "")
            body = resp.json() if "application/json" in ctype else resp.content
        if expect_headers:
            return body, dict(resp.headers)
        return body

    async def get(self, path: str, **kw: Any) -> Any:
        return await self.request("GET", path, **kw)

    async def get_binary(self, path: str, **kw: Any) -> bytes:
        return await self.request("GET", path, expect_binary=True, **kw)

    async def get_binary_with_headers(
        self, path: str, **kw: Any
    ) -> tuple[bytes, dict[str, str]]:
        return await self.request(
            "GET", path, expect_binary=True, expect_headers=True, **kw
        )

    async def post(self, path: str, **kw: Any) -> Any:
        return await self.request("POST", path, **kw)

    async def paginate(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        max_items: int | None = None,
        page_size: int = 100,
        progress_cb: Callable[[int, int | None], Awaitable[None]] | None = None,
    ) -> tuple[list[dict[str, Any]], int | None, bool]:
        """Auto-paginate a DRF list endpoint.

        Returns (items, total, has_more). `total` is the upstream `count` field
        when available (None for plain-list endpoints). `has_more` is True when
        results exist beyond what was returned — either upstream still has a
        `next` page when we stopped, or we truncated to `max_items`.

        If `progress_cb` is provided, it is awaited after each page with
        (items_collected_so_far, total_or_None).
        """
        items: list[dict[str, Any]] = []
        total: int | None = None
        p = dict(params or {})
        p.setdefault("page_size", page_size)
        p["page"] = 1
        while True:
            data = await self.get(path, params=p)
            if not isinstance(data, dict):
                if not isinstance(data, list):
                    return [], None, False
                if max_items is not None and len(data) > max_items:
                    truncated = data[:max_items]
                    if progress_cb is not None:
                        await progress_cb(len(truncated), None)
                    return truncated, None, True
                if progress_cb is not None:
                    await progress_cb(len(data), None)
                return data, None, False
            if total is None:
                count = data.get("count")
                total = int(count) if isinstance(count, int) else None
            results = data.get("results")
            if results is None:
                if progress_cb is not None:
                    await progress_cb(0, total)
                return [], total, False
            items.extend(results)
            if max_items is not None and len(items) >= max_items:
                truncated_items = items[:max_items]
                has_more = len(items) > max_items or bool(data.get("next"))
                if progress_cb is not None:
                    await progress_cb(len(truncated_items), total)
                return truncated_items, total, has_more
            if progress_cb is not None:
                await progress_cb(len(items), total)
            if not data.get("next"):
                return items, total, False
            p["page"] = int(p["page"]) + 1

    async def iter_pages(
        self, path: str, params: dict[str, Any] | None = None, *, page_size: int = 100
    ) -> AsyncIterator[dict[str, Any]]:
        p = dict(params or {})
        p.setdefault("page_size", page_size)
        p["page"] = 1
        while True:
            data = await self.get(path, params=p)
            yield data
            if not isinstance(data, dict) or not data.get("next"):
                return
            p["page"] = int(p["page"]) + 1
