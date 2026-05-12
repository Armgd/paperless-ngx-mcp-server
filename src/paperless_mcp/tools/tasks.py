"""Task / job inspection tools."""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..app import READ_ONLY, client, mcp
from ._schemas import TaskListResponse, make_page_info


@mcp.tool(annotations=READ_ONLY)
async def paperless_list_tasks(
    max_results: Annotated[int, Field(ge=1, le=500)] = 100,
) -> TaskListResponse:
    """List background tasks (consumer/index/etc)."""
    data = await client.get("/api/tasks/")
    if isinstance(data, list):
        total = len(data)
        items = data[:max_results]
        has_more = total > max_results
    elif isinstance(data, dict):
        results = data.get("results") or []
        if not isinstance(results, list):
            results = []
        upstream_total = data.get("count")
        total = int(upstream_total) if isinstance(upstream_total, int) else len(results)
        items = results[:max_results]
        has_more = len(results) > max_results or bool(data.get("next"))
    else:
        items, total, has_more = [], 0, False
    return TaskListResponse(
        tasks=items,
        page_info=make_page_info(len(items), total, has_more, max_results),
    )
