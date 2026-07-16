from __future__ import annotations

import shutil
from pathlib import Path

from core.files import manipulador_download


def test_extrair_urls_relatorio_promax_remove_duplicatas():
    html = """
        <a href="/pw/tmp/rels/03.01.11_PW02041R_F7367_22310592.csv.inf">CSV</a>
        <script>var arquivo='/pw/tmp/rels/03.01.11_PW02041R_F7367_22310592.csv.inf';</script>
    """

    urls = manipulador_download._extrair_urls_relatorio(
        html,
        "http://paubrasil.promaxcloud.com.br/pw/cgi-bin/PP00100.exe",
    )

    assert urls == [
        "http://paubrasil.promaxcloud.com.br/pw/tmp/rels/03.01.11_PW02041R_F7367_22310592.csv.inf"
    ]


def test_extrair_url_pdf_promax_sem_inf():
    html = '<script>window.location="/pw/tmp/rels/bol_237_007544_000000_999999_22502754.pdf";</script>'

    urls = manipulador_download._extrair_urls_relatorio(
        html,
        "http://paubrasil.promaxcloud.com.br/pw/cgi-bin/PP00100.exe",
    )

    assert urls == [
        "http://paubrasil.promaxcloud.com.br/pw/tmp/rels/bol_237_007544_000000_999999_22502754.pdf"
    ]


def test_tentar_download_http_salva_csv_sem_fluxo_visual(monkeypatch):
    base = Path.cwd() / ".test_tmp_manipulador_download"
    shutil.rmtree(base, ignore_errors=True)
    try:
        destino = base / "relatorio.csv"
        destino.parent.mkdir(parents=True, exist_ok=True)
        url = "http://promax.local/pw/tmp/rels/relatorio.csv.inf"

        monkeypatch.setattr(
            manipulador_download,
            "_coletar_urls_relatorio_driver",
            lambda _driver: [url],
        )

        def fake_baixar(_driver, url_recebida, caminho_final, extensao):
            assert url_recebida == url
            assert extensao == ".csv"
            caminho_final.write_bytes(b"coluna;valor\n1;2\n")
            return True, "Download HTTP direto validado (18 bytes)"

        monkeypatch.setattr(manipulador_download, "_baixar_url_relatorio", fake_baixar)

        resultado = manipulador_download._tentar_download_http(
            object(),
            destino,
            ".csv",
            timeout_segundos=1,
        )

        assert resultado[0] is True
        assert destino.read_bytes().startswith(b"coluna;valor")
    finally:
        shutil.rmtree(base, ignore_errors=True)


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
