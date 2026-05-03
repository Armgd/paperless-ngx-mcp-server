"""Tests for container healthcheck script."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from paperless_mcp import healthcheck


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_HOST", raising=False)
    monkeypatch.delenv("MCP_PORT", raising=False)


def _mock_response(status: int) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def test_returns_zero_on_200(clean_env: None) -> None:
    with patch("urllib.request.urlopen", return_value=_mock_response(200)):
        assert healthcheck.main() == 0


def test_returns_one_on_non_200(clean_env: None) -> None:
    with patch("urllib.request.urlopen", return_value=_mock_response(503)):
        assert healthcheck.main() == 1


def test_returns_one_on_connection_error(clean_env: None) -> None:
    with patch("urllib.request.urlopen", side_effect=URLError("refused")):
        assert healthcheck.main() == 1


def test_returns_one_on_timeout(clean_env: None) -> None:
    with patch("urllib.request.urlopen", side_effect=TimeoutError):
        assert healthcheck.main() == 1


def test_uses_env_host_and_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_HOST", "example.local")
    monkeypatch.setenv("MCP_PORT", "9000")
    with patch("urllib.request.urlopen", return_value=_mock_response(200)) as m:
        healthcheck.main()
    assert m.call_args.args[0] == "http://example.local:9000/health"


def test_rewrites_bind_all_to_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_PORT", "8000")
    with patch("urllib.request.urlopen", return_value=_mock_response(200)) as m:
        healthcheck.main()
    assert m.call_args.args[0] == "http://127.0.0.1:8000/health"


def test_defaults_when_env_unset(clean_env: None) -> None:
    with patch("urllib.request.urlopen", return_value=_mock_response(200)) as m:
        healthcheck.main()
    assert m.call_args.args[0] == "http://127.0.0.1:8000/health"
