"""Full-text search tools."""
from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from ..app import client, mcp


@mcp.tool(annotations={"readOnlyHint": True})
async def search_documents(
    query: Annotated[str, Field(description="Full-text query (Whoosh syntax supported)")],
    db_only: Annotated[bool, Field(description="Skip Whoosh index, DB-only search")] = False,
    max_results: Annotated[int, Field(ge=1, le=200)] = 20,
) -> dict[str, Any]:
    """Full-text search Paperless documents. Returns hits with highlighted excerpts."""
    params: dict[str, Any] = {"query": query}
    if db_only:
        params["db_only"] = "true"
    data = await client.get("/api/search/", params=params)
    results = data.get("results", []) if isinstance(data, dict) else []
    return {
        "query": query,
        "count": data.get("count") if isinstance(data, dict) else len(results),
        "results": results[:max_results],
    }


@mcp.tool(annotations={"readOnlyHint": True})
async def search_autocomplete(
    term: Annotated[str, Field(description="Prefix term")],
    limit: Annotated[int, Field(ge=1, le=50)] = 10,
) -> list[str]:
    """Get autocomplete completions for a search term."""
    return await client.get(
        "/api/search/autocomplete/", params={"term": term, "limit": limit}
    )
