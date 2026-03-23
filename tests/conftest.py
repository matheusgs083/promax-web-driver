from __future__ import annotations

from pathlib import Path

import pytest
from selenium.webdriver.ie.options import Options as IEOptions

from core import movimentador


@pytest.fixture
def ie_mode_options() -> IEOptions:
    """
    Simula a configuracao recomendada para Edge em IE Mode.
    O teste nao abre navegador real; apenas documenta e valida o contrato esperado.
    """
    options = IEOptions()
    options.add_additional_option("ie.edgechromium", True)
    options.add_additional_option("ie.edgepath", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    options.attach_to_edge_chrome = False
    options.force_create_process_api = True
    options.ensure_clean_session = False
    options.ignore_protected_mode_settings = True
    options.ignore_zoom_level = True
    options.require_window_focus = True
    options.page_load_strategy = "none"
    return options


@pytest.fixture
def isolated_publication_paths(tmp_path, monkeypatch):
    base = tmp_path / "logs"
    pending = base / "publicacao_pendente"
    event = base / "publicacao_eventos.jsonl"

    monkeypatch.setattr(movimentador, "BASE_LOG_DIR", base)
    monkeypatch.setattr(movimentador, "PENDING_DIR", pending)
    monkeypatch.setattr(movimentador, "EVENT_LOG_FILE", event)
    return {
        "base": base,
        "pending": pending,
        "event": event,
    }
