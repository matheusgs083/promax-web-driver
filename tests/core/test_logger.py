from __future__ import annotations

import logging
from pathlib import Path

from core.config.project_paths import LOGS_DIR, PROJECT_ROOT
from core.observability import logger as logger_module


def test_resolve_log_dir_usa_logs_da_raiz_por_padrao(monkeypatch):
    monkeypatch.delenv("LOG_BASE_DIR", raising=False)
    monkeypatch.delenv("LOG_DIR", raising=False)

    assert logger_module._resolve_log_dir() == LOGS_DIR


def test_resolve_log_dir_respeita_overrides_de_ambiente(monkeypatch):
    monkeypatch.delenv("LOG_BASE_DIR", raising=False)
    monkeypatch.setenv("LOG_DIR", "logs-custom")

    assert logger_module._resolve_log_dir() == PROJECT_ROOT / "logs-custom"

    monkeypatch.setenv("LOG_BASE_DIR", str(Path(r"C:\temp\promax")))
    monkeypatch.setenv("LOG_DIR", "logs-alt")

    assert logger_module._resolve_log_dir() == Path(r"C:\temp\promax") / "logs-alt"


def test_repair_mojibake_text_corrige_texto_simples():
    assert (
        logger_module._repair_mojibake_text("Situa\u00c3\u00a7\u00c3\u00a3o: marcando Todos")
        == "Situação: marcando Todos"
    )


def test_repair_mojibake_text_corrige_texto_duplamente_corrompido():
    assert (
        logger_module._repair_mojibake_text("M\u00c3\u0192\u00c2\u00b3dulos visuais ausentes")
        == "Módulos visuais ausentes"
    )


def test_mojibake_safe_formatter_corrige_mensagem_renderizada():
    formatter = logger_module.MojibakeSafeFormatter("%(message)s")
    record = logging.LogRecord(
        name="TESTE",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Status: %s",
        args=("Situa\u00c3\u00a7\u00c3\u00a3o: marcando Todos",),
        exc_info=None,
    )

    assert formatter.format(record) == "Status: Situação: marcando Todos"
