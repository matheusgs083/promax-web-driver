from __future__ import annotations

from core.config.settings import get_settings

try:
    from core.files.manipulador_download import salvar_arquivo_visual
except ImportError:
    salvar_arquivo_visual = None


def capturar_download_relatorio(
    nome_arquivo_final: str,
    diretorio_intermediario=None,
    *,
    diretorio_destino=None,
):
    """
    Centraliza a captura do arquivo baixado pelo IE na pasta intermediaria.
    """
    if not salvar_arquivo_visual:
        return False, "Modulos visuais ausentes"

    pasta_intermediaria = diretorio_destino or diretorio_intermediario or get_settings().download_dir
    return salvar_arquivo_visual(
        diretorio_destino=str(pasta_intermediaria),
        nome_arquivo_final=nome_arquivo_final,
    )


