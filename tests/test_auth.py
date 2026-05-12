"""paperless_verify_auth tool."""
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
    result = await mcp_client.call_tool("paperless_verify_auth", {})
    assert result.structured_content["authenticated"] is True
    assert result.structured_content["user"]["username"] == "alice"
    assert result.structured_content["base_url"] == "http://test.invalid"


async def test_verify_auth_failure_redacts_body(
    mcp_client: Client, fake_client: FakeClient
) -> None:
    fake_client.set_get_error("/api/profile/", 401, "secret upstream body")
    result = await mcp_client.call_tool("paperless_verify_auth", {})
    assert result.structured_content["authenticated"] is False
    assert result.structured_content["status"] == 401
    # Upstream body must not be echoed to the client.
    assert "error" not in result.structured_content
    assert "secret upstream body" not in str(result.structured_content)
