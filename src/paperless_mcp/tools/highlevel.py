"""High-level workflow helpers built on top of basic tools.

These resolve human-friendly inputs (names, periods) to IDs internally and
combine multiple endpoints into single tool calls.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Annotated, Any, cast

from fastmcp import Context
from fastmcp.exceptions import ToolError
from mcp import McpError
from pydantic import Field

from ..app import READ_ONLY, client, mcp
from ..client import PaperlessAPIError
from ._filters import FilterRequest, build_document_filters
from ._helpers import slim_document


@mcp.tool(annotations=READ_ONLY)
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


@mcp.tool(annotations=READ_ONLY)
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
        except PaperlessAPIError as e:
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


@mcp.tool(annotations=READ_ONLY)
async def interactive_search(
    ctx: Context,
    max_results: Annotated[int, Field(ge=1, le=200)] = 25,
) -> dict[str, Any]:
    """Interactive document search. Elicits strategy + parameters from user step by step.

    Use when user asks vague questions like "find my documents" without enough detail.
    Asks: which strategy (full-text / filters / recent), then gathers needed inputs.
    Raises `ToolError` naming alternative tools (`find_documents`, `answer_from_documents`,
    `recent_documents`) if the client doesn't support MCP elicitation.
    """
    try:
        strategy = await ctx.elicit(
            "How do you want to search?",
            response_type=["full_text", "filters", "recent"],  # type: ignore[arg-type]
        )
    except (McpError, NotImplementedError, RuntimeError) as exc:
        raise ToolError(
            "interactive_search requires a client that supports MCP elicitation. "
            "Use find_documents, answer_from_documents, or recent_documents instead."
        ) from exc
    if strategy.action != "accept":
        return {"status": strategy.action, "step": "strategy"}
    strategy_value = str(strategy.data)

    if strategy_value == "full_text":
        q = await ctx.elicit("Enter full-text query (Whoosh syntax ok):", response_type=str)  # type: ignore[arg-type]
        if q.action != "accept":
            return {"status": q.action, "step": "query"}
        data = await client.get("/api/search/", params={"query": str(q.data)})
        results = data.get("results", []) if isinstance(data, dict) else []
        return {
            "strategy": "full_text",
            "query": str(q.data),
            "count": data.get("count") if isinstance(data, dict) else len(results),
            "results": results[:max_results],
        }

    if strategy_value == "recent":
        days = await ctx.elicit("Look-back window in days?", response_type=int)  # type: ignore[arg-type]
        if days.action != "accept":
            return {"status": days.action, "step": "days"}
        from datetime import date, timedelta

        days_raw = days.data
        days_int = max(1, int(days_raw) if isinstance(days_raw, (int, str)) else 1)
        since = (date.today() - timedelta(days=days_int)).isoformat()
        recent_params = {"added__date__gte": since, "ordering": "-added"}
        recent_docs = await client.paginate(
            "/api/documents/", params=recent_params, max_items=max_results
        )
        return {
            "strategy": "recent",
            "since": since,
            "count": len(recent_docs),
            "documents": [slim_document(d) for d in recent_docs],
        }

    form = await ctx.elicit(
        "Provide any filters (leave blank to skip). Tags as comma-separated names.",
        response_type=_FilterForm,  # type: ignore[arg-type]
    )
    if form.action != "accept":
        return {"status": form.action, "step": "filters"}
    f = cast(_FilterForm, form.data)

    tag_names = (
        [n.strip() for n in f.tag_names_csv.split(",") if n.strip()]
        if f.tag_names_csv
        else []
    )
    req = FilterRequest(
        correspondent_name=f.correspondent_name or None,
        document_type_name=f.document_type_name or None,
        tag_names_all=tag_names,
        title_contains=f.title_contains or None,
        year=f.year or None,
        created_after=f.created_after or None,
        created_before=f.created_before or None,
    )
    filter_params, unresolved = await build_document_filters(req)
    filter_params["ordering"] = "-created"

    if len(filter_params) == 1:
        confirm = await ctx.elicit(
            "No filters provided. Run unfiltered listing (most recent)?",
            response_type=None,
        )
        if confirm.action != "accept":
            return {"status": confirm.action, "step": "confirm_unfiltered"}

    filter_docs = await client.paginate(
        "/api/documents/", params=filter_params, max_items=max_results
    )
    return {
        "strategy": "filters",
        "unresolved": unresolved,
        "filters_applied": {k: v for k, v in filter_params.items() if k != "ordering"},
        "count": len(filter_docs),
        "documents": [slim_document(d) for d in filter_docs],
    }


@mcp.tool(annotations=READ_ONLY)
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
