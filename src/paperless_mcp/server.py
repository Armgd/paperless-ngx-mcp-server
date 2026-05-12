"""FastMCP server entrypoint."""

from __future__ import annotations

import os

from ._envutil import env_bool
from ._origin_check import OriginAllowlistMiddleware, parse_allowed_origins
from .app import mcp

# Register tools by importing modules (decorator side-effect).
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
        from starlette.middleware import Middleware

        allowed = parse_allowed_origins(os.environ.get("MCP_ALLOWED_ORIGINS"))
        middleware = (
            [Middleware(OriginAllowlistMiddleware, allowed=allowed)]
            if allowed
            else None
        )
        mcp.run(
            transport="http",
            host=os.environ.get("MCP_HOST", "127.0.0.1"),
            port=int(os.environ.get("MCP_PORT", "8000")),
            path=os.environ.get("MCP_PATH", "/mcp"),
            stateless_http=env_bool(os.environ.get("MCP_STATELESS"), default=True),
            middleware=middleware,
        )
        return
    raise SystemExit(f"Unsupported MCP_TRANSPORT={transport!r} (use stdio or http)")


if __name__ == "__main__":
    main()
