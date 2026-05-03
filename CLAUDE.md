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
- `client.py` — `PaperlessClient` async httpx wrapper. Token auth header (`Authorization: Token <token>`), `Accept: application/json; version=6`. Provides `get/post/get_binary/paginate/iter_pages`. `paginate()` auto-walks DRF `next` cursor; tools cap with `max_results`.
- `server.py` — `main()` imports all `tools/*` submodules (registration side-effect via `@mcp.tool` decorators) then calls `mcp.run()`. **To add a new tool module, import it in `server.py`.**
- `tools/_helpers.py` — `resolve_name_to_id()` (case-insensitive taxonomy lookup via `name__iexact`), `slim_document()` (trims verbose list payloads).

**Tool modules** each register a category via `@mcp.tool`:
- `auth.py` — `verify_auth` (probes `/api/profile/`)
- `documents.py` — list/get/content/notes/suggestions/history/download/thumbnail/preview
- `search.py` — `search_documents` (Whoosh full-text), `search_autocomplete`
- `taxonomy.py` — tags, correspondents, doc types, storage paths, custom fields, saved views
- `tasks.py`, `stats.py` — ops endpoints
- `highlevel.py` — composed helpers (`find_documents`, `answer_from_documents` for RAG, `recent_documents`) that resolve names → ids before delegating

**Auth**: token only. Basic auth and session cookie are intentionally unsupported (see README rationale). Bootstrap a token via `POST /api/token/` manually if needed.

**Binary content**: `download_document` / `get_document_preview` default to inline base64 capped at 2MB; pass `save_to_path` for larger files. For RAG prefer `get_document_content` (OCR text) over PDF bytes.

**Scope**: read-only by design for v1. No create/update/delete tools. The vendored OpenAPI spec (`Paperless-ngx REST API (9).yaml`) is the reference for endpoint shapes.

## Conventions

- Frozen dataclasses for config/DTOs (immutability rule).
- Tool modules register via decorator import side-effect — keep `server.py` import list in sync.
- All list endpoints flow through `client.paginate()`; never re-implement DRF cursor walking in tool code.
- Name-based UX (`find_documents`) resolves via `_helpers.resolve_name_to_id`; keep id-based primitives in `documents.py` and name-resolving wrappers in `highlevel.py`.
- `Settings.from_env()` runs at import of `paperless_mcp.app` (transitively via `paperless_mcp.config`). Tests must set `PAPERLESS_URL` and `PAPERLESS_TOKEN` *before* importing any project module — see `tests/conftest.py:8-9`.
