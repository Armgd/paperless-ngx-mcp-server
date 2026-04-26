"""build_document_filters helper."""
from __future__ import annotations

from paperless_mcp.tools._filters import FilterRequest, build_document_filters

from .conftest import FakeClient


async def test_resolves_correspondent_and_doc_type(fake_client: FakeClient) -> None:
    fake_client.set_get(
        "/api/correspondents/", {"results": [{"id": 7, "name": "Acme"}]}
    )
    fake_client.set_get(
        "/api/document_types/", {"results": [{"id": 3, "name": "Invoice"}]}
    )
    req = FilterRequest(correspondent_name="Acme", document_type_name="Invoice")
    params, unresolved = await build_document_filters(req)
    assert params["correspondent__id"] == 7
    assert params["document_type__id"] == 3
    assert unresolved == []


async def test_collects_unresolved(fake_client: FakeClient) -> None:
    fake_client.set_get("/api/correspondents/", {"results": []})
    req = FilterRequest(correspondent_name="Ghost")
    params, unresolved = await build_document_filters(req)
    assert "correspondent:Ghost" in unresolved
    assert "correspondent__id" not in params


async def test_resolves_tag_lists(fake_client: FakeClient) -> None:
    fake_client.set_get("/api/tags/", {"results": [{"id": 11, "name": "tax"}]})
    req = FilterRequest(tag_names_all=["tax"])
    params, _ = await build_document_filters(req)
    assert params["tags__id__all"] == "11"


async def test_passes_through_simple_filters(fake_client: FakeClient) -> None:
    req = FilterRequest(
        title_contains="invoice",
        text_contains="rent",
        year=2026,
        month=4,
        created_after="2026-01-01",
        created_before="2026-12-31",
    )
    params, _ = await build_document_filters(req)
    assert params["title__icontains"] == "invoice"
    assert params["content__icontains"] == "rent"
    assert params["created__year"] == 2026
    assert params["created__month"] == 4
    assert params["created__date__gte"] == "2026-01-01"
    assert params["created__date__lte"] == "2026-12-31"
