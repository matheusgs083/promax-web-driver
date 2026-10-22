from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta
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
    holidays: frozenset[date] = frozenset()

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
        holidays = _configured_holidays(os.environ.get("CORA_HOLIDAYS", ""))
        return cls(
            url=os.environ.get("CORA_URL", DEFAULT_CORA_URL).strip() or DEFAULT_CORA_URL,
            headless=raw_headless in {"1", "true", "yes"},
            timeout_seconds=timeout,
            username=os.environ.get("CORA_USER", "").strip(),
            password=os.environ.get("CORA_PASS", ""),
            download_dir=download_dir,
            holidays=holidays,
        )


def _configured_holidays(raw_value: str) -> frozenset[date]:
    """Return national Brazilian holidays plus optional local dates.

    Local/municipal holidays can be added through CORA_HOLIDAYS as a
    comma-separated ISO list (YYYY-MM-DD). Invalid entries fail fast so a
    schedule cannot silently query the wrong delivery day.
    """
    current_year = date.today().year
    dates = set().union(*(_national_holidays(year) for year in (current_year - 1, current_year, current_year + 1)))
    for raw in str(raw_value or "").split(","):
        value = raw.strip()
        if not value:
            continue
        try:
            dates.add(date.fromisoformat(value))
        except ValueError as exc:
            raise ValueError(f"CORA_HOLIDAYS contém data inválida: {value}") from exc
    return frozenset(dates)


def _national_holidays(year: int) -> set[date]:
    dates = {
        date(year, month, day)
        for month, day in (
            (1, 1), (4, 21), (5, 1), (9, 7), (10, 12),
            (11, 2), (11, 15), (12, 25),
        )
    }
    easter = _easter_sunday(year)
    dates.update({
        easter,
        easter - timedelta(days=2),
        easter - timedelta(days=47),
        easter + timedelta(days=60),
    })
    return dates


def _easter_sunday(year: int) -> date:
    """Gregorian Easter calculation (Anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f, g = divmod(b + 8, 25)
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)
