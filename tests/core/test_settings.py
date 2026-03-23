from __future__ import annotations

import pytest

from core.config.settings import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_get_settings_require_window_focus_faz_fallback_para_false(monkeypatch):
    monkeypatch.setenv("PROMAX_REQUIRE_WINDOW_FOCUS", "valor_invalido")

    settings = get_settings()

    assert settings.require_window_focus is False


def test_get_settings_accepta_false_no_env(monkeypatch):
    monkeypatch.setenv("PROMAX_REQUIRE_WINDOW_FOCUS", "false")

    settings = get_settings()

    assert settings.require_window_focus is False
