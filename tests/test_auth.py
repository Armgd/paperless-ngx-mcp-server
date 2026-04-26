"""verify_auth tool."""
from __future__ import annotations

from fastmcp import Client

from .conftest import FakeClient


async def test_verify_auth_success(mcp_client: Client, fake_client: FakeClient) -> None:
    fake_client.set_get(
        "/api/profile/",
        {
            "id": 1,
            "username": "alice",
            "email": "a@x.com",
            "first_name": "Alice",
            "last_name": "X",
            "is_superuser": False,
        },
    )
    result = await mcp_client.call_tool("verify_auth", {})
    assert result.data["authenticated"] is True
    assert result.data["user"]["username"] == "alice"
    assert result.data["base_url"] == "http://test.invalid"


async def test_verify_auth_failure(mcp_client: Client, fake_client: FakeClient) -> None:
    fake_client.set_get_error("/api/profile/", 401, "unauthorized")
    result = await mcp_client.call_tool("verify_auth", {})
    assert result.data["authenticated"] is False
    assert result.data["status"] == 401
