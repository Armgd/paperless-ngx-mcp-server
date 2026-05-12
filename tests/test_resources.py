"""Tests for paperless:// resource templates."""
from __future__ import annotations

import base64
import json

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


@pytest.mark.asyncio
async def test_resource_document_metadata(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_get(
        "/api/documents/42/",
        {
            "id": 42,
            "title": "Invoice",
            "created": "2026-01-15",
            "content": "long ocr text that should be omitted from metadata",
        },
    )
    result = await mcp_client.read_resource("paperless://documents/42/metadata")
    assert len(result) == 1
    assert result[0].mimeType == "application/json"
    payload = json.loads(result[0].text)
    assert payload["id"] == 42
    assert payload["title"] == "Invoice"
    assert "content" not in payload


@pytest.mark.asyncio
async def test_resource_document_preview(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_binary("/api/documents/42/preview/", b"%PDF-1.4 fake pdf bytes")
    result = await mcp_client.read_resource("paperless://documents/42/preview")
    assert len(result) == 1
    assert result[0].mimeType == "application/pdf"
    assert base64.b64decode(result[0].blob) == b"%PDF-1.4 fake pdf bytes"


@pytest.mark.asyncio
async def test_resource_document_thumbnail(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_binary("/api/documents/42/thumb/", b"\x89PNG\r\n\x1a\nfake")
    result = await mcp_client.read_resource("paperless://documents/42/thumbnail")
    assert len(result) == 1
    assert result[0].mimeType in {"image/png", "image/webp"}
    assert base64.b64decode(result[0].blob) == b"\x89PNG\r\n\x1a\nfake"


@pytest.mark.asyncio
async def test_resource_document_download(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_binary("/api/documents/42/download/", b"original-bytes")
    result = await mcp_client.read_resource("paperless://documents/42/download")
    assert len(result) == 1
    assert result[0].mimeType == "application/octet-stream"
    assert base64.b64decode(result[0].blob) == b"original-bytes"


@pytest.mark.asyncio
async def test_resource_binary_rejects_oversized(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_binary("/api/documents/42/preview/", b"x" * 20_000_001)
    with pytest.raises(Exception) as excinfo:
        await mcp_client.read_resource("paperless://documents/42/preview")
    assert "too large" in str(excinfo.value).lower()
