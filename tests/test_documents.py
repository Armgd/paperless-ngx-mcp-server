"""Document tools."""
from __future__ import annotations

import base64
import json

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from .conftest import FakeClient


def _doc(doc_id: int, **overrides: object) -> dict:
    base = {
        "id": doc_id,
        "title": f"Doc {doc_id}",
        "content": "OCR text body.",
        "created": "2026-01-01T00:00:00Z",
        "tags": [1, 2],
        "correspondent": 7,
        "document_type": 3,
        "permissions": {"view": [], "change": []},
    }
    base.update(overrides)
    return base


async def test_list_documents_slims_payload(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_paginate(
        "/api/documents/", [_doc(1), _doc(2, title="Other")]
    )
    result = await mcp_client.call_tool("list_documents", {"max_results": 50})
    assert result.data["count"] == 2
    docs = result.data["documents"]
    assert {d["id"] for d in docs} == {1, 2}
    # slimmed: no content, no permissions
    for d in docs:
        assert "content" not in d
        assert "permissions" not in d


async def test_list_documents_passes_filters(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_paginate("/api/documents/", [])
    await mcp_client.call_tool(
        "list_documents",
        {
            "correspondent_id": 5,
            "tag_ids_all": [1, 2],
            "title_contains": "invoice",
            "created_year": 2026,
        },
    )
    method, path, params = fake_client.calls[-1]
    assert method == "PAGINATE"
    assert path == "/api/documents/"
    assert params is not None
    assert params["correspondent__id"] == 5
    assert params["tags__id__all"] == "1,2"
    assert params["title__icontains"] == "invoice"
    assert params["created__year"] == 2026


async def test_get_document_strips_content(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_get("/api/documents/42/", _doc(42, content="huge ocr"))
    result = await mcp_client.call_tool("get_document", {"document_id": 42})
    assert result.data["id"] == 42
    assert "content" not in result.data


async def test_get_document_content_truncates(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    big = "x" * 1000
    fake_client.set_get("/api/documents/9/", _doc(9, content=big))
    result = await mcp_client.call_tool(
        "get_document_content", {"document_id": 9, "max_chars": 100}
    )
    assert result.data["content_truncated"] is True
    assert result.data["content_total_chars"] == 1000
    assert len(result.data["content"]) == 100


async def test_get_document_content_no_truncation(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_get("/api/documents/3/", _doc(3, content="short"))
    result = await mcp_client.call_tool(
        "get_document_content", {"document_id": 3, "max_chars": 1000}
    )
    assert result.data["content_truncated"] is False
    assert result.data["content"] == "short"


async def test_download_document_inline_b64(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    blob = b"PDFDATA"
    fake_client.set_binary("/api/documents/1/download/", blob)
    result = await mcp_client.call_tool("download_document", {"document_id": 1})
    assert result.data["bytes"] == len(blob)
    assert base64.b64decode(result.data["data"]) == blob


async def test_download_document_too_large(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_binary("/api/documents/1/download/", b"x" * 5000)
    with pytest.raises(ToolError) as excinfo:
        await mcp_client.call_tool(
            "download_document", {"document_id": 1, "max_inline_bytes": 1024}
        )
    msg = str(excinfo.value)
    assert "5000" in msg
    assert "save_to_path" in msg


async def test_download_document_save_to_path(
    mcp_client: Client, fake_client: FakeClient, tmp_path, monkeypatch
) -> None:
    from dataclasses import replace

    from paperless_mcp import app as app_module
    from paperless_mcp.tools import documents as docs_mod

    new_settings = replace(app_module.settings, download_dir=tmp_path)
    monkeypatch.setattr(app_module, "settings", new_settings)
    monkeypatch.setattr(docs_mod, "settings", new_settings)

    blob = b"abc"
    fake_client.set_binary("/api/documents/1/download/", blob)
    target = tmp_path / "out.pdf"
    result = await mcp_client.call_tool(
        "download_document",
        {"document_id": 1, "save_to_path": str(target)},
    )
    assert result.data["saved_to"] == str(target)
    assert target.read_bytes() == blob


async def test_download_document_rejects_traversal(
    mcp_client: Client, fake_client: FakeClient, tmp_path, monkeypatch
) -> None:
    from dataclasses import replace

    from paperless_mcp import app as app_module
    from paperless_mcp.tools import documents as docs_mod

    new_settings = replace(app_module.settings, download_dir=tmp_path)
    monkeypatch.setattr(app_module, "settings", new_settings)
    monkeypatch.setattr(docs_mod, "settings", new_settings)

    fake_client.set_binary("/api/documents/1/download/", b"x")
    with pytest.raises(ToolError) as excinfo:
        await mcp_client.call_tool(
            "download_document",
            {"document_id": 1, "save_to_path": "../escape.pdf"},
        )
    assert "outside" in str(excinfo.value).lower()


async def test_download_document_save_disabled_without_root(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_binary("/api/documents/1/download/", b"x")
    with pytest.raises(ToolError) as excinfo:
        await mcp_client.call_tool(
            "download_document",
            {"document_id": 1, "save_to_path": "/tmp/x.pdf"},
        )
    assert "PAPERLESS_DOWNLOAD_DIR" in str(excinfo.value)


async def test_get_next_asn(mcp_client: Client, fake_client: FakeClient) -> None:
    fake_client.set_get("/api/documents/next_asn/", 42)
    result = await mcp_client.call_tool("get_next_asn", {})
    assert result.data["next_asn"] == 42


@pytest.mark.parametrize(
    "tool,path,payload",
    [
        ("get_document_metadata", "/api/documents/1/metadata/", {"mime_type": "application/pdf"}),
        ("get_document_notes", "/api/documents/1/notes/", [{"id": 1, "note": "hi"}]),
        ("get_document_suggestions", "/api/documents/1/suggestions/", {"correspondents": [1]}),
        ("get_document_history", "/api/documents/1/history/", [{"action": "create"}]),
    ],
)
async def test_passthrough_endpoints(
    mcp_client: Client,
    fake_client: FakeClient,
    tool: str,
    path: str,
    payload: object,
) -> None:
    fake_client.set_get(path, payload)
    result = await mcp_client.call_tool(tool, {"document_id": 1})
    # `get_document_history` returns Any (no schema) — data=None, fall back to text.
    actual = result.data if result.data is not None else json.loads(result.content[0].text)
    assert actual == payload


async def test_thumbnail_uses_response_mime(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_binary_with_headers(
        "/api/documents/1/thumb/", b"PNGDATA", {"content-type": "image/png"}
    )
    result = await mcp_client.call_tool("get_document_thumbnail", {"document_id": 1})
    assert result.data["mime"] == "image/png"
