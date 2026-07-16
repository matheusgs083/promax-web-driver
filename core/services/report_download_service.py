from __future__ import annotations

from threading import Lock

from core.config.settings import get_settings
from core.execution.execution_result import ExecutionResult, ExecutionStatus

try:
    from core.services.concurrent_report_download_service import FilaDownloadsRelatorios
    from core.files.manipulador_download import (
        preparar_download_http_formulario,
        salvar_arquivo_http_formulario,
        salvar_arquivo_visual,
        salvar_url_temporaria_relatorio,
    )
except ImportError:
    FilaDownloadsRelatorios = None
    preparar_download_http_formulario = None
    salvar_arquivo_http_formulario = None
    salvar_arquivo_visual = None
    salvar_url_temporaria_relatorio = None


_pool_lock = Lock()
_pool_downloads: FilaDownloadsRelatorios | None = None


def ativar_pool_downloads(
    *,
    max_workers: int = 5,
    max_retentativas_html: int = 1,
) -> None:
    global _pool_downloads
    with _pool_lock:
        if _pool_downloads is not None:
            raise RuntimeError("Pool de downloads HTTP já está ativo")
        if FilaDownloadsRelatorios is None:
            raise RuntimeError("Pool de downloads HTTP indisponível")
        _pool_downloads = FilaDownloadsRelatorios(
            max_workers=max_workers,
            max_retentativas_html=max_retentativas_html,
        )


def aguardar_downloads_pendentes() -> ExecutionResult:
    with _pool_lock:
        pool = _pool_downloads
    if pool is None:
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message="Pool de downloads HTTP não foi ativado.",
        )
    return pool.aguardar()


def desativar_pool_downloads() -> None:
    global _pool_downloads
    with _pool_lock:
        pool = _pool_downloads
        _pool_downloads = None
    if pool is not None:
        pool.encerrar()


def capturar_download_por_formulario(
    driver,
    botao,
    nome_arquivo_final,
    diretorio_intermediario=None,
    extensao_final=".csv",
):
    if not salvar_arquivo_http_formulario:
        return False, "Download HTTP por formulário indisponível"
    pasta_intermediaria = diretorio_intermediario or get_settings().download_dir

    with _pool_lock:
        pool = _pool_downloads

    # PDFs permanecem síncronos porque algumas rotinas os convertem
    # imediatamente. CSVs só são consumidos após o esvaziamento da fila.
    if (
        pool is not None
        and str(extensao_final).lower() == ".csv"
        and preparar_download_http_formulario is not None
    ):
        try:
            download = preparar_download_http_formulario(
                driver,
                botao,
                str(pasta_intermediaria),
                nome_arquivo_final,
                extensao_final,
            )
            pool.enviar(download)
            return True, f"Download HTTP agendado: {download.nome_arquivo}"
        except Exception as exc:
            return False, f"Falha ao agendar download HTTP: {exc}"

    return salvar_arquivo_http_formulario(
        driver,
        botao,
        str(pasta_intermediaria),
        nome_arquivo_final,
        extensao_final,
    )


def capturar_url_temporaria(
    driver,
    nome_arquivo_final,
    diretorio_intermediario=None,
    extensao_final=".csv",
    timeout_segundos=15,
):
    if not salvar_url_temporaria_relatorio:
        return False, "Captura de URL temporária indisponível"
    pasta_intermediaria = diretorio_intermediario or get_settings().download_dir
    return salvar_url_temporaria_relatorio(
        driver,
        str(pasta_intermediaria),
        nome_arquivo_final,
        extensao_final,
        timeout_segundos,
    )


def capturar_download_relatorio(
    nome_arquivo_final: str,
    diretorio_intermediario=None,
    *,
    diretorio_destino=None,
    extensao_final=".csv",
    driver=None,
):
    """
    Centraliza a captura do arquivo baixado pelo IE na pasta intermediaria.
    """
    if not salvar_arquivo_visual:
        return False, "Modulos visuais ausentes"

    # A captura sempre acontece na área intermediária. O destino final pertence
    # à etapa de publicação, depois que o arquivo foi completamente validado.
    pasta_intermediaria = diretorio_intermediario or get_settings().download_dir
    kwargs = {
        "diretorio_destino": str(pasta_intermediaria),
        "nome_arquivo_final": nome_arquivo_final,
    }
    if driver is not None:
        kwargs["driver"] = driver
    if str(extensao_final).lower() != ".csv":
        kwargs["extensao_final"] = extensao_final
    return salvar_arquivo_visual(**kwargs)


