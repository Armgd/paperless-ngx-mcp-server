"""Authentication verification."""
from __future__ import annotations

from typing import Any

from ..app import client, mcp, settings
from ..client import PaperlessAPIError


@mcp.tool(annotations={"readOnlyHint": True})
async def verify_auth() -> dict[str, Any]:
    """Verify Paperless credentials by fetching the current user profile.

    Returns authenticated user info on success or a structured error
    with the HTTP status and base URL on failure.
    """
    try:
        profile = await client.get("/api/profile/")
    except PaperlessAPIError as e:
        return {
            "authenticated": False,
            "base_url": settings.base_url,
            "status": e.status,
            "error": str(e),
        }
    return {
        "authenticated": True,
        "base_url": settings.base_url,
        "user": {
            "id": profile.get("id"),
            "username": profile.get("username"),
            "email": profile.get("email"),
            "first_name": profile.get("first_name"),
            "last_name": profile.get("last_name"),
            "is_superuser": profile.get("is_superuser"),
        },
    }
