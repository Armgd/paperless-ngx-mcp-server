"""Shared FastMCP instance and Paperless client. Imported by all tool modules."""
from __future__ import annotations

from fastmcp import FastMCP

from .client import PaperlessClient
from .config import Settings

settings = Settings.from_env()
client = PaperlessClient(settings)
mcp: FastMCP = FastMCP(name="paperless-ngx")
