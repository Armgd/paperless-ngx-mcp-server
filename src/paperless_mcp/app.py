"""Shared FastMCP instance and Paperless client. Imported by all tool modules."""
from __future__ import annotations

import os

from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from starlette.requests import Request
from starlette.responses import JSONResponse

from .client import PaperlessClient
from .config import Settings


def _build_auth() -> StaticTokenVerifier | None:
    """Bearer token auth for HTTP transport. None if MCP_AUTH_TOKEN unset."""
    token = os.environ.get("MCP_AUTH_TOKEN")
    if not token:
        return None
    return StaticTokenVerifier(
        tokens={token: {"client_id": "paperless-mcp", "scopes": ["mcp:access"]}},
        required_scopes=["mcp:access"],
    )


settings = Settings.from_env()
client = PaperlessClient(settings)
mcp: FastMCP = FastMCP(name="paperless-ngx", auth=_build_auth())


@mcp.custom_route("/health", methods=["GET"])
async def health_check(_: Request) -> JSONResponse:
    return JSONResponse({"status": "healthy", "service": "paperless-mcp"})
