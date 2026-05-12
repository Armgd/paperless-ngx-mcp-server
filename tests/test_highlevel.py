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
        "paperless_find_documents",
        {"correspondent_name": "Acme", "document_type_name": "Invoice"},
    )
    assert result.structured_content["page_info"]["returned"] == 1
    assert result.structured_content["unresolved"] == []
    filters = result.structured_content["filters_applied"]
    assert filters["correspondent__id"] == 7
    assert filters["document_type__id"] == 3


async def test_find_documents_unresolved(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_get("/api/correspondents/", {"results": []})
    fake_client.set_paginate("/api/documents/", [])
    result = await mcp_client.call_tool(
        "paperless_find_documents", {"correspondent_name": "Ghost"}
    )
    assert "correspondent:Ghost" in result.structured_content["unresolved"]
    assert "correspondent__id" not in result.structured_content["filters_applied"]


async def test_find_documents_tag_resolution(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_get("/api/tags/", {"results": [{"id": 11, "name": "tax"}]})
    fake_client.set_paginate("/api/documents/", [])
    result = await mcp_client.call_tool(
        "paperless_find_documents", {"tag_names_all": ["tax"]}
    )
    assert result.structured_content["filters_applied"]["tags__id__all"] == "11"


async def test_recent_documents_default_added(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_paginate(
        "/api/documents/", [{"id": 1, "title": "Recent"}]
    )
    result = await mcp_client.call_tool(
        "paperless_recent_documents", {"days": 7, "limit": 5}
    )
    assert result.structured_content["by"] == "added"
    assert result.structured_content["page_info"]["returned"] == 1
    _, _, params = fake_client.calls[-1]
    assert params is not None
    assert "added__date__gte" in params
    assert params["ordering"] == "-added"


async def test_recent_documents_by_created(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_paginate("/api/documents/", [])
    await mcp_client.call_tool(
        "paperless_recent_documents", {"days": 30, "by": "created"}
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
        "paperless_answer_from_documents",
        {"query": "rent", "top_k": 5, "excerpt_chars": 200},
    )
    assert result.structured_content["total_hits"] == 2
    assert result.structured_content["returned"] == 2
    sources = result.structured_content["sources"]
    first = next(s for s in sources if s["id"] == 10)
    assert len(first["excerpt"]) == 200
    assert first["excerpt_truncated"] is True
    second = next(s for s in sources if s["id"] == 20)
    assert second["excerpt_truncated"] is False


async def test_find_documents_emits_progress_and_warnings(
    fake_client: FakeClient,
) -> None:
    fake_client.set_get("/api/correspondents/", {"results": []})
    fake_client.set_get("/api/tags/", {"results": []})
    fake_client.set_get("/api/document_types/", {"results": []})
    fake_client.set_get("/api/storage_paths/", {"results": []})
    fake_client.set_paginate(
        "/api/documents/",
        [{"id": i, "title": f"d{i}"} for i in range(2)],
    )

    progress: list[tuple[float, float | None]] = []
    logs: list[tuple[str, str]] = []

    async def on_progress(p: float, t: float | None, _: str | None) -> None:
        progress.append((p, t))

    async def on_log(message) -> None:
        logs.append((message.level, str(message.data)))

    from paperless_mcp.app import mcp as server

    async with Client(server, progress_handler=on_progress, log_handler=on_log) as c:
        result = await c.call_tool(
            "paperless_find_documents",
            {"correspondent_name": "unknown-co", "max_results": 50},
        )

    assert result.data.page_info.returned == 2
    assert any(level == "warning" for level, _ in logs)
    assert progress


async def test_answer_from_documents_reports_enrichment_progress(
    fake_client: FakeClient,
) -> None:
    fake_client.set_get(
        "/api/search/",
        {
            "count": 2,
            "results": [
                {"id": 1, "score": 0.9},
                {"id": 2, "score": 0.8},
            ],
        },
    )
    fake_client.set_get("/api/documents/1/", {"id": 1, "title": "A", "content": "x"})
    fake_client.set_get("/api/documents/2/", {"id": 2, "title": "B", "content": "y"})

    progress: list[tuple[float, float | None]] = []
    logs: list[tuple[str, str]] = []

    async def on_progress(p: float, t: float | None, _: str | None) -> None:
        progress.append((p, t))

    async def on_log(message) -> None:
        logs.append((message.level, str(message.data)))

    from paperless_mcp.app import mcp as server

    async with Client(server, progress_handler=on_progress, log_handler=on_log) as c:
        result = await c.call_tool(
            "paperless_answer_from_documents", {"query": "x", "top_k": 2}
        )

    assert result.data.returned == 2
    assert (2.0, 2.0) in progress
    assert any("enriching" in msg.lower() for _, msg in logs)


async def test_recent_documents_emits_progress(fake_client: FakeClient) -> None:
    fake_client.set_paginate(
        "/api/documents/",
        [{"id": i, "title": f"r{i}"} for i in range(4)],
    )
    progress: list[tuple[float, float | None]] = []

    async def on_progress(p: float, t: float | None, _: str | None) -> None:
        progress.append((p, t))

    from paperless_mcp.app import mcp as server

    async with Client(server, progress_handler=on_progress) as c:
        result = await c.call_tool(
            "paperless_recent_documents", {"days": 7, "limit": 10}
        )

    docs = result.data["documents"] if isinstance(result.data, dict) else result.data.documents
    assert len(docs) == 4
    assert progress
