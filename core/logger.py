import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os
import sys

def _project_root() -> Path:

    return Path(__file__).resolve().parents[1]

def get_logger(name: str = "PROMAX") -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    # nível configurável (INFO default)
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)

    # Pasta de logs SEM depender do cwd
    base_dir = Path(os.getenv("LOG_BASE_DIR", str(_project_root())))
    log_dir = base_dir / os.getenv("LOG_DIR", "logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Arquivo único
    log_file = log_dir / os.getenv("LOG_FILE", "app.log")

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=int(os.getenv("LOG_MAX_BYTES", 5 * 1024 * 1024)),  # 5MB default
        backupCount=int(os.getenv("LOG_BACKUP_COUNT", 5)),
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level)

    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setFormatter(fmt)
    console_handler.setLevel(level)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    if os.getenv("SILENCE_SELENIUM_LOGS", "1") == "1":
        logging.getLogger("selenium").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger.propagate = False
    logger.info("Logger iniciado | arquivo=%s | level=%s", str(log_file), level_name)

    return logger
