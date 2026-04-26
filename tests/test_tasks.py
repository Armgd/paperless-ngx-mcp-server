"""list_tasks tool."""
from __future__ import annotations

from fastmcp import Client

from .conftest import FakeClient


async def test_list_tasks_handles_list(mcp_client: Client, fake_client: FakeClient) -> None:
    fake_client.set_get("/api/tasks/", [{"id": 1}, {"id": 2}])
    result = await mcp_client.call_tool("list_tasks", {"max_results": 1})
    assert len(result.data) == 1


async def test_list_tasks_handles_drf_dict(mcp_client: Client, fake_client: FakeClient) -> None:
    fake_client.set_get("/api/tasks/", {"results": [{"id": 1}]})
    result = await mcp_client.call_tool("list_tasks", {})
    assert result.data == [{"id": 1}]


async def test_list_tasks_handles_null_results(mcp_client: Client, fake_client: FakeClient) -> None:
    fake_client.set_get("/api/tasks/", {"results": None})
    result = await mcp_client.call_tool("list_tasks", {})
    assert result.data == []
