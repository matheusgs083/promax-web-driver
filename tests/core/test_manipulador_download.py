from __future__ import annotations

import shutil
from pathlib import Path

from core.files import manipulador_download


def test_houve_atividade_download_detecta_novo_arquivo():
    base = Path.cwd() / ".test_tmp_manipulador_download"
    shutil.rmtree(base, ignore_errors=True)
    try:
        downloads_dir = base / "Downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        arquivos_antes = set(downloads_dir.iterdir())

        (downloads_dir / "novo.csv").write_text("a,b\n1,2\n", encoding="utf-8")

        assert manipulador_download._houve_atividade_download(downloads_dir, arquivos_antes) is True
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

        def fake_validar(*_args, **_kwargs):
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


def test_salvar_arquivo_visual_envia_alt_s_quando_clique_nao_inicia_download(monkeypatch):
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

        class FakeClock:
            def __init__(self):
                self.now = 0.0

            def time(self):
                self.now += 6.0
                return self.now

            def sleep(self, seconds):
                self.now += float(seconds)

        hotkeys = []
        clock = FakeClock()

        monkeypatch.setattr(manipulador_download, "validar_elemento", lambda *_args, **_kwargs: FakeBox())
        monkeypatch.setattr(manipulador_download, "_houve_atividade_download", lambda *_args, **_kwargs: False)
        monkeypatch.setattr(manipulador_download.pyautogui, "center", lambda *_args, **_kwargs: (10, 20))
        monkeypatch.setattr(manipulador_download.pyautogui, "moveTo", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(manipulador_download.pyautogui, "click", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(manipulador_download.pyautogui, "hotkey", lambda *args, **_kwargs: hotkeys.append(args))
        monkeypatch.setattr(manipulador_download.time, "time", clock.time)
        monkeypatch.setattr(manipulador_download.time, "sleep", clock.sleep)

        resultado = manipulador_download.salvar_arquivo_visual(str(destino), "relatorio_teste")

        assert ("alt", "s") in hotkeys
        assert resultado == (False, "Timeout na espera da rede/download do arquivo")
    finally:
        shutil.rmtree(base, ignore_errors=True)
