from __future__ import annotations

from pathlib import Path

from core.execution.execution_result import ExecutionResult, ExecutionStatus
from core.files.renomeador import limpar_nomes_relatorios


def exportar_tracker_csv(tracker, diretorio_destino, logger) -> ExecutionResult:
    try:
        caminho_csv = tracker.gerar_csv(str(diretorio_destino))
    except Exception as exc:
        logger.error(f"Erro ao gerar o CSV consolidado: {exc}", exc_info=True)
        return ExecutionResult(
            status=ExecutionStatus.TECHNICAL_FAILURE,
            message=f"Falha ao gerar CSV consolidado: {exc}",
        )

    if not caminho_csv:
        mensagem = "Nenhum registro de tracker para exportar."
        logger.info(mensagem)
        return ExecutionResult(status=ExecutionStatus.SUCCESS, message=mensagem)

    logger.info(f"==> RELATORIO CONSOLIDADO SALVO EM: {caminho_csv}")
    return ExecutionResult(
        status=ExecutionStatus.SUCCESS,
        message=f"Tracker exportado em {caminho_csv}",
    )


def higienizar_relatorios_intermediarios(
    pasta_intermediaria,
    caminho_planilha_auxiliar,
    logger,
) -> ExecutionResult:
    pasta_intermediaria = Path(pasta_intermediaria)

    if not caminho_planilha_auxiliar:
        mensagem = "Planilha auxiliar nao informada. Higienizacao ignorada."
        logger.warning(mensagem)
        return ExecutionResult(status=ExecutionStatus.SUCCESS, message=mensagem)

    caminho_planilha_auxiliar = Path(caminho_planilha_auxiliar)
    if not caminho_planilha_auxiliar.is_file():
        mensagem = f"Planilha auxiliar nao encontrada: {caminho_planilha_auxiliar}"
        logger.error(mensagem)
        return ExecutionResult(status=ExecutionStatus.SUCCESS, message=mensagem)

    try:
        limpar_nomes_relatorios(str(pasta_intermediaria), str(caminho_planilha_auxiliar))
    except Exception as exc:
        logger.error(
            f"Falha ao executar a limpeza de nomes e organizacao de pastas: {exc}",
            exc_info=True,
        )
        return ExecutionResult(
            status=ExecutionStatus.TECHNICAL_FAILURE,
            message=f"Falha no pos-processamento: {exc}",
        )

    return ExecutionResult(
        status=ExecutionStatus.SUCCESS,
        message=f"Pos-processamento concluido em {pasta_intermediaria}",
    )


def encontrar_primeira_planilha_excel(pasta_data) -> Path | None:
    pasta_data = Path(pasta_data)
    if not pasta_data.is_dir():
        return None

    arquivos_excel = sorted(
        arquivo
        for arquivo in pasta_data.glob("*.xlsx")
        if not arquivo.name.startswith("~$")
    )
    return arquivos_excel[0] if arquivos_excel else None


