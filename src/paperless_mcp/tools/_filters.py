"""Shared document filter assembly. Resolves names → ids in parallel."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from ._helpers import resolve_name_to_id, resolve_names_to_ids


@dataclass(frozen=True)
class FilterRequest:
    correspondent_name: str | None = None
    document_type_name: str | None = None
    storage_path_name: str | None = None
    tag_names_all: list[str] = field(default_factory=list)
    tag_names_any: list[str] = field(default_factory=list)
    title_contains: str | None = None
    text_contains: str | None = None
    year: int | None = None
    month: int | None = None
    created_after: str | None = None
    created_before: str | None = None


async def build_document_filters(
    req: FilterRequest,
) -> tuple[dict[str, Any], list[str]]:
    """Resolve names to IDs concurrently and assemble DRF query params."""
    params: dict[str, Any] = {}
    unresolved: list[str] = []

    async def _resolve_one(path: str, name: str | None) -> int | None:
        if not name:
            return None
        return await resolve_name_to_id(path, name)

    async def _empty() -> list[int]:
        return []

    corr, dtype, spath, tags_all, tags_any = await asyncio.gather(
        _resolve_one("/api/correspondents/", req.correspondent_name),
        _resolve_one("/api/document_types/", req.document_type_name),
        _resolve_one("/api/storage_paths/", req.storage_path_name),
        resolve_names_to_ids("/api/tags/", req.tag_names_all)
        if req.tag_names_all
        else _empty(),
        resolve_names_to_ids("/api/tags/", req.tag_names_any)
        if req.tag_names_any
        else _empty(),
    )

    if req.correspondent_name:
        if corr is None:
            unresolved.append(f"correspondent:{req.correspondent_name}")
        else:
            params["correspondent__id"] = corr
    if req.document_type_name:
        if dtype is None:
            unresolved.append(f"document_type:{req.document_type_name}")
        else:
            params["document_type__id"] = dtype
    if req.storage_path_name:
        if spath is None:
            unresolved.append(f"storage_path:{req.storage_path_name}")
        else:
            params["storage_path__id"] = spath
    if req.tag_names_all:
        if len(tags_all) != len(req.tag_names_all):
            unresolved.append(f"some tags missing in: {req.tag_names_all}")
        if tags_all:
            params["tags__id__all"] = ",".join(str(i) for i in tags_all)
    if req.tag_names_any and tags_any:
        params["tags__id__in"] = ",".join(str(i) for i in tags_any)
    if req.title_contains:
        params["title__icontains"] = req.title_contains
    if req.text_contains:
        params["content__icontains"] = req.text_contains
    if req.year is not None:
        params["created__year"] = req.year
    if req.month is not None:
        params["created__month"] = req.month
    if req.created_after:
        params["created__date__gte"] = req.created_after
    if req.created_before:
        params["created__date__lte"] = req.created_before
    return params, unresolved
