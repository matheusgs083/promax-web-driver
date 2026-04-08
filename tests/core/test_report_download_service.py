from pathlib import Path

from core.services import report_download_service


def test_capturar_download_relatorio_usa_pasta_intermediaria(monkeypatch):
    chamada = {}

    def fake_salvar_arquivo_visual(*, diretorio_destino, nome_arquivo_final):
        chamada["diretorio_destino"] = diretorio_destino
        chamada["nome_arquivo_final"] = nome_arquivo_final
        return True, "ok"

    monkeypatch.setattr(report_download_service, "salvar_arquivo_visual", fake_salvar_arquivo_visual)
    monkeypatch.setattr(
        report_download_service,
        "get_settings",
        lambda: type("Settings", (), {"download_dir": Path("C:/downloads/padrao")})(),
    )

    resultado = report_download_service.capturar_download_relatorio(
        "relatorio.csv",
        diretorio_intermediario=Path("C:/downloads/intermediaria"),
        diretorio_destino=Path("C:/destino/final"),
    )

    assert resultado == (True, "ok")
    assert chamada == {
        "diretorio_destino": "C:\\downloads\\intermediaria",
        "nome_arquivo_final": "relatorio.csv",
    }


def test_capturar_download_relatorio_ignora_destino_final_na_captura(monkeypatch):
    chamada = {}

    def fake_salvar_arquivo_visual(*, diretorio_destino, nome_arquivo_final):
        chamada["diretorio_destino"] = diretorio_destino
        chamada["nome_arquivo_final"] = nome_arquivo_final
        return True, "ok"

    monkeypatch.setattr(report_download_service, "salvar_arquivo_visual", fake_salvar_arquivo_visual)
    monkeypatch.setattr(
        report_download_service,
        "get_settings",
        lambda: type("Settings", (), {"download_dir": Path("C:/downloads/padrao")})(),
    )

    resultado = report_download_service.capturar_download_relatorio(
        "relatorio.csv",
        diretorio_destino=Path("C:/destino/final"),
    )

    assert resultado == (True, "ok")
    assert chamada == {
        "diretorio_destino": "C:\\downloads\\padrao",
        "nome_arquivo_final": "relatorio.csv",
    }
