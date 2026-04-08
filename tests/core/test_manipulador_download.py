from __future__ import annotations

import shutil
from pathlib import Path

from core.files import manipulador_download


def test_salvar_arquivo_visual_retorna_erro_quando_barra_nao_aparece(monkeypatch):
    base = Path.cwd() / ".test_tmp_manipulador_download"
    shutil.rmtree(base, ignore_errors=True)
    try:
        downloads_home = base / "usuario"
        (downloads_home / "Downloads").mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(manipulador_download.Path, "home", lambda: downloads_home)
        monkeypatch.setattr(manipulador_download, "validar_elemento", lambda *args, **kwargs: None)

        resultado = manipulador_download.salvar_arquivo_visual(str(base / "saida"), "relatorio_teste")

        assert resultado == (False, "Barra de download nativa não apareceu")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_salvar_arquivo_visual_move_arquivo_quando_download_aparece(monkeypatch):
    base = Path.cwd() / ".test_tmp_manipulador_download"
    shutil.rmtree(base, ignore_errors=True)
    try:
        destino = base / "saida"
        downloads_home = base / "usuario"
        downloads_dir = downloads_home / "Downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(manipulador_download.Path, "home", lambda: downloads_home)

        class FakeBox:
            pass

        def fake_validar(*args, **kwargs):
            (downloads_dir / "arquivo_baixado.csv").write_text("coluna\nvalor\n", encoding="utf-8")
            return FakeBox()

        monkeypatch.setattr(manipulador_download, "validar_elemento", fake_validar)
        monkeypatch.setattr(manipulador_download.pyautogui, "center", lambda *_args, **_kwargs: (10, 20))
        monkeypatch.setattr(manipulador_download.pyautogui, "moveTo", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(manipulador_download.pyautogui, "click", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(manipulador_download.pyautogui, "hotkey", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(manipulador_download.time, "sleep", lambda *_args, **_kwargs: None)

        resultado = manipulador_download.salvar_arquivo_visual(str(destino), "relatorio_teste")

        assert resultado[0] is True
        assert (destino / "relatorio_teste.csv").exists()
    finally:
        shutil.rmtree(base, ignore_errors=True)
