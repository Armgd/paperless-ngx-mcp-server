# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                          # install deps
uv run paperless-mcp             # run MCP server (stdio)
uv run pytest                    # run tests
uv run pytest tests/path::test   # single test
uv run ruff check .              # lint
uv run mypy src                  # type check
```

Requires Python 3.12+. Env vars `PAPERLESS_URL` and `PAPERLESS_TOKEN` mandatory (loaded from `.env` via python-dotenv at import time of `config.py`).

## Architecture

FastMCP server exposing read-only tools over Paperless-ngx REST API.

**Module layout (`src/paperless_mcp/`):**
- `app.py` — single shared `mcp: FastMCP` instance + module-level `client` and `settings`. All tool modules import from here. Side-effectful: instantiates client on import.
- `config.py` — `Settings` frozen dataclass loaded from env. Raises at import if `PAPERLESS_URL`/`PAPERLESS_TOKEN` missing.
- `client.py` — `PaperlessClient` async httpx wrapper. Token auth header (`Authorization: Token <token>`), `Accept: application/json; version=6`. Provides `get/post/get_binary/paginate/iter_pages`. `paginate()` auto-walks DRF `next` cursor and returns `(items, total, has_more)`; tools cap with `max_results`. `PaperlessAPIError` redacts the upstream body from its message (kept on `.body` and logged via stderr) — never echo it to clients.
- `server.py` — `main()` imports all `tools/*` submodules (registration side-effect via `@mcp.tool` decorators) then calls `mcp.run()`. **To add a new tool module, import it in `server.py`.** HTTP transport defaults to `127.0.0.1`; opts into LAN exposure via `MCP_HOST=0.0.0.0` + `MCP_ALLOWED_ORIGINS`.
- `_origin_check.py` — ASGI middleware enforcing `MCP_ALLOWED_ORIGINS` when HTTP transport is used.
- `tools/_helpers.py` — `resolve_name_to_id()`, `slim_document()`, `slim_metadata()`.
- `tools/_schemas.py` — TypedDict output shapes (`PageInfo`, `DocumentListResponse`, …) that drive FastMCP `outputSchema`. New tools should return one of these (or extend the file).
- `resources/documents.py` — `@mcp.resource` templates under the `paperless://documents/{id}/...` URI scheme: `content` (text/plain OCR), `metadata` (application/json record), `preview` (application/pdf), `thumbnail` (image/webp), `download` (application/octet-stream). Binary resources cap at 20 MB; oversized requests raise `ValueError` and point the client at the equivalent tool with `save_to_path`. Resources coexist with the binary tools — clients that prefer resource semantics can use them, clients that need disk persistence still call the tools.

**Tool naming**: every registered tool uses the `paperless_` prefix (e.g. `paperless_list_documents`). This avoids collisions when multiple MCP servers are loaded into the same client. Keep new tools prefixed.

**Tool modules** each register a category via `@mcp.tool`:
- `auth.py` — `paperless_verify_auth` (probes `/api/profile/`)
- `documents.py` — list/get/content/notes/suggestions/history/download/thumbnail/preview
- `search.py` — `paperless_search_documents` (Whoosh full-text), `paperless_search_autocomplete`
- `taxonomy.py` — tags, correspondents, doc types, storage paths, custom fields, saved views
- `tasks.py`, `stats.py` — ops endpoints
- `highlevel.py` — composed helpers (`paperless_find_documents`, `paperless_answer_from_documents`, `paperless_recent_documents`, `paperless_interactive_search`) that resolve names → ids before delegating

**Auth**: token only. Basic auth and session cookie are intentionally unsupported (see README rationale). Bootstrap a token via `POST /api/token/` manually if needed.

**Binary content**: `paperless_download_document`, `paperless_get_document_preview`, and `paperless_get_document_thumbnail` default to inline base64 capped at 2MB; pass `save_to_path` (constrained to `PAPERLESS_DOWNLOAD_DIR`) for larger files. For RAG prefer `paperless_get_document_content` (OCR text) over PDF bytes.

**Pagination contract**: every list-returning tool packages results with a `page_info` object (`returned`, `total`, `has_more`, `capped_by_max_results`). Build it via `tools/_schemas.make_page_info()` from the `(items, total, has_more)` tuple returned by `client.paginate()`. Never return raw lists without `page_info`.

**Scope**: read-only by design for v1. No create/update/delete tools. The vendored OpenAPI spec (`Paperless-ngx REST API (9).yaml`) is the reference for endpoint shapes.

**Context & observability**: tools that walk multiple pages or fetch N child docs accept `ctx: Context` (auto-injected by FastMCP) and emit `await ctx.report_progress(progress=seen, total=count)` per page plus `await ctx.debug/info/warning(...)` for query setup, completion, and unresolved-name warnings. Wired into `paperless_list_documents`, `paperless_find_documents`, `paperless_answer_from_documents`, `paperless_recent_documents`, and `paperless_interactive_search` (which also uses `ctx.elicit`). To plug a tool into the pagination progress stream, pass a `progress_cb` to `client.paginate(...)`.

## Conventions

- Frozen dataclasses for config/DTOs (immutability rule).
- Tool modules register via decorator import side-effect — keep `server.py` import list in sync.
- All list endpoints flow through `client.paginate()`; never re-implement DRF cursor walking in tool code.
- Name-based UX (`paperless_find_documents`) resolves via `_helpers.resolve_name_to_id`; keep id-based primitives in `documents.py` and name-resolving wrappers in `highlevel.py`.
- Tool return types use `TypedDict`s from `tools/_schemas.py` so FastMCP advertises `outputSchema`. `dict[str, Any]` returns ship without a schema — only use them for genuinely heterogeneous payloads (e.g. `paperless_get_document` passing through the full Paperless record).
- `Settings.from_env()` runs at import of `paperless_mcp.app` (transitively via `paperless_mcp.config`). Tests must set `PAPERLESS_URL` and `PAPERLESS_TOKEN` *before* importing any project module — see `tests/conftest.py:8-9`.
