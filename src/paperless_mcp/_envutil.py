"""Internal env parsing utilities."""
from __future__ import annotations

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}


def env_bool(raw: str | None, *, default: bool) -> bool:
    """Parse env string to bool. Falls back to default if unset or unrecognized."""
    if raw is None:
        return default
    norm = raw.strip().lower()
    if norm in _TRUTHY:
        return True
    if norm in _FALSY:
        return False
    return default
