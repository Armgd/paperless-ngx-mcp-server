"""Authentication verification."""
from __future__ import annotations

from ..app import READ_ONLY, client, mcp, settings
from ..client import PaperlessAPIError
from ._schemas import AuthResult


@mcp.tool(annotations=READ_ONLY)
async def paperless_verify_auth() -> AuthResult:
    """Verify Paperless credentials by fetching the current user profile.

    Returns authenticated user info on success or a structured error with the
    HTTP status on failure. Upstream response bodies are not echoed to the
    client; check server logs for full error details.
    """
    try:
        profile = await client.get("/api/profile/")
    except PaperlessAPIError as e:
        return AuthResult(
            authenticated=False,
            base_url=settings.base_url,
            status=e.status,
        )
    return AuthResult(
        authenticated=True,
        base_url=settings.base_url,
        user={
            "id": profile.get("id"),
            "username": profile.get("username"),
            "email": profile.get("email"),
            "first_name": profile.get("first_name"),
            "last_name": profile.get("last_name"),
            "is_superuser": profile.get("is_superuser"),
        },
    )
