# CHANGELOG


## v0.2.0 (2026-05-12)

### Chores

- Sync uv.lock to v0.1.2 after merge
  ([`012441c`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/012441c3d192c5448102887f605e0eb8c755554e))

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>


## v0.1.2 (2026-05-03)

### Chores

- Sync uv.lock to v0.1.1
  ([`e6c9489`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/e6c94899f452932a5eb456f8add6cf22ef167e97))

The release commit bumped pyproject but missed regenerating the lockfile.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>

### Documentation

- Document resources, Context, progress and logging
  ([`b3151cf`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/b3151cf445926db89d890f780746a0d2cdc18cbd))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **plans**: Add superpowers planning docs
  ([`32df22a`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/32df22aa8419b350d588aa164c557efd48b08208))

Archives the implementation plans driven through the subagent-driven-development workflow: the
  FastMCP r1 (hardening) and r2 (typed responses) follow-ups, the earlier code-review-corrections
  plan, and the most recent MCP advanced-features plan (resources + Context observability).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>

### Features

- **client**: Paginate accepts optional progress_cb
  ([`6dbcc13`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/6dbcc1318c2afca834d68863d8bc2490e9a7972e))

Adds an optional `progress_cb: Callable[[int, int | None], Awaitable[None]]` keyword argument to
  `PaperlessClient.paginate` (and mirrors it in `FakeClient`). The callback is awaited after each
  page with (items_so_far, total_or_None), covering both paginated and plain-list paths including
  truncation via max_items.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **helpers**: Add slim_metadata helper
  ([`f02060a`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/f02060a024aaf84e692e9ff13f150e2e0728cb8e))

Trims verbose document metadata records: drops the large original_metadata / archive_metadata arrays
  while keeping checksum, size, filenames, lang, page_count, and similar small fields. Used by
  paperless_get_document_metadata.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>

- **resources**: Add paperless://documents/{id}/content resource template
  ([`771bb29`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/771bb29a4b49f96c533f653b0d98118ae91a5c63))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **resources**: Add paperless://documents/{id}/metadata resource template
  ([`baafc3a`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/baafc3aa98afc1b0327ad1be1ee9145d0ce197aa))

- **resources**: Add preview/thumbnail/download binary resource templates
  ([`7be8d63`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/7be8d6388efbddc66f0dc11dce32a2f6b60d207c))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **schemas**: Add TypedDict output shapes module
  ([`630617a`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/630617abcee52ec7d0572640a4b264e8a7c8ff9e))

Defines PageInfo, DocumentListResponse, TaxonomyListResponse, TaskListResponse, SearchResponse,
  AuthResult, AnswerResponse, and related shapes used by tool return types to drive FastMCP
  outputSchema advertisement. Includes the `make_page_info` helper that flattens (returned, total,
  has_more) into the PageInfo wire shape with capped_by_max_results derived consistently.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>

- **server**: Add origin allowlist ASGI middleware
  ([`2c7e7e5`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/2c7e7e5c52f473b5f55524b2d27f40e32c94c90a))

OriginAllowlistMiddleware rejects HTTP requests whose Origin header is not in the configured
  allowlist, blocking DNS-rebinding and cross-site abuse of an HTTP-transported MCP server.
  parse_allowed_origins parses the MCP_ALLOWED_ORIGINS env var (comma-separated). Wired in server.py
  only when the variable is set, so stdio transport and local-only HTTP deployments are unaffected.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>

- **tools**: Highlevel tools emit progress + structured logging via Context
  ([`4a3c438`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/4a3c438564e0238b63d64e3bf4bc9f0ad2b9619d))

Wire ctx: Context into paperless_find_documents, paperless_answer_from_documents, and
  paperless_recent_documents — progress callbacks, debug/info/warning logs. Switch
  answer_from_documents from asyncio.gather to sequential enrichment for monotonic progress; remove
  now-unused asyncio import.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **tools**: List_documents emits progress + structured logging via Context
  ([`d156c56`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/d156c5616535159c7dc64ad21c065d655b514f66))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

### Refactoring

- **auth**: Paperless_ prefix + typed AuthResult, redact upstream body
  ([`ba0e407`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/ba0e40766b37b472deb6949a22443d3d2ed72686))

Renames verify_auth -> paperless_verify_auth and returns the AuthResult TypedDict so FastMCP
  advertises an outputSchema. The failure branch no longer echoes the upstream error string to the
  client — only the HTTP status code and the configured base_url leave the server. The full upstream
  body is still recorded on the PaperlessAPIError instance and logged server-side.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>

- **search**: Paperless_ prefix + typed SearchResponse
  ([`236bb2a`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/236bb2a4ca7417d760007f3b5d24378232a9f6ca))

Renames search_documents and search_autocomplete to paperless_* and switches search_documents to
  return the SearchResponse TypedDict (query, count, results) so FastMCP can publish an
  outputSchema. Tests read structured_content since the response now carries a schema-bound payload.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>

- **stats**: Paperless_ prefix on statistics tools
  ([`6af36a7`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/6af36a7882cf85beedd24be3fd33a26c3c99977a))

Renames get_statistics, get_status, and get_remote_version to their paperless_ -prefixed
  counterparts so the entire tool surface is namespaced consistently when multiple MCP servers are
  loaded in the same client.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>

- **tasks**: Paperless_ prefix + typed TaskListResponse with page_info
  ([`a2c67e3`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/a2c67e3175e988551b760d9264cadd9ddf683ace))

Renames list_tasks -> paperless_list_tasks and returns TaskListResponse with a page_info envelope.
  /api/tasks/ may respond as either a plain list or a DRF dict; both shapes are normalized to
  (tasks, page_info) so callers can detect truncation via has_more / capped_by_max_results without
  inspecting the upstream payload.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>

- **taxonomy**: Paperless_ prefix + typed responses with page_info
  ([`90dff7a`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/90dff7ab07fa7216da0ad59b53ad0064402e5d2a))

Renames the eleven taxonomy tools (tags, correspondents, document types, storage paths, custom
  fields, saved views) to their paperless_ -prefixed counterparts and switches list endpoints to
  TaxonomyListResponse with the shared page_info envelope. Adds _list_response helper to keep the
  slim_taxonomy + page_info packaging in one place.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>

### Testing

- **interactive_search**: Align with paperless_ prefix and structured_content
  ([`cd3e4cc`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/cd3e4cc7782d863082aeba0a755778d1a785ced8))

Updates the four-branch elicitation suite to call paperless_interactive_search and read
  result.structured_content. The unsupported-elicit assertions also match the renamed
  paperless_find_documents / answer_from_documents / recent_documents that the tool's error message
  now points clients at.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>

- **server**: Paperless_ prefix audit and HTTP transport hardening
  ([`2147929`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/2147929884d34bcb077147c39c1baa4cd7ae89c1))

Updates the core-tools expected set to the paperless_ -prefixed names and adds
  test_all_tools_are_prefixed so any future tool that forgets the prefix fails fast. Adds two
  HTTP-transport assertions: the server binds 127.0.0.1 by default (no LAN exposure without an
  explicit MCP_HOST), and the origin allowlist middleware is wired exactly once when
  MCP_ALLOWED_ORIGINS is set.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>


## v0.1.1 (2026-05-03)

### Bug Fixes

- Align with FastMCP best practices
  ([`a0e66ac`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/a0e66ac29ce3d2ee1b6d6ff34fe02908fa34a9b3))

- close shared httpx client via FastMCP lifespan to stop resource leak - raise ToolError from
  download_document/get_document_preview instead of returning {"error": ...} dicts so MCP error
  contract is honored - centralize tool annotations as READ_ONLY (ToolAnnotations) with
  idempotentHint=True; replace ad-hoc dicts across all tool modules - narrow except Exception ->
  except PaperlessAPIError in highlevel._enrich - update test_documents.py to assert
  pytest.raises(ToolError)

- **highlevel**: Raise ToolError when client does not support elicitation
  ([`19ec695`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/19ec69504dab2813cb7391a0ca606bd2d33d8db6))

### Code Style

- **server**: Drop unused E402 noqa on tools import
  ([`ac35fb0`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/ac35fb05eda4f4602c300532767e534b70014ba6))

Block sits at module top with no preceding code, so E402 cannot fire.

### Documentation

- **claude**: Note Settings.from_env() runs at import time
  ([`50985b0`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/50985b07a7380065dec56ef29e143d144dbf3a9d))

- **readme**: Document MCP_STATELESS env var default
  ([`47ef09f`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/47ef09f14ecc619537f74d5d7bea83c2b9622212))

### Refactoring

- **client**: Fold get_binary_with_headers into request(expect_headers=True)
  ([`0fb8c99`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/0fb8c99d5f0d46170803649c34cc2d47740ad3c0))

- **docker**: Extract healthcheck to paperless-mcp-healthcheck script
  ([`5333f04`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/5333f0414eefeff4e7c4483c4d841cbfe7046b7b))

Replace inline python -c probe in Dockerfile with a console script entry point. Drop redundant
  healthcheck block from docker-compose (HEALTHCHECK in image is authoritative). Honors
  MCP_HOST/MCP_PORT and rewrites 0.0.0.0 to loopback.


## v0.1.0 (2026-05-03)

### Bug Fixes

- **client**: Cap plain-list paginate responses with max_items
  ([`acda870`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/acda870d9761fe4d7a5cabf6db95219fc117df38))

- **highlevel**: Type-safe interactive_search; cover all elicit branches
  ([`4c18558`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/4c1855845c183ddd3864e09505c6284b12eb7b10))

- **security**: Require MCP_AUTH_TOKEN for HTTP transport
  ([`3715afd`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/3715afd3081ab2c540983f3910120707f2cfb754))

- **security**: Sandbox save_to_path under PAPERLESS_DOWNLOAD_DIR
  ([`7c1ab84`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/7c1ab84d925dc8cb18efc8c4609744e2208a3d79))

- **tasks**: Handle null results from /api/tasks/
  ([`c902cb4`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/c902cb4b6c80110cc6c2da908819d02f39a662ae))

### Chores

- Bootstrap uv project with fastmcp deps
  ([`e54b9c0`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/e54b9c0835bb13f39c8dc8bdf145e54078f65e52))

- Vendor Paperless-ngx OpenAPI spec v6.0.0
  ([`d08ea5d`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/d08ea5d313a2618ce519aa174678e310bd41c942))

- **docker**: Bump uv image to 0.11.7
  ([`e205b41`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/e205b41981b562ad9b7de452e2355c6720da05b8))

### Continuous Integration

- Add python-semantic-release workflow
  ([`e1eb29c`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/e1eb29c7a1e0c62004974022d65c84a40f79e4fd))

Configure PSR via pyproject.toml and add GitHub Actions release workflow. Releases triggered on push
  to main; produces git tag, CHANGELOG.md, and GitHub Release entry. major_on_zero disabled to keep
  0.x stable.

### Documentation

- Expand README with tool list, auth notes, and scope
  ([`8f7d2a7`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/8f7d2a724290e489ca04237cc890e99a4734ab09))

### Features

- Add config, async HTTP client, and shared FastMCP app
  ([`7d6fbb5`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/7d6fbb5e4a862d8ecfd9cea1805443c9e5997fb6))

- Add server entrypoint and tool package helpers
  ([`a55de7b`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/a55de7b52a66a4529f41448e981bca2c984d2573))

- Pytest suite, HTTP transport, Docker, interactive search
  ([`5540470`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/5540470c7574689d36ce713f11cbe327a944d388))

- tests/: 45 pytest tests covering auth, documents, search, taxonomy, highlevel, helpers, and client
  (httpx MockTransport). FastMCP in-memory Client fixture with FakeClient mocking PaperlessClient. -
  app.py: optional StaticTokenVerifier for HTTP bearer auth, /health route. - server.py: stdio +
  streamable-http transports via MCP_TRANSPORT. - highlevel.py: interactive_search tool using
  ctx.elicit for step-by-step strategy + filter gathering. - Dockerfile, docker-compose.yml,
  .dockerignore: container deployment. - inspector_entry.py: MCP Inspector entrypoint. - CLAUDE.md:
  project guidance for Claude Code. - .gitignore: ignore .env, .claude/, tool caches. - Rename
  OpenAPI spec to Paperless-ngx-spec.yaml.

- **tools**: Add verify_auth to confirm token works
  ([`8d319d3`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/8d319d39d8e3890d7e4c0d7213138f751f8e432f))

- **tools**: Document retrieval tools (list, get, content, download, preview, thumb)
  ([`5e483ba`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/5e483ba61dc3fc9fd4ff299d9f272b3e70da83a0))

- **tools**: Full-text search and autocomplete
  ([`444e6e6`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/444e6e6c9eeba7bf4e9f5a6b046c154f5bc3a8aa))

- **tools**: High-level helpers (find_documents, answer_from_documents, recent_documents)
  ([`add6963`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/add69630e1d6c553368bbabae51fa78af32ccfa1))

- **tools**: Tasks list and instance statistics/status
  ([`a9b129a`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/a9b129a21acdf32e77f159642e072942443d405f))

- **tools**: Taxonomy reads (tags, correspondents, types, storage paths, custom fields, saved views)
  ([`b450fbe`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/b450fbe6c4998035523953e663470efef940150d))

### Refactoring

- Drop dead _OrderingChoice; thumbnail mime from response header
  ([`39d3d09`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/39d3d0974e88f124c4e14ce4ecd971aaf094a193))

- Unify env-bool parsing across config and server
  ([`3fa3a6f`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/3fa3a6fa341c1a3888cc5ac8fefd49bbfe841eb3))

- **tools**: Extract FilterRequest builder, parallelize name resolution
  ([`4a6e05b`](https://github.com/Armgd/paperless-ngx-mcp-server/commit/4a6e05b56e4a450e1e87f754900f8da360e7c7f2))
