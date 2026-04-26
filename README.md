# paperless-mcp

MCP server for [Paperless-ngx](https://docs.paperless-ngx.com/) built on [FastMCP](https://github.com/jlowin/fastmcp).

## Setup

```bash
uv sync
cp .env.example .env
# edit .env: PAPERLESS_URL, PAPERLESS_TOKEN
```

## Run

```bash
uv run paperless-mcp
```

## Dev

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

## Config

| Var | Default | Notes |
|---|---|---|
| `PAPERLESS_URL` | — | Base URL, no trailing slash |
| `PAPERLESS_TOKEN` | — | API token from Paperless profile |
| `PAPERLESS_TIMEOUT` | 30 | HTTP timeout (s) |
| `PAPERLESS_VERIFY_SSL` | true | Set `false` for self-signed |
