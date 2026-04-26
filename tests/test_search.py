"""Search tools."""
from __future__ import annotations

from fastmcp import Client

from .conftest import FakeClient


async def test_search_documents(mcp_client: Client, fake_client: FakeClient) -> None:
    fake_client.set_get(
        "/api/search/",
        {"count": 2, "results": [{"id": 1, "score": 0.9}, {"id": 2, "score": 0.5}]},
    )
    result = await mcp_client.call_tool(
        "search_documents", {"query": "invoice", "max_results": 10}
    )
    assert result.data["count"] == 2
    assert result.data["query"] == "invoice"
    assert len(result.data["results"]) == 2

    _, _, params = fake_client.calls[-1]
    assert params == {"query": "invoice"}


async def test_search_documents_db_only(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_get("/api/search/", {"count": 0, "results": []})
    await mcp_client.call_tool(
        "search_documents", {"query": "x", "db_only": True}
    )
    _, _, params = fake_client.calls[-1]
    assert params is not None
    assert params["db_only"] == "true"


async def test_search_documents_caps_results(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_get(
        "/api/search/",
        {"count": 50, "results": [{"id": i} for i in range(50)]},
    )
    result = await mcp_client.call_tool(
        "search_documents", {"query": "q", "max_results": 5}
    )
    assert len(result.data["results"]) == 5
    assert result.data["count"] == 50


async def test_autocomplete(mcp_client: Client, fake_client: FakeClient) -> None:
    fake_client.set_get(
        "/api/search/autocomplete/", ["invoice", "invoices", "invoiced"]
    )
    result = await mcp_client.call_tool(
        "search_autocomplete", {"term": "invo", "limit": 10}
    )
    assert result.data == ["invoice", "invoices", "invoiced"]
