from datetime import datetime, timedelta
from pathlib import Path

import dotenv
import pandas as pd

from core.config.project_paths import DATA_DIR, LOGS_DIR
from core.config.settings import get_settings
from core.execution.entrypoint_helpers import (
    encerrar_driver,
    executar_tarefa_com_retry as executar_tarefa_com_retry_base,
    iniciar_sessao_padrao,
)
from core.observability.logger import get_logger
from core.observability.relatorio_execucao import tracker
from core.services.report_orchestration_service import ReportOrchestrationService, RoutineTask
from core.services.report_post_processing_service import encontrar_primeira_planilha_excel
from pages.reports.relatorio_030237_page import Relatorio030237Page
from pages.reports.relatorio_030803_page import Relatorio030803Page
from pages.reports.relatorio_030312_page import Relatorio030312Page
from pages.reports.relatorio_031120_page import Relatorio031120Page
from pages.reports.relatorio_03114902_page import Relatorio03114902Page


dotenv.load_dotenv()
logger = get_logger("MAIN_030312")

settings = get_settings()

driver = None
menu_page = None

hoje = datetime.now()
ontem = hoje - timedelta(days=1)
data_anterior = pd.Timestamp.now() - pd.offsets.BusinessDay(1)
ultimo_dia_util = data_anterior.strftime("%d-%m-%Y")

data_hoje_arquivo = hoje.strftime("%d-%m-%Y")
data_hoje_formatada = hoje.strftime("%d/%m/%Y")
data_ontem_formatada = ontem.strftime("%d/%m/%Y")
ultimo_dia_util_formatado = data_anterior.strftime("%d/%m/%Y")

def calcular_periodo_030312(
    pasta_030312: Path,
    *,
    modificado_desde: datetime | None = None,
):
    arquivos = sorted(pasta_030312.glob("*.csv"))
    if modificado_desde is not None:
        arquivos = [
            arquivo
            for arquivo in arquivos
            if datetime.fromtimestamp(arquivo.stat().st_mtime) >= modificado_desde
        ]

    if not arquivos:
        raise RuntimeError(f"Nenhum CSV da 030312 encontrado em {pasta_030312}")

    datas = []
    datas_ignoradas = 0
    for arquivo in arquivos:
        try:
            df = pd.read_csv(arquivo, sep=";", dtype=str, encoding="utf-8-sig")
        except UnicodeDecodeError:
            df = pd.read_csv(arquivo, sep=";", dtype=str, encoding="latin1")

        if df.shape[1] < 4:
            logger.warning("CSV 030312 ignorado sem coluna D: %s", arquivo)
            continue

        serie_datas = df.iloc[:, 3].astype(str).str.strip()
        datas_arquivo = pd.to_datetime(
            serie_datas[serie_datas.ne("") & serie_datas.ne("00/00/0000")],
            format="%d/%m/%Y",
            errors="coerce",
        ).dropna()

        limite_inferior = pd.Timestamp(hoje.year - 1, 1, 1)
        limite_superior = pd.Timestamp(hoje) + pd.Timedelta(days=31)
        datas_validas = datas_arquivo[
            datas_arquivo.ge(limite_inferior) & datas_arquivo.le(limite_superior)
        ]
        datas_ignoradas += len(datas_arquivo) - len(datas_validas)
        datas.extend(datas_validas.to_list())

    if not datas:
        raise RuntimeError("Nenhuma data valida encontrada na coluna D dos CSVs da 030312.")

    data_inicial = min(datas).strftime("%d/%m/%Y")
    data_final = max(datas).strftime("%d/%m/%Y")
    logger.info(
        "Periodo calculado pela 030312: %s a %s (%s arquivo(s), %s data(s), %s ignorada(s))",
        data_inicial,
        data_final,
        len(arquivos),
        len(datas),
        datas_ignoradas,
    )
    return data_inicial, data_final


def limitar_periodo_03114902(data_inicial: str, data_final: str):
    fim = pd.to_datetime(data_final, format="%d/%m/%Y")
    inicio = fim - pd.DateOffset(months=1) + pd.Timedelta(days=1)

    logger.info(
        "Periodo 03114902 limitado a 1 mes para tras: %s a %s (periodo 030312: %s a %s)",
        inicio.strftime("%d/%m/%Y"),
        fim.strftime("%d/%m/%Y"),
        data_inicial,
        data_final,
    )
    return inicio.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y")


def iniciar_sessao():
    global driver, menu_page
    encerrar_driver(driver)
    driver = None
    menu_page = None

    logger.info(">>> Iniciando nova sessão (Browser + Login)...")
    driver, menu_page = iniciar_sessao_padrao(logger, settings, settings.unidade_relatorios)
    return driver, menu_page


def executar_tarefa_com_retry(nome_tarefa, funcao_logica, tentativas=3, espera_segundos=3):
    global driver, menu_page
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


def main():
    logger.info("=== INICIANDO ROBÔ PROMAX 030312 (COM AUTO-RECOVERY) ===")

    inicio_execucao = datetime.now()
    pasta_intermediaria = Path(settings.download_dir)
    periodo_030312 = None

    def obter_periodo_030312():
        nonlocal periodo_030312
        if periodo_030312 is None:
            periodo_030312 = calcular_periodo_030312(
                pasta_intermediaria / "030312",
                modificado_desde=inicio_execucao,
            )
        return periodo_030312

    def tarefa_030312(unidades_alvo=None):
        janela = menu_page.acessar_rotina("030312")
        page = Relatorio030312Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "030312"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            acao="BotGeraCsv",
            nome_arquivo="030312_nUnidade",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_030803(unidades_alvo=None):
        data_inicial, data_final = obter_periodo_030312()
        janela = menu_page.acessar_rotina("030803")
        page = Relatorio030803Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "030803"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            data_inicial=data_inicial,
            data_final=data_final,
            nome_arquivo="030803_nUnidade.pdf",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_030237(unidades_alvo=["0640001"]):
        data_inicial, data_final = obter_periodo_030312()
        janela = menu_page.acessar_rotina("030237")
        page = Relatorio030237Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "030237 financeiro"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            quebra1="14",
            quebra2="16",
            tp_consolidacao="5",
            data_inicial=data_inicial,
            data_final=data_final,
            nome_arquivo=f"030237",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_030237_entrada(unidades_alvo=["0640001"]):
        data_inicial, data_final = obter_periodo_030312()
        janela = menu_page.acessar_rotina("030237")
        page = Relatorio030237Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "030237 financeiro entrada"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            quebra1="14",
            quebra2="16",
            tipo_nota="NE",
            tp_consolidacao="5",
            data_inicial=data_inicial,
            data_final=data_final,
            nome_arquivo=f"030237 entrada",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_03114902(unidades_alvo=["0640001"]):
        data_inicial, data_final = calcular_periodo_030312(
            pasta_intermediaria / "030312",
            modificado_desde=inicio_execucao,
        )
        data_inicial, data_final = limitar_periodo_03114902(data_inicial, data_final)
        janela = menu_page.acessar_rotina("03114902")
        page = Relatorio03114902Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "03114902"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            classificacao="Mapa",
            tipo_mapa_rota=True,
            tipo_mapa_as=True,
            todas_operacoes=True,
            mapas_roteirizados=True,
            data_inicial=data_inicial,
            data_final=data_final,
            roadshow_inicial="0",
            roadshow_final="99",
            transportadora_inicial="0",
            transportadora_final="999999",
            armazem="Todos",
            csv_geo=True,
            nome_arquivo="03114902_geo",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_031120(unidades_alvo=None):
        data_inicial, data_final = obter_periodo_030312()
        janela = menu_page.acessar_rotina("031120")
        page = Relatorio031120Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "031120"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            opcao_rel="1",
            data_inicial=data_inicial,
            data_final=data_final,
            cod_armazem="01",
            nome_arquivo="031120_nUnidade",
        )
        page.fechar_e_voltar()
        return resultado

    tarefas = {
        "030312": RoutineTask(key="030312", name="Rotina 030312", runner=tarefa_030312),
        "030237": RoutineTask(key="030237", name="Rotina 030237", runner=tarefa_030237),
        "030237_entrada": RoutineTask(key="030237_entrada", name="Rotina 030237 Entrada", runner=tarefa_030237_entrada),
        "03114902": RoutineTask(key="03114902", name="Rotina 03114902", runner=tarefa_03114902),
        "030803": RoutineTask(key="030803", name="Rotina 030803", runner=tarefa_030803),
        "031120": RoutineTask(key="031120", name="Rotina 031120", runner=tarefa_031120),
    }

    pasta_data = DATA_DIR
    caminho_planilha_auxiliar = Path(pasta_data / "dRevendas.xlsx")
    if not caminho_planilha_auxiliar.is_file():
        caminho_planilha_auxiliar = encontrar_primeira_planilha_excel(pasta_data)

    orchestrator = ReportOrchestrationService(
        logger=logger,
        tracker=tracker,
        iniciar_sessao=iniciar_sessao,
        executar_tarefa_com_retry=executar_tarefa_com_retry,
        encerrar_sessao=encerrar_sessao,
    )
    return orchestrator.run(
        tasks=tarefas,
        tracker_output_dir=LOGS_DIR / "relatorios_baixados",
        intermediate_dir=pasta_intermediaria,
        auxiliary_sheet=caminho_planilha_auxiliar,
        publication_plan=None,
        automatic_repescagem=True,
        protect_artifacts_on_failure=True,
    )


if __name__ == "__main__":
    main()
