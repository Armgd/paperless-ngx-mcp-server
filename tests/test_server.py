"""Smoke tests: server boots, tools register."""
from __future__ import annotations

import pytest
from fastmcp import Client

from paperless_mcp.server import main


async def test_list_tools_includes_core(mcp_client: Client) -> None:
    tools = await mcp_client.list_tools()
    names = {t.name for t in tools}
    expected = {
        "paperless_verify_auth",
        "paperless_list_documents",
        "paperless_get_document",
        "paperless_get_document_content",
        "paperless_search_documents",
        "paperless_search_autocomplete",
        "paperless_list_tags",
        "paperless_list_correspondents",
        "paperless_find_documents",
        "paperless_answer_from_documents",
        "paperless_recent_documents",
    }
    missing = expected - names
    assert not missing, f"missing tools: {missing}"


async def test_all_tools_are_prefixed(mcp_client: Client) -> None:
    tools = await mcp_client.list_tools()
    for t in tools:
        assert t.name.startswith("paperless_"), f"{t.name} missing paperless_ prefix"


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


def test_http_transport_binds_localhost_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("MCP_AUTH_TOKEN", "x" * 32)
    monkeypatch.delenv("MCP_HOST", raising=False)
    captured: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> None:
        captured.update(kwargs)

    from paperless_mcp import app as app_module
    monkeypatch.setattr(app_module.mcp, "run", fake_run)
    main()
    assert captured["host"] == "127.0.0.1"


def test_http_transport_attaches_origin_middleware_when_allowlist_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("MCP_AUTH_TOKEN", "x" * 32)
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "http://localhost:5173")
    captured: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> None:
        captured.update(kwargs)

    from paperless_mcp import app as app_module
    monkeypatch.setattr(app_module.mcp, "run", fake_run)
    main()
    middleware = captured["middleware"]
    assert middleware is not None
    assert len(list(middleware)) == 1  # type: ignore[arg-type]
