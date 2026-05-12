# CHANGELOG


## v0.1.2 (2026-05-03)


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
