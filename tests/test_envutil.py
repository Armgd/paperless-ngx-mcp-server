"""env_bool helper."""
from __future__ import annotations

import pytest

from paperless_mcp._envutil import env_bool


@pytest.mark.parametrize(
    "raw,default,expected",
    [
        (None, True, True),
        (None, False, False),
        ("1", False, True),
        ("true", False, True),
        ("TRUE", False, True),
        ("yes", False, True),
        ("on", False, True),
        ("0", True, False),
        ("false", True, False),
        ("no", True, False),
        ("off", True, False),
        ("  true  ", False, True),
        ("garbage", True, True),
        ("garbage", False, False),
    ],
)
def test_env_bool(raw: str | None, default: bool, expected: bool) -> None:
    assert env_bool(raw, default=default) is expected
