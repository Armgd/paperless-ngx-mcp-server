"""High-level composed tools."""
from __future__ import annotations

from fastmcp import Client

from .conftest import FakeClient


async def test_find_documents_resolves_names(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_get(
        "/api/correspondents/", {"results": [{"id": 7, "name": "Acme"}]}
    )
    fake_client.set_get(
        "/api/document_types/", {"results": [{"id": 3, "name": "Invoice"}]}
    )
    fake_client.set_paginate("/api/documents/", [{"id": 1, "title": "Inv 1"}])

    result = await mcp_client.call_tool(
        "find_documents",
        {"correspondent_name": "Acme", "document_type_name": "Invoice"},
    )
    assert result.data["count"] == 1
    assert result.data["unresolved"] == []
    filters = result.data["filters_applied"]
    assert filters["correspondent__id"] == 7
    assert filters["document_type__id"] == 3


async def test_find_documents_unresolved(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_get("/api/correspondents/", {"results": []})
    fake_client.set_paginate("/api/documents/", [])
    result = await mcp_client.call_tool(
        "find_documents", {"correspondent_name": "Ghost"}
    )
    assert "correspondent:Ghost" in result.data["unresolved"]
    assert "correspondent__id" not in result.data["filters_applied"]


async def test_find_documents_tag_resolution(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    # resolve_name_to_id is called per tag — single shared path with overwriting response.
    # Use a side-effect approach: only one tag exists.
    fake_client.set_get("/api/tags/", {"results": [{"id": 11, "name": "tax"}]})
    fake_client.set_paginate("/api/documents/", [])
    result = await mcp_client.call_tool(
        "find_documents", {"tag_names_all": ["tax"]}
    )
    assert result.data["filters_applied"]["tags__id__all"] == "11"


async def test_recent_documents_default_added(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_paginate(
        "/api/documents/", [{"id": 1, "title": "Recent"}]
    )
    result = await mcp_client.call_tool(
        "recent_documents", {"days": 7, "limit": 5}
    )
    assert result.data["by"] == "added"
    assert result.data["count"] == 1
    _, _, params = fake_client.calls[-1]
    assert params is not None
    assert "added__date__gte" in params
    assert params["ordering"] == "-added"


async def test_recent_documents_by_created(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_paginate("/api/documents/", [])
    await mcp_client.call_tool(
        "recent_documents", {"days": 30, "by": "created"}
    )
    _, _, params = fake_client.calls[-1]
    assert params is not None
    assert "created__date__gte" in params
    assert params["ordering"] == "-created"


async def test_answer_from_documents(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_get(
        "/api/search/",
        {
            "count": 2,
            "results": [
                {"id": 10, "score": 0.9, "highlights": "match"},
                {"id": 20, "score": 0.5},
            ],
        },
    )
    fake_client.set_get(
        "/api/documents/10/",
        {
            "id": 10,
            "title": "First",
            "content": "long ocr content " * 100,
            "tags": [],
        },
    )
    fake_client.set_get(
        "/api/documents/20/",
        {"id": 20, "title": "Second", "content": "tiny", "tags": []},
    )

    result = await mcp_client.call_tool(
        "answer_from_documents",
        {"query": "rent", "top_k": 5, "excerpt_chars": 200},
    )
    assert result.data["total_hits"] == 2
    assert result.data["returned"] == 2
    sources = result.data["sources"]
    first = next(s for s in sources if s["id"] == 10)
    assert len(first["excerpt"]) == 200
    assert first["excerpt_truncated"] is True
    second = next(s for s in sources if s["id"] == 20)
    assert second["excerpt_truncated"] is False
