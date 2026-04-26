"""High-level workflow helpers built on top of basic tools.

These resolve human-friendly inputs (names, periods) to IDs internally and
combine multiple endpoints into single tool calls.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Annotated, Any

from fastmcp import Context
from pydantic import Field

from ..app import client, mcp
from ._filters import FilterRequest, build_document_filters
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
    req = FilterRequest(
        correspondent_name=correspondent_name,
        document_type_name=document_type_name,
        storage_path_name=storage_path_name,
        tag_names_all=tag_names_all or [],
        tag_names_any=tag_names_any or [],
        title_contains=title_contains,
        text_contains=text_contains,
        year=year,
        month=month,
        created_after=created_after,
        created_before=created_before,
    )
    filter_params, unresolved = await build_document_filters(req)
    params: dict[str, Any] = {"ordering": "-created", **filter_params}

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


@dataclass
class _FilterForm:
    correspondent_name: str = ""
    document_type_name: str = ""
    tag_names_csv: str = ""
    title_contains: str = ""
    year: int = 0
    created_after: str = ""
    created_before: str = ""


@mcp.tool(annotations={"readOnlyHint": True})
async def interactive_search(
    ctx: Context,
    max_results: Annotated[int, Field(ge=1, le=200)] = 25,
) -> dict[str, Any]:
    """Interactive document search. Elicits strategy + parameters from user step by step.

    Use when user asks vague questions like "find my documents" without enough detail.
    Asks: which strategy (full-text / filters / recent), then gathers needed inputs.
    Falls back to error dict if client doesn't support elicitation.
    """
    strategy = await ctx.elicit(
        "How do you want to search?",
        response_type=["full_text", "filters", "recent"],
    )
    if strategy.action != "accept":
        return {"status": strategy.action, "step": "strategy"}

    if strategy.data == "full_text":
        q = await ctx.elicit("Enter full-text query (Whoosh syntax ok):", response_type=str)
        if q.action != "accept":
            return {"status": q.action, "step": "query"}
        data = await client.get("/api/search/", params={"query": q.data})
        results = data.get("results", []) if isinstance(data, dict) else []
        return {
            "strategy": "full_text",
            "query": q.data,
            "count": data.get("count") if isinstance(data, dict) else len(results),
            "results": results[:max_results],
        }

    if strategy.data == "recent":
        days = await ctx.elicit("Look-back window in days?", response_type=int)
        if days.action != "accept":
            return {"status": days.action, "step": "days"}
        from datetime import date, timedelta

        since = (date.today() - timedelta(days=max(1, days.data))).isoformat()
        params = {"added__date__gte": since, "ordering": "-added"}
        docs = await client.paginate("/api/documents/", params=params, max_items=max_results)
        return {
            "strategy": "recent",
            "since": since,
            "count": len(docs),
            "documents": [slim_document(d) for d in docs],
        }

    form = await ctx.elicit(
        "Provide any filters (leave blank to skip). Tags as comma-separated names.",
        response_type=_FilterForm,
    )
    if form.action != "accept":
        return {"status": form.action, "step": "filters"}
    f = form.data

    params: dict[str, Any] = {"ordering": "-created"}
    unresolved: list[str] = []

    if f.correspondent_name:
        cid = await resolve_name_to_id("/api/correspondents/", f.correspondent_name)
        if cid is None:
            unresolved.append(f"correspondent:{f.correspondent_name}")
        else:
            params["correspondent__id"] = cid
    if f.document_type_name:
        dtid = await resolve_name_to_id("/api/document_types/", f.document_type_name)
        if dtid is None:
            unresolved.append(f"document_type:{f.document_type_name}")
        else:
            params["document_type__id"] = dtid
    if f.tag_names_csv:
        names = [n.strip() for n in f.tag_names_csv.split(",") if n.strip()]
        ids = await resolve_names_to_ids("/api/tags/", names)
        if len(ids) != len(names):
            unresolved.append(f"some tags missing in: {names}")
        if ids:
            params["tags__id__all"] = ",".join(str(i) for i in ids)
    if f.title_contains:
        params["title__icontains"] = f.title_contains
    if f.year:
        params["created__year"] = f.year
    if f.created_after:
        params["created__date__gte"] = f.created_after
    if f.created_before:
        params["created__date__lte"] = f.created_before

    if len(params) == 1:
        confirm = await ctx.elicit(
            "No filters provided. Run unfiltered listing (most recent)?",
            response_type=None,
        )
        if confirm.action != "accept":
            return {"status": confirm.action, "step": "confirm_unfiltered"}

    docs = await client.paginate("/api/documents/", params=params, max_items=max_results)
    return {
        "strategy": "filters",
        "unresolved": unresolved,
        "filters_applied": {k: v for k, v in params.items() if k != "ordering"},
        "count": len(docs),
        "documents": [slim_document(d) for d in docs],
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
