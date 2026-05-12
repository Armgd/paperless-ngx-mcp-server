# FastMCP Followup — Phase 2 Typed Pydantic Response Models

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `dict[str, Any]` / `list[dict[str, Any]]` return types on read tools with frozen Pydantic models so FastMCP advertises a real `outputSchema` per tool. Strengthens client-side typing, gives MCP clients a structured contract, and lets `slim_document` / `_slim_taxonomy` be enforced by the schema rather than convention.

**Architecture:** Introduce one new module `src/paperless_mcp/models.py` housing all response DTOs (frozen `BaseModel` subclasses with `model_config = ConfigDict(frozen=True, extra="ignore")`). Refactor each tool module to construct and return the typed model instead of a hand-built dict. `slim_document` and `_slim_taxonomy` become *constructors* that map raw paperless JSON → DTO. No wire-format change for current MCP clients (FastMCP serializes BaseModel via `model_dump`); the gain is the advertised JSON Schema in `tools/list`. Out of scope: tool input schemas (already typed via `Annotated[..., Field]`), write/POST tools (none yet).

**Tech Stack:** Python 3.12, FastMCP 3.2.4, Pydantic 2.x (already a transitive dep via FastMCP), pytest-asyncio, mypy strict, ruff.

**Why empirical first:** Paperless responses contain optional / nullable fields (`storage_path`, `archive_serial_number`, `archived_file_name`, custom field shapes) whose `None`-ability and types we must observe before locking a schema. Task 1 captures real samples into `tests/fixtures/`.

---

## File Structure

**Create:**
- `src/paperless_mcp/models.py` — all response DTOs.
- `tests/fixtures/paperless/documents_list.json` — captured DRF list page.
- `tests/fixtures/paperless/document_detail.json` — captured detail.
- `tests/fixtures/paperless/tags_list.json`, `correspondents_list.json`, `document_types_list.json`, `storage_paths_list.json`, `custom_fields_list.json`, `saved_views_list.json`.
- `tests/fixtures/paperless/search_results.json` — Whoosh `/api/search/` payload.
- `tests/fixtures/paperless/suggestions.json`, `metadata.json`, `notes.json`.
- `tests/fixtures/paperless/stats.json`, `tasks.json`, `profile.json`.
- `tests/test_models.py` — round-trip tests: fixture JSON → model → `model_dump()` ⊆ original.
- `scripts/capture_fixtures.py` — one-shot runner that hits a live paperless and writes fixtures (gitignored target host).

**Modify:**
- `src/paperless_mcp/tools/_helpers.py` — `slim_document` returns `DocumentSummary`; add `slim_taxonomy_item`.
- `src/paperless_mcp/tools/documents.py` — annotate every tool with concrete return type; build models.
- `src/paperless_mcp/tools/taxonomy.py` — same.
- `src/paperless_mcp/tools/highlevel.py` — `find_documents` → `FindDocumentsResult`; `answer_from_documents` → `AnswerFromDocumentsResult`; `recent_documents` → `RecentDocumentsResult`; keep `interactive_search` returning `dict[str, Any]` (heterogeneous union — covered separately, see Task 5 step 1).
- `src/paperless_mcp/tools/search.py` — `SearchResult` model.
- `src/paperless_mcp/tools/stats.py`, `tasks.py`, `auth.py` — typed returns.
- `tests/conftest.py:21-89` — `FakeClient` unchanged; add a `load_fixture(name)` helper at module scope.
- All `tests/test_*.py` — assertions move from `result["foo"]` (dict) to `result.foo` (model attr) where assertions probe tool *return values*. MCP-client-call assertions stay dict-shaped because FastMCP serializes on the wire.
- `pyproject.toml` — pin `pydantic>=2.7` explicitly (already pulled in transitively but make it intentional).
- `CLAUDE.md` — append a "Response models" subsection under Conventions.

**No deleted files.**

---

## Task 1: Capture live fixtures

**Files:** `scripts/capture_fixtures.py`, `tests/fixtures/paperless/*.json`

Empirical grounding before model design. Without real samples we will guess wrong on nullability.

- [ ] **Step 1: Create capture script**

Write `scripts/capture_fixtures.py`:

```python
"""Capture live paperless responses into tests/fixtures/paperless/.

Usage: PAPERLESS_URL=... PAPERLESS_TOKEN=... uv run python scripts/capture_fixtures.py
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from paperless_mcp.client import PaperlessClient
from paperless_mcp.config import Settings

ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "paperless"


async def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    s = Settings.from_env()
    c = PaperlessClient(s)
    try:
        targets = {
            "documents_list.json": ("/api/documents/", {"page_size": 5}),
            "tags_list.json": ("/api/tags/", {"page_size": 5}),
            "correspondents_list.json": ("/api/correspondents/", {"page_size": 5}),
            "document_types_list.json": ("/api/document_types/", {"page_size": 5}),
            "storage_paths_list.json": ("/api/storage_paths/", {"page_size": 5}),
            "custom_fields_list.json": ("/api/custom_fields/", {"page_size": 5}),
            "saved_views_list.json": ("/api/saved_views/", {"page_size": 5}),
            "search_results.json": ("/api/search/", {"query": "the"}),
            "stats.json": ("/api/statistics/", None),
            "tasks.json": ("/api/tasks/", None),
            "profile.json": ("/api/profile/", None),
        }
        for fname, (path, params) in targets.items():
            try:
                data = await c.get(path, params=params)
            except Exception as e:  # capture failures too
                data = {"__error__": str(e)}
            (ROOT / fname).write_text(json.dumps(data, indent=2, default=str))

        # detail fixtures from first list result
        docs = json.loads((ROOT / "documents_list.json").read_text()).get("results", [])
        if docs:
            doc_id = docs[0]["id"]
            for fname, path in [
                ("document_detail.json", f"/api/documents/{doc_id}/"),
                ("metadata.json", f"/api/documents/{doc_id}/metadata/"),
                ("notes.json", f"/api/documents/{doc_id}/notes/"),
                ("suggestions.json", f"/api/documents/{doc_id}/suggestions/"),
            ]:
                try:
                    data = await c.get(path)
                except Exception as e:
                    data = {"__error__": str(e)}
                (ROOT / fname).write_text(json.dumps(data, indent=2, default=str))
    finally:
        await c.aclose()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run against live paperless and inspect**

Run: `uv run python scripts/capture_fixtures.py && ls tests/fixtures/paperless/`

Expected: 14 JSON files written. Open `documents_list.json` and `document_detail.json` and confirm presence of fields used by `slim_document` (id, title, correspondent, document_type, storage_path, tags, created, created_date, modified, added, archive_serial_number, original_file_name, archived_file_name, mime_type, custom_fields, page_count, notes). Note any field that is `null` in real data — those become `Optional` in the model.

If a target paperless instance is not available, fall back to handcrafted minimal fixtures based on the vendored `Paperless-ngx REST API (9).yaml` schema; mark each file's first key as `"__source__": "openapi-skeleton"` so future captures can replace them.

- [ ] **Step 3: Sanitize**

Manually scan fixtures for PII (names, emails, document titles). Replace sensitive strings with `"REDACTED-<n>"` while keeping types and lengths roughly intact. Confirm no auth tokens leaked in `profile.json`.

- [ ] **Step 4: Commit fixtures**

```bash
git add tests/fixtures/paperless/ scripts/capture_fixtures.py
git commit -m "test(fixtures): capture sanitized paperless response samples"
```

---

## Task 2: Define `models.py` core DTOs

**Files:** `src/paperless_mcp/models.py`, `tests/test_models.py`

- [ ] **Step 1: Write failing model round-trip test**

Create `tests/test_models.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperless_mcp.models import (
    DocumentDetail,
    DocumentSummary,
    DocumentsListResult,
    TaxonomyItem,
)

FIXTURES = Path(__file__).parent / "fixtures" / "paperless"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_document_summary_from_list_fixture() -> None:
    page = _load("documents_list.json")
    raw = page["results"][0]
    summary = DocumentSummary.model_validate(raw)
    assert summary.id == raw["id"]
    assert summary.title == raw["title"]
    # frozen
    with pytest.raises(Exception):
        summary.id = -1  # type: ignore[misc]


def test_document_detail_round_trip() -> None:
    raw = _load("document_detail.json")
    detail = DocumentDetail.model_validate(raw)
    dumped = detail.model_dump(exclude_none=True)
    for k in ("id", "title", "created"):
        assert dumped[k] == raw[k]


def test_taxonomy_item_optional_fields() -> None:
    page = _load("tags_list.json")
    item = TaxonomyItem.model_validate(page["results"][0])
    assert item.id is not None
    assert item.name


def test_documents_list_result_envelope() -> None:
    page = _load("documents_list.json")
    summaries = [DocumentSummary.model_validate(r) for r in page["results"][:2]]
    result = DocumentsListResult(count=len(summaries), documents=summaries)
    assert result.count == 2
    assert result.documents[0].id == page["results"][0]["id"]
```

Run: `uv run pytest tests/test_models.py -v` → all FAIL with `ModuleNotFoundError: paperless_mcp.models`.

- [ ] **Step 2: Create `models.py`**

Write `src/paperless_mcp/models.py`:

```python
"""Frozen Pydantic response models advertised via FastMCP outputSchema."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


# --- Documents ---

class CustomFieldValue(_Frozen):
    field: int
    value: Any = None  # polymorphic per data_type (string/number/date/monetary)


class DocumentNote(_Frozen):
    id: int
    note: str
    created: str | None = None
    user: int | None = None


class DocumentSummary(_Frozen):
    """Slimmed document used in list endpoints (mirrors `slim_document`)."""
    id: int
    title: str
    correspondent: int | None = None
    document_type: int | None = None
    storage_path: int | None = None
    tags: list[int] = Field(default_factory=list)
    created: str | None = None
    created_date: str | None = None
    modified: str | None = None
    added: str | None = None
    archive_serial_number: int | None = None
    original_file_name: str | None = None
    archived_file_name: str | None = None
    mime_type: str | None = None
    is_shared_by_requester: bool | None = None
    custom_fields: list[CustomFieldValue] = Field(default_factory=list)
    page_count: int | None = None
    notes: list[DocumentNote] = Field(default_factory=list)


class DocumentDetail(DocumentSummary):
    """Full record returned by `get_document` (no `content`; that's separate)."""
    owner: int | None = None
    user_can_change: bool | None = None


class DocumentContent(_Frozen):
    id: int
    title: str
    created: str | None = None
    correspondent: int | None = None
    document_type: int | None = None
    tags: list[int] = Field(default_factory=list)
    content: str
    content_truncated: bool
    content_total_chars: int


class DocumentsListResult(_Frozen):
    count: int
    documents: list[DocumentSummary]


# --- Taxonomy ---

class TaxonomyItem(_Frozen):
    id: int
    name: str
    slug: str | None = None
    match: str | None = None
    matching_algorithm: int | None = None
    is_insensitive: bool | None = None
    document_count: int | None = None
    color: str | None = None
    is_inbox_tag: bool | None = None
    owner: int | None = None
    path: str | None = None
    data_type: str | None = None


# --- Search ---

class SearchHit(_Frozen):
    id: int
    title: str | None = None
    score: float | None = None
    highlights: Any = None
    note_highlights: Any = None


class SearchResult(_Frozen):
    count: int
    results: list[SearchHit]


# --- Highlevel ---

class FindDocumentsResult(_Frozen):
    count: int
    unresolved: list[str] = Field(default_factory=list)
    filters_applied: dict[str, Any] = Field(default_factory=dict)
    documents: list[DocumentSummary]


class AnswerSource(_Frozen):
    id: int
    title: str | None = None
    created: str | None = None
    correspondent: int | None = None
    document_type: int | None = None
    tags: list[int] = Field(default_factory=list)
    score: float | None = None
    highlights: Any = None
    excerpt: str
    excerpt_truncated: bool


class AnswerFromDocumentsResult(_Frozen):
    query: str
    total_hits: int | None = None
    returned: int
    sources: list[AnswerSource]


class RecentDocumentsResult(_Frozen):
    since: str
    by: str
    count: int
    documents: list[DocumentSummary]


# --- Binary tool envelopes ---

class InlineBinary(_Frozen):
    encoding: str = "base64"
    mime: str | None = None
    bytes: int
    data: str


class SavedBinary(_Frozen):
    saved_to: str
    bytes: int


# --- Misc envelopes ---

class NextAsn(_Frozen):
    next_asn: int


class AuthOk(_Frozen):
    authenticated: bool
    username: str | None = None


__all__ = [
    "AnswerFromDocumentsResult",
    "AnswerSource",
    "AuthOk",
    "CustomFieldValue",
    "DocumentContent",
    "DocumentDetail",
    "DocumentNote",
    "DocumentSummary",
    "DocumentsListResult",
    "FindDocumentsResult",
    "InlineBinary",
    "NextAsn",
    "RecentDocumentsResult",
    "SavedBinary",
    "SearchHit",
    "SearchResult",
    "TaxonomyItem",
]
```

- [ ] **Step 3: Run model tests**

Run: `uv run pytest tests/test_models.py -v`

Expected: PASS. If a fixture field surfaces an unexpected `null`, widen the model field to `... | None = None` and rerun. **Do not loosen any int/str field to `Any` without leaving a comment in the model class explaining why.**

- [ ] **Step 4: mypy + ruff**

Run: `uv run ruff check . && uv run mypy src`

Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/paperless_mcp/models.py tests/test_models.py
git commit -m "feat(models): add frozen Pydantic response DTOs"
```

---

## Task 3: Wire `DocumentSummary` into `slim_document` + `documents.py`

**Files:** `src/paperless_mcp/tools/_helpers.py`, `src/paperless_mcp/tools/documents.py`, `tests/test_documents.py`

- [ ] **Step 1: Replace `slim_document` body**

Edit `src/paperless_mcp/tools/_helpers.py`. Replace `slim_document` with:

```python
from ..models import DocumentSummary, TaxonomyItem


def slim_document(doc: dict[str, Any]) -> DocumentSummary:
    """Trim verbose document payload for list responses (drop content + permissions)."""
    return DocumentSummary.model_validate(doc)


def slim_taxonomy_item(item: dict[str, Any]) -> TaxonomyItem:
    return TaxonomyItem.model_validate(item)
```

Drop the inline `keep` set — `extra="ignore"` on the model handles it.

- [ ] **Step 2: Update `documents.py` returns**

Annotate `list_documents` → `DocumentsListResult`, `get_document` → `DocumentDetail`, `get_document_content` → `DocumentContent`, `get_document_thumbnail` / `get_document_preview` / `download_document` → `InlineBinary | SavedBinary`. Construct via `model_validate` on raw dicts.

For example, `list_documents` becomes:

```python
async def list_documents(...) -> DocumentsListResult:
    ...
    docs = await client.paginate(...)
    summaries = [slim_document(d) for d in docs]
    return DocumentsListResult(count=len(summaries), documents=summaries)
```

For `get_document`, drop the `doc.pop("content", None)` line (model `extra="ignore"` drops it implicitly), then `return DocumentDetail.model_validate(doc)`.

For `get_document_content`, build `DocumentContent(...)` directly. Return type changes from `dict[str, Any]` to `DocumentContent`.

For binary tools, return `SavedBinary(saved_to=..., bytes=...)` or `InlineBinary(encoding="base64", mime=..., bytes=..., data=...)`. If FastMCP 3.2.4 cannot generate a union outputSchema cleanly, split into two tools (`download_document_inline` / `download_document_to_file`) — decide based on the FastMCP changelog at implementation time.

- [ ] **Step 3: Update `tests/test_documents.py`**

Tests that call tools through `mcp_client.call_tool(...)` continue to assert on dict-shaped JSON (FastMCP serializes). Tests that import the tool function directly (if any) must switch to attribute access. Run the file and fix mismatches.

Run: `uv run pytest tests/test_documents.py -v`

Expected: green.

- [ ] **Step 4: Run full suite + lint + mypy**

```bash
uv run pytest && uv run ruff check . && uv run mypy src
```

Expected: green. mypy may flag the binary-tool union return — adjust signature or split tools as decided in step 2.

- [ ] **Step 5: Commit**

```bash
git add src/paperless_mcp/tools/_helpers.py src/paperless_mcp/tools/documents.py tests/test_documents.py
git commit -m "refactor(documents): return typed DocumentSummary/DocumentDetail models"
```

---

## Task 4: Type `taxonomy.py`

**Files:** `src/paperless_mcp/tools/taxonomy.py`, `tests/test_taxonomy.py`

- [ ] **Step 1: Replace `_slim_taxonomy` with `slim_taxonomy_item`**

Delete the local `_slim_taxonomy` function. Import `slim_taxonomy_item` from `_helpers`. Change every `list_*` return type to `list[TaxonomyItem]`. Change `get_tag` / `get_correspondent` / `get_document_type` / `get_saved_view` to return `TaxonomyItem`.

- [ ] **Step 2: Run + fix tests**

```bash
uv run pytest tests/test_taxonomy.py -v
```

- [ ] **Step 3: Commit**

```bash
git add src/paperless_mcp/tools/taxonomy.py tests/test_taxonomy.py
git commit -m "refactor(taxonomy): return typed TaxonomyItem models"
```

---

## Task 5: Type `highlevel.py` (find / answer / recent)

**Files:** `src/paperless_mcp/tools/highlevel.py`, `tests/test_highlevel.py`

- [ ] **Step 1: Update return types**

- `find_documents` → `FindDocumentsResult`
- `answer_from_documents` → `AnswerFromDocumentsResult` (build `AnswerSource` per hit — hits with `fetch_error` raise `ToolError` instead of returning a partial dict; matches existing fail-fast convention. **If any test relies on `fetch_error` propagating, keep the existing dict path and skip wrapping that one tool — note the deviation in the commit message.**)
- `recent_documents` → `RecentDocumentsResult`
- `interactive_search` stays `dict[str, Any]` — its return is a discriminated union over `strategy` + `status`, would need `InteractiveSearchAccepted | InteractiveSearchAborted` union models. Defer to phase 2.1. Add `# TODO(phase-2.1): model interactive_search response union` comment above the function.

- [ ] **Step 2: Tests**

```bash
uv run pytest tests/test_highlevel.py tests/test_interactive_search.py -v
```

- [ ] **Step 3: Commit**

```bash
git add src/paperless_mcp/tools/highlevel.py tests/test_highlevel.py
git commit -m "refactor(highlevel): return typed FindDocumentsResult/AnswerFromDocumentsResult"
```

---

## Task 6: Type `search.py`, `auth.py`; defer `stats.py` / `tasks.py`

**Files:** the four tool modules + their tests.

- [ ] **Step 1: `search_documents` → `SearchResult`**

Build `SearchResult(count=..., results=[SearchHit.model_validate(r) for r in raw_results])`.

- [ ] **Step 2: `verify_auth` → `AuthOk`**

Return `AuthOk(authenticated=True, username=profile.get("username"))`. On failure, propagate the existing `PaperlessAPIError` — do not wrap.

- [ ] **Step 3: `stats.py` and `tasks.py`**

Both endpoints return loosely-typed paperless payloads. Skip strict modeling for now — keep `dict[str, Any]` and `list[dict[str, Any]]` and add a `# TODO(phase-2.2): model stats/tasks once shape stabilizes` comment. Captured fixtures (`stats.json`, `tasks.json`) document the current shape for the next pass.

- [ ] **Step 4: Tests + lint + mypy**

```bash
uv run pytest && uv run ruff check . && uv run mypy src
```

- [ ] **Step 5: Commit**

```bash
git add src/paperless_mcp/tools/search.py src/paperless_mcp/tools/auth.py tests/test_search.py tests/test_auth.py
git commit -m "refactor(search,auth): return typed SearchResult/AuthOk"
```

---

## Task 7: Verify FastMCP advertises `outputSchema`

**Files:** new test only.

- [ ] **Step 1: Add a meta-test**

Append to `tests/test_server.py`:

```python
async def test_tools_advertise_output_schema(mcp_client: Client) -> None:
    tools = await mcp_client.list_tools()
    by_name = {t.name: t for t in tools}
    expected = {
        "list_documents",
        "get_document",
        "get_document_content",
        "find_documents",
        "answer_from_documents",
        "recent_documents",
        "search_documents",
        "list_tags",
        "verify_auth",
    }
    missing = [n for n in expected if not by_name[n].outputSchema]
    assert not missing, f"tools without outputSchema: {missing}"
```

If the FastMCP `Tool` object exposes the schema under a different attribute (e.g. `output_schema`), adapt accordingly — confirm by `print(tools[0].__dict__)` once.

Run: `uv run pytest tests/test_server.py::test_tools_advertise_output_schema -v`

Expected: PASS.

- [ ] **Step 2: Commit**

```bash
git add tests/test_server.py
git commit -m "test(server): assert tools advertise outputSchema"
```

---

## Task 8: Document the convention

**Files:** `CLAUDE.md`

- [ ] **Step 1: Append a Conventions bullet**

Edit `CLAUDE.md` under `## Conventions`:

```markdown
- Tool return types are frozen Pydantic models from `src/paperless_mcp/models.py`. Add new response shapes there, not inline. `extra="ignore"` lets paperless evolve without breaking; widen fields to `... | None` rather than `Any` when a real payload contains a null. Use `model_validate(raw)` to construct from paperless dicts; never construct via `**raw` (silently drops type checks for extras).
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): document Pydantic response model convention"
```

---

## Final verification

- [ ] **Step 1: Quality gate**

```bash
uv run pytest && uv run ruff check . && uv run mypy src
```

Expected: all green; pytest count = prior 91 + new model + outputSchema tests.

- [ ] **Step 2: Smoke test against MCP Inspector**

```bash
uv run mcp dev src/paperless_mcp/server.py
```

In the Inspector UI, open `tools/list` and confirm `outputSchema` appears for `list_documents`, `find_documents`, `answer_from_documents`. Spot-check `find_documents` returns a body that validates against the advertised schema.

- [ ] **Step 3: Push both remotes**

```bash
git push origin main
git push github main
```

---

## Risks & mitigations

- **Hidden paperless field types.** Mitigation: Task 1 captures real samples; round-trip tests (Task 2 step 1) catch missed fields. `extra="ignore"` keeps unknown fields from blowing up — at the cost of silently dropping them. If a tool consumer needs raw passthrough, expose a sibling `*_raw` tool returning `dict[str, Any]` rather than weakening the model.
- **FastMCP serialization regressions.** Existing tests mostly assert on the wire dict shape from `mcp_client.call_tool` — those should keep passing because Pydantic's `model_dump` mirrors the prior hand-built dicts. If any test breaks on field order or `None` inclusion, fix by setting `model_config["json_schema_serialization_defaults_required"] = True` or by passing `exclude_none` — see Pydantic 2 docs.
- **Custom fields polymorphism.** `value` is genuinely `Any` (string / number / monetary / date depending on `data_type`). Acceptable: leave `CustomFieldValue.value: Any`. Documented in models.py.
- **Union outputSchema for binary tools.** FastMCP may not advertise a clean union schema. Fallback: split into two tools as called out in Task 3 step 2.
- **`interactive_search` discriminated union.** Deferred to phase 2.1 to keep this plan bounded. The `# TODO` comment is the contract.

---

## Out of scope (future plans)

- **Phase 2.1 — discriminated union for `interactive_search` responses** (status/step variants).
- **Phase 2.2 — typed stats/tasks/profile** once captured fixtures are reviewed.
- **Phase 3 — MCP Resources** (still blocked on scoping decision: taxonomy-only vs. include documents).
- **`FileSystemProvider` auto-discovery (M4)** — unchanged from phase 1.

Each becomes a standalone plan in `docs/superpowers/plans/` once unblocked.
