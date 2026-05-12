# paperless-mcp

MCP server for [Paperless-ngx](https://docs.paperless-ngx.com/) built on [FastMCP](https://github.com/jlowin/fastmcp).

Read-only retrieval + RAG-style search for your document archive. Exposes ~30 tools covering documents, search, taxonomy, tasks, and stats.

All tools are prefixed `paperless_` to avoid collisions when loaded alongside other MCP servers. List endpoints return a `page_info` object so the model can tell whether more results exist beyond what was returned.

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

Call the `paperless_verify_auth` tool — fetches `/api/profile/` and returns user info or a structured error. Use this first when wiring up a new client.

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

All tools are prefixed `paperless_`.

### Auth
- `paperless_verify_auth` — fetch profile, confirm credentials work

### Documents (retrieval)
- `paperless_list_documents` — structured filters (correspondent, type, tags, dates, ASN, ...)
- `paperless_get_document` / `paperless_get_document_metadata` / `paperless_get_document_content`
- `paperless_get_document_notes` / `paperless_get_document_suggestions` / `paperless_get_document_history`
- `paperless_download_document` — base64 or `save_to_path`
- `paperless_get_document_thumbnail` / `paperless_get_document_preview`
- `paperless_get_next_asn`

### Search
- `paperless_search_documents` — full-text via Whoosh, returns highlights
- `paperless_search_autocomplete`

### High-level helpers
- `paperless_find_documents` — name-based filters (resolves correspondent/tag/type names → ids)
- `paperless_answer_from_documents` — RAG: search + top-k content excerpts ready to synthesize
- `paperless_recent_documents` — recently added/created window
- `paperless_interactive_search` — elicits search strategy + parameters from user

### Taxonomy
- `paperless_list_tags` / `paperless_get_tag`
- `paperless_list_correspondents` / `paperless_get_correspondent`
- `paperless_list_document_types` / `paperless_get_document_type`
- `paperless_list_storage_paths`
- `paperless_list_custom_fields`
- `paperless_list_saved_views` / `paperless_get_saved_view`

### Ops
- `paperless_list_tasks`
- `paperless_get_statistics` / `paperless_get_status` / `paperless_get_remote_version`

## Pagination

All list tools auto-paginate with `max_results` cap (default 50, max 500). DRF `page`/`page_size` handled internally.

Every list response carries a `page_info` object:

```json
{
  "page_info": {
    "returned": 50,
    "total": 4123,
    "has_more": true,
    "capped_by_max_results": true
  }
}
```

- `returned` — items in this response
- `total` — upstream count (`null` for plain-list endpoints)
- `has_more` — more results exist beyond what was returned
- `capped_by_max_results` — `has_more` was triggered by hitting your `max_results` cap (raise it or refine filters)

## Binary content

`paperless_download_document`, `paperless_get_document_preview`, and `paperless_get_document_thumbnail` default to base64 inline (capped at 2MB; thumbnails too). For larger files pass `save_to_path` to write to disk and get back the path — avoids token blow-up. Disk writes require `PAPERLESS_DOWNLOAD_DIR` to be set; paths are constrained inside that root.

For RAG use cases prefer `paperless_get_document_content` (OCR text) or `paperless_answer_from_documents` (search + excerpts) — model can read text directly, no PDF byte parsing needed.

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

## HTTP / Docker

Set `MCP_TRANSPORT=http` to expose the server over streamable HTTP (defaults: `127.0.0.1:8000/mcp`, stateless).

HTTP transport refuses to start without `MCP_AUTH_TOKEN`. Set it to a long random string; clients send `Authorization: Bearer <token>`.

By default the server binds to `127.0.0.1` (local only). To expose it on a LAN set `MCP_HOST=0.0.0.0` *and* set `MCP_ALLOWED_ORIGINS` to a comma-separated list of allowed browser `Origin` headers (DNS-rebinding protection). Requests without an `Origin` header (curl, MCP CLIs) pass through; requests with a non-allowlisted Origin get 403. Leaving `MCP_ALLOWED_ORIGINS` empty disables the check.

| Var | Default | Notes |
|---|---|---|
| `MCP_HOST` | `127.0.0.1` | Bind address. Set to `0.0.0.0` for LAN. |
| `MCP_PORT` | 8000 | TCP port. |
| `MCP_PATH` | `/mcp` | HTTP path. |
| `MCP_AUTH_TOKEN` | — | Required for HTTP transport. |
| `MCP_ALLOWED_ORIGINS` | (unset) | CSV of allowed Origin headers. |
| `MCP_STATELESS` | `true` | Each request stands alone — set `false` if your client maintains a session. |

## Dev

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

## Scope

This server is **read-only by design** for v1. No create/update/delete tools. Document tagging, note creation, and bulk edits are out of scope until explicitly requested.
