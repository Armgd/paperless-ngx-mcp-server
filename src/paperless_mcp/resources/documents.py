"""Per-document resource templates under the paperless:// URI scheme."""
from __future__ import annotations

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
