"""Statistics and instance status tools."""
from __future__ import annotations

from typing import Any

from ..app import client, mcp


@mcp.tool(annotations={"readOnlyHint": True})
async def get_statistics() -> dict[str, Any]:
    """Get Paperless aggregate statistics (doc counts, inbox, characters, ...)."""
    return await client.get("/api/statistics/")


@mcp.tool(annotations={"readOnlyHint": True})
async def get_status() -> dict[str, Any]:
    """Get instance health and component status."""
    return await client.get("/api/status/")


@mcp.tool(annotations={"readOnlyHint": True})
async def get_remote_version() -> dict[str, Any]:
    """Get latest remote Paperless-ngx version info."""
    return await client.get("/api/remote_version/")
