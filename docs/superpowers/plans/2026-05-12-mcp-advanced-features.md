# MCP Advanced Features (Resources, Context, Progress, Logging) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add FastMCP advanced features (resource templates for documents, structured `ctx` logging, and pagination progress reporting) to `paperless-mcp`, coexisting with existing tools.

**Architecture:** A new `src/paperless_mcp/resources/` package exposes per-document `@mcp.resource` templates under the `paperless://` URI scheme (content / metadata / preview / thumbnail / download). The shared `PaperlessClient.paginate()` gains an optional `progress_cb` so any tool can wire `ctx.report_progress` into its DRF cursor walk without re-implementing pagination. Long-running tools (`paperless_list_documents`, `paperless_find_documents`, `paperless_answer_from_documents`, `paperless_recent_documents`) accept an auto-injected `Context` and emit `ctx.debug/info/warning` + page-by-page progress. Binary resources cap response size at 20 MB and raise `ValueError` above the cap (FastMCP wraps it as a resource error).

**Tech Stack:** Python 3.12, FastMCP, httpx, pytest, ruff, mypy.

---

## File Structure

**Created:**
- `src/paperless_mcp/resources/__init__.py` — package marker (empty)
- `src/paperless_mcp/resources/documents.py` — five `@mcp.resource` templates (content, metadata, preview, thumbnail, download)
- `tests/test_resources.py` — resource-reading tests against the in-memory MCP client

**Modified:**
- `src/paperless_mcp/client.py` — `paginate()` gains optional `progress_cb: Callable[[int, int | None], Awaitable[None]] | None = None`
- `src/paperless_mcp/server.py` — import `resources.documents` for registration side-effect
- `src/paperless_mcp/tools/documents.py` — inject `Context` into `paperless_list_documents`, wire `ctx.report_progress` + `ctx.info`
- `src/paperless_mcp/tools/highlevel.py` — inject `Context` into `paperless_find_documents`, `paperless_answer_from_documents`, `paperless_recent_documents`; wire progress + logging
- `tests/conftest.py` — `FakeClient.paginate()` honors `progress_cb`; tests can record ctx messages via a custom `Client` log handler
- `tests/test_documents.py` — assert progress/log calls for `paperless_list_documents`
- `tests/test_highlevel.py` — assert progress/log calls for find/answer/recent
- `CLAUDE.md` — document resources module + `Context` conventions
- `README.md` — short section on resources and progress/logging

---

## Conventions Reminder

- All five `@mcp.resource` templates use the `paperless://documents/{id}/...` scheme.
- Resource functions are `async` and use the shared `client` from `paperless_mcp.app`.
- Resources do NOT accept `save_to_path` (resources are read-only by protocol design). Binary tools keep that knob.
- Tools that gain `ctx: Context` keep it after `document_id` / required positional args but before other keyword args — FastMCP auto-injects it regardless of position, but be consistent for readability. Defer to existing pattern in `paperless_interactive_search` (ctx first after self/args).
- `ctx.report_progress` is only awaited when `total` is known (DRF `count`). For plain-list endpoints (no `count`), emit `ctx.info` only.
- Binary resources cap at `_MAX_RESOURCE_BYTES = 20_000_000` (20 MB). Above that, raise `ValueError` with a message pointing the client at the equivalent tool with `save_to_path`.

---

## Task 1: Add `progress_cb` hook to `PaperlessClient.paginate`

**Files:**
- Modify: `src/paperless_mcp/client.py:84-126`
- Modify: `tests/conftest.py:76-91`
- Test: `tests/test_client.py`

- [ ] **Step 1: Write failing test for `progress_cb`**

Add to `tests/test_client.py` (place near other paginate tests):

```python
import pytest
import respx
from httpx import Response

from paperless_mcp.client import PaperlessClient
from paperless_mcp.config import Settings


@pytest.mark.asyncio
async def test_paginate_invokes_progress_cb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPERLESS_URL", "http://test.invalid")
    monkeypatch.setenv("PAPERLESS_TOKEN", "tok")
    settings = Settings.from_env()
    client = PaperlessClient(settings)
    calls: list[tuple[int, int | None]] = []

    async def record(seen: int, total: int | None) -> None:
        calls.append((seen, total))

    with respx.mock(base_url="http://test.invalid") as mock:
        mock.get("/api/documents/", params={"page": "1", "page_size": "100"}).mock(
            return_value=Response(
                200,
                json={
                    "count": 3,
                    "next": "http://test.invalid/api/documents/?page=2",
                    "results": [{"id": 1}, {"id": 2}],
                },
            )
        )
        mock.get("/api/documents/", params={"page": "2", "page_size": "100"}).mock(
            return_value=Response(200, json={"count": 3, "next": None, "results": [{"id": 3}]})
        )

        items, total, has_more = await client.paginate(
            "/api/documents/", progress_cb=record
        )

    await client.aclose()
    assert items == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert total == 3
    assert has_more is False
    assert calls == [(2, 3), (3, 3)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_client.py::test_paginate_invokes_progress_cb -v`
Expected: FAIL — `paginate()` got unexpected keyword `progress_cb`.

- [ ] **Step 3: Add `progress_cb` to `paginate`**

In `src/paperless_mcp/client.py`, update imports and method signature.

Replace the top imports block:

```python
"""Async HTTP client for Paperless-ngx with auto-pagination."""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, AsyncIterator

import httpx

from .config import Settings
```

Replace the `paginate` method (currently `client.py:84-126`) with:

```python
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
```

- [ ] **Step 4: Update `FakeClient.paginate` in conftest to honor `progress_cb`**

In `tests/conftest.py`, replace the `paginate` method (lines 76-91) with:

```python
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
```

- [ ] **Step 5: Run paginate tests + existing client tests**

Run: `uv run pytest tests/test_client.py -v`
Expected: PASS (all existing tests still pass + new `test_paginate_invokes_progress_cb`).

Run: `uv run pytest -q`
Expected: full suite still green.

- [ ] **Step 6: Commit**

```bash
git add src/paperless_mcp/client.py tests/conftest.py tests/test_client.py
git commit -m "feat(client): paginate accepts optional progress_cb"
```

---

## Task 2: Create resources package + content resource

**Files:**
- Create: `src/paperless_mcp/resources/__init__.py`
- Create: `src/paperless_mcp/resources/documents.py`
- Modify: `src/paperless_mcp/server.py:12-20`
- Create: `tests/test_resources.py`

- [ ] **Step 1: Write failing test for content resource**

Create `tests/test_resources.py`:

```python
"""Tests for paperless:// resource templates."""
from __future__ import annotations

import base64
import json

import pytest
from fastmcp import Client

from tests.conftest import FakeClient  # noqa: TC002 (re-exported via fixture)


@pytest.mark.asyncio
async def test_resource_document_content(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_get(
        "/api/documents/42/",
        {"id": 42, "title": "Invoice", "content": "hello world"},
    )
    result = await mcp_client.read_resource("paperless://documents/42/content")
    # FastMCP read_resource returns a list of TextResourceContents / BlobResourceContents
    assert len(result) == 1
    assert result[0].text == "hello world"
    assert result[0].mimeType == "text/plain"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_resources.py::test_resource_document_content -v`
Expected: FAIL — `paperless://documents/42/content` not found (ResourceError / Unknown resource).

- [ ] **Step 3: Create the resources package**

Create `src/paperless_mcp/resources/__init__.py` (empty file — package marker).

Create `src/paperless_mcp/resources/documents.py`:

```python
"""Per-document resource templates under the paperless:// URI scheme."""
from __future__ import annotations

from ..app import client, mcp

_MAX_RESOURCE_BYTES = 20_000_000


@mcp.resource(
    uri="paperless://documents/{document_id}/content",
    name="paperless_document_content",
    description="OCR / extracted text content of a Paperless document.",
    mime_type="text/plain",
    tags={"paperless", "document", "content"},
)
async def document_content(document_id: int) -> str:
    """Return the OCR text body of a document."""
    doc = await client.get(f"/api/documents/{document_id}/")
    return doc.get("content") or ""
```

- [ ] **Step 4: Register the resources module in server.py**

In `src/paperless_mcp/server.py`, update the import block (lines 12-20):

```python
# Register tools and resources by importing modules (decorator side-effect).
from .tools import (  # noqa: F401
    auth,
    documents,
    highlevel,
    search,
    stats,
    tasks,
    taxonomy,
)
from .resources import documents as _resources_documents  # noqa: F401
```

- [ ] **Step 5: Run resource test to verify it passes**

Run: `uv run pytest tests/test_resources.py::test_resource_document_content -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/paperless_mcp/resources/__init__.py src/paperless_mcp/resources/documents.py src/paperless_mcp/server.py tests/test_resources.py
git commit -m "feat(resources): add paperless://documents/{id}/content resource template"
```

---

## Task 3: Add metadata resource

**Files:**
- Modify: `src/paperless_mcp/resources/documents.py`
- Modify: `tests/test_resources.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_resources.py`:

```python
@pytest.mark.asyncio
async def test_resource_document_metadata(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_get(
        "/api/documents/42/",
        {
            "id": 42,
            "title": "Invoice",
            "created": "2026-01-15",
            "content": "long ocr text that should be omitted from metadata",
        },
    )
    result = await mcp_client.read_resource("paperless://documents/42/metadata")
    assert len(result) == 1
    assert result[0].mimeType == "application/json"
    payload = json.loads(result[0].text)
    assert payload["id"] == 42
    assert payload["title"] == "Invoice"
    assert "content" not in payload
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_resources.py::test_resource_document_metadata -v`
Expected: FAIL — unknown resource.

- [ ] **Step 3: Add metadata resource**

Append to `src/paperless_mcp/resources/documents.py`:

```python
@mcp.resource(
    uri="paperless://documents/{document_id}/metadata",
    name="paperless_document_metadata",
    description="Full Paperless document record (OCR content omitted).",
    mime_type="application/json",
    tags={"paperless", "document", "metadata"},
)
async def document_metadata(document_id: int) -> dict:
    """Return the document record without the (potentially large) OCR content."""
    doc = await client.get(f"/api/documents/{document_id}/")
    doc.pop("content", None)
    return doc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_resources.py::test_resource_document_metadata -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/paperless_mcp/resources/documents.py tests/test_resources.py
git commit -m "feat(resources): add paperless://documents/{id}/metadata resource template"
```

---

## Task 4: Add binary resources (preview, thumbnail, download)

**Files:**
- Modify: `src/paperless_mcp/resources/documents.py`
- Modify: `tests/test_resources.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_resources.py`:

```python
@pytest.mark.asyncio
async def test_resource_document_preview(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_binary("/api/documents/42/preview/", b"%PDF-1.4 fake pdf bytes")
    result = await mcp_client.read_resource("paperless://documents/42/preview")
    assert len(result) == 1
    assert result[0].mimeType == "application/pdf"
    assert base64.b64decode(result[0].blob) == b"%PDF-1.4 fake pdf bytes"


@pytest.mark.asyncio
async def test_resource_document_thumbnail(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_binary("/api/documents/42/thumb/", b"\x89PNG\r\n\x1a\nfake")
    result = await mcp_client.read_resource("paperless://documents/42/thumbnail")
    assert len(result) == 1
    assert result[0].mimeType in {"image/png", "image/webp"}
    assert base64.b64decode(result[0].blob) == b"\x89PNG\r\n\x1a\nfake"


@pytest.mark.asyncio
async def test_resource_document_download(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_binary("/api/documents/42/download/", b"original-bytes")
    result = await mcp_client.read_resource("paperless://documents/42/download")
    assert len(result) == 1
    assert result[0].mimeType == "application/octet-stream"
    assert base64.b64decode(result[0].blob) == b"original-bytes"


@pytest.mark.asyncio
async def test_resource_binary_rejects_oversized(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_binary("/api/documents/42/preview/", b"x" * 20_000_001)
    with pytest.raises(Exception) as excinfo:
        await mcp_client.read_resource("paperless://documents/42/preview")
    assert "too large" in str(excinfo.value).lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_resources.py -v -k "preview or thumbnail or download or oversized"`
Expected: FAIL — unknown resources.

- [ ] **Step 3: Add binary resources**

Append to `src/paperless_mcp/resources/documents.py`:

```python
async def _fetch_capped_binary(path: str) -> bytes:
    blob = await client.get_binary(path)
    if len(blob) > _MAX_RESOURCE_BYTES:
        raise ValueError(
            f"resource too large for inline transfer ({len(blob)} bytes, "
            f"cap {_MAX_RESOURCE_BYTES}); use the equivalent tool with "
            "save_to_path instead"
        )
    return blob


@mcp.resource(
    uri="paperless://documents/{document_id}/preview",
    name="paperless_document_preview",
    description="PDF preview rendering of a Paperless document.",
    mime_type="application/pdf",
    tags={"paperless", "document", "preview", "binary"},
)
async def document_preview(document_id: int) -> bytes:
    """Return a PDF preview of the document."""
    return await _fetch_capped_binary(f"/api/documents/{document_id}/preview/")


@mcp.resource(
    uri="paperless://documents/{document_id}/thumbnail",
    name="paperless_document_thumbnail",
    description="Thumbnail image of a Paperless document (typically WebP or PNG).",
    mime_type="image/webp",
    tags={"paperless", "document", "thumbnail", "binary"},
)
async def document_thumbnail(document_id: int) -> bytes:
    """Return the document thumbnail bytes."""
    return await _fetch_capped_binary(f"/api/documents/{document_id}/thumb/")


@mcp.resource(
    uri="paperless://documents/{document_id}/download",
    name="paperless_document_download",
    description="Original/archived file bytes for a Paperless document.",
    mime_type="application/octet-stream",
    tags={"paperless", "document", "download", "binary"},
)
async def document_download(document_id: int) -> bytes:
    """Return the document download bytes (archived PDF by default)."""
    return await _fetch_capped_binary(f"/api/documents/{document_id}/download/")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_resources.py -v`
Expected: all five tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/paperless_mcp/resources/documents.py tests/test_resources.py
git commit -m "feat(resources): add preview/thumbnail/download binary resource templates"
```

---

## Task 5: Wire `Context` progress + logging into `paperless_list_documents`

**Files:**
- Modify: `src/paperless_mcp/tools/documents.py:24-83`
- Modify: `tests/test_documents.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_documents.py` (near other list-documents tests):

```python
import pytest
from fastmcp import Client

from tests.conftest import FakeClient


class _RecordingLogHandler:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    async def __call__(self, message) -> None:  # MessageHandler-like protocol
        # message is a LoggingMessageNotification; record level + text
        self.messages.append((message.level, message.data))


@pytest.mark.asyncio
async def test_list_documents_emits_progress_and_log(
    fake_client: FakeClient,
) -> None:
    fake_client.set_paginate(
        "/api/documents/",
        [{"id": i, "title": f"doc{i}"} for i in range(3)],
    )
    progress_events: list[tuple[float, float | None]] = []

    async def on_progress(progress: float, total: float | None, message: str | None) -> None:
        progress_events.append((progress, total))

    log_events: list[tuple[str, str]] = []

    async def on_log(message) -> None:
        log_events.append((message.level, str(message.data)))

    from paperless_mcp.app import mcp as server

    async with Client(
        server, progress_handler=on_progress, log_handler=on_log
    ) as c:
        result = await c.call_tool("paperless_list_documents", {"max_results": 50})

    assert result.data["page_info"]["returned"] == 3
    assert progress_events  # at least one progress update
    assert any("documents" in msg.lower() for _, msg in log_events)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_documents.py::test_list_documents_emits_progress_and_log -v`
Expected: FAIL — no progress / log events recorded.

- [ ] **Step 3: Inject `Context` and wire progress/logging**

In `src/paperless_mcp/tools/documents.py`, update imports (top of file) to include `Context`:

```python
from fastmcp import Context
from fastmcp.exceptions import ToolError
from pydantic import Field
```

Replace the `paperless_list_documents` signature and body (currently lines 24-83). Add `ctx: Context` as the first parameter and wire progress + info logging:

```python
@mcp.tool(annotations=READ_ONLY)
async def paperless_list_documents(
    ctx: Context,
    correspondent_id: Annotated[int | None, Field(description="Filter by correspondent id")] = None,
    document_type_id: Annotated[int | None, Field(description="Filter by doc type id")] = None,
    storage_path_id: Annotated[int | None, Field(description="Filter by storage path id")] = None,
    tag_ids_all: Annotated[list[int] | None, Field(description="Docs with ALL these tag ids")] = None,
    tag_ids_any: Annotated[list[int] | None, Field(description="Docs with ANY of these tag ids")] = None,
    title_contains: Annotated[str | None, Field(description="Title icontains substring")] = None,
    content_contains: Annotated[str | None, Field(description="OCR content icontains substring")] = None,
    created_year: Annotated[int | None, Field(description="Document created year")] = None,
    created_month: Annotated[int | None, Field(description="Document created month (1-12)")] = None,
    created_after: Annotated[str | None, Field(description="ISO date YYYY-MM-DD, created >=")] = None,
    created_before: Annotated[str | None, Field(description="ISO date YYYY-MM-DD, created <=")] = None,
    added_after: Annotated[str | None, Field(description="ISO date YYYY-MM-DD, added >=")] = None,
    is_in_inbox: Annotated[bool | None, Field(description="Filter to inbox-tagged docs")] = None,
    archive_serial_number: Annotated[int | None, Field(description="Exact ASN")] = None,
    ordering: Annotated[
        str | None,
        Field(description="Sort field, prefix '-' for desc. e.g. '-created'"),
    ] = "-created",
    max_results: Annotated[int, Field(ge=1, le=500, description="Cap on returned docs")] = 50,
) -> DocumentListResponse:
    """List documents with structured filters. Auto-paginates up to max_results."""
    params: dict[str, Any] = {"ordering": ordering}
    if correspondent_id is not None:
        params["correspondent__id"] = correspondent_id
    if document_type_id is not None:
        params["document_type__id"] = document_type_id
    if storage_path_id is not None:
        params["storage_path__id"] = storage_path_id
    if tag_ids_all:
        params["tags__id__all"] = ",".join(str(i) for i in tag_ids_all)
    if tag_ids_any:
        params["tags__id__in"] = ",".join(str(i) for i in tag_ids_any)
    if title_contains:
        params["title__icontains"] = title_contains
    if content_contains:
        params["content__icontains"] = content_contains
    if created_year is not None:
        params["created__year"] = created_year
    if created_month is not None:
        params["created__month"] = created_month
    if created_after:
        params["created__date__gte"] = created_after
    if created_before:
        params["created__date__lte"] = created_before
    if added_after:
        params["added__date__gte"] = added_after
    if is_in_inbox is not None:
        params["is_in_inbox"] = is_in_inbox
    if archive_serial_number is not None:
        params["archive_serial_number"] = archive_serial_number

    await ctx.debug(f"paperless_list_documents params={params!r} max_results={max_results}")

    async def _progress(seen: int, total: int | None) -> None:
        if total is not None:
            await ctx.report_progress(progress=seen, total=total)

    docs, total, has_more = await client.paginate(
        "/api/documents/", params=params, max_items=max_results, progress_cb=_progress
    )
    await ctx.info(
        f"returned {len(docs)} documents"
        + (f" of {total} total" if total is not None else "")
    )
    return DocumentListResponse(
        documents=[slim_document(d) for d in docs],  # type: ignore[misc]
        page_info=make_page_info(len(docs), total, has_more, max_results),
    )
```

- [ ] **Step 4: Run new + existing list_documents tests**

Run: `uv run pytest tests/test_documents.py -v`
Expected: PASS. Existing tests that call `paperless_list_documents` via `mcp_client.call_tool(...)` still work because FastMCP auto-injects `ctx`.

- [ ] **Step 5: Commit**

```bash
git add src/paperless_mcp/tools/documents.py tests/test_documents.py
git commit -m "feat(tools): list_documents emits progress + structured logging via Context"
```

---

## Task 6: Wire `Context` into highlevel tools

**Files:**
- Modify: `src/paperless_mcp/tools/highlevel.py:29-73, 76-120, 240-260`
- Modify: `tests/test_highlevel.py`

- [ ] **Step 1: Write failing test for `paperless_find_documents`**

Add to `tests/test_highlevel.py`:

```python
import pytest
from fastmcp import Client

from tests.conftest import FakeClient


@pytest.mark.asyncio
async def test_find_documents_emits_progress_and_warnings(
    fake_client: FakeClient,
) -> None:
    fake_client.set_paginate("/api/correspondents/", [])
    fake_client.set_paginate("/api/tags/", [])
    fake_client.set_paginate("/api/document_types/", [])
    fake_client.set_paginate("/api/storage_paths/", [])
    fake_client.set_paginate(
        "/api/documents/",
        [{"id": i, "title": f"d{i}"} for i in range(2)],
    )

    progress: list[tuple[float, float | None]] = []
    logs: list[tuple[str, str]] = []

    async def on_progress(p: float, t: float | None, _: str | None) -> None:
        progress.append((p, t))

    async def on_log(message) -> None:
        logs.append((message.level, str(message.data)))

    from paperless_mcp.app import mcp as server

    async with Client(server, progress_handler=on_progress, log_handler=on_log) as c:
        result = await c.call_tool(
            "paperless_find_documents",
            {"correspondent_name": "unknown-co", "max_results": 50},
        )

    assert result.data["page_info"]["returned"] == 2
    assert any(level == "warning" for level, _ in logs)
    assert progress
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_highlevel.py::test_find_documents_emits_progress_and_warnings -v`
Expected: FAIL — no progress or warning recorded.

- [ ] **Step 3: Inject Context into `paperless_find_documents`**

In `src/paperless_mcp/tools/highlevel.py`, replace `paperless_find_documents` (lines 29-73) with:

```python
@mcp.tool(annotations=READ_ONLY)
async def paperless_find_documents(
    ctx: Context,
    correspondent_name: Annotated[str | None, Field(description="Correspondent name (resolved to id)")] = None,
    document_type_name: Annotated[str | None, Field(description="Doc type name (resolved to id)")] = None,
    storage_path_name: Annotated[str | None, Field(description="Storage path name (resolved to id)")] = None,
    tag_names_all: Annotated[list[str] | None, Field(description="All tag names (resolved)")] = None,
    tag_names_any: Annotated[list[str] | None, Field(description="Any tag names (resolved)")] = None,
    title_contains: Annotated[str | None, Field(description="Title icontains")] = None,
    text_contains: Annotated[str | None, Field(description="OCR content icontains (DB-only, no relevance ranking — prefer paperless_answer_from_documents for relevance)")] = None,
    year: Annotated[int | None, Field(description="Document creation year")] = None,
    month: Annotated[int | None, Field(description="Document creation month 1-12")] = None,
    created_after: Annotated[str | None, Field(description="ISO YYYY-MM-DD")] = None,
    created_before: Annotated[str | None, Field(description="ISO YYYY-MM-DD")] = None,
    max_results: Annotated[int, Field(ge=1, le=200)] = 50,
) -> DocumentListResponse:
    """Find documents using human-friendly names. Resolves names→IDs then queries.

    Use this when the user asks about documents from a person/company, of a type,
    in a period, or with tags — and you don't already have IDs.
    """
    req = FilterRequest(
        correspondent_name=correspondent_name,
        document_type_name=document_type_name,
        storage_path_name=storage_path_name,
        tag_names_all=tag_names_all or [],
        tag_names_any=tag_names_any or [],
        title_contains=title_contains,
        text_contains=text_contains,
        year=year,
        month=month,
        created_after=created_after,
        created_before=created_before,
    )
    await ctx.debug("resolving names to ids")
    filter_params, unresolved = await build_document_filters(req)
    if unresolved:
        await ctx.warning(f"unresolved names ignored: {unresolved}")
    params: dict[str, Any] = {"ordering": "-created", **filter_params}

    async def _progress(seen: int, total: int | None) -> None:
        if total is not None:
            await ctx.report_progress(progress=seen, total=total)

    docs, total, has_more = await client.paginate(
        "/api/documents/", params=params, max_items=max_results, progress_cb=_progress
    )
    await ctx.info(
        f"returned {len(docs)} documents"
        + (f" of {total} total" if total is not None else "")
    )
    return DocumentListResponse(
        documents=[slim_document(d) for d in docs],  # type: ignore[misc]
        page_info=make_page_info(len(docs), total, has_more, max_results),
        unresolved=unresolved,
        filters_applied={k: v for k, v in params.items() if k != "ordering"},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_highlevel.py::test_find_documents_emits_progress_and_warnings -v`
Expected: PASS.

- [ ] **Step 5: Write failing test for `paperless_answer_from_documents`**

Add to `tests/test_highlevel.py`:

```python
@pytest.mark.asyncio
async def test_answer_from_documents_reports_enrichment_progress(
    fake_client: FakeClient,
) -> None:
    fake_client.set_get(
        "/api/search/",
        {
            "count": 2,
            "results": [
                {"id": 1, "score": 0.9},
                {"id": 2, "score": 0.8},
            ],
        },
    )
    fake_client.set_get("/api/documents/1/", {"id": 1, "title": "A", "content": "x"})
    fake_client.set_get("/api/documents/2/", {"id": 2, "title": "B", "content": "y"})

    progress: list[tuple[float, float | None]] = []
    logs: list[tuple[str, str]] = []

    async def on_progress(p: float, t: float | None, _: str | None) -> None:
        progress.append((p, t))

    async def on_log(message) -> None:
        logs.append((message.level, str(message.data)))

    from paperless_mcp.app import mcp as server

    async with Client(server, progress_handler=on_progress, log_handler=on_log) as c:
        result = await c.call_tool(
            "paperless_answer_from_documents", {"query": "x", "top_k": 2}
        )

    assert result.data["returned"] == 2
    assert (2.0, 2.0) in progress  # final 2/2
    assert any("enriching" in msg.lower() for _, msg in logs)
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/test_highlevel.py::test_answer_from_documents_reports_enrichment_progress -v`
Expected: FAIL.

- [ ] **Step 7: Inject Context into `paperless_answer_from_documents`**

Replace `paperless_answer_from_documents` (lines 76-120) with:

```python
@mcp.tool(annotations=READ_ONLY)
async def paperless_answer_from_documents(
    ctx: Context,
    query: Annotated[str, Field(description="Natural-language question or full-text query")],
    top_k: Annotated[int, Field(ge=1, le=20)] = 5,
    excerpt_chars: Annotated[
        int, Field(ge=200, le=20_000, description="Max OCR chars per excerpt")
    ] = 4000,
) -> AnswerResponse:
    """RAG helper: full-text search, then return top-k docs with content excerpts.

    Use this for any "what does my paperwork say about X" / "find me the invoice
    where Y" question — gives the model retrieved excerpts ready to synthesize.
    """
    await ctx.debug(f"full-text search query={query!r} top_k={top_k}")
    search = await client.get("/api/search/", params={"query": query})
    hits = (search.get("results") or [])[:top_k] if isinstance(search, dict) else []
    total_hits = len(hits)
    await ctx.info(f"enriching {total_hits} hits with content excerpts")

    enriched: list[AnswerSource] = []

    async def _enrich(hit: dict[str, Any]) -> AnswerSource:
        doc_id = hit.get("id")
        if doc_id is None:
            return cast(AnswerSource, dict(hit))
        try:
            doc = await client.get(f"/api/documents/{doc_id}/")
        except PaperlessAPIError as e:
            await ctx.warning(f"failed to fetch document {doc_id}: {e.status}")
            return AnswerSource(id=doc_id, fetch_error_status=e.status)
        content = (doc.get("content") or "")[:excerpt_chars]
        return AnswerSource(
            id=doc.get("id"),
            title=doc.get("title"),
            created=doc.get("created"),
            correspondent=doc.get("correspondent"),
            document_type=doc.get("document_type"),
            tags=doc.get("tags"),
            score=hit.get("score"),
            highlights=hit.get("highlights") or hit.get("note_highlights"),
            excerpt=content,
            excerpt_truncated=len(doc.get("content") or "") > excerpt_chars,
        )

    for idx, hit in enumerate(hits, start=1):
        enriched.append(await _enrich(hit))
        await ctx.report_progress(progress=idx, total=total_hits)

    return AnswerResponse(
        query=query,
        total_hits=search.get("count") if isinstance(search, dict) else len(hits),
        returned=len(enriched),
        sources=enriched,
    )
```

Note: this replaces the prior `asyncio.gather` parallel enrichment with a sequential loop so progress is monotonic. If concurrency matters, switch to `gather` and emit a single `report_progress(total, total)` at the end — but document that tradeoff to the user before changing. (Default plan: sequential, since `top_k ≤ 20` and we already pay a network round-trip per hit either way.)

Also remove the now-unused `import asyncio` line if no other reference remains; leave it if anything else uses it. Quick check: `asyncio` is only imported and used for the removed `gather`. Remove the import (line 8).

- [ ] **Step 8: Run test to verify it passes**

Run: `uv run pytest tests/test_highlevel.py::test_answer_from_documents_reports_enrichment_progress -v`
Expected: PASS.

- [ ] **Step 9: Write failing test for `paperless_recent_documents`**

Add to `tests/test_highlevel.py`:

```python
@pytest.mark.asyncio
async def test_recent_documents_emits_progress(fake_client: FakeClient) -> None:
    fake_client.set_paginate(
        "/api/documents/",
        [{"id": i, "title": f"r{i}"} for i in range(4)],
    )
    progress: list[tuple[float, float | None]] = []

    async def on_progress(p: float, t: float | None, _: str | None) -> None:
        progress.append((p, t))

    from paperless_mcp.app import mcp as server

    async with Client(server, progress_handler=on_progress) as c:
        result = await c.call_tool(
            "paperless_recent_documents", {"days": 7, "limit": 10}
        )

    assert len(result.data["documents"]) == 4
    assert progress
```

- [ ] **Step 10: Run test to verify it fails**

Run: `uv run pytest tests/test_highlevel.py::test_recent_documents_emits_progress -v`
Expected: FAIL.

- [ ] **Step 11: Inject Context into `paperless_recent_documents`**

Replace `paperless_recent_documents` (lines 240-260) with:

```python
@mcp.tool(annotations=READ_ONLY)
async def paperless_recent_documents(
    ctx: Context,
    days: Annotated[int, Field(ge=1, le=3650, description="Look back window in days")] = 30,
    limit: Annotated[int, Field(ge=1, le=200)] = 20,
    by: Annotated[str, Field(description="'added' or 'created'")] = "added",
) -> dict[str, Any]:
    """Most recently added or created documents."""
    from datetime import date, timedelta

    field = "added" if by == "added" else "created"
    since = (date.today() - timedelta(days=days)).isoformat()
    params = {f"{field}__date__gte": since, "ordering": f"-{field}"}
    await ctx.debug(f"recent_documents since={since} by={field}")

    async def _progress(seen: int, total: int | None) -> None:
        if total is not None:
            await ctx.report_progress(progress=seen, total=total)

    docs, total, has_more = await client.paginate(
        "/api/documents/", params=params, max_items=limit, progress_cb=_progress
    )
    await ctx.info(f"returned {len(docs)} recent documents")
    return {
        "since": since,
        "by": field,
        "documents": [slim_document(d) for d in docs],
        "page_info": make_page_info(len(docs), total, has_more, limit),
    }
```

- [ ] **Step 12: Run full highlevel test suite**

Run: `uv run pytest tests/test_highlevel.py -v`
Expected: all tests PASS (including pre-existing `paperless_interactive_search` tests, which already use `Context`).

- [ ] **Step 13: Run the full test suite**

Run: `uv run pytest -q`
Expected: green.

- [ ] **Step 14: Commit**

```bash
git add src/paperless_mcp/tools/highlevel.py tests/test_highlevel.py
git commit -m "feat(tools): highlevel tools emit progress + structured logging via Context"
```

---

## Task 7: Lint, type-check, and update docs

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: Run lint + type checks**

Run: `uv run ruff check .`
Expected: clean (or fix any issues reported — typically unused-import for the removed `asyncio`).

Run: `uv run mypy src`
Expected: clean.

- [ ] **Step 2: Update CLAUDE.md**

In `CLAUDE.md`, add a new subsection under the "Architecture" section. Insert directly after the `tools/_schemas.py` bullet:

```markdown
- `resources/documents.py` — `@mcp.resource` templates under the `paperless://documents/{id}/...` URI scheme: `content` (text/plain OCR), `metadata` (application/json record), `preview` (application/pdf), `thumbnail` (image/webp), `download` (application/octet-stream). Binary resources cap at 20 MB; oversized requests raise `ValueError` and point the client at the equivalent tool with `save_to_path`. Resources coexist with the binary tools — clients that prefer resource semantics can use them, clients that need disk persistence still call the tools.
```

Then add a new "Context, progress, logging" subsection at the end of the "Architecture" section:

```markdown
**Context & observability**: tools that walk multiple pages or fetch N child docs accept `ctx: Context` (auto-injected by FastMCP) and emit `await ctx.report_progress(progress=seen, total=count)` per page plus `await ctx.debug/info/warning(...)` for query setup, completion, and unresolved-name warnings. Wired into `paperless_list_documents`, `paperless_find_documents`, `paperless_answer_from_documents`, `paperless_recent_documents`, and `paperless_interactive_search` (which also uses `ctx.elicit`). To plug a tool into the pagination progress stream, pass a `progress_cb` to `client.paginate(...)`.
```

- [ ] **Step 3: Update README.md**

In `README.md`, add a section near the existing tool listing (place after the tools section, before any "Limitations" section):

```markdown
## Resources

In addition to the read-only tools, the server exposes per-document MCP resource templates under the `paperless://` scheme. Clients that support `resources/read` can fetch:

| URI | MIME | Description |
| --- | --- | --- |
| `paperless://documents/{id}/content` | `text/plain` | OCR / extracted text |
| `paperless://documents/{id}/metadata` | `application/json` | Document record (no OCR body) |
| `paperless://documents/{id}/preview` | `application/pdf` | PDF preview |
| `paperless://documents/{id}/thumbnail` | `image/webp` | Thumbnail |
| `paperless://documents/{id}/download` | `application/octet-stream` | Original/archived file |

Binary resources are capped at 20 MB. For larger files use the equivalent tool (`paperless_download_document`, `paperless_get_document_preview`, `paperless_get_document_thumbnail`) with `save_to_path`.

## Progress & logging

Long-running tools (`paperless_list_documents`, `paperless_find_documents`, `paperless_answer_from_documents`, `paperless_recent_documents`) emit MCP `progress` notifications per page of upstream results and `logging/message` entries at `debug` / `info` / `warning` levels. Pass `progress_handler` and `log_handler` to your `fastmcp.Client` to consume them.
```

- [ ] **Step 4: Final verification**

Run: `uv run ruff check . && uv run mypy src && uv run pytest -q`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: document resources, Context, progress and logging"
```

---

## Self-Review

1. **Spec coverage:**
   - Resource templates for documents (content, metadata, preview, thumbnail, download) → Tasks 2-4.
   - Progress reporting (`ctx.report_progress`) → Tasks 1, 5, 6.
   - Structured logging (`ctx.info/debug/warning`) → Tasks 5, 6.
   - Broadened `ctx` usage in existing tools → Tasks 5, 6 inject `Context` into the four heaviest tools.
   - Coexist with existing binary tools → resources are additive; `paperless_download_document`/`preview`/`thumbnail` remain untouched.

2. **Placeholder scan:** No TBDs / "implement later" — every step shows the actual code or command. The one decision callout (sequential vs gather in Task 6 Step 7) is explicitly resolved in favor of sequential.

3. **Type consistency:** Resource function names (`document_content`, `document_metadata`, `document_preview`, `document_thumbnail`, `document_download`) are used only inside their module — no cross-task references to break. `_MAX_RESOURCE_BYTES` and `_fetch_capped_binary` are defined in Task 4 before first use. `progress_cb` signature `Callable[[int, int | None], Awaitable[None]]` matches the `_progress` closures in Tasks 5 and 6. `FakeClient.paginate` (Task 1 Step 4) accepts the same kwarg.
