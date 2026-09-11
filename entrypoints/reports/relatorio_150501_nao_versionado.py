from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.config.project_paths import DATA_DIR, LOGS_DIR
from core.config.settings import get_settings
from core.execution.entrypoint_helpers import (
    encerrar_driver,
    executar_tarefa_com_retry as executar_tarefa_com_retry_base,
    iniciar_sessao_padrao,
)
from core.execution.execution_result import ExecutionResult, ExecutionStatus
from core.observability.logger import get_logger
from core.observability.relatorio_execucao import tracker
from core.services.report_orchestration_service import ReportOrchestrationService, RoutineTask
from core.services.report_post_processing_service import encontrar_primeira_planilha_excel
from pages.reports.relatorio_150501_page import Relatorio150501Page


logger = get_logger("MAIN_150501_NAO_VERSIONADO")
settings = get_settings()

driver = None
menu_page = None

DEFAULT_UNITS = ["3610006", "3610007", "3610008"]


def iniciar_sessao():
    global driver, menu_page
    encerrar_driver(driver)
    driver = None
    menu_page = None

    logger.info(">>> Iniciando nova sessao 150501 nao versionada...")
    driver, menu_page = iniciar_sessao_padrao(logger, settings, settings.unidade_relatorios)
    return driver, menu_page


def executar_tarefa_com_retry(nome_tarefa, funcao_logica, tentativas=3, espera_segundos=3):
    return executar_tarefa_com_retry_base(
        nome_tarefa,
        funcao_logica,
        logger=logger,
        iniciar_sessao=iniciar_sessao,
        tentativas=tentativas,
        espera_segundos=espera_segundos,
    )


def encerrar_sessao():
    global driver, menu_page
    encerrar_driver(driver)
    driver = None
    menu_page = None


def _normalizar_unidades(units) -> list[str]:
    if not units:
        return list(DEFAULT_UNITS)

    unidades = []
    for value in units:
        for item in str(value).replace(";", ",").split(","):
            cleaned = item.strip()
            if not cleaned:
                continue
            if cleaned in {"6", "7", "8"}:
                cleaned = {
                    "6": "3610006",
                    "7": "3610007",
                    "8": "3610008",
                }[cleaned]
            if cleaned not in unidades:
                unidades.append(cleaned)
    return unidades


def _normalizar_meses(months, year: int) -> list[str]:
    if not months:
        return [f"{month:02d}/{year}" for month in range(1, 13)]

    meses = []
    for value in months:
        for item in str(value).replace(";", ",").split(","):
            cleaned = item.strip()
            if not cleaned:
                continue
            if "/" not in cleaned:
                cleaned = f"{int(cleaned):02d}/{year}"
            parsed = datetime.strptime(cleaned, "%m/%Y")
            mes_ano = parsed.strftime("%m/%Y")
            if mes_ano not in meses:
                meses.append(mes_ano)
    return meses


def _nome_arquivo_mes(mes_ano: str) -> str:
    mes, ano = mes_ano.split("/")
    return f"{ano}-{mes} nomeUnidade150501"


def main(
    *,
    year: int | None = None,
    months=None,
    units=None,
    download_workers: int = 3,
):
    if int(download_workers) < 1 or int(download_workers) > 8:
        raise ValueError("download-workers deve estar entre 1 e 8.")

    ano = int(year or datetime.now().year)
    meses = _normalizar_meses(months, ano)
    unidades = _normalizar_unidades(units)

    logger.info(
        "150501 nao versionada configurada para %s mes(es) e unidades %s.",
        len(meses),
        ", ".join(unidades),
    )

    def tarefa_mes(mes_ano: str):
        def runner(unidades_alvo=None):
            janela = menu_page.acessar_rotina("150501")
            page = Relatorio150501Page(janela.driver, janela.handle_menu)
            page.subpasta_download = "150501 nao versionado"
            page.tracker_name = f"Rotina 150501 Nao Versionado {mes_ano}"
            resultado = page.gerar_relatorio(
                unidade=unidades_alvo or unidades,
                visao="02",
                periodo="M",
                mes_ano=mes_ano,
                totaliza_periodo=True,
                nome_arquivo=_nome_arquivo_mes(mes_ano),
            )
            page.fechar_e_voltar()
            return resultado

        return runner

    tarefas = {
        f"150501_NAO_VERSIONADO_{mes_ano.replace('/', '_')}": RoutineTask(
            key=f"150501_NAO_VERSIONADO_{mes_ano.replace('/', '_')}",
            name=f"Rotina 150501 Nao Versionado {mes_ano}",
            runner=tarefa_mes(mes_ano),
        )
        for mes_ano in meses
    }

    pasta_intermediaria = Path(settings.download_dir)
    caminho_planilha_auxiliar = Path(DATA_DIR / "dRevendas.xlsx")
    if not caminho_planilha_auxiliar.is_file():
        caminho_planilha_auxiliar = encontrar_primeira_planilha_excel(DATA_DIR)

    orchestrator = ReportOrchestrationService(
        logger=logger,
        tracker=tracker,
        iniciar_sessao=iniciar_sessao,
        executar_tarefa_com_retry=executar_tarefa_com_retry,
        encerrar_sessao=encerrar_sessao,
    )
    result = orchestrator.run(
        tasks=tarefas,
        tracker_output_dir=LOGS_DIR / "relatorios_baixados",
        intermediate_dir=pasta_intermediaria,
        auxiliary_sheet=caminho_planilha_auxiliar,
        publication_plan=None,
        post_process_dirs=[pasta_intermediaria],
        automatic_repescagem=False,
        protect_artifacts_on_failure=True,
        download_workers=int(download_workers),
    )

    metadata = dict(result.metadata or {})
    metadata.update(
        {
            "months": meses,
            "units": unidades,
            "output_folder": str(pasta_intermediaria / "150501 nao versionado"),
        }
    )
    return ExecutionResult(
        status=result.status,
        message=result.message,
        retry=result.retry,
        metadata=metadata,
    )


if __name__ == "__main__":
    main()
