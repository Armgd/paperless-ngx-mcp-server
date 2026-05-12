"""Taxonomy tools."""
from __future__ import annotations

import pytest
from fastmcp import Client

from .conftest import FakeClient


@pytest.mark.parametrize(
    "tool,path",
    [
        ("paperless_list_tags", "/api/tags/"),
        ("paperless_list_correspondents", "/api/correspondents/"),
        ("paperless_list_document_types", "/api/document_types/"),
        ("paperless_list_storage_paths", "/api/storage_paths/"),
        ("paperless_list_custom_fields", "/api/custom_fields/"),
    ],
)
async def test_taxonomy_listings_slim(
    mcp_client: Client, fake_client: FakeClient, tool: str, path: str
) -> None:
    fake_client.set_paginate(
        path,
        [
            {"id": 1, "name": "Foo", "extra_garbage": "drop", "document_count": 5},
            {"id": 2, "name": "Bar", "extra_garbage": "drop", "document_count": 0},
        ],
    )
    result = await mcp_client.call_tool(tool, {})
    items = result.structured_content["items"]
    assert len(items) == 2
    for it in items:
        assert "extra_garbage" not in it
        assert "id" in it
    info = result.structured_content["page_info"]
    assert info["returned"] == 2
    assert info["has_more"] is False


async def test_get_tag(mcp_client: Client, fake_client: FakeClient) -> None:
    fake_client.set_get("/api/tags/3/", {"id": 3, "name": "urgent"})
    result = await mcp_client.call_tool("paperless_get_tag", {"tag_id": 3})
    assert result.structured_content == {"id": 3, "name": "urgent"}


async def test_list_saved_views(mcp_client: Client, fake_client: FakeClient) -> None:
    fake_client.set_paginate(
        "/api/saved_views/", [{"id": 1, "name": "Inbox", "filter_rules": []}]
    )
    result = await mcp_client.call_tool("paperless_list_saved_views", {})
    assert result.structured_content["items"][0]["name"] == "Inbox"
    assert result.structured_content["page_info"]["returned"] == 1


async def test_list_tags_with_filter(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_paginate("/api/tags/", [])
    await mcp_client.call_tool(
        "paperless_list_tags", {"name_contains": "urg"}
    )
    _, _, params = fake_client.calls[-1]
    assert params == {"name__icontains": "urg"}
