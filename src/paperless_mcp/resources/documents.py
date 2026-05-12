"""Per-document resource templates under the paperless:// URI scheme."""
from __future__ import annotations

from fastmcp.resources import ResourceContent, ResourceResult

from ..app import client, mcp

_MAX_RESOURCE_BYTES = 20_000_000


@mcp.resource(
    uri="paperless://documents/{document_id}/content",
    name="paperless_document_content",
    description="OCR / extracted text content of a Paperless document.",
    mime_type="text/plain",
    tags={"paperless", "document", "content"},
)
async def document_content(document_id: int) -> str:
    """Return the OCR text body of a document."""
    doc = await client.get(f"/api/documents/{document_id}/")
    return doc.get("content") or ""


@mcp.resource(
    uri="paperless://documents/{document_id}/metadata",
    name="paperless_document_metadata",
    description="Full Paperless document record (OCR content omitted).",
    mime_type="application/json",
    tags={"paperless", "document", "metadata"},
)
async def document_metadata(document_id: int) -> dict:
    """Return the document record without the (potentially large) OCR content."""
    doc = await client.get(f"/api/documents/{document_id}/")
    doc.pop("content", None)
    return doc


async def _fetch_capped_binary(path: str, mime_type: str) -> ResourceResult:
    blob = await client.get_binary(path)
    if len(blob) > _MAX_RESOURCE_BYTES:
        raise ValueError(
            f"resource too large for inline transfer ({len(blob)} bytes, "
            f"cap {_MAX_RESOURCE_BYTES}); use the equivalent tool with "
            "save_to_path instead"
        )
    return ResourceResult([ResourceContent(blob, mime_type=mime_type)])


@mcp.resource(
    uri="paperless://documents/{document_id}/preview",
    name="paperless_document_preview",
    description="PDF preview rendering of a Paperless document.",
    mime_type="application/pdf",
    tags={"paperless", "document", "preview", "binary"},
)
async def document_preview(document_id: int) -> ResourceResult:
    """Return a PDF preview of the document."""
    return await _fetch_capped_binary(
        f"/api/documents/{document_id}/preview/", "application/pdf"
    )


@mcp.resource(
    uri="paperless://documents/{document_id}/thumbnail",
    name="paperless_document_thumbnail",
    description="Thumbnail image of a Paperless document (typically WebP or PNG).",
    mime_type="image/webp",
    tags={"paperless", "document", "thumbnail", "binary"},
)
async def document_thumbnail(document_id: int) -> ResourceResult:
    """Return the document thumbnail bytes."""
    return await _fetch_capped_binary(
        f"/api/documents/{document_id}/thumb/", "image/webp"
    )


@mcp.resource(
    uri="paperless://documents/{document_id}/download",
    name="paperless_document_download",
    description="Original/archived file bytes for a Paperless document.",
    mime_type="application/octet-stream",
    tags={"paperless", "document", "download", "binary"},
)
async def document_download(document_id: int) -> ResourceResult:
    """Return the document download bytes (archived PDF by default)."""
    return await _fetch_capped_binary(
        f"/api/documents/{document_id}/download/", "application/octet-stream"
    )
