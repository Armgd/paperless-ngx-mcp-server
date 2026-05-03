"""interactive_search tool — mocks Context.elicit to drive each branch."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastmcp import Client

from .conftest import FakeClient


@dataclass
class _ElicitResult:
    action: str
    data: Any = None


class _ScriptedContext:
    """Replay scripted elicit responses; matches FastMCP Context.elicit shape."""

    def __init__(self, script: list[_ElicitResult]) -> None:
        self._script = list(script)
        self.prompts: list[str] = []

    async def elicit(self, prompt: str, response_type: Any = None, **_: Any) -> _ElicitResult:
        self.prompts.append(prompt)
        return self._script.pop(0)


@pytest.fixture
async def patch_elicit(monkeypatch: pytest.MonkeyPatch):
    """Replace registered interactive_search's fn to bypass FastMCP context injection."""
    from paperless_mcp.app import mcp

    tool = await mcp.get_tool("interactive_search")
    original = tool.fn

    def install(script: list[_ElicitResult]) -> _ScriptedContext:
        ctx = _ScriptedContext(script)

        async def wrapper(_injected_ctx: Any = None, **kwargs: Any) -> Any:
            return await original(ctx, **kwargs)

        monkeypatch.setattr(tool, "fn", wrapper)
        return ctx

    return install


async def test_full_text_branch(
    mcp_client: Client, fake_client: FakeClient, patch_elicit: Any
) -> None:
    patch_elicit(
        [
            _ElicitResult("accept", "full_text"),
            _ElicitResult("accept", "rent"),
        ]
    )
    fake_client.set_get(
        "/api/search/", {"count": 1, "results": [{"id": 1, "score": 0.9}]}
    )
    result = await mcp_client.call_tool("interactive_search", {})
    assert result.data["strategy"] == "full_text"
    assert result.data["query"] == "rent"
    assert result.data["count"] == 1


async def test_recent_branch(
    mcp_client: Client, fake_client: FakeClient, patch_elicit: Any
) -> None:
    patch_elicit(
        [
            _ElicitResult("accept", "recent"),
            _ElicitResult("accept", 14),
        ]
    )
    fake_client.set_paginate("/api/documents/", [{"id": 9, "title": "x"}])
    result = await mcp_client.call_tool("interactive_search", {})
    assert result.data["strategy"] == "recent"
    assert result.data["count"] == 1


async def test_filters_branch(
    mcp_client: Client, fake_client: FakeClient, patch_elicit: Any
) -> None:
    from paperless_mcp.tools.highlevel import _FilterForm

    patch_elicit(
        [
            _ElicitResult("accept", "filters"),
            _ElicitResult(
                "accept",
                _FilterForm(correspondent_name="Acme", title_contains="bill"),
            ),
        ]
    )
    fake_client.set_get(
        "/api/correspondents/", {"results": [{"id": 7, "name": "Acme"}]}
    )
    fake_client.set_paginate("/api/documents/", [])
    result = await mcp_client.call_tool("interactive_search", {})
    assert result.data["strategy"] == "filters"
    assert result.data["filters_applied"]["correspondent__id"] == 7
    assert result.data["filters_applied"]["title__icontains"] == "bill"


async def test_user_declines_strategy(
    mcp_client: Client, fake_client: FakeClient, patch_elicit: Any
) -> None:
    patch_elicit([_ElicitResult("decline")])
    result = await mcp_client.call_tool("interactive_search", {})
    assert result.data["status"] == "decline"
    assert result.data["step"] == "strategy"


async def test_elicit_unsupported_raises_tool_error(
    mcp_client: Client, fake_client: FakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastmcp.exceptions import ToolError
    from mcp import McpError
    from mcp.types import ErrorData

    from paperless_mcp.app import mcp

    tool = await mcp.get_tool("interactive_search")
    original = tool.fn

    class _NoElicitContext:
        async def elicit(self, *_: object, **__: object) -> object:
            raise McpError(
                ErrorData(code=-32601, message="elicitation not supported")
            )

    async def wrapper(_injected_ctx: object = None, **kwargs: object) -> object:
        return await original(_NoElicitContext(), **kwargs)

    monkeypatch.setattr(tool, "fn", wrapper)

    with pytest.raises(ToolError) as excinfo:
        await mcp_client.call_tool("interactive_search", {})
    msg = str(excinfo.value)
    assert "elicit" in msg.lower()
    assert "find_documents" in msg
    assert "answer_from_documents" in msg
    assert "recent_documents" in msg
