"""Shared utilities for tool modules: name resolution, formatting."""
from __future__ import annotations

from typing import Any

from ..app import client


async def resolve_name_to_id(path: str, name: str) -> int | None:
    """Look up a taxonomy item by exact (case-insensitive) name. Returns id or None."""
    data = await client.get(path, params={"name__iexact": name, "page_size": 1})
    results = data.get("results") if isinstance(data, dict) else None
    if results:
        return int(results[0]["id"])
    return None


async def resolve_names_to_ids(path: str, names: list[str]) -> list[int]:
    out: list[int] = []
    for n in names:
        rid = await resolve_name_to_id(path, n)
        if rid is not None:
            out.append(rid)
    return out


def slim_document(doc: dict[str, Any]) -> dict[str, Any]:
    """Trim verbose document payload for list responses (drop content + permissions)."""
    keep = {
        "id",
        "title",
        "correspondent",
        "document_type",
        "storage_path",
        "tags",
        "created",
        "created_date",
        "modified",
        "added",
        "archive_serial_number",
        "original_file_name",
        "archived_file_name",
        "mime_type",
        "is_shared_by_requester",
        "custom_fields",
        "page_count",
        "notes",
    }
    return {k: v for k, v in doc.items() if k in keep}


def slim_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    """Trim verbose document metadata. Drops original_metadata / archive_metadata arrays."""
    keep = {
        "original_checksum",
        "original_size",
        "original_mime_type",
        "original_filename",
        "archive_checksum",
        "archive_size",
        "archive_filename",
        "media_filename",
        "has_archive_version",
        "lang",
        "page_count",
    }
    return {k: v for k, v in meta.items() if k in keep}
