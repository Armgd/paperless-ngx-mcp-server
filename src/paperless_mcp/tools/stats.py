"""Statistics and instance status tools."""
from __future__ import annotations

from typing import Any

from ..app import READ_ONLY, client, mcp


@mcp.tool(annotations=READ_ONLY)
async def paperless_get_statistics() -> dict[str, Any]:
    """Get Paperless aggregate statistics (doc counts, inbox, characters, ...)."""
    return await client.get("/api/statistics/")


@mcp.tool(annotations=READ_ONLY)
async def paperless_get_status() -> dict[str, Any]:
    """Get instance health and component status."""
    return await client.get("/api/status/")


@mcp.tool(annotations=READ_ONLY)
async def paperless_get_remote_version() -> dict[str, Any]:
    """Get latest remote Paperless-ngx version info."""
    return await client.get("/api/remote_version/")
