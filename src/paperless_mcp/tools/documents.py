"""Document retrieval tools."""
from __future__ import annotations

import base64
from typing import Annotated, Any

from fastmcp import Context
from fastmcp.exceptions import ToolError
from pydantic import Field

from ..app import READ_ONLY, client, mcp, settings
from ._helpers import slim_document, slim_metadata
from ._safe_path import UnsafePathError, sanitize_save_path
from ._schemas import (
    BinaryInline,
    BinarySaved,
    DocumentContent,
    DocumentListResponse,
    MetadataResponse,
    NextAsnResponse,
    make_page_info,
)


@mcp.tool(annotations=READ_ONLY)
async def paperless_list_documents(
    ctx: Context,
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
) -> DocumentListResponse:
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

    await ctx.debug(f"paperless_list_documents params={params!r} max_results={max_results}")

    async def _progress(seen: int, total: int | None) -> None:
        if total is not None:
            await ctx.report_progress(progress=seen, total=total)

    docs, total, has_more = await client.paginate(
        "/api/documents/", params=params, max_items=max_results, progress_cb=_progress
    )
    await ctx.info(
        f"returned {len(docs)} documents"
        + (f" of {total} total" if total is not None else "")
    )
    return DocumentListResponse(
        documents=[slim_document(d) for d in docs],  # type: ignore[misc]
        page_info=make_page_info(len(docs), total, has_more, max_results),
    )


@mcp.tool(annotations=READ_ONLY)
async def paperless_get_document(
    document_id: Annotated[int, Field(description="Document id")],
) -> dict[str, Any]:
    """Fetch full document record (no OCR content)."""
    doc = await client.get(f"/api/documents/{document_id}/")
    doc.pop("content", None)
    return doc


@mcp.tool(annotations=READ_ONLY)
async def paperless_get_document_content(
    document_id: Annotated[int, Field(description="Document id")],
    max_chars: Annotated[int, Field(ge=100, le=200_000, description="Truncate OCR text")] = 50_000,
) -> DocumentContent:
    """Fetch OCR/extracted text for a document, plus key metadata. Use as RAG source."""
    doc = await client.get(f"/api/documents/{document_id}/")
    content = doc.get("content") or ""
    truncated = len(content) > max_chars
    return DocumentContent(
        id=doc.get("id"),
        title=doc.get("title"),
        created=doc.get("created"),
        correspondent=doc.get("correspondent"),
        document_type=doc.get("document_type"),
        tags=doc.get("tags"),
        content=content[:max_chars],
        content_truncated=truncated,
        content_total_chars=len(content),
    )


@mcp.tool(annotations=READ_ONLY)
async def paperless_get_document_metadata(
    document_id: Annotated[int, Field(description="Document id")],
    include_raw_metadata: Annotated[
        bool,
        Field(
            description="Include verbose original_metadata / archive_metadata arrays (often >100 entries)"
        ),
    ] = False,
) -> MetadataResponse:
    """Get extended file metadata (mime, size, checksums, page count, lang).

    By default omits the verbose `original_metadata` / `archive_metadata` arrays.
    Set `include_raw_metadata=True` to receive them.
    """
    raw = await client.get(f"/api/documents/{document_id}/metadata/")
    if include_raw_metadata:
        return raw
    return slim_metadata(raw)  # type: ignore[return-value]


@mcp.tool(annotations=READ_ONLY)
async def paperless_get_document_notes(
    document_id: Annotated[int, Field(description="Document id")],
) -> list[dict[str, Any]]:
    """List notes attached to a document."""
    return await client.get(f"/api/documents/{document_id}/notes/")


@mcp.tool(annotations=READ_ONLY)
async def paperless_get_document_suggestions(
    document_id: Annotated[int, Field(description="Document id")],
) -> dict[str, Any]:
    """Get classifier suggestions (correspondent, tags, type, dates) for a document."""
    return await client.get(f"/api/documents/{document_id}/suggestions/")


@mcp.tool(annotations=READ_ONLY)
async def paperless_get_document_history(
    document_id: Annotated[int, Field(description="Document id")],
) -> list[dict[str, Any]]:
    """Get audit history for a document."""
    data = await client.get(f"/api/documents/{document_id}/history/")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        results = data.get("results")
        return list(results) if isinstance(results, list) else []
    return []


@mcp.tool(annotations=READ_ONLY)
async def paperless_download_document(
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
) -> BinaryInline | BinarySaved:
    """Download a document as PDF/original. Prefer save_to_path for large files."""
    params = {"original": "true"} if original else None
    blob = await client.get_binary(f"/api/documents/{document_id}/download/", params=params)
    size = len(blob)
    if save_to_path:
        try:
            path = sanitize_save_path(save_to_path, root=settings.download_dir)
        except UnsafePathError as exc:
            raise ToolError(str(exc)) from exc
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        return BinarySaved(saved_to=str(path), bytes=size)
    if size > max_inline_bytes:
        raise ToolError(
            f"file too large for inline base64 ({size} bytes); "
            "set save_to_path to write to disk"
        )
    return BinaryInline(
        encoding="base64",
        bytes=size,
        data=base64.b64encode(blob).decode("ascii"),
    )


@mcp.tool(annotations=READ_ONLY)
async def paperless_get_document_thumbnail(
    document_id: Annotated[int, Field(description="Document id")],
    save_to_path: Annotated[
        str | None, Field(description="Write to disk instead of b64")
    ] = None,
    max_inline_bytes: Annotated[
        int,
        Field(ge=1024, le=20_000_000, description="Refuse inline b64 above this size"),
    ] = 2_000_000,
) -> BinaryInline | BinarySaved:
    """Get document thumbnail (typically small PNG). Prefer save_to_path for oversized blobs."""
    blob, headers = await client.get_binary_with_headers(
        f"/api/documents/{document_id}/thumb/"
    )
    size = len(blob)
    mime = headers.get("content-type", "application/octet-stream").split(";")[0].strip()
    if save_to_path:
        try:
            path = sanitize_save_path(save_to_path, root=settings.download_dir)
        except UnsafePathError as exc:
            raise ToolError(str(exc)) from exc
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        return BinarySaved(saved_to=str(path), bytes=size)
    if size > max_inline_bytes:
        raise ToolError(
            f"thumbnail too large for inline base64 ({size} bytes); "
            "set save_to_path to write to disk"
        )
    return BinaryInline(
        encoding="base64",
        mime=mime,
        bytes=size,
        data=base64.b64encode(blob).decode("ascii"),
    )


@mcp.tool(annotations=READ_ONLY)
async def paperless_get_document_preview(
    document_id: Annotated[int, Field(description="Document id")],
    save_to_path: Annotated[str | None, Field(description="Write to disk instead of b64")] = None,
    max_inline_bytes: Annotated[int, Field(ge=1024, le=20_000_000)] = 2_000_000,
) -> BinaryInline | BinarySaved:
    """Get document preview (PDF). Prefer save_to_path for large files."""
    blob = await client.get_binary(f"/api/documents/{document_id}/preview/")
    size = len(blob)
    if save_to_path:
        try:
            path = sanitize_save_path(save_to_path, root=settings.download_dir)
        except UnsafePathError as exc:
            raise ToolError(str(exc)) from exc
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        return BinarySaved(saved_to=str(path), bytes=size)
    if size > max_inline_bytes:
        raise ToolError(
            f"preview too large for inline base64 ({size} bytes); "
            "set save_to_path"
        )
    return BinaryInline(
        encoding="base64",
        bytes=size,
        data=base64.b64encode(blob).decode("ascii"),
    )


@mcp.tool(annotations=READ_ONLY)
async def paperless_get_next_asn() -> NextAsnResponse:
    """Get the next available archive serial number."""
    val = await client.get("/api/documents/next_asn/")
    return NextAsnResponse(next_asn=int(val))


__all__ = [
    "paperless_list_documents",
    "paperless_get_document",
    "paperless_get_document_content",
    "paperless_get_document_metadata",
    "paperless_get_document_notes",
    "paperless_get_document_suggestions",
    "paperless_get_document_history",
    "paperless_download_document",
    "paperless_get_document_thumbnail",
    "paperless_get_document_preview",
    "paperless_get_next_asn",
]
