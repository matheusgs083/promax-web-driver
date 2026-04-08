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

from pages.reports.relatorio_030237_page import Relatorio030237Page
from pages.reports.relatorio_120601_page import Relatorio120601Page
from pages.reports.relatorio_0513_page import Relatorio0513Page
from pages.reports.relatorio_120616_page import Relatorio120616Page
from pages.reports.relatorio_0512_page import Relatorio0512Page
from pages.reports.relatorio_150501_page import Relatorio150501Page
from pages.reports.relatorio_020220_page import Relatorio020220Page

dotenv.load_dotenv()
logger = get_logger("MAIN_PROMAX")

settings = get_settings()

driver = None
menu_page = None

hoje = datetime.now()
ontem = hoje - timedelta(days=1)

ano_atual = hoje.strftime("%Y")
mes_atual = hoje.strftime("%m")
mes_ano_atual = hoje.strftime("%m/%Y")
data_hoje_arquivo = hoje.strftime("%d-%m-%Y")
data_ontem_formatada = ontem.strftime("%d/%m/%Y")
data_hoje_formatada = hoje.strftime("%d/%m/%Y")
primeiro_dia_mes_atual = hoje.replace(day=1).strftime("%d/%m/%Y")

ultimo_dia_mes_passado_dt = hoje.replace(day=1) - timedelta(days=1)
primeiro_dia_mes_passado = ultimo_dia_mes_passado_dt.replace(day=1).strftime("%d/%m/%Y")
ultimo_dia_mes_passado = ultimo_dia_mes_passado_dt.strftime("%d/%m/%Y")
ano_mes_passado = ultimo_dia_mes_passado_dt.strftime("%Y")
mes_passado = ultimo_dia_mes_passado_dt.strftime("%m")
mes_ano_passado = ultimo_dia_mes_passado_dt.strftime("%m/%Y")

ultimo_dia_mes_retrasado_dt = ultimo_dia_mes_passado_dt.replace(day=1) - timedelta(days=1)
primeiro_dia_mes_retrasado = ultimo_dia_mes_retrasado_dt.replace(day=1).strftime("%d/%m/%Y")



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
    logger.info("=== INICIANDO ROBÔ PROMAX (COM AUTO-RECOVERY) ===")

    def tarefa_0513(unidades_alvo=None):
        janela = menu_page.acessar_rotina("0513")
        page = Relatorio0513Page(janela.driver, janela.handle_menu)
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            opcao_rel="12",
            volume_fin="F",
            tp_equipe="A",
            mes_ano_inicial=mes_ano_atual,
            mes_ano_final=mes_ano_atual,
            quantos_clientes="99999",
            nome_arquivo=f"{data_hoje_arquivo} (nUnidade) nomeUnidade0513",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_120616(unidades_alvo=None):
        janela = menu_page.acessar_rotina("120616")
        page = Relatorio120616Page(janela.driver, janela.handle_menu)
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            opcao_rel="3",
            mes_ano=mes_ano_atual,
            nome_arquivo=f"{data_hoje_arquivo} (nUnidade) 120616_nomeUnidade120616",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_120601(unidades_alvo=None):
        janela = menu_page.acessar_rotina("120601")
        page = Relatorio120601Page(janela.driver, janela.handle_menu)
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            opcao_rel="01",
            id_notas_tit_nao_atu=False,
            ini_vencimento=primeiro_dia_mes_passado,
            fim_vencimento=data_ontem_formatada,
            ini_especie=4,
            fim_especie=4,
            nome_arquivo=f"{data_hoje_arquivo} 120601_nomeUnidade120601",
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
            nome_arquivo=f"05,12 {ano_atual} nomeUnidade0512",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_150501(unidades_alvo=None):
        janela = menu_page.acessar_rotina("150501")
        page = Relatorio150501Page(janela.driver, janela.handle_menu)
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            visao="02",
            periodo="M",
            mes_ano=mes_ano_atual,
            totaliza_periodo=True,
            nome_arquivo=f"{ano_atual}-{mes_atual} nomeUnidade150501",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_030237(unidades_alvo=None):
        janela = menu_page.acessar_rotina("030237")
        page = Relatorio030237Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "030237"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            quebra1="14",
            quebra2="12",
            quebra3="16",
            data_inicial=primeiro_dia_mes_atual,
            data_final=data_ontem_formatada,
            nome_arquivo=f"{mes_atual}-{ano_atual} nomeUnidade030237",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_030237_Giro(unidades_alvo=None):
        janela = menu_page.acessar_rotina("030237")
        page = Relatorio030237Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "030237 Giro"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            quebra1="14",
            itens="s",
            data_inicial=primeiro_dia_mes_atual,
            data_final=data_hoje_formatada,
            nome_arquivo=f"{mes_atual}-{ano_atual} nomeUnidade030237",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_020220_Auditool(unidades_alvo=["3610008"]):
        janela = menu_page.acessar_rotina("020220")
        page = Relatorio020220Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "020220 Auditool"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            opcao_rel="01",
            mercadoria_todos=False,
            mercadoria_garrafeira=True,
            mercadoria_vasilhame=True,
            mercadoria_sopi_visa=True,
            exibe_inf_documentos=True,
            selecao_comodatos="P",
            nome_arquivo="020220 Auditool - nomeUnidade020220",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_020220_Giro(unidades_alvo=None):
        janela = menu_page.acessar_rotina("020220")
        page = Relatorio020220Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "020220 Giro"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            opcao_rel="01",
            mercadoria_todos=False,
            mercadoria_garrafeira=True,
            mercadoria_sopi_visa=True,
            selecao_comodatos="T",
            nome_arquivo="02,02,20_nUnidade",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_020220_Recolhas(unidades_alvo=None):
        janela = menu_page.acessar_rotina("020220")
        page = Relatorio020220Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "020220 Recolhas"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            opcao_rel="01",
            mercadoria_todos=False,
            mercadoria_garrafeira=True,
            mercadoria_vasilhame=True,
            selecao_comodatos="T",
            nome_arquivo="020220 Recolhas - nomeUnidade020220",
        )
        page.fechar_e_voltar()
        return resultado

    tarefas = {
        #inadimplencia
        #"0513": RoutineTask(key="0513", name="Rotina 0513", runner=tarefa_0513),
        #"120616": RoutineTask(key="120616", name="Rotina 120616", runner=tarefa_120616),
        #"120601": RoutineTask(key="120601", name="Rotina 120601", runner=tarefa_120601),
        # OBZ
        "0512": RoutineTask(key="0512", name="Rotina 0512", runner=tarefa_0512),
        "150501": RoutineTask(key="150501", name="Rotina 150501", runner=tarefa_150501),
        #adf
        #"030237": RoutineTask(key="030237", name="Rotina 030237", runner=tarefa_030237),
        #outros
        #"020220": RoutineTask(key="020220", name="Rotina 020220 Auditool", runner=tarefa_020220_Auditool),
        # "020220_RECOLHAS": RoutineTask(key="020220_RECOLHAS", name="Rotina 020220 Recolhas", runner=tarefa_020220_Recolhas),
        #Giro
        #"030237 Giro": RoutineTask(key="030237_GIRO", name="Rotina 030237 Giro", runner=tarefa_030237_Giro),
        #"020220 Giro": RoutineTask(key="020220_GIRO", name="Rotina 020220 Giro", runner=tarefa_020220_Giro),
    }

    pasta_intermediaria = Path(settings.download_dir)
    pasta_data = DATA_DIR
    caminho_planilha_auxiliar = Path(pasta_data / "dRevendas.xlsx")
    if not caminho_planilha_auxiliar.is_file():
        caminho_planilha_auxiliar = encontrar_primeira_planilha_excel(pasta_data)

    meses_pt = {
        "01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril",
        "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto",
        "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro",
    }
    nome_mes_atual = meses_pt[mes_atual]

    publication_plan = PublicationPlan(
        mapping={
            os.path.join(str(pasta_intermediaria), "0513"): r"\\dc01n\PUBLICO\REVENDA\Power BI\Inadimplência\05.13",
            os.path.join(str(pasta_intermediaria), "120616"): r"\\dc01n\PUBLICO\REVENDA\Power BI\Inadimplência\12.06.16",
            os.path.join(str(pasta_intermediaria), "120601"): r"\\dc01n\PUBLICO\REVENDA\Power BI\Inadimplência\12.06.01",
            os.path.join(str(pasta_intermediaria), "0512"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\05.12\{ano_atual}",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_atual}-{mes_atual} Sousa.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\1. SOUSA",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_atual}-{mes_atual} Itaporanga.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\2. ITAPORANGA",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_atual}-{mes_atual} Patos.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\3. PATOS",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_atual}-{mes_atual} Sumé.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\4. SUMÉ",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_atual}-{mes_atual} Guarabira.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\5. GUARABIRA",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_atual}-{mes_atual} Brumado.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\6. BRUMADO",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_atual}-{mes_atual} Barra.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\7. BARRA",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_atual}-{mes_atual} Caculé.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\8. CACULÉ",
            os.path.join(str(pasta_intermediaria), "030237"): r"\\dc01n\PUBLICO\REVENDA\Power BI\ADF",
            os.path.join(str(pasta_intermediaria), "020220 Auditool"): r"M:\ADMINISTRATIVO\FINANCEIRO\GERÊNCIA\Relatorios\02.02.20 - auditool",
            os.path.join(str(pasta_intermediaria), "020220 Recolhas"): r"M:\ADMINISTRATIVO\FINANCEIRO\GERÊNCIA\Relatorios\02.02.20 - recolhas",
            os.path.join(str(pasta_intermediaria), "030237 Giro", f"{mes_atual}-{ano_atual} Sousa.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Giro\Fato\03.02.37\Total\{ano_atual}\01. Sousa",
            os.path.join(str(pasta_intermediaria), "030237 Giro", f"{mes_atual}-{ano_atual} Itaporanga.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Giro\Fato\03.02.37\Total\{ano_atual}\02. Itaporanga",
            os.path.join(str(pasta_intermediaria), "030237 Giro", f"{mes_atual}-{ano_atual} Patos.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Giro\Fato\03.02.37\Total\{ano_atual}\03. Patos",
            os.path.join(str(pasta_intermediaria), "030237 Giro", f"{mes_atual}-{ano_atual} Sumé.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Giro\Fato\03.02.37\Total\{ano_atual}\04. Sumé",
            os.path.join(str(pasta_intermediaria), "030237 Giro", f"{mes_atual}-{ano_atual} Guarabira.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Giro\Fato\03.02.37\Total\{ano_atual}\05. Guarabira",
            os.path.join(str(pasta_intermediaria), "030237 Giro", f"{mes_atual}-{ano_atual} Brumado.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Giro\Fato\03.02.37\Total\{ano_atual}\06. Brumado",
            os.path.join(str(pasta_intermediaria), "030237 Giro", f"{mes_atual}-{ano_atual} Barra.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Giro\Fato\03.02.37\Total\{ano_atual}\07. Barra",
            os.path.join(str(pasta_intermediaria), "030237 Giro", f"{mes_atual}-{ano_atual} Caculé.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Giro\Fato\03.02.37\Total\{ano_atual}\08. Caculé",
            os.path.join(str(pasta_intermediaria), "020220 Giro"): r"\\dc01n\PUBLICO\REVENDA\Power BI\Giro\Fato\02.02.20"
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
        automatic_repescagem=True,
        protect_artifacts_on_failure=True,
    )

if __name__ == "__main__":
    main()
