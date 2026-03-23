from __future__ import annotations

import shutil
from pathlib import Path

from core.files import manipulador_download


def test_acionar_barra_download_prioriza_pywinauto(monkeypatch):
    chamadas = {"pywinauto": 0, "pyautogui": 0}

    def fake_pywinauto(timeout_segundos=manipulador_download.DOWNLOAD_TRIGGER_TIMEOUT_SECONDS):
        chamadas["pywinauto"] += 1
        return True, "ok"

    def fake_pyautogui(timeout_segundos=120):
        chamadas["pyautogui"] += 1
        return True, "fallback"

    monkeypatch.setattr(manipulador_download, "_acionar_barra_download_pywinauto", fake_pywinauto)
    monkeypatch.setattr(manipulador_download, "_acionar_barra_download_pyautogui", fake_pyautogui)

    resultado = manipulador_download._acionar_barra_download()

    assert resultado == (True, "ok")
    assert chamadas == {"pywinauto": 1, "pyautogui": 0}


def test_acionar_barra_download_faz_fallback_para_pyautogui(monkeypatch):
    chamadas = {"pywinauto": 0, "pyautogui": 0}

    def fake_pywinauto(timeout_segundos=manipulador_download.DOWNLOAD_TRIGGER_TIMEOUT_SECONDS):
        chamadas["pywinauto"] += 1
        return False, "nao encontrou controle"

    def fake_pyautogui(timeout_segundos=120):
        chamadas["pyautogui"] += 1
        return True, "fallback"

    monkeypatch.setattr(manipulador_download, "_acionar_barra_download_pywinauto", fake_pywinauto)
    monkeypatch.setattr(manipulador_download, "_acionar_barra_download_pyautogui", fake_pyautogui)

    resultado = manipulador_download._acionar_barra_download()

    assert resultado == (True, "fallback")
    assert chamadas == {"pywinauto": 1, "pyautogui": 1}


def test_fechar_barra_download_pywinauto_limpa_assinatura(monkeypatch):
    clicks = []

    class FakeRect:
        def __init__(self, bottom, left):
            self.bottom = bottom
            self.left = left

    class FakeControl:
        def window_text(self):
            return "Fechar"

        def class_name(self):
            return "Button"

        def is_visible(self):
            return True

        def is_enabled(self):
            return True

        def rectangle(self):
            return FakeRect(140, 10)

        def invoke(self):
            clicks.append("fechou")

    class FakeWindow:
        def window_text(self):
            return "Promax - Download"

        def class_name(self):
            return "IEFrame"

        def descendants(self):
            return [FakeControl()]

    class FakeDesktop:
        def __init__(self, backend):
            self.backend = backend

        def windows(self):
            return [FakeWindow()]

    monkeypatch.setattr(manipulador_download, "Desktop", FakeDesktop)
    monkeypatch.setattr(
        manipulador_download,
        "LAST_DOWNLOAD_CONTROL_SIGNATURE",
        ("promax - download", "ieframe", "salvar", "button", (140, 10)),
    )

    resultado = manipulador_download._fechar_barra_download_pywinauto()

    assert resultado[0] is True
    assert clicks == ["fechou"]
    assert manipulador_download.LAST_DOWNLOAD_CONTROL_SIGNATURE is None


def test_acionar_barra_download_pywinauto_prioriza_ultimo_botao_empilhado(monkeypatch):
    clicks = []

    class FakeRect:
        def __init__(self, bottom, left):
            self.bottom = bottom
            self.left = left

    class FakeControl:
        def __init__(self, text, bottom, left, control_id):
            self._text = text
            self._bottom = bottom
            self._left = left
            self._control_id = control_id

        def window_text(self):
            return self._text

        def class_name(self):
            return "Button"

        def is_visible(self):
            return True

        def is_enabled(self):
            return True

        def rectangle(self):
            return FakeRect(self._bottom, self._left)

        def invoke(self):
            clicks.append(self._control_id)

    class FakeWindow:
        def window_text(self):
            return "Promax - Download"

        def class_name(self):
            return "IEFrame"

        def descendants(self):
            return [
                FakeControl("Salvar", 100, 10, "primeiro"),
                FakeControl("Salvar", 140, 10, "segundo"),
            ]

    class FakeDesktop:
        def __init__(self, backend):
            self.backend = backend

        def windows(self):
            return [FakeWindow()]

    monkeypatch.setattr(manipulador_download, "Desktop", FakeDesktop)
    monkeypatch.setattr(manipulador_download, "LAST_DOWNLOAD_CONTROL_SIGNATURE", None)

    resultado = manipulador_download._acionar_barra_download_pywinauto(timeout_segundos=0.1)

    assert resultado[0] is True
    assert clicks == ["segundo"]


def test_acionar_barra_download_pywinauto_evita_repetir_mesmo_controle(monkeypatch):
    clicks = []

    class FakeRect:
        def __init__(self, bottom, left):
            self.bottom = bottom
            self.left = left

    class FakeControl:
        def __init__(self, text, bottom, left, control_id):
            self._text = text
            self._bottom = bottom
            self._left = left
            self._control_id = control_id

        def window_text(self):
            return self._text

        def class_name(self):
            return "Button"

        def is_visible(self):
            return True

        def is_enabled(self):
            return True

        def rectangle(self):
            return FakeRect(self._bottom, self._left)

        def invoke(self):
            clicks.append(self._control_id)

    class FakeWindow:
        def window_text(self):
            return "Promax - Download"

        def class_name(self):
            return "IEFrame"

        def descendants(self):
            return [
                FakeControl("Salvar", 100, 10, "primeiro"),
                FakeControl("Salvar", 140, 10, "segundo"),
            ]

    class FakeDesktop:
        def __init__(self, backend):
            self.backend = backend

        def windows(self):
            return [FakeWindow()]

    monkeypatch.setattr(manipulador_download, "Desktop", FakeDesktop)
    monkeypatch.setattr(
        manipulador_download,
        "LAST_DOWNLOAD_CONTROL_SIGNATURE",
        ("promax - download", "ieframe", "salvar", "button", (140, 10)),
    )

    resultado = manipulador_download._acionar_barra_download_pywinauto(timeout_segundos=0.1)

    assert resultado[0] is True
    assert clicks == ["primeiro"]


def test_acionar_barra_download_pywinauto_ignora_barra_fantasma_ate_timeout(monkeypatch):
    clicks = []

    class FakeRect:
        def __init__(self, bottom, left):
            self.bottom = bottom
            self.left = left

    class FakeControl:
        def window_text(self):
            return "Salvar"

        def class_name(self):
            return "Button"

        def is_visible(self):
            return True

        def is_enabled(self):
            return True

        def rectangle(self):
            return FakeRect(140, 10)

        def invoke(self):
            clicks.append("clicou")

    class FakeWindow:
        def window_text(self):
            return "Promax - Download"

        def class_name(self):
            return "IEFrame"

        def descendants(self):
            return [FakeControl()]

    class FakeDesktop:
        def __init__(self, backend):
            self.backend = backend

        def windows(self):
            return [FakeWindow()]

    timeline = iter([0.0, 0.1, 1.0, 2.0, 3.0, 4.0, 5.0, 5.5, 6.1, 6.2, 6.3, 6.4])

    monkeypatch.setattr(manipulador_download, "Desktop", FakeDesktop)
    monkeypatch.setattr(
        manipulador_download,
        "LAST_DOWNLOAD_CONTROL_SIGNATURE",
        ("promax - download", "ieframe", "salvar", "button", (140, 10)),
    )
    monkeypatch.setattr(manipulador_download.logger, "info", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(manipulador_download.logger, "debug", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(manipulador_download.time, "time", lambda: next(timeline))
    monkeypatch.setattr(manipulador_download.time, "sleep", lambda *_args, **_kwargs: None)

    resultado = manipulador_download._acionar_barra_download_pywinauto(timeout_segundos=6)

    assert resultado == (
        False,
        "Apenas a barra anterior foi encontrada; uma nova barra de download nao apareceu",
    )
    assert clicks == []


def test_salvar_arquivo_visual_usa_monitoramento_apos_acionamento(monkeypatch):
    base = Path.cwd() / ".test_tmp_manipulador_download"
    shutil.rmtree(base, ignore_errors=True)
    try:
        destino = base / "saida"
        downloads_home = base / "usuario"
        downloads_dir = downloads_home / "Downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(manipulador_download.Path, "home", lambda: downloads_home)
        monkeypatch.setattr(
            manipulador_download,
            "get_settings",
            lambda: type("Settings", (), {"download_dir": destino})(),
        )
        monkeypatch.setattr(
            manipulador_download,
            "LAST_DOWNLOAD_CONTROL_SIGNATURE",
            ("promax - download", "ieframe", "salvar", "button", (140, 10)),
        )
        monkeypatch.setattr(manipulador_download, "_acionar_barra_download", lambda: (True, "acionado"))
        fechamento = {"count": 0}

        observado = {}

        def fake_monitorar(*, pasta_downloads: Path, arquivos_antes: set[Path], caminho_final: Path, timeout_segundos=500):
            observado["pasta_downloads"] = pasta_downloads
            observado["arquivos_antes"] = arquivos_antes
            observado["caminho_final"] = caminho_final
            return True, "ok"

        monkeypatch.setattr(manipulador_download, "_monitorar_download_e_mover", fake_monitorar)
        monkeypatch.setattr(
            manipulador_download,
            "_fechar_barra_download_pywinauto",
            lambda: fechamento.__setitem__("count", fechamento["count"] + 1) or (True, "fechada"),
        )
        monkeypatch.setattr(manipulador_download.time, "sleep", lambda *_args, **_kwargs: None)

        resultado = manipulador_download.salvar_arquivo_visual(str(destino), "relatorio_teste")

        assert resultado == (True, "ok")
        assert observado["pasta_downloads"] == downloads_dir
        assert observado["arquivos_antes"] == set()
        assert observado["caminho_final"] == destino / "relatorio_teste.csv"
        assert fechamento["count"] == 1
    finally:
        shutil.rmtree(base, ignore_errors=True)
