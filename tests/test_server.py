"""Smoke tests: server boots, tools register."""
from __future__ import annotations

from fastmcp import Client


async def test_list_tools_includes_core(mcp_client: Client) -> None:
    tools = await mcp_client.list_tools()
    names = {t.name for t in tools}
    expected = {
        "verify_auth",
        "list_documents",
        "get_document",
        "get_document_content",
        "search_documents",
        "search_autocomplete",
        "list_tags",
        "list_correspondents",
        "find_documents",
        "answer_from_documents",
        "recent_documents",
    }
    missing = expected - names
    assert not missing, f"missing tools: {missing}"


async def test_all_core_tools_are_read_only(mcp_client: Client) -> None:
    tools = await mcp_client.list_tools()
    for t in tools:
        ann = t.annotations
        if ann is not None:
            assert ann.readOnlyHint is True, f"{t.name} not marked read-only"
