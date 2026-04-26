"""Constrain user-supplied save paths to a configured download directory."""
from __future__ import annotations

from pathlib import Path


class UnsafePathError(ValueError):
    """Raised when a save path escapes the allowed root."""


def sanitize_save_path(raw: str, *, root: Path | None) -> Path:
    """Resolve `raw` against `root` and ensure result stays inside `root`.

    Without `root`, all writes are refused. Relative paths are joined to root.
    Absolute paths must already be inside root after resolution.
    """
    if root is None:
        raise UnsafePathError(
            "save_to_path is disabled: set PAPERLESS_DOWNLOAD_DIR to enable disk writes"
        )
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise UnsafePathError(
            f"save_to_path {raw!r} resolves outside PAPERLESS_DOWNLOAD_DIR ({root_resolved})"
        ) from exc
    return resolved
