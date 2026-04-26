"""Path sandbox helper."""
from __future__ import annotations

from pathlib import Path

import pytest

from paperless_mcp.tools._safe_path import UnsafePathError, sanitize_save_path


def test_resolves_inside_root(tmp_path: Path) -> None:
    target = sanitize_save_path("file.pdf", root=tmp_path)
    assert target == tmp_path / "file.pdf"


def test_creates_subdir_under_root(tmp_path: Path) -> None:
    target = sanitize_save_path("sub/file.pdf", root=tmp_path)
    assert target == tmp_path / "sub" / "file.pdf"


def test_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(UnsafePathError):
        sanitize_save_path("../escape.pdf", root=tmp_path)


def test_rejects_absolute_outside_root(tmp_path: Path) -> None:
    with pytest.raises(UnsafePathError):
        sanitize_save_path("/etc/passwd", root=tmp_path)


def test_accepts_absolute_inside_root(tmp_path: Path) -> None:
    inside = tmp_path / "ok.pdf"
    target = sanitize_save_path(str(inside), root=tmp_path)
    assert target == inside


def test_requires_root_when_no_default() -> None:
    with pytest.raises(UnsafePathError):
        sanitize_save_path("/tmp/x.pdf", root=None)
