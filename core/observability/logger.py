import logging
import os
import sys
import threading
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

from core.config.project_paths import LOGS_DIR, PROJECT_ROOT


MOJIBAKE_MARKERS = (
    "\u00c3",
    "\u00c2",
    "\u00e2",
    "\u0192",
    "\ufffd",
)


def _looks_like_mojibake(text: str) -> bool:
    return any(marker in text for marker in MOJIBAKE_MARKERS)


def _repair_mojibake_text(text: str, max_passes: int = 3) -> str:
    repaired = text

    for _ in range(max_passes):
        if not _looks_like_mojibake(repaired):
            break

        updated = None
        for encoding in ("cp1252", "latin1"):
            try:
                candidate = repaired.encode(encoding).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue

            if candidate != repaired:
                updated = candidate
                break

        if updated is None:
            break

        repaired = updated

    return repaired


class MojibakeSafeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        return _repair_mojibake_text(rendered)


def _resolve_log_dir() -> Path:
    base_dir = os.getenv("LOG_BASE_DIR")
    log_dir_name = os.getenv("LOG_DIR")

    if not base_dir and not log_dir_name:
        return LOGS_DIR

    base_path = Path(base_dir) if base_dir else PROJECT_ROOT
    return base_path / (log_dir_name or "logs")


def _parse_level(env_name: str, default: str) -> int:
    level_name = os.getenv(env_name, default).upper()
    return getattr(logging, level_name, getattr(logging, default, logging.INFO))


def _configure_stdio_utf8() -> None:
    """Força UTF-8 no console para preservar acentuação pt-BR nos logs."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue

        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _install_excepthooks(logger: logging.Logger) -> None:
    """Garante que exceções não tratadas vão para o log principal e para threads."""

    def handle_exception(exc_type, exc, tb):
        logger.critical("Exceção não tratada", exc_info=(exc_type, exc, tb))

    sys.excepthook = handle_exception

    if hasattr(threading, "excepthook"):
        def thread_hook(args):
            logger.critical(
                "Exceção não tratada em thread '%s'",
                getattr(args.thread, "name", "unknown"),
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )

        threading.excepthook = thread_hook


def get_logger(name: str = "PROMAX") -> logging.Logger:
    logger = logging.getLogger(name)

    if getattr(logger, "_configured", False):
        return logger

    _configure_stdio_utf8()

    file_level = _parse_level("LOG_LEVEL_FILE", os.getenv("LOG_LEVEL", "INFO"))
    console_level = _parse_level("LOG_LEVEL_CONSOLE", os.getenv("LOG_LEVEL", "INFO"))

    logger.setLevel(min(file_level, console_level))

    log_dir = _resolve_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / os.getenv("LOG_FILE", "app.log")

    fmt = MojibakeSafeFormatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | pid=%(process)d | %(filename)s:%(lineno)d | %(funcName)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = TimedRotatingFileHandler(
        filename=str(log_file),
        when=os.getenv("LOG_ROTATE_WHEN", "midnight"),
        interval=int(os.getenv("LOG_ROTATE_INTERVAL", 1)),
        backupCount=int(os.getenv("LOG_BACKUP_COUNT", 14)),
        encoding="utf-8",
        utc=False,
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(fmt)
    file_handler.setLevel(file_level)

    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setFormatter(fmt)
    console_handler.setLevel(console_level)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    if os.getenv("SILENCE_SELENIUM_LOGS", "1") == "1":
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
        logging.getLogger("selenium.webdriver.remote.remote_connection").setLevel(logging.WARNING)

    logger.propagate = False
    logger._configured = True

    _install_excepthooks(logger)

    logger.info(
        "Logger iniciado | arquivo=%s | level_file=%s | level_console=%s",
        str(log_file),
        logging.getLevelName(file_level),
        logging.getLevelName(console_level),
    )
    return logger

