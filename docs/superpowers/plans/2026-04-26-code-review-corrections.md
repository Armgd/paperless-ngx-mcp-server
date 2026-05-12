# Code Review Corrections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve all CRITICAL/HIGH/MEDIUM findings from code review of paperless-mcp: secure HTTP transport, eliminate path-traversal write primitive, fix mypy errors in `interactive_search`, harden client + tools, normalize env-bool parsing.

**Architecture:** Surgical fixes inside existing module layout. New helpers stay in their owning module (no new files except a focused `tools/_filters.py` for shared param assembly and a `tests/test_interactive_search.py` for elicitation coverage). All changes are additive to public surface; no breaking signature changes.

**Tech Stack:** Python 3.12, FastMCP 3, httpx, pydantic 2, pytest-asyncio, mypy strict-ish, ruff.

---

## File Structure

**Modify:**
- `src/paperless_mcp/server.py` — refuse HTTP transport without `MCP_AUTH_TOKEN`
- `src/paperless_mcp/config.py` — `Settings` gains `download_dir: Path | None`; unify env-bool helper
- `src/paperless_mcp/client.py` — fix plain-list pagination cap; add response-headers escape hatch for `get_binary`
- `src/paperless_mcp/tools/documents.py` — sandbox `save_to_path`; remove dead `_OrderingChoice`; thumbnail mime from header
- `src/paperless_mcp/tools/highlevel.py` — fix mypy errors in `interactive_search`; parallelize `find_documents` resolution; reuse extracted filter helper
- `src/paperless_mcp/tools/tasks.py` — guard against `None` results
- `src/paperless_mcp/tools/_helpers.py` — add `_env_bool` (re-exported from config) — actually keep helper in `config.py` and import from there

**Create:**
- `src/paperless_mcp/_envutil.py` — single `env_bool` function used by both `config.py` and `server.py`
- `src/paperless_mcp/tools/_filters.py` — `build_document_filters(...)` shared between `find_documents` and `interactive_search`
- `tests/test_interactive_search.py` — branch coverage for elicit-driven tool
- `tests/test_safe_path.py` — sandbox helper coverage

**Test files modified:**
- `tests/test_documents.py` — add path-sandbox negative tests
- `tests/test_client.py` — add plain-list `max_items` test
- `tests/test_server.py` — assert HTTP transport refuses without `MCP_AUTH_TOKEN`

---

## Task 1: Unified env_bool helper

**Files:**
- Create: `src/paperless_mcp/_envutil.py`
- Modify: `src/paperless_mcp/config.py`
- Modify: `src/paperless_mcp/server.py`
- Test: `tests/test_envutil.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_envutil.py`:

```python
"""env_bool helper."""
from __future__ import annotations

import pytest

from paperless_mcp._envutil import env_bool


@pytest.mark.parametrize(
    "raw,default,expected",
    [
        (None, True, True),
        (None, False, False),
        ("1", False, True),
        ("true", False, True),
        ("TRUE", False, True),
        ("yes", False, True),
        ("on", False, True),
        ("0", True, False),
        ("false", True, False),
        ("no", True, False),
        ("off", True, False),
        ("  true  ", False, True),
        ("garbage", True, True),
        ("garbage", False, False),
    ],
)
def test_env_bool(raw: str | None, default: bool, expected: bool) -> None:
    assert env_bool(raw, default=default) is expected
```

- [ ] **Step 2: Run test, verify fail**

Run: `uv run pytest tests/test_envutil.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement helper**

Create `src/paperless_mcp/_envutil.py`:

```python
"""Internal env parsing utilities."""
from __future__ import annotations

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}


def env_bool(raw: str | None, *, default: bool) -> bool:
    """Parse env string to bool. Falls back to default if unset or unrecognized."""
    if raw is None:
        return default
    norm = raw.strip().lower()
    if norm in _TRUTHY:
        return True
    if norm in _FALSY:
        return False
    return default
```

- [ ] **Step 4: Wire into config.py**

Replace existing `Settings.from_env` body — change `verify_ssl` line:

```python
from ._envutil import env_bool
# ...
verify_ssl=env_bool(os.environ.get("PAPERLESS_VERIFY_SSL"), default=True),
```

- [ ] **Step 5: Wire into server.py**

Delete local `_env_bool` function (`server.py:20-24`). Replace usage at `server.py:38` with import:

```python
from ._envutil import env_bool
# ...
stateless_http=env_bool(os.environ.get("MCP_STATELESS"), default=True),
```

- [ ] **Step 6: Run tests + mypy + ruff**

Run: `uv run pytest tests/test_envutil.py -v && uv run ruff check . && uv run mypy src`
Expected: tests pass, no new lint/type errors.

- [ ] **Step 7: Commit**

```bash
git add src/paperless_mcp/_envutil.py src/paperless_mcp/config.py src/paperless_mcp/server.py tests/test_envutil.py
git commit -m "refactor: unify env-bool parsing across config and server"
```

---

## Task 2: Refuse HTTP transport without MCP_AUTH_TOKEN (C2)

**Files:**
- Modify: `src/paperless_mcp/server.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_server.py`:

```python
import os
import pytest

from paperless_mcp.server import main


def test_http_transport_requires_auth_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    with pytest.raises(SystemExit) as exc:
        main()
    assert "MCP_AUTH_TOKEN" in str(exc.value)


def test_stdio_transport_does_not_require_auth_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    called: dict[str, bool] = {}

    def fake_run(*_: object, **__: object) -> None:
        called["yes"] = True

    from paperless_mcp import app as app_module
    monkeypatch.setattr(app_module.mcp, "run", fake_run)
    main()
    assert called == {"yes": True}
```

- [ ] **Step 2: Run, verify fail**

Run: `uv run pytest tests/test_server.py -v`
Expected: `test_http_transport_requires_auth_token` FAIL.

- [ ] **Step 3: Implement guard**

Edit `src/paperless_mcp/server.py:main()` — add check before HTTP branch:

```python
def main() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport == "stdio":
        mcp.run()
        return
    if transport in {"http", "streamable-http"}:
        if not os.environ.get("MCP_AUTH_TOKEN"):
            raise SystemExit(
                "Refusing to start HTTP transport without MCP_AUTH_TOKEN. "
                "Set MCP_AUTH_TOKEN to a long random string, or use MCP_TRANSPORT=stdio."
            )
        mcp.run(
            transport="http",
            host=os.environ.get("MCP_HOST", "0.0.0.0"),
            port=int(os.environ.get("MCP_PORT", "8000")),
            path=os.environ.get("MCP_PATH", "/mcp"),
            stateless_http=env_bool(os.environ.get("MCP_STATELESS"), default=True),
        )
        return
    raise SystemExit(f"Unsupported MCP_TRANSPORT={transport!r} (use stdio or http)")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_server.py -v`
Expected: PASS.

- [ ] **Step 5: Update README + .env.example**

Add to `.env.example`:

```
# Required when MCP_TRANSPORT=http. Long random string. Clients send `Authorization: Bearer <token>`.
MCP_AUTH_TOKEN=
```

Add a brief note to `README.md` under HTTP/Docker section: "HTTP transport refuses to start without `MCP_AUTH_TOKEN`."

- [ ] **Step 6: Commit**

```bash
git add src/paperless_mcp/server.py tests/test_server.py .env.example README.md
git commit -m "fix(security): require MCP_AUTH_TOKEN for HTTP transport"
```

---

## Task 3: Sandbox save_to_path (C1)

**Files:**
- Create: `src/paperless_mcp/tools/_safe_path.py`
- Create: `tests/test_safe_path.py`
- Modify: `src/paperless_mcp/config.py`
- Modify: `src/paperless_mcp/tools/documents.py`
- Modify: `tests/test_documents.py`

- [ ] **Step 1: Add download_dir to Settings**

Edit `src/paperless_mcp/config.py`:

```python
from pathlib import Path
# ...
@dataclass(frozen=True)
class Settings:
    base_url: str
    token: str
    timeout: float
    verify_ssl: bool
    download_dir: Path | None

    @classmethod
    def from_env(cls) -> "Settings":
        url = os.environ.get("PAPERLESS_URL")
        token = os.environ.get("PAPERLESS_TOKEN")
        if not url:
            raise RuntimeError("PAPERLESS_URL not set")
        if not token:
            raise RuntimeError("PAPERLESS_TOKEN not set")
        raw_dir = os.environ.get("PAPERLESS_DOWNLOAD_DIR")
        download_dir = Path(raw_dir).expanduser().resolve() if raw_dir else None
        return cls(
            base_url=url.rstrip("/"),
            token=token,
            timeout=float(os.environ.get("PAPERLESS_TIMEOUT", "30")),
            verify_ssl=env_bool(os.environ.get("PAPERLESS_VERIFY_SSL"), default=True),
            download_dir=download_dir,
        )
```

- [ ] **Step 2: Write failing test for sandbox helper**

Create `tests/test_safe_path.py`:

```python
"""Path sandbox helper."""
from __future__ import annotations

from pathlib import Path

import pytest

from paperless_mcp.tools._safe_path import UnsafePathError, sanitize_save_path


def test_resolves_inside_root(tmp_path: Path) -> None:
    target = sanitize_save_path("file.pdf", root=tmp_path)
    assert target == tmp_path / "file.pdf"


def test_creates_subdir_under_root(tmp_path: Path) -> None:
    target = sanitize_save_path("sub/file.pdf", root=tmp_path)
    assert target == tmp_path / "sub" / "file.pdf"


def test_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(UnsafePathError):
        sanitize_save_path("../escape.pdf", root=tmp_path)


def test_rejects_absolute_outside_root(tmp_path: Path) -> None:
    with pytest.raises(UnsafePathError):
        sanitize_save_path("/etc/passwd", root=tmp_path)


def test_accepts_absolute_inside_root(tmp_path: Path) -> None:
    inside = tmp_path / "ok.pdf"
    target = sanitize_save_path(str(inside), root=tmp_path)
    assert target == inside


def test_requires_root_when_no_default() -> None:
    with pytest.raises(UnsafePathError):
        sanitize_save_path("/tmp/x.pdf", root=None)
```

- [ ] **Step 3: Run, verify fail**

Run: `uv run pytest tests/test_safe_path.py -v`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement sandbox helper**

Create `src/paperless_mcp/tools/_safe_path.py`:

```python
"""Constrain user-supplied save paths to a configured download directory."""
from __future__ import annotations

from pathlib import Path


class UnsafePathError(ValueError):
    """Raised when a save path escapes the allowed root."""


def sanitize_save_path(raw: str, *, root: Path | None) -> Path:
    """Resolve `raw` against `root` and ensure result stays inside `root`.

    Without `root`, all writes are refused. Relative paths are joined to root.
    Absolute paths must already be inside root after resolution.
    """
    if root is None:
        raise UnsafePathError(
            "save_to_path is disabled: set PAPERLESS_DOWNLOAD_DIR to enable disk writes"
        )
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise UnsafePathError(
            f"save_to_path {raw!r} resolves outside PAPERLESS_DOWNLOAD_DIR ({root_resolved})"
        ) from exc
    return resolved
```

- [ ] **Step 5: Run helper tests**

Run: `uv run pytest tests/test_safe_path.py -v`
Expected: PASS.

- [ ] **Step 6: Wire into download_document and get_document_preview**

Edit `src/paperless_mcp/tools/documents.py`:

```python
from ..app import client, mcp, settings
from ._safe_path import UnsafePathError, sanitize_save_path
```

Replace `save_to_path` block in `download_document` (lines 154-158):

```python
    if save_to_path:
        try:
            path = sanitize_save_path(save_to_path, root=settings.download_dir)
        except UnsafePathError as exc:
            return {"error": str(exc)}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        return {"saved_to": str(path), "bytes": size}
```

Same change in `get_document_preview` (lines 194-198).

- [ ] **Step 7: Update existing tests**

Edit `tests/test_documents.py::test_download_document_save_to_path`:

```python
async def test_download_document_save_to_path(
    mcp_client: Client, fake_client: FakeClient, tmp_path, monkeypatch
) -> None:
    from paperless_mcp import app as app_module
    from paperless_mcp.tools import documents as docs_mod
    from dataclasses import replace

    new_settings = replace(app_module.settings, download_dir=tmp_path)
    monkeypatch.setattr(app_module, "settings", new_settings)
    monkeypatch.setattr(docs_mod, "settings", new_settings)

    blob = b"abc"
    fake_client.set_binary("/api/documents/1/download/", blob)
    target = tmp_path / "out.pdf"
    result = await mcp_client.call_tool(
        "download_document",
        {"document_id": 1, "save_to_path": str(target)},
    )
    assert result.data["saved_to"] == str(target)
    assert target.read_bytes() == blob
```

Add new tests:

```python
async def test_download_document_rejects_traversal(
    mcp_client: Client, fake_client: FakeClient, tmp_path, monkeypatch
) -> None:
    from paperless_mcp import app as app_module
    from paperless_mcp.tools import documents as docs_mod
    from dataclasses import replace

    new_settings = replace(app_module.settings, download_dir=tmp_path)
    monkeypatch.setattr(app_module, "settings", new_settings)
    monkeypatch.setattr(docs_mod, "settings", new_settings)

    fake_client.set_binary("/api/documents/1/download/", b"x")
    result = await mcp_client.call_tool(
        "download_document",
        {"document_id": 1, "save_to_path": "../escape.pdf"},
    )
    assert "error" in result.data
    assert "outside" in result.data["error"].lower()


async def test_download_document_save_disabled_without_root(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_binary("/api/documents/1/download/", b"x")
    result = await mcp_client.call_tool(
        "download_document",
        {"document_id": 1, "save_to_path": "/tmp/x.pdf"},
    )
    assert "error" in result.data
    assert "PAPERLESS_DOWNLOAD_DIR" in result.data["error"]
```

- [ ] **Step 8: Run full test suite + mypy**

Run: `uv run pytest && uv run mypy src && uv run ruff check .`
Expected: all pass.

- [ ] **Step 9: Document env var**

Append to `.env.example`:

```
# Optional. Absolute path. Required to allow download_document/get_document_preview save_to_path writes.
# Leave unset to disable disk writes entirely.
PAPERLESS_DOWNLOAD_DIR=
```

- [ ] **Step 10: Commit**

```bash
git add src/paperless_mcp/tools/_safe_path.py src/paperless_mcp/tools/documents.py src/paperless_mcp/config.py tests/test_safe_path.py tests/test_documents.py .env.example
git commit -m "fix(security): sandbox save_to_path under PAPERLESS_DOWNLOAD_DIR"
```

---

## Task 4: Fix paginate cap on plain-list responses (H3)

**Files:**
- Modify: `src/paperless_mcp/client.py`
- Modify: `tests/test_client.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_client.py`:

```python
async def test_paginate_caps_plain_list_with_max_items() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": i} for i in range(10)])

    c = _make_client(handler)
    items = await c.paginate("/api/list/", max_items=3)
    assert len(items) == 3
    await c.aclose()
```

- [ ] **Step 2: Verify fail**

Run: `uv run pytest tests/test_client.py::test_paginate_caps_plain_list_with_max_items -v`
Expected: FAIL — returns 10 items.

- [ ] **Step 3: Fix client**

Edit `src/paperless_mcp/client.py:80-84`:

```python
            results = data.get("results") if isinstance(data, dict) else None
            if results is None:
                if not isinstance(data, list):
                    return []
                return data[:max_items] if max_items is not None else data
```

- [ ] **Step 4: Verify pass**

Run: `uv run pytest tests/test_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/paperless_mcp/client.py tests/test_client.py
git commit -m "fix(client): cap plain-list paginate responses with max_items"
```

---

## Task 5: Guard tasks.list_tasks against None results (H2)

**Files:**
- Modify: `src/paperless_mcp/tools/tasks.py`
- Create: `tests/test_tasks.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_tasks.py`:

```python
"""list_tasks tool."""
from __future__ import annotations

from fastmcp import Client

from .conftest import FakeClient


async def test_list_tasks_handles_list(mcp_client: Client, fake_client: FakeClient) -> None:
    fake_client.set_get("/api/tasks/", [{"id": 1}, {"id": 2}])
    result = await mcp_client.call_tool("list_tasks", {"max_results": 1})
    assert len(result.data) == 1


async def test_list_tasks_handles_drf_dict(mcp_client: Client, fake_client: FakeClient) -> None:
    fake_client.set_get("/api/tasks/", {"results": [{"id": 1}]})
    result = await mcp_client.call_tool("list_tasks", {})
    assert result.data == [{"id": 1}]


async def test_list_tasks_handles_null_results(mcp_client: Client, fake_client: FakeClient) -> None:
    fake_client.set_get("/api/tasks/", {"results": None})
    result = await mcp_client.call_tool("list_tasks", {})
    assert result.data == []
```

- [ ] **Step 2: Verify fail**

Run: `uv run pytest tests/test_tasks.py -v`
Expected: `test_list_tasks_handles_null_results` FAIL with TypeError.

- [ ] **Step 3: Fix tasks.py**

Edit `src/paperless_mcp/tools/tasks.py:19-21`:

```python
    if isinstance(data, dict):
        results = data.get("results") or []
        return results[:max_results]
    return []
```

- [ ] **Step 4: Verify pass**

Run: `uv run pytest tests/test_tasks.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/paperless_mcp/tools/tasks.py tests/test_tasks.py
git commit -m "fix(tasks): handle null results from /api/tasks/"
```

---

## Task 6: Extract shared filter builder (M3) and parallelize resolution (M2)

**Files:**
- Create: `src/paperless_mcp/tools/_filters.py`
- Modify: `src/paperless_mcp/tools/highlevel.py`
- Create: `tests/test_filters.py`

- [ ] **Step 1: Write failing test for builder**

Create `tests/test_filters.py`:

```python
"""build_document_filters helper."""
from __future__ import annotations

from paperless_mcp.tools._filters import FilterRequest, build_document_filters

from .conftest import FakeClient


async def test_resolves_correspondent_and_doc_type(fake_client: FakeClient) -> None:
    fake_client.set_get(
        "/api/correspondents/", {"results": [{"id": 7, "name": "Acme"}]}
    )
    fake_client.set_get(
        "/api/document_types/", {"results": [{"id": 3, "name": "Invoice"}]}
    )
    req = FilterRequest(correspondent_name="Acme", document_type_name="Invoice")
    params, unresolved = await build_document_filters(req)
    assert params["correspondent__id"] == 7
    assert params["document_type__id"] == 3
    assert unresolved == []


async def test_collects_unresolved(fake_client: FakeClient) -> None:
    fake_client.set_get("/api/correspondents/", {"results": []})
    req = FilterRequest(correspondent_name="Ghost")
    params, unresolved = await build_document_filters(req)
    assert "correspondent:Ghost" in unresolved
    assert "correspondent__id" not in params


async def test_resolves_tag_lists(fake_client: FakeClient) -> None:
    fake_client.set_get("/api/tags/", {"results": [{"id": 11, "name": "tax"}]})
    req = FilterRequest(tag_names_all=["tax"])
    params, _ = await build_document_filters(req)
    assert params["tags__id__all"] == "11"


async def test_passes_through_simple_filters(fake_client: FakeClient) -> None:
    req = FilterRequest(
        title_contains="invoice",
        text_contains="rent",
        year=2026,
        month=4,
        created_after="2026-01-01",
        created_before="2026-12-31",
    )
    params, _ = await build_document_filters(req)
    assert params["title__icontains"] == "invoice"
    assert params["content__icontains"] == "rent"
    assert params["created__year"] == 2026
    assert params["created__month"] == 4
    assert params["created__date__gte"] == "2026-01-01"
    assert params["created__date__lte"] == "2026-12-31"
```

- [ ] **Step 2: Verify fail**

Run: `uv run pytest tests/test_filters.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement builder**

Create `src/paperless_mcp/tools/_filters.py`:

```python
"""Shared document filter assembly. Resolves names → ids in parallel."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from ._helpers import resolve_name_to_id, resolve_names_to_ids


@dataclass(frozen=True)
class FilterRequest:
    correspondent_name: str | None = None
    document_type_name: str | None = None
    storage_path_name: str | None = None
    tag_names_all: list[str] = field(default_factory=list)
    tag_names_any: list[str] = field(default_factory=list)
    title_contains: str | None = None
    text_contains: str | None = None
    year: int | None = None
    month: int | None = None
    created_after: str | None = None
    created_before: str | None = None


async def build_document_filters(
    req: FilterRequest,
) -> tuple[dict[str, Any], list[str]]:
    """Resolve names to IDs concurrently and assemble DRF query params."""
    params: dict[str, Any] = {}
    unresolved: list[str] = []

    async def _resolve_one(path: str, name: str | None) -> int | None:
        if not name:
            return None
        return await resolve_name_to_id(path, name)

    corr, dtype, spath, tags_all, tags_any = await asyncio.gather(
        _resolve_one("/api/correspondents/", req.correspondent_name),
        _resolve_one("/api/document_types/", req.document_type_name),
        _resolve_one("/api/storage_paths/", req.storage_path_name),
        resolve_names_to_ids("/api/tags/", req.tag_names_all) if req.tag_names_all else _empty_ids(),
        resolve_names_to_ids("/api/tags/", req.tag_names_any) if req.tag_names_any else _empty_ids(),
    )

    if req.correspondent_name:
        if corr is None:
            unresolved.append(f"correspondent:{req.correspondent_name}")
        else:
            params["correspondent__id"] = corr
    if req.document_type_name:
        if dtype is None:
            unresolved.append(f"document_type:{req.document_type_name}")
        else:
            params["document_type__id"] = dtype
    if req.storage_path_name:
        if spath is None:
            unresolved.append(f"storage_path:{req.storage_path_name}")
        else:
            params["storage_path__id"] = spath
    if req.tag_names_all:
        if len(tags_all) != len(req.tag_names_all):
            unresolved.append(f"some tags missing in: {req.tag_names_all}")
        if tags_all:
            params["tags__id__all"] = ",".join(str(i) for i in tags_all)
    if req.tag_names_any and tags_any:
        params["tags__id__in"] = ",".join(str(i) for i in tags_any)
    if req.title_contains:
        params["title__icontains"] = req.title_contains
    if req.text_contains:
        params["content__icontains"] = req.text_contains
    if req.year is not None:
        params["created__year"] = req.year
    if req.month is not None:
        params["created__month"] = req.month
    if req.created_after:
        params["created__date__gte"] = req.created_after
    if req.created_before:
        params["created__date__lte"] = req.created_before
    return params, unresolved


async def _empty_ids() -> list[int]:
    return []
```

- [ ] **Step 4: Verify builder tests pass**

Run: `uv run pytest tests/test_filters.py -v`
Expected: PASS.

- [ ] **Step 5: Refactor find_documents to use builder**

Edit `src/paperless_mcp/tools/highlevel.py` — replace `find_documents` body (keep tool decorator and signature):

```python
@mcp.tool(annotations={"readOnlyHint": True})
async def find_documents(
    correspondent_name: Annotated[str | None, Field(description="Correspondent name (resolved to id)")] = None,
    document_type_name: Annotated[str | None, Field(description="Doc type name (resolved to id)")] = None,
    storage_path_name: Annotated[str | None, Field(description="Storage path name (resolved to id)")] = None,
    tag_names_all: Annotated[list[str] | None, Field(description="All tag names (resolved)")] = None,
    tag_names_any: Annotated[list[str] | None, Field(description="Any tag names (resolved)")] = None,
    title_contains: Annotated[str | None, Field(description="Title icontains")] = None,
    text_contains: Annotated[str | None, Field(description="OCR content icontains (DB-only)")] = None,
    year: Annotated[int | None, Field(description="Document creation year")] = None,
    month: Annotated[int | None, Field(description="Document creation month 1-12")] = None,
    created_after: Annotated[str | None, Field(description="ISO YYYY-MM-DD")] = None,
    created_before: Annotated[str | None, Field(description="ISO YYYY-MM-DD")] = None,
    max_results: Annotated[int, Field(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    """Find documents using human-friendly names. Resolves names→IDs then queries."""
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
    params, unresolved = await build_document_filters(req)
    params["ordering"] = "-created"
    docs = await client.paginate("/api/documents/", params=params, max_items=max_results)
    return {
        "count": len(docs),
        "unresolved": unresolved,
        "filters_applied": {k: v for k, v in params.items() if k != "ordering"},
        "documents": [slim_document(d) for d in docs],
    }
```

Add import at top of `highlevel.py`:

```python
from ._filters import FilterRequest, build_document_filters
```

- [ ] **Step 6: Run existing highlevel tests**

Run: `uv run pytest tests/test_highlevel.py -v`
Expected: PASS (existing test_find_documents_* still green).

- [ ] **Step 7: Commit**

```bash
git add src/paperless_mcp/tools/_filters.py src/paperless_mcp/tools/highlevel.py tests/test_filters.py
git commit -m "refactor(tools): extract FilterRequest builder, parallelize name resolution"
```

---

## Task 7: Fix mypy errors and add tests for interactive_search (H1)

**Files:**
- Modify: `src/paperless_mcp/tools/highlevel.py`
- Create: `tests/test_interactive_search.py`

- [ ] **Step 1: Write failing branch tests**

Create `tests/test_interactive_search.py`:

```python
"""interactive_search tool — mocks Context.elicit to drive each branch."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastmcp import Client

from .conftest import FakeClient


@dataclass
class _ElicitResult:
    action: str
    data: Any = None


class _ScriptedContext:
    """Replay scripted elicit responses; matches FastMCP Context.elicit shape."""

    def __init__(self, script: list[_ElicitResult]) -> None:
        self._script = list(script)
        self.prompts: list[str] = []

    async def elicit(self, prompt: str, response_type: Any = None) -> _ElicitResult:
        self.prompts.append(prompt)
        return self._script.pop(0)


@pytest.fixture
def patch_elicit(monkeypatch: pytest.MonkeyPatch):
    """Replace highlevel.interactive_search Context dependency by injecting through call."""
    from paperless_mcp.tools import highlevel as hl

    def install(script: list[_ElicitResult]) -> _ScriptedContext:
        ctx = _ScriptedContext(script)
        # Patch the underlying function to bypass FastMCP's context injection.
        original = hl.interactive_search.fn

        async def wrapper(_injected_ctx, **kwargs):
            return await original(ctx, **kwargs)

        monkeypatch.setattr(hl.interactive_search, "fn", wrapper)
        return ctx

    return install


async def test_full_text_branch(
    mcp_client: Client, fake_client: FakeClient, patch_elicit
) -> None:
    patch_elicit(
        [
            _ElicitResult("accept", "full_text"),
            _ElicitResult("accept", "rent"),
        ]
    )
    fake_client.set_get(
        "/api/search/", {"count": 1, "results": [{"id": 1, "score": 0.9}]}
    )
    result = await mcp_client.call_tool("interactive_search", {})
    assert result.data["strategy"] == "full_text"
    assert result.data["query"] == "rent"
    assert result.data["count"] == 1


async def test_recent_branch(
    mcp_client: Client, fake_client: FakeClient, patch_elicit
) -> None:
    patch_elicit(
        [
            _ElicitResult("accept", "recent"),
            _ElicitResult("accept", 14),
        ]
    )
    fake_client.set_paginate("/api/documents/", [{"id": 9, "title": "x"}])
    result = await mcp_client.call_tool("interactive_search", {})
    assert result.data["strategy"] == "recent"
    assert result.data["count"] == 1


async def test_filters_branch(
    mcp_client: Client, fake_client: FakeClient, patch_elicit
) -> None:
    from paperless_mcp.tools.highlevel import _FilterForm

    patch_elicit(
        [
            _ElicitResult("accept", "filters"),
            _ElicitResult(
                "accept",
                _FilterForm(correspondent_name="Acme", title_contains="bill"),
            ),
        ]
    )
    fake_client.set_get(
        "/api/correspondents/", {"results": [{"id": 7, "name": "Acme"}]}
    )
    fake_client.set_paginate("/api/documents/", [])
    result = await mcp_client.call_tool("interactive_search", {})
    assert result.data["strategy"] == "filters"
    assert result.data["filters_applied"]["correspondent__id"] == 7
    assert result.data["filters_applied"]["title__icontains"] == "bill"


async def test_user_declines_strategy(
    mcp_client: Client, fake_client: FakeClient, patch_elicit
) -> None:
    patch_elicit([_ElicitResult("decline")])
    result = await mcp_client.call_tool("interactive_search", {})
    assert result.data["status"] == "decline"
    assert result.data["step"] == "strategy"
```

> Note: if the wrapper-injection seam fails against current FastMCP `tool.fn` API, swap to `monkeypatch.setattr` against `hl.interactive_search` directly with a wrapper produced by `mcp.tool(...)`. Verify by running tests after Step 4.

- [ ] **Step 2: Run, verify fail**

Run: `uv run pytest tests/test_interactive_search.py -v`
Expected: FAIL — current code raises type errors at runtime when `f.correspondent_name` accessed if FastMCP returns dict.

- [ ] **Step 3: Fix mypy errors and runtime safety in interactive_search**

Edit `src/paperless_mcp/tools/highlevel.py` — replace `interactive_search` body. Key changes: cast elicit data, rename inner `params`, switch to `FilterRequest`/`build_document_filters`, fix `max(1, days.data)`:

```python
@mcp.tool(annotations={"readOnlyHint": True})
async def interactive_search(
    ctx: Context,
    max_results: Annotated[int, Field(ge=1, le=200)] = 25,
) -> dict[str, Any]:
    """Interactive document search. Elicits strategy + parameters from user step by step."""
    strategy = await ctx.elicit(
        "How do you want to search?",
        response_type=["full_text", "filters", "recent"],
    )
    if strategy.action != "accept":
        return {"status": strategy.action, "step": "strategy"}
    strategy_value = str(strategy.data)

    if strategy_value == "full_text":
        q = await ctx.elicit("Enter full-text query (Whoosh syntax ok):", response_type=str)
        if q.action != "accept":
            return {"status": q.action, "step": "query"}
        data = await client.get("/api/search/", params={"query": str(q.data)})
        results = data.get("results", []) if isinstance(data, dict) else []
        return {
            "strategy": "full_text",
            "query": str(q.data),
            "count": data.get("count") if isinstance(data, dict) else len(results),
            "results": results[:max_results],
        }

    if strategy_value == "recent":
        days = await ctx.elicit("Look-back window in days?", response_type=int)
        if days.action != "accept":
            return {"status": days.action, "step": "days"}
        from datetime import date, timedelta

        days_int = max(1, int(days.data) if days.data is not None else 1)
        since = (date.today() - timedelta(days=days_int)).isoformat()
        recent_params = {"added__date__gte": since, "ordering": "-added"}
        recent_docs = await client.paginate(
            "/api/documents/", params=recent_params, max_items=max_results
        )
        return {
            "strategy": "recent",
            "since": since,
            "count": len(recent_docs),
            "documents": [slim_document(d) for d in recent_docs],
        }

    form = await ctx.elicit(
        "Provide any filters (leave blank to skip). Tags as comma-separated names.",
        response_type=_FilterForm,
    )
    if form.action != "accept":
        return {"status": form.action, "step": "filters"}
    f = cast(_FilterForm, form.data)

    tag_names = [n.strip() for n in f.tag_names_csv.split(",") if n.strip()] if f.tag_names_csv else []
    req = FilterRequest(
        correspondent_name=f.correspondent_name or None,
        document_type_name=f.document_type_name or None,
        tag_names_all=tag_names,
        title_contains=f.title_contains or None,
        year=f.year or None,
        created_after=f.created_after or None,
        created_before=f.created_before or None,
    )
    filter_params, unresolved = await build_document_filters(req)
    filter_params["ordering"] = "-created"

    if len(filter_params) == 1:
        confirm = await ctx.elicit(
            "No filters provided. Run unfiltered listing (most recent)?",
            response_type=None,
        )
        if confirm.action != "accept":
            return {"status": confirm.action, "step": "confirm_unfiltered"}

    filter_docs = await client.paginate(
        "/api/documents/", params=filter_params, max_items=max_results
    )
    return {
        "strategy": "filters",
        "unresolved": unresolved,
        "filters_applied": {k: v for k, v in filter_params.items() if k != "ordering"},
        "count": len(filter_docs),
        "documents": [slim_document(d) for d in filter_docs],
    }
```

Add import at top of file:

```python
from typing import Annotated, Any, cast
```

- [ ] **Step 4: Run mypy + tests**

Run: `uv run mypy src && uv run pytest -v`
Expected: mypy clean for `highlevel.py`; new and existing tests green. If `interactive_search` patching seam fails, adjust the test wrapper to operate on `mcp._tool_manager` registration — verify against FastMCP 3 internals at runtime.

- [ ] **Step 5: Commit**

```bash
git add src/paperless_mcp/tools/highlevel.py tests/test_interactive_search.py
git commit -m "fix(highlevel): type-safe interactive_search; cover all elicit branches"
```

---

## Task 8: Remove dead `_OrderingChoice` and align thumbnail mime (M1, M6)

**Files:**
- Modify: `src/paperless_mcp/tools/documents.py`
- Modify: `src/paperless_mcp/client.py`

- [ ] **Step 1: Delete `_OrderingChoice`**

Edit `src/paperless_mcp/tools/documents.py` — delete lines 219-230 (`_OrderingChoice = Literal[...]`). Remove `Literal` from imports if no longer used.

- [ ] **Step 2: Add `get_binary_with_headers` to client**

Edit `src/paperless_mcp/client.py` — add after `get_binary`:

```python
    async def get_binary_with_headers(
        self, path: str, **kw: Any
    ) -> tuple[bytes, dict[str, str]]:
        clean = {k: v for k, v in (kw.get("params") or {}).items() if v is not None}
        resp = await self._client.request("GET", path, params=clean)
        if resp.status_code >= 400:
            raise PaperlessAPIError(resp.status_code, resp.text, "GET", path)
        return resp.content, dict(resp.headers)
```

- [ ] **Step 3: Update FakeClient in conftest**

Edit `tests/conftest.py` — extend `FakeClient`:

```python
    def set_binary_with_headers(self, path: str, blob: bytes, headers: dict[str, str]) -> None:
        self.binary_responses[path] = blob
        self.binary_headers = getattr(self, "binary_headers", {})
        self.binary_headers[path] = headers

    async def get_binary_with_headers(self, path: str, **_: Any) -> tuple[bytes, dict[str, str]]:
        self.calls.append(("GET_BIN_HDR", path, None))
        if path not in self.binary_responses:
            raise AssertionError(f"Unexpected GET_BIN_HDR {path}")
        headers = getattr(self, "binary_headers", {}).get(path, {})
        return self.binary_responses[path], headers
```

- [ ] **Step 4: Update thumbnail tool**

Edit `src/paperless_mcp/tools/documents.py::get_document_thumbnail`:

```python
@mcp.tool(annotations={"readOnlyHint": True})
async def get_document_thumbnail(
    document_id: Annotated[int, Field(description="Document id")],
) -> dict[str, Any]:
    """Get document thumbnail as base64."""
    blob, headers = await client.get_binary_with_headers(
        f"/api/documents/{document_id}/thumb/"
    )
    mime = headers.get("content-type", "application/octet-stream").split(";")[0].strip()
    return {
        "encoding": "base64",
        "mime": mime,
        "bytes": len(blob),
        "data": base64.b64encode(blob).decode("ascii"),
    }
```

- [ ] **Step 5: Add test**

Append to `tests/test_documents.py`:

```python
async def test_thumbnail_uses_response_mime(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_binary_with_headers(
        "/api/documents/1/thumb/", b"PNGDATA", {"content-type": "image/png"}
    )
    result = await mcp_client.call_tool("get_document_thumbnail", {"document_id": 1})
    assert result.data["mime"] == "image/png"
```

- [ ] **Step 6: Run tests + mypy + ruff**

Run: `uv run pytest && uv run mypy src && uv run ruff check .`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/paperless_mcp/tools/documents.py src/paperless_mcp/client.py tests/conftest.py tests/test_documents.py
git commit -m "refactor: drop dead _OrderingChoice; thumbnail mime from response header"
```

---

## Task 9: Final verification

- [ ] **Step 1: Full sweep**

Run:
```bash
uv run ruff check .
uv run mypy src
uv run pytest -v
```

Expected:
- ruff: All checks passed
- mypy: zero errors across `src/`
- pytest: all tests green (45 original + ~20 new)

- [ ] **Step 2: Smoke test stdio boot**

Run: `MCP_TRANSPORT=stdio PAPERLESS_URL=http://x.invalid PAPERLESS_TOKEN=t timeout 2 uv run paperless-mcp || true`
Expected: process starts then exits on timeout (no import-time crash).

- [ ] **Step 3: Smoke test HTTP refusal**

Run: `MCP_TRANSPORT=http PAPERLESS_URL=http://x.invalid PAPERLESS_TOKEN=t uv run paperless-mcp; echo "exit=$?"`
Expected: exit nonzero, stderr mentions `MCP_AUTH_TOKEN`.

- [ ] **Step 4: Final commit (if any pending)**

```bash
git status
# If clean — done. Otherwise commit residuals.
```

---

## Self-Review Notes

- **Spec coverage**: C1 (Task 3), C2 (Task 2), H1 (Task 7), H2 (Task 5), H3 (Task 4), M1 (Task 8), M2 (Task 6), M3 (Task 6), M4+M5 (Task 1), M6 (Task 8). M7/M8/M9 not addressed (test seam refactor, additional coverage, server-transport tests) — left as follow-up because they are LOW-impact polish; flag in commit message of Task 9 if desired.
- **Type consistency**: `FilterRequest` field names align between `_filters.py` and both call sites (`find_documents`, `interactive_search`). `_FilterForm.tag_names_csv` stays string; conversion to list happens at the call site in Task 7.
- **Placeholder scan**: no TBD/TODO. All code blocks complete.

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-04-26-code-review-corrections.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — execute tasks in this session with checkpoints

Which approach?
