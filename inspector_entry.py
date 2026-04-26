"""Entry point for `mcp dev` (absolute imports, since dev loads as script)."""
from paperless_mcp.server import mcp

__all__ = ["mcp"]
