import logging
import os
import sys
import threading
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _parse_level(env_name: str, default: str) -> int:
    level_name = os.getenv(env_name, default).upper()
    return getattr(logging, level_name, getattr(logging, default, logging.INFO))


def _install_excepthooks(logger: logging.Logger) -> None:
    """Garante que exceções não tratadas vão para o log (main + threads)."""

    def handle_exception(exc_type, exc, tb):
        # Evita perder stacktrace quando o processo morre
        logger.critical("Exceção não tratada", exc_info=(exc_type, exc, tb))

    sys.excepthook = handle_exception

    # Python 3.8+ threads
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

    # Evita duplicar handlers e permite diferenciar "já configurei"
    if getattr(logger, "_configured", False):
        return logger

    # Níveis separados (console mais limpo, arquivo mais detalhado)
    file_level = _parse_level("LOG_LEVEL_FILE", os.getenv("LOG_LEVEL", "INFO"))
    console_level = _parse_level("LOG_LEVEL_CONSOLE", os.getenv("LOG_LEVEL", "INFO"))

    # O logger base precisa ser o menor nível entre os handlers
    logger.setLevel(min(file_level, console_level))

    # Pasta de logs SEM depender do cwd
    base_dir = Path(os.getenv("LOG_BASE_DIR", str(_project_root())))
    log_dir = base_dir / os.getenv("LOG_DIR", "logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Arquivo (por dia)
    log_file = log_dir / os.getenv("LOG_FILE", "app.log")

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | pid=%(process)d | %(filename)s:%(lineno)d | %(funcName)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotação diária (mantém X dias)
    file_handler = TimedRotatingFileHandler(
        filename=str(log_file),
        when=os.getenv("LOG_ROTATE_WHEN", "midnight"),  # midnight default
        interval=int(os.getenv("LOG_ROTATE_INTERVAL", 1)),
        backupCount=int(os.getenv("LOG_BACKUP_COUNT", 14)),  # ex: 14 dias
        encoding="utf-8",
        utc=False,
    )
    # suffix ajuda a ficar legível: app.log.2026-02-08
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(fmt)
    file_handler.setLevel(file_level)

    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setFormatter(fmt)
    console_handler.setLevel(console_level)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Silenciar libs (mais específico e sem "matar" tudo do selenium)
    if os.getenv("SILENCE_SELENIUM_LOGS", "1") == "1":
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
        logging.getLogger("selenium.webdriver.remote.remote_connection").setLevel(logging.WARNING)

    logger.propagate = False
    logger._configured = True  # marca como configurado

    # Hooks de exceção não tratada
    _install_excepthooks(logger)

    logger.info(
        "Logger iniciado | arquivo=%s | level_file=%s | level_console=%s",
        str(log_file),
        logging.getLevelName(file_level),
        logging.getLevelName(console_level),
    )
    return logger
