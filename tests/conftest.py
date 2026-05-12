"""Test fixtures: in-memory FastMCP client, mockable Paperless client."""
from __future__ import annotations

import os
from typing import Any, AsyncIterator

# Set required env BEFORE importing app — config.py validates at import time.
os.environ.setdefault("PAPERLESS_URL", "http://test.invalid")
os.environ.setdefault("PAPERLESS_TOKEN", "test-token")

import pytest
from fastmcp import Client

from paperless_mcp import app as app_module
from paperless_mcp.client import PaperlessAPIError

# Import server to trigger tool registration side-effects.
import paperless_mcp.server  # noqa: F401


class FakeClient:
    """Drop-in replacement for PaperlessClient with scriptable responses."""

    def __init__(self) -> None:
        self.get_responses: dict[str, Any] = {}
        self.binary_responses: dict[str, bytes] = {}
        self.binary_headers: dict[str, dict[str, str]] = {}
        self.paginate_responses: dict[str, list[dict[str, Any]]] = {}
        self.get_errors: dict[str, PaperlessAPIError] = {}
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def set_get(self, path: str, response: Any) -> None:
        self.get_responses[path] = response

    def set_get_error(self, path: str, status: int, body: str = "error") -> None:
        self.get_errors[path] = PaperlessAPIError(status, body, "GET", path)

    def set_paginate(self, path: str, results: list[dict[str, Any]]) -> None:
        self.paginate_responses[path] = results

    def set_binary(self, path: str, blob: bytes) -> None:
        self.binary_responses[path] = blob

    async def get(self, path: str, *, params: dict[str, Any] | None = None, **_: Any) -> Any:
        self.calls.append(("GET", path, params))
        if path in self.get_errors:
            raise self.get_errors[path]
        if path not in self.get_responses:
            raise AssertionError(f"Unexpected GET {path}")
        return self.get_responses[path]

    async def get_binary(self, path: str, **_: Any) -> bytes:
        self.calls.append(("GET_BIN", path, None))
        if path not in self.binary_responses:
            raise AssertionError(f"Unexpected GET_BIN {path}")
        return self.binary_responses[path]

    def set_binary_with_headers(
        self, path: str, blob: bytes, headers: dict[str, str]
    ) -> None:
        self.binary_responses[path] = blob
        self.binary_headers[path] = headers

    async def get_binary_with_headers(
        self, path: str, **_: Any
    ) -> tuple[bytes, dict[str, str]]:
        self.calls.append(("GET_BIN_HDR", path, None))
        if path not in self.binary_responses:
            raise AssertionError(f"Unexpected GET_BIN_HDR {path}")
        return self.binary_responses[path], self.binary_headers.get(path, {})

    async def post(self, path: str, **kw: Any) -> Any:
        self.calls.append(("POST", path, kw.get("params")))
        return self.get_responses.get(path)

    async def paginate(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        max_items: int | None = None,
        page_size: int = 100,
        progress_cb: Any = None,
    ) -> tuple[list[dict[str, Any]], int | None, bool]:
        self.calls.append(("PAGINATE", path, params))
        if path not in self.paginate_responses:
            raise AssertionError(f"Unexpected PAGINATE {path}")
        items = self.paginate_responses[path]
        total = len(items)
        if max_items is not None and len(items) > max_items:
            truncated = items[:max_items]
            if progress_cb is not None:
                await progress_cb(len(truncated), total)
            return truncated, total, True
        if progress_cb is not None:
            await progress_cb(len(items), total)
        return items, total, False


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> FakeClient:
    """Replace shared client with FakeClient. Patches all import sites."""
    fake = FakeClient()
    monkeypatch.setattr(app_module, "client", fake)
    # Tool modules grabbed `client` at import time via `from ..app import client`.
    # Patch each module's local reference too.
    from paperless_mcp.tools import (
        _helpers, auth, documents, highlevel, search, stats, tasks, taxonomy,
    )
    from paperless_mcp.resources import documents as resources_documents
    for mod in (_helpers, auth, documents, highlevel, search, stats, tasks, taxonomy, resources_documents):
        monkeypatch.setattr(mod, "client", fake)
    return fake


@pytest.fixture
async def mcp_client() -> AsyncIterator[Client]:
    async with Client(app_module.mcp) as c:
        yield c
