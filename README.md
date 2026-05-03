# paperless-mcp

MCP server for [Paperless-ngx](https://docs.paperless-ngx.com/) built on [FastMCP](https://github.com/jlowin/fastmcp).

Read-only retrieval + RAG-style search for your document archive. Exposes ~31 tools covering documents, search, taxonomy, tasks, and stats.

## Setup

```bash
uv sync
cp .env.example .env
# edit .env: PAPERLESS_URL, PAPERLESS_TOKEN
```

Generate a token in Paperless: **Profile → API Auth Token**.

## Run

```bash
uv run paperless-mcp
```

## Verify auth

Call the `verify_auth` tool — fetches `/api/profile/` and returns user info or a structured error. Use this first when wiring up a new client.

## Auth

Server uses **token auth** only (`Authorization: Token <token>`).

Spec also defines HTTP Basic and session cookie schemes — both intentionally not supported:

- **Basic auth**: stores raw password in env, less secure than revocable tokens.
- **Session cookie**: requires browser/CSRF flow, no fit for headless MCP.

If you need to bootstrap a token from username/password, hit `POST /api/token/` once manually.

## Config

| Var | Default | Notes |
|---|---|---|
| `PAPERLESS_URL` | — | Base URL, no trailing slash |
| `PAPERLESS_TOKEN` | — | API token from Paperless profile |
| `PAPERLESS_TIMEOUT` | 30 | HTTP timeout (s) |
| `PAPERLESS_VERIFY_SSL` | true | Set `false` for self-signed |

## Tools

### Auth
- `verify_auth` — fetch profile, confirm credentials work

### Documents (retrieval)
- `list_documents` — structured filters (correspondent, type, tags, dates, ASN, ...)
- `get_document` / `get_document_metadata` / `get_document_content`
- `get_document_notes` / `get_document_suggestions` / `get_document_history`
- `download_document` — base64 or `save_to_path`
- `get_document_thumbnail` / `get_document_preview`
- `get_next_asn`

### Search
- `search_documents` — full-text via Whoosh, returns highlights
- `search_autocomplete`

### High-level helpers
- `find_documents` — name-based filters (resolves correspondent/tag/type names → ids)
- `answer_from_documents` — RAG: search + top-k content excerpts ready to synthesize
- `recent_documents` — recently added/created window

### Taxonomy
- `list_tags` / `get_tag`
- `list_correspondents` / `get_correspondent`
- `list_document_types` / `get_document_type`
- `list_storage_paths`
- `list_custom_fields`
- `list_saved_views` / `get_saved_view`

### Ops
- `list_tasks`
- `get_statistics` / `get_status` / `get_remote_version`

## Pagination

All list tools auto-paginate with `max_results` cap (default 50, max 500). DRF `page`/`page_size` handled internally.

## Binary content

`download_document` and `get_document_preview` default to base64 inline (capped at 2MB). For larger files pass `save_to_path` to write to disk and get back the path — avoids token blow-up.

For RAG use cases prefer `get_document_content` (OCR text) or `answer_from_documents` (search + excerpts) — model can read text directly, no PDF byte parsing needed.

## HTTP / Docker

Set `MCP_TRANSPORT=http` to expose the server over streamable HTTP (defaults: `0.0.0.0:8000/mcp`, stateless).

HTTP transport refuses to start without `MCP_AUTH_TOKEN`. Set it to a long random string; clients send `Authorization: Bearer <token>`.

By default `MCP_STATELESS=true` — each request stands alone, no MCP session continuity. Set `MCP_STATELESS=false` only if your client maintains a streamable HTTP session and relies on per-session state (most don't).

## Dev

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

## Scope

This server is **read-only by design** for v1. No create/update/delete tools. Document tagging, note creation, and bulk edits are out of scope until explicitly requested.
