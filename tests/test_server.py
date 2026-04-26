"""Smoke tests: server boots, tools register."""
from __future__ import annotations

import pytest
from fastmcp import Client

from paperless_mcp.server import main


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


def test_http_transport_requires_auth_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    with pytest.raises(SystemExit) as exc:
        main()
    assert "MCP_AUTH_TOKEN" in str(exc.value)


def test_stdio_transport_does_not_require_auth_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    called: dict[str, bool] = {}

    def fake_run(*_: object, **__: object) -> None:
        called["yes"] = True

    from paperless_mcp import app as app_module
    monkeypatch.setattr(app_module.mcp, "run", fake_run)
    main()
    assert called == {"yes": True}
