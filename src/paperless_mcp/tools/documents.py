"""Document retrieval tools."""
from __future__ import annotations

import base64
from typing import Annotated, Any

from pydantic import Field

from ..app import client, mcp, settings
from ._helpers import slim_document
from ._safe_path import UnsafePathError, sanitize_save_path


@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True},
)
async def list_documents(
    correspondent_id: Annotated[int | None, Field(description="Filter by correspondent id")] = None,
    document_type_id: Annotated[int | None, Field(description="Filter by doc type id")] = None,
    storage_path_id: Annotated[int | None, Field(description="Filter by storage path id")] = None,
    tag_ids_all: Annotated[list[int] | None, Field(description="Docs with ALL these tag ids")] = None,
    tag_ids_any: Annotated[list[int] | None, Field(description="Docs with ANY of these tag ids")] = None,
    title_contains: Annotated[str | None, Field(description="Title icontains substring")] = None,
    content_contains: Annotated[str | None, Field(description="OCR content icontains substring")] = None,
    created_year: Annotated[int | None, Field(description="Document created year")] = None,
    created_month: Annotated[int | None, Field(description="Document created month (1-12)")] = None,
    created_after: Annotated[str | None, Field(description="ISO date YYYY-MM-DD, created >=")] = None,
    created_before: Annotated[str | None, Field(description="ISO date YYYY-MM-DD, created <=")] = None,
    added_after: Annotated[str | None, Field(description="ISO date YYYY-MM-DD, added >=")] = None,
    is_in_inbox: Annotated[bool | None, Field(description="Filter to inbox-tagged docs")] = None,
    archive_serial_number: Annotated[int | None, Field(description="Exact ASN")] = None,
    ordering: Annotated[
        str | None,
        Field(description="Sort field, prefix '-' for desc. e.g. '-created'"),
    ] = "-created",
    max_results: Annotated[int, Field(ge=1, le=500, description="Cap on returned docs")] = 50,
) -> dict[str, Any]:
    """List documents with structured filters. Auto-paginates up to max_results."""
    params: dict[str, Any] = {"ordering": ordering}
    if correspondent_id is not None:
        params["correspondent__id"] = correspondent_id
    if document_type_id is not None:
        params["document_type__id"] = document_type_id
    if storage_path_id is not None:
        params["storage_path__id"] = storage_path_id
    if tag_ids_all:
        params["tags__id__all"] = ",".join(str(i) for i in tag_ids_all)
    if tag_ids_any:
        params["tags__id__in"] = ",".join(str(i) for i in tag_ids_any)
    if title_contains:
        params["title__icontains"] = title_contains
    if content_contains:
        params["content__icontains"] = content_contains
    if created_year is not None:
        params["created__year"] = created_year
    if created_month is not None:
        params["created__month"] = created_month
    if created_after:
        params["created__date__gte"] = created_after
    if created_before:
        params["created__date__lte"] = created_before
    if added_after:
        params["added__date__gte"] = added_after
    if is_in_inbox is not None:
        params["is_in_inbox"] = is_in_inbox
    if archive_serial_number is not None:
        params["archive_serial_number"] = archive_serial_number

    docs = await client.paginate("/api/documents/", params=params, max_items=max_results)
    return {"count": len(docs), "documents": [slim_document(d) for d in docs]}


@mcp.tool(annotations={"readOnlyHint": True})
async def get_document(
    document_id: Annotated[int, Field(description="Document id")],
) -> dict[str, Any]:
    """Fetch full document record (no OCR content)."""
    doc = await client.get(f"/api/documents/{document_id}/")
    doc.pop("content", None)
    return doc


@mcp.tool(annotations={"readOnlyHint": True})
async def get_document_content(
    document_id: Annotated[int, Field(description="Document id")],
    max_chars: Annotated[int, Field(ge=100, le=200_000, description="Truncate OCR text")] = 50_000,
) -> dict[str, Any]:
    """Fetch OCR/extracted text for a document, plus key metadata. Use as RAG source."""
    doc = await client.get(f"/api/documents/{document_id}/")
    content = doc.get("content") or ""
    truncated = len(content) > max_chars
    return {
        "id": doc.get("id"),
        "title": doc.get("title"),
        "created": doc.get("created"),
        "correspondent": doc.get("correspondent"),
        "document_type": doc.get("document_type"),
        "tags": doc.get("tags"),
        "content": content[:max_chars],
        "content_truncated": truncated,
        "content_total_chars": len(content),
    }


@mcp.tool(annotations={"readOnlyHint": True})
async def get_document_metadata(
    document_id: Annotated[int, Field(description="Document id")],
) -> dict[str, Any]:
    """Get extended file metadata (mime, size, original/archive checksums, parsed fields)."""
    return await client.get(f"/api/documents/{document_id}/metadata/")


@mcp.tool(annotations={"readOnlyHint": True})
async def get_document_notes(
    document_id: Annotated[int, Field(description="Document id")],
) -> list[dict[str, Any]]:
    """List notes attached to a document."""
    return await client.get(f"/api/documents/{document_id}/notes/")


@mcp.tool(annotations={"readOnlyHint": True})
async def get_document_suggestions(
    document_id: Annotated[int, Field(description="Document id")],
) -> dict[str, Any]:
    """Get classifier suggestions (correspondent, tags, type, dates) for a document."""
    return await client.get(f"/api/documents/{document_id}/suggestions/")


@mcp.tool(annotations={"readOnlyHint": True})
async def get_document_history(
    document_id: Annotated[int, Field(description="Document id")],
) -> Any:
    """Get audit history for a document."""
    return await client.get(f"/api/documents/{document_id}/history/")


@mcp.tool(annotations={"readOnlyHint": True})
async def download_document(
    document_id: Annotated[int, Field(description="Document id")],
    original: Annotated[bool, Field(description="Download original (not archived PDF)")] = False,
    save_to_path: Annotated[
        str | None,
        Field(description="If set, write to this absolute path and return path; else return base64"),
    ] = None,
    max_inline_bytes: Annotated[
        int,
        Field(ge=1024, le=20_000_000, description="Refuse inline b64 above this size"),
    ] = 2_000_000,
) -> dict[str, Any]:
    """Download a document as PDF/original. Prefer save_to_path for large files."""
    params = {"original": "true"} if original else None
    blob = await client.get_binary(f"/api/documents/{document_id}/download/", params=params)
    size = len(blob)
    if save_to_path:
        try:
            path = sanitize_save_path(save_to_path, root=settings.download_dir)
        except UnsafePathError as exc:
            return {"error": str(exc)}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        return {"saved_to": str(path), "bytes": size}
    if size > max_inline_bytes:
        return {
            "error": "file too large for inline base64",
            "bytes": size,
            "hint": "set save_to_path to write to disk",
        }
    return {
        "encoding": "base64",
        "bytes": size,
        "data": base64.b64encode(blob).decode("ascii"),
    }


@mcp.tool(annotations={"readOnlyHint": True})
async def get_document_thumbnail(
    document_id: Annotated[int, Field(description="Document id")],
) -> dict[str, Any]:
    """Get document thumbnail as base64."""
    blob, headers = await client.get_binary_with_headers(
        f"/api/documents/{document_id}/thumb/"
    )
    mime = headers.get("content-type", "application/octet-stream").split(";")[0].strip()
    return {
        "encoding": "base64",
        "mime": mime,
        "bytes": len(blob),
        "data": base64.b64encode(blob).decode("ascii"),
    }


@mcp.tool(annotations={"readOnlyHint": True})
async def get_document_preview(
    document_id: Annotated[int, Field(description="Document id")],
    save_to_path: Annotated[str | None, Field(description="Write to disk instead of b64")] = None,
    max_inline_bytes: Annotated[int, Field(ge=1024, le=20_000_000)] = 2_000_000,
) -> dict[str, Any]:
    """Get document preview (PDF). Prefer save_to_path for large files."""
    blob = await client.get_binary(f"/api/documents/{document_id}/preview/")
    if save_to_path:
        try:
            path = sanitize_save_path(save_to_path, root=settings.download_dir)
        except UnsafePathError as exc:
            return {"error": str(exc)}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        return {"saved_to": str(path), "bytes": len(blob)}
    if len(blob) > max_inline_bytes:
        return {
            "error": "preview too large for inline base64",
            "bytes": len(blob),
            "hint": "set save_to_path",
        }
    return {
        "encoding": "base64",
        "bytes": len(blob),
        "data": base64.b64encode(blob).decode("ascii"),
    }


@mcp.tool(annotations={"readOnlyHint": True})
async def get_next_asn() -> dict[str, Any]:
    """Get the next available archive serial number."""
    val = await client.get("/api/documents/next_asn/")
    return {"next_asn": val}


__all__ = [
    "list_documents",
    "get_document",
    "get_document_content",
    "get_document_metadata",
    "get_document_notes",
    "get_document_suggestions",
    "get_document_history",
    "download_document",
    "get_document_thumbnail",
    "get_document_preview",
    "get_next_asn",
]
