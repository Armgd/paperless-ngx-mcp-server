"""Taxonomy tools."""
from __future__ import annotations

import pytest
from fastmcp import Client

from .conftest import FakeClient


@pytest.mark.parametrize(
    "tool,path",
    [
        ("list_tags", "/api/tags/"),
        ("list_correspondents", "/api/correspondents/"),
        ("list_document_types", "/api/document_types/"),
        ("list_storage_paths", "/api/storage_paths/"),
        ("list_custom_fields", "/api/custom_fields/"),
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
    items = result.data
    assert len(items) == 2
    for it in items:
        assert "extra_garbage" not in it
        assert "id" in it


async def test_get_tag(mcp_client: Client, fake_client: FakeClient) -> None:
    fake_client.set_get("/api/tags/3/", {"id": 3, "name": "urgent"})
    result = await mcp_client.call_tool("get_tag", {"tag_id": 3})
    assert result.data == {"id": 3, "name": "urgent"}


async def test_list_saved_views(mcp_client: Client, fake_client: FakeClient) -> None:
    fake_client.set_paginate(
        "/api/saved_views/", [{"id": 1, "name": "Inbox", "filter_rules": []}]
    )
    result = await mcp_client.call_tool("list_saved_views", {})
    assert result.data[0]["name"] == "Inbox"


async def test_list_tags_with_filter(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_paginate("/api/tags/", [])
    await mcp_client.call_tool("list_tags", {"name_contains": "urg"})
    _, _, params = fake_client.calls[-1]
    assert params == {"name__icontains": "urg"}
