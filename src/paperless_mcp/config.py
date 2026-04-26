"""Runtime configuration loaded from env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from ._envutil import env_bool

load_dotenv()


@dataclass(frozen=True)
class Settings:
    base_url: str
    token: str
    timeout: float
    verify_ssl: bool
    download_dir: Path | None

    @classmethod
    def from_env(cls) -> "Settings":
        url = os.environ.get("PAPERLESS_URL")
        token = os.environ.get("PAPERLESS_TOKEN")
        if not url:
            raise RuntimeError("PAPERLESS_URL not set")
        if not token:
            raise RuntimeError("PAPERLESS_TOKEN not set")
        raw_dir = os.environ.get("PAPERLESS_DOWNLOAD_DIR")
        download_dir = Path(raw_dir).expanduser().resolve() if raw_dir else None
        return cls(
            base_url=url.rstrip("/"),
            token=token,
            timeout=float(os.environ.get("PAPERLESS_TIMEOUT", "30")),
            verify_ssl=env_bool(os.environ.get("PAPERLESS_VERIFY_SSL"), default=True),
            download_dir=download_dir,
        )
