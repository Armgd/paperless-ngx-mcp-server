"""Task / job inspection tools."""
from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from ..app import READ_ONLY, client, mcp


@mcp.tool(annotations=READ_ONLY)
async def list_tasks(
    max_results: Annotated[int, Field(ge=1, le=500)] = 100,
) -> list[dict[str, Any]]:
    """List background tasks (consumer/index/etc)."""
    data = await client.get("/api/tasks/")
    if isinstance(data, list):
        return data[:max_results]
    if isinstance(data, dict):
        results = data.get("results") or []
        return results[:max_results]
    return []
