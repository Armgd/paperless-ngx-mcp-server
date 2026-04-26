"""Taxonomy tools: tags, correspondents, document types, storage paths, custom fields, saved views."""
from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from ..app import client, mcp


def _slim_taxonomy(item: dict[str, Any]) -> dict[str, Any]:
    keep = {"id", "name", "slug", "match", "matching_algorithm", "is_insensitive",
            "document_count", "color", "is_inbox_tag", "owner", "path", "data_type"}
    return {k: v for k, v in item.items() if k in keep}


# --- Tags ---

@mcp.tool(annotations={"readOnlyHint": True})
async def list_tags(
    name_contains: Annotated[str | None, Field(description="Filter name icontains")] = None,
    max_results: Annotated[int, Field(ge=1, le=1000)] = 200,
) -> list[dict[str, Any]]:
    """List all tags."""
    params = {"name__icontains": name_contains} if name_contains else None
    items = await client.paginate("/api/tags/", params=params, max_items=max_results)
    return [_slim_taxonomy(i) for i in items]


@mcp.tool(annotations={"readOnlyHint": True})
async def get_tag(tag_id: Annotated[int, Field(description="Tag id")]) -> dict[str, Any]:
    """Fetch a single tag."""
    return await client.get(f"/api/tags/{tag_id}/")


# --- Correspondents ---

@mcp.tool(annotations={"readOnlyHint": True})
async def list_correspondents(
    name_contains: Annotated[str | None, Field(description="Filter name icontains")] = None,
    max_results: Annotated[int, Field(ge=1, le=1000)] = 200,
) -> list[dict[str, Any]]:
    """List all correspondents."""
    params = {"name__icontains": name_contains} if name_contains else None
    items = await client.paginate("/api/correspondents/", params=params, max_items=max_results)
    return [_slim_taxonomy(i) for i in items]


@mcp.tool(annotations={"readOnlyHint": True})
async def get_correspondent(
    correspondent_id: Annotated[int, Field(description="Correspondent id")],
) -> dict[str, Any]:
    """Fetch a single correspondent."""
    return await client.get(f"/api/correspondents/{correspondent_id}/")


# --- Document Types ---

@mcp.tool(annotations={"readOnlyHint": True})
async def list_document_types(
    name_contains: Annotated[str | None, Field(description="Filter name icontains")] = None,
    max_results: Annotated[int, Field(ge=1, le=1000)] = 200,
) -> list[dict[str, Any]]:
    """List all document types."""
    params = {"name__icontains": name_contains} if name_contains else None
    items = await client.paginate("/api/document_types/", params=params, max_items=max_results)
    return [_slim_taxonomy(i) for i in items]


@mcp.tool(annotations={"readOnlyHint": True})
async def get_document_type(
    document_type_id: Annotated[int, Field(description="Document type id")],
) -> dict[str, Any]:
    """Fetch a single document type."""
    return await client.get(f"/api/document_types/{document_type_id}/")


# --- Storage Paths ---

@mcp.tool(annotations={"readOnlyHint": True})
async def list_storage_paths(
    max_results: Annotated[int, Field(ge=1, le=1000)] = 200,
) -> list[dict[str, Any]]:
    """List all storage paths."""
    items = await client.paginate("/api/storage_paths/", max_items=max_results)
    return [_slim_taxonomy(i) for i in items]


# --- Custom Fields ---

@mcp.tool(annotations={"readOnlyHint": True})
async def list_custom_fields(
    max_results: Annotated[int, Field(ge=1, le=1000)] = 200,
) -> list[dict[str, Any]]:
    """List all custom field definitions."""
    items = await client.paginate("/api/custom_fields/", max_items=max_results)
    return [_slim_taxonomy(i) for i in items]


# --- Saved Views ---

@mcp.tool(annotations={"readOnlyHint": True})
async def list_saved_views(
    max_results: Annotated[int, Field(ge=1, le=1000)] = 200,
) -> list[dict[str, Any]]:
    """List all saved views."""
    return await client.paginate("/api/saved_views/", max_items=max_results)


@mcp.tool(annotations={"readOnlyHint": True})
async def get_saved_view(
    saved_view_id: Annotated[int, Field(description="Saved view id")],
) -> dict[str, Any]:
    """Fetch a single saved view (incl. filter rules)."""
    return await client.get(f"/api/saved_views/{saved_view_id}/")
