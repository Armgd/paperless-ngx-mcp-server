"""Pure helpers."""
from __future__ import annotations

from paperless_mcp.tools._helpers import resolve_name_to_id, slim_document

from .conftest import FakeClient


def test_slim_document_keeps_known_fields() -> None:
    doc = {
        "id": 1,
        "title": "T",
        "content": "drop",
        "permissions": "drop",
        "tags": [1],
        "owner": "drop",
        "created": "2026-01-01",
    }
    slim = slim_document(doc)
    assert slim == {"id": 1, "title": "T", "tags": [1], "created": "2026-01-01"}


async def test_resolve_name_to_id_hit(fake_client: FakeClient) -> None:
    fake_client.set_get(
        "/api/correspondents/", {"results": [{"id": 9, "name": "Acme"}]}
    )
    rid = await resolve_name_to_id("/api/correspondents/", "Acme")
    assert rid == 9
    _, _, params = fake_client.calls[-1]
    assert params == {"name__iexact": "Acme", "page_size": 1}


async def test_resolve_name_to_id_miss(fake_client: FakeClient) -> None:
    fake_client.set_get("/api/tags/", {"results": []})
    rid = await resolve_name_to_id("/api/tags/", "ghost")
    assert rid is None
