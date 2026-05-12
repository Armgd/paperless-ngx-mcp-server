"""TypedDict output shapes for tool returns. Drive FastMCP outputSchema."""
from __future__ import annotations

from typing import Any, TypedDict


class PageInfo(TypedDict):
    returned: int
    total: int | None
    has_more: bool
    capped_by_max_results: bool


def make_page_info(
    returned: int, total: int | None, has_more: bool, max_results: int
) -> PageInfo:
    return PageInfo(
        returned=returned,
        total=total,
        has_more=has_more,
        capped_by_max_results=has_more and returned >= max_results,
    )


class DocumentSummary(TypedDict, total=False):
    id: int
    title: str
    correspondent: int | None
    document_type: int | None
    storage_path: int | None
    tags: list[int]
    created: str | None
    created_date: str | None
    modified: str | None
    added: str | None
    archive_serial_number: int | None
    original_file_name: str | None
    archived_file_name: str | None
    mime_type: str | None
    is_shared_by_requester: bool
    custom_fields: list[dict[str, Any]]
    page_count: int | None
    notes: list[dict[str, Any]]


class DocumentListResponse(TypedDict, total=False):
    documents: list[DocumentSummary]
    page_info: PageInfo
    unresolved: list[str]
    filters_applied: dict[str, Any]


class DocumentContent(TypedDict):
    id: int | None
    title: str | None
    created: str | None
    correspondent: int | None
    document_type: int | None
    tags: list[int] | None
    content: str
    content_truncated: bool
    content_total_chars: int


class BinaryInline(TypedDict, total=False):
    encoding: str
    mime: str
    bytes: int
    data: str


class BinarySaved(TypedDict):
    saved_to: str
    bytes: int


class TaxonomyItem(TypedDict, total=False):
    id: int
    name: str
    slug: str
    match: str
    matching_algorithm: int
    is_insensitive: bool
    document_count: int
    color: str
    is_inbox_tag: bool
    owner: int | None
    path: str
    data_type: str


class TaxonomyListResponse(TypedDict):
    items: list[TaxonomyItem]
    page_info: PageInfo


class TaskItem(TypedDict, total=False):
    id: int
    task_id: str
    task_file_name: str
    date_created: str
    date_done: str | None
    type: str
    status: str
    result: str | None
    acknowledged: bool


class TaskListResponse(TypedDict):
    tasks: list[TaskItem]
    page_info: PageInfo


class SearchHit(TypedDict, total=False):
    id: int
    score: float
    highlights: str
    note_highlights: str
    rank: int


class SearchResponse(TypedDict):
    query: str
    count: int | None
    results: list[SearchHit]


class AnswerSource(TypedDict, total=False):
    id: int | None
    title: str | None
    created: str | None
    correspondent: int | None
    document_type: int | None
    tags: list[int] | None
    score: float | None
    highlights: str | None
    excerpt: str
    excerpt_truncated: bool
    fetch_error_status: int


class AnswerResponse(TypedDict):
    query: str
    total_hits: int | None
    returned: int
    sources: list[AnswerSource]


class AuthResult(TypedDict, total=False):
    authenticated: bool
    base_url: str
    status: int
    user: dict[str, Any]


class NextAsnResponse(TypedDict):
    next_asn: int


class MetadataResponse(TypedDict, total=False):
    original_checksum: str
    original_size: int
    original_mime_type: str
    original_filename: str
    archive_checksum: str
    archive_size: int
    archive_filename: str
    media_filename: str
    has_archive_version: bool
    lang: str
    page_count: int
    original_metadata: list[dict[str, Any]]
    archive_metadata: list[dict[str, Any]]
