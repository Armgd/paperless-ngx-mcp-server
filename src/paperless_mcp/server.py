"""FastMCP server entrypoint."""
from __future__ import annotations

from .app import mcp


def main() -> None:
    # Register tools by importing modules.
    from .tools import (  # noqa: F401
        auth,
        documents,
        highlevel,
        search,
        stats,
        tasks,
        taxonomy,
    )

    mcp.run()


if __name__ == "__main__":
    main()
