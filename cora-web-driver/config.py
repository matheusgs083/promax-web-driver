from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


DEFAULT_CORA_URL = "https://cora.ab-inbev.com/?redirectTo=%2F"


@dataclass(frozen=True)
class CoraSettings:
    url: str = DEFAULT_CORA_URL
    headless: bool = False
    timeout_seconds: float = 30.0
    username: str = ""
    password: str = ""
    download_dir: Path = Path("downloads") / "cora"

    @property
    def base_url(self) -> str:
        parts = urlsplit(self.url)
        return urlunsplit((parts.scheme, parts.netloc, "", "", "")).rstrip("/")

    @classmethod
    def from_env(cls) -> "CoraSettings":
        raw_headless = os.environ.get("CORA_HEADLESS", "0").strip().lower()
        if raw_headless not in {"0", "1", "true", "false", "yes", "no"}:
            raise ValueError("CORA_HEADLESS deve ser 0/1 ou true/false.")
        raw_timeout = os.environ.get("CORA_TIMEOUT_SECONDS", "30").strip()
        try:
            timeout = float(raw_timeout)
        except ValueError as exc:
            raise ValueError("CORA_TIMEOUT_SECONDS deve ser numérico.") from exc
        if timeout <= 0:
            raise ValueError("CORA_TIMEOUT_SECONDS deve ser positivo.")
        raw_download_dir = os.environ.get("CORA_DOWNLOAD_DIR", "").strip()
        download_dir = Path(raw_download_dir).expanduser() if raw_download_dir else (
            Path(__file__).resolve().parents[1] / "downloads" / "cora"
        )
        if not download_dir.is_absolute():
            download_dir = Path(__file__).resolve().parents[1] / download_dir
        return cls(
            url=os.environ.get("CORA_URL", DEFAULT_CORA_URL).strip() or DEFAULT_CORA_URL,
            headless=raw_headless in {"1", "true", "yes"},
            timeout_seconds=timeout,
            username=os.environ.get("CORA_USER", "").strip(),
            password=os.environ.get("CORA_PASS", ""),
            download_dir=download_dir,
        )
