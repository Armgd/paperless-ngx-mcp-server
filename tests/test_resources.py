"""Tests for paperless:// resource templates."""
from __future__ import annotations

import pytest
from fastmcp import Client

from tests.conftest import FakeClient  # noqa: TC002 (re-exported via fixture)


@pytest.mark.asyncio
async def test_resource_document_content(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_get(
        "/api/documents/42/",
        {"id": 42, "title": "Invoice", "content": "hello world"},
    )
    result = await mcp_client.read_resource("paperless://documents/42/content")
    assert len(result) == 1
    assert result[0].text == "hello world"
    assert result[0].mimeType == "text/plain"
