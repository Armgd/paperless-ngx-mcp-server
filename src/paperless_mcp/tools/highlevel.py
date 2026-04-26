"""High-level workflow helpers built on top of basic tools.

These resolve human-friendly inputs (names, periods) to IDs internally and
combine multiple endpoints into single tool calls.
"""
from __future__ import annotations

import asyncio
from typing import Annotated, Any

from pydantic import Field

from ..app import client, mcp
from ._helpers import resolve_name_to_id, resolve_names_to_ids, slim_document


@mcp.tool(annotations={"readOnlyHint": True})
async def find_documents(
    correspondent_name: Annotated[str | None, Field(description="Correspondent name (resolved to id)")] = None,
    document_type_name: Annotated[str | None, Field(description="Doc type name (resolved to id)")] = None,
    storage_path_name: Annotated[str | None, Field(description="Storage path name (resolved to id)")] = None,
    tag_names_all: Annotated[list[str] | None, Field(description="All tag names (resolved)")] = None,
    tag_names_any: Annotated[list[str] | None, Field(description="Any tag names (resolved)")] = None,
    title_contains: Annotated[str | None, Field(description="Title icontains")] = None,
    text_contains: Annotated[str | None, Field(description="OCR content icontains (DB-only, no relevance ranking — prefer answer_from_documents for relevance)")] = None,
    year: Annotated[int | None, Field(description="Document creation year")] = None,
    month: Annotated[int | None, Field(description="Document creation month 1-12")] = None,
    created_after: Annotated[str | None, Field(description="ISO YYYY-MM-DD")] = None,
    created_before: Annotated[str | None, Field(description="ISO YYYY-MM-DD")] = None,
    max_results: Annotated[int, Field(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    """Find documents using human-friendly names. Resolves names→IDs then queries.

    Use this when the user asks about documents from a person/company, of a type,
    in a period, or with tags — and you don't already have IDs.
    """
    params: dict[str, Any] = {"ordering": "-created"}
    unresolved: list[str] = []

    if correspondent_name:
        cid = await resolve_name_to_id("/api/correspondents/", correspondent_name)
        if cid is None:
            unresolved.append(f"correspondent:{correspondent_name}")
        else:
            params["correspondent__id"] = cid
    if document_type_name:
        dtid = await resolve_name_to_id("/api/document_types/", document_type_name)
        if dtid is None:
            unresolved.append(f"document_type:{document_type_name}")
        else:
            params["document_type__id"] = dtid
    if storage_path_name:
        spid = await resolve_name_to_id("/api/storage_paths/", storage_path_name)
        if spid is None:
            unresolved.append(f"storage_path:{storage_path_name}")
        else:
            params["storage_path__id"] = spid
    if tag_names_all:
        ids = await resolve_names_to_ids("/api/tags/", tag_names_all)
        if len(ids) != len(tag_names_all):
            unresolved.append(f"some tags missing in: {tag_names_all}")
        if ids:
            params["tags__id__all"] = ",".join(str(i) for i in ids)
    if tag_names_any:
        ids = await resolve_names_to_ids("/api/tags/", tag_names_any)
        if ids:
            params["tags__id__in"] = ",".join(str(i) for i in ids)
    if title_contains:
        params["title__icontains"] = title_contains
    if text_contains:
        params["content__icontains"] = text_contains
    if year is not None:
        params["created__year"] = year
    if month is not None:
        params["created__month"] = month
    if created_after:
        params["created__date__gte"] = created_after
    if created_before:
        params["created__date__lte"] = created_before

    docs = await client.paginate("/api/documents/", params=params, max_items=max_results)
    return {
        "count": len(docs),
        "unresolved": unresolved,
        "filters_applied": {k: v for k, v in params.items() if k != "ordering"},
        "documents": [slim_document(d) for d in docs],
    }


@mcp.tool(annotations={"readOnlyHint": True})
async def answer_from_documents(
    query: Annotated[str, Field(description="Natural-language question or full-text query")],
    top_k: Annotated[int, Field(ge=1, le=20)] = 5,
    excerpt_chars: Annotated[
        int, Field(ge=200, le=20_000, description="Max OCR chars per excerpt")
    ] = 4000,
) -> dict[str, Any]:
    """RAG helper: full-text search, then return top-k docs with content excerpts.

    Use this for any "what does my paperwork say about X" / "find me the invoice
    where Y" question — gives the model retrieved excerpts ready to synthesize.
    """
    search = await client.get("/api/search/", params={"query": query})
    hits = (search.get("results") or [])[:top_k] if isinstance(search, dict) else []

    async def _enrich(hit: dict[str, Any]) -> dict[str, Any]:
        doc_id = hit.get("id")
        if doc_id is None:
            return hit
        try:
            doc = await client.get(f"/api/documents/{doc_id}/")
        except Exception as e:  # noqa: BLE001
            return {**hit, "fetch_error": str(e)}
        content = (doc.get("content") or "")[:excerpt_chars]
        return {
            "id": doc.get("id"),
            "title": doc.get("title"),
            "created": doc.get("created"),
            "correspondent": doc.get("correspondent"),
            "document_type": doc.get("document_type"),
            "tags": doc.get("tags"),
            "score": hit.get("score"),
            "highlights": hit.get("highlights") or hit.get("note_highlights"),
            "excerpt": content,
            "excerpt_truncated": len(doc.get("content") or "") > excerpt_chars,
        }

    enriched = await asyncio.gather(*[_enrich(h) for h in hits])
    return {
        "query": query,
        "total_hits": search.get("count") if isinstance(search, dict) else len(hits),
        "returned": len(enriched),
        "sources": list(enriched),
    }


@mcp.tool(annotations={"readOnlyHint": True})
async def recent_documents(
    days: Annotated[int, Field(ge=1, le=3650, description="Look back window in days")] = 30,
    limit: Annotated[int, Field(ge=1, le=200)] = 20,
    by: Annotated[str, Field(description="'added' or 'created'")] = "added",
) -> dict[str, Any]:
    """Most recently added or created documents."""
    from datetime import date, timedelta

    field = "added" if by == "added" else "created"
    since = (date.today() - timedelta(days=days)).isoformat()
    params = {f"{field}__date__gte": since, "ordering": f"-{field}"}
    docs = await client.paginate("/api/documents/", params=params, max_items=limit)
    return {
        "since": since,
        "by": field,
        "count": len(docs),
        "documents": [slim_document(d) for d in docs],
    }
