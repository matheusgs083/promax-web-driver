import os
import dotenv
from datetime import datetime, timedelta
from pathlib import Path

from core.execution.entrypoint_helpers import (
    encerrar_driver,
    executar_tarefa_com_retry as executar_tarefa_com_retry_base,
    iniciar_sessao_padrao,
)
from core.observability.logger import get_logger
from core.config.project_paths import DATA_DIR, LOGS_DIR
from core.services.publication_service import PublicationPlan
from core.observability.relatorio_execucao import tracker
from core.services.report_orchestration_service import ReportOrchestrationService, RoutineTask
from core.services.report_post_processing_service import encontrar_primeira_planilha_excel
from core.config.settings import get_settings

# --- IMPORTAÇÃO DO RENOMEADOR E MOVIMENTADOR ---

# Importação das Rotinas
from pages.reports.relatorio_030237_page import Relatorio030237Page
from pages.reports.relatorio_120616_page import Relatorio120616Page
from pages.reports.relatorio_0512_page import Relatorio0512Page
from pages.reports.relatorio_150501_page import Relatorio150501Page

# Carrega variáveis
dotenv.load_dotenv()
logger = get_logger("MAIN_REPESCAGEM")
settings = get_settings()

# --- VARIÁVEIS GLOBAIS DE CONTROLE ---
driver = None
menu_page = None

# --- DATAS (Padronizadas e 100% Seguras) ---
hoje = datetime.now()
ontem = hoje - timedelta(days=1)

ano_atual = hoje.strftime('%Y')
mes_atual = hoje.strftime('%m')
mes_ano_atual = hoje.strftime("%m/%Y")
data_ontem_formatada = ontem.strftime('%d/%m/%Y')

data_ultimo_dia_mes_passado = hoje.replace(day=1) - timedelta(days=1)
ano_mes_passado = data_ultimo_dia_mes_passado.strftime('%Y')
mes_passado = data_ultimo_dia_mes_passado.strftime('%m')
mes_ano_passado = data_ultimo_dia_mes_passado.strftime("%m/%Y")
ultimo_dia_mes_passado = data_ultimo_dia_mes_passado.strftime('%d/%m/%Y')
primeiro_dia_mes_passado = data_ultimo_dia_mes_passado.replace(day=1).strftime('%d/%m/%Y')

data_ultimo_dia_mes_retrasado = data_ultimo_dia_mes_passado.replace(day=1) - timedelta(days=1)
primeiro_dia_mes_retrasado = data_ultimo_dia_mes_retrasado.replace(day=1).strftime('%d/%m/%Y')


def iniciar_sessao():
    global driver, menu_page
    encerrar_driver(driver)
    driver = None
    menu_page = None

    logger.info(">>> Iniciando nova sessão para Repescagem...")
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
    logger.info("=== INICIANDO ROBÔ DE REPESCAGEM PROMAX ===")

    def tarefa_120616(unidades_alvo=None):
        janela = menu_page.acessar_rotina("120616")
        page = Relatorio120616Page(janela.driver, janela.handle_menu)
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            opcao_rel="3",
            mes_ano=mes_ano_passado,
            nome_arquivo=f"{ultimo_dia_mes_passado.replace('/','-')} (nUnidade) 120616_nomeUnidade120616",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_0512(unidades_alvo=None):
        janela = menu_page.acessar_rotina("0512")
        page = Relatorio0512Page(janela.driver, janela.handle_menu)
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            opcao_rel="11",
            ano=ano_atual,
            id_converte_hecto=True,
            nome_arquivo=f"0512 {ano_atual} nomeUnidade0512",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_150501(unidades_alvo=None):
        janela = menu_page.acessar_rotina("150501")
        page = Relatorio150501Page(janela.driver, janela.handle_menu)
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            periodo="M",
            mes_ano=mes_ano_passado,
            totaliza_periodo=True,
            nome_arquivo=f"{ano_mes_passado}-{mes_passado} nomeUnidade150501",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_030237(unidades_alvo=None):
        janela = menu_page.acessar_rotina("030237")
        page = Relatorio030237Page(janela.driver, janela.handle_menu)
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            quebra1="14",
            quebra2="12",
            quebra3="16",
            data_inicial=primeiro_dia_mes_passado,
            data_final=ultimo_dia_mes_passado,
            nome_arquivo=f"{mes_passado}-{ano_mes_passado} nomeUnidade030237",
        )
        page.fechar_e_voltar()
        return resultado

    tarefas = {
        "120616": RoutineTask(key="120616", name="Relatório 120616", runner=tarefa_120616),
        "0512": RoutineTask(key="0512", name="Relatório 0512", runner=tarefa_0512),
        "150501": RoutineTask(key="150501", name="Relatório 150501", runner=tarefa_150501),
        "030237": RoutineTask(key="030237", name="Relatório 030237", runner=tarefa_030237),
    }
    repescagem_alvos = {
        "120616": ["2210004"],
        "0512": ["3610006"],
        "150501": ["3610007"],
        "030237": ["640001", "640002", "3480005", "3610006", "3610007", "3610008"],
    }

    pasta_intermediaria = Path(settings.download_dir)
    pasta_data = DATA_DIR
    caminho_planilha_auxiliar = encontrar_primeira_planilha_excel(pasta_data)

    meses_pt = {
        "01": "JANEIRO", "02": "FEVEREIRO", "03": "MARÇO", "04": "ABRIL",
        "05": "MAIO", "06": "JUNHO", "07": "JULHO", "08": "AGOSTO",
        "09": "SETEMBRO", "10": "OUTUBRO", "11": "NOVEMBRO", "12": "DEZEMBRO",
    }
    nome_mes_passado = meses_pt[mes_passado]

    publication_plan = PublicationPlan(
        mapping={
            os.path.join(str(pasta_intermediaria), "0513"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Inadimplência\05.13\{ano_mes_passado}\{mes_passado}. {nome_mes_passado}",
            os.path.join(str(pasta_intermediaria), "120616"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Inadimplência\12.06.16\{ano_mes_passado}\{mes_passado}. {nome_mes_passado}",
            os.path.join(str(pasta_intermediaria), "120601"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Inadimplência\12.06.01\{ano_mes_passado}\{mes_passado}. {nome_mes_passado}",
            os.path.join(str(pasta_intermediaria), "0512"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\05.12\{ano_atual}",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_mes_passado}-{mes_passado} Sousa.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\1. SOUSA",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_mes_passado}-{mes_passado} Itaporanga.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\2. ITAPORANGA",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_mes_passado}-{mes_passado} Patos.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\3. PATOS",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_mes_passado}-{mes_passado} Sumé.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\4. SUMÉ",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_mes_passado}-{mes_passado} Guarabira.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\5. GUARABIRA",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_mes_passado}-{mes_passado} Brumado.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\6. BRUMADO",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_mes_passado}-{mes_passado} Barra.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\7. BARRA",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_mes_passado}-{mes_passado} Caculé.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\8. CACULÉ",
            os.path.join(str(pasta_intermediaria), "030237"): r"\\dc01n\PUBLICO\REVENDA\Power BI\ADF",
            os.path.join(str(pasta_intermediaria), "020220"): r"M:\ADMINISTRATIVO\FINANCEIRO\GERÊNCIA\Relatorios\02.02.20 - Recolhas",
        },
        success_message="Movimentação concluída com sucesso.",
        partial_prefix="Movimentação concluída com pendências de publicação.",
        technical_prefix="Movimentação finalizada com falha técnica de publicação.",
    )

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
        publication_plan=publication_plan,
        run_initial_execution=False,
        manual_repescagem=repescagem_alvos,
    )

if __name__ == "__main__":
    main()

