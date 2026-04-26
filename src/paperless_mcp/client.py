"""Async HTTP client for Paperless-ngx with auto-pagination."""
from __future__ import annotations

from typing import Any, AsyncIterator

import httpx

from .config import Settings


class PaperlessAPIError(Exception):
    def __init__(self, status: int, body: str, method: str, path: str) -> None:
        super().__init__(f"{method} {path} -> {status}: {body[:500]}")
        self.status = status
        self.body = body


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
    ) -> Any:
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        resp = await self._client.request(method, path, params=clean, json=json)
        if resp.status_code >= 400:
            raise PaperlessAPIError(resp.status_code, resp.text, method, path)
        if resp.status_code == 204 or not resp.content:
            return None
        if expect_binary:
            return resp.content
        ctype = resp.headers.get("content-type", "")
        if "application/json" in ctype:
            return resp.json()
        return resp.content

    async def get(self, path: str, **kw: Any) -> Any:
        return await self.request("GET", path, **kw)

    async def get_binary(self, path: str, **kw: Any) -> bytes:
        return await self.request("GET", path, expect_binary=True, **kw)

    async def get_binary_with_headers(
        self, path: str, **kw: Any
    ) -> tuple[bytes, dict[str, str]]:
        clean = {k: v for k, v in (kw.get("params") or {}).items() if v is not None}
        resp = await self._client.request("GET", path, params=clean)
        if resp.status_code >= 400:
            raise PaperlessAPIError(resp.status_code, resp.text, "GET", path)
        return resp.content, dict(resp.headers)

    async def post(self, path: str, **kw: Any) -> Any:
        return await self.request("POST", path, **kw)

    async def paginate(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        max_items: int | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Auto-paginate a DRF list endpoint. Returns flat results list."""
        items: list[dict[str, Any]] = []
        p = dict(params or {})
        p.setdefault("page_size", page_size)
        p["page"] = 1
        while True:
            data = await self.get(path, params=p)
            results = data.get("results") if isinstance(data, dict) else None
            if results is None:
                # endpoint returns plain list
                if not isinstance(data, list):
                    return []
                return data[:max_items] if max_items is not None else data
            items.extend(results)
            if max_items is not None and len(items) >= max_items:
                return items[:max_items]
            if not data.get("next"):
                return items
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
