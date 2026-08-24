import os
import dotenv
from datetime import date, datetime, timedelta
from pathlib import Path
import pandas as pd

from core.config.report_group_loader import (
    load_report_groups,
    select_report_group,
)
from core.execution.entrypoint_helpers import (
    encerrar_driver,
    executar_tarefa_com_retry as executar_tarefa_com_retry_base,
    iniciar_sessao_padrao,
)
from core.execution.execution_result import ExecutionResult
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
from pages.reports.relatorio_020502_page import Relatorio020502Page
from pages.reports.relatorio_140506_page import Relatorio140506Page
from pages.reports.relatorio_120606_page import Relatorio120606Page
from pages.reports.relatorio_030206_page import Relatorio030206Page
from pages.reports.relatorio_0105070402_page import Relatorio0105070402Page
from pages.reports.relatorio_030111_page import Relatorio030111Page
from pages.reports.relatorio_031702_page import Relatorio031702Page
from pages.reports.relatorio_020304_page import Relatorio020304Page
from pages.reports.relatorio_031120_page import Relatorio031120Page
from pages.reports.relatorio_03114902_page import Relatorio03114902Page

dotenv.load_dotenv()
logger = get_logger("MAIN_PROMAX")

settings = get_settings()

driver = None
menu_page = None

hoje = datetime.now()
ontem = hoje - timedelta(days=1)
data_anterior = pd.Timestamp.now() - pd.offsets.BusinessDay(1)
ultimo_dia_util = data_anterior.strftime("%d-%m-%Y")

ano_atual = hoje.strftime("%Y")
mes_atual = hoje.strftime("%m")
mes_ano_atual = hoje.strftime("%m/%Y")
data_hoje_arquivo = hoje.strftime("%d-%m-%Y")
data_ontem_formatada = ontem.strftime("%d/%m/%Y")
data_hoje_formatada = hoje.strftime("%d/%m/%Y")
data_duas_semanas_atras_formatada = (hoje - timedelta(days=14)).strftime("%d/%m/%Y")
primeiro_dia_mes_atual = hoje.replace(day=1).strftime("%d/%m/%Y")
primeiro_dia_mes_atual_traco = hoje.replace(day=1).strftime("%d-%m-%Y")
ultimo_dia_util_mes_atual = data_anterior.strftime("%d/%m/%Y")

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


def _parse_iso_date(value, *, field_name):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{field_name} deve usar o formato YYYY-MM-DD.") from exc


def _normalize_list(values):
    normalized = []
    for value in values or []:
        for item in str(value).replace(";", ",").split(","):
            cleaned = item.strip()
            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)
    return normalized


def _primeira_unidade_geo(unidades_alvo):
    unidades = _normalize_list(unidades_alvo)
    return unidades[0] if unidades else "0640001"


def main(
    *,
    profile="fluxo_caixa",
    date_start=None,
    date_end=None,
    units=None,
    routines=None,
    publish=True,
    job_id="",
    download_workers=5,
    use_api_dates=True,
):
    logger.info("=== INICIANDO ROBÔ PROMAX (COM AUTO-RECOVERY) ===")
    requested_units = _normalize_list(units)
    requested_routines = _normalize_list(routines)
    requested_start = _parse_iso_date(date_start, field_name="data-inicial") if use_api_dates else None
    requested_end = _parse_iso_date(date_end, field_name="data-final") if use_api_dates else None
    if requested_start and requested_end and requested_start > requested_end:
        raise ValueError("data-inicial nao pode ser posterior a data-final.")
    if int(download_workers) < 1 or int(download_workers) > 8:
        raise ValueError("download-workers deve estar entre 1 e 8.")

    groups = load_report_groups()
    report_group, selected_routines = select_report_group(
        groups,
        profile or "fluxo_caixa",
        requested_routines,
    )
    report_start_text = requested_start.strftime("%d/%m/%Y") if requested_start else None
    report_end_text = requested_end.strftime("%d/%m/%Y") if requested_end else None
    logger.info(
        "Grupo de relatorios selecionado: %s (%s)",
        report_group.name,
        report_group.key,
    )
    if requested_start or requested_end:
        logger.info(
            "Periodo recebido pelo job: %s a %s. "
            "Os filtros informados substituirao as datas padrao das rotinas.",
            requested_start.isoformat() if requested_start else "-",
            requested_end.isoformat() if requested_end else "-",
        )
    elif not use_api_dates and (date_start or date_end):
        logger.info(
            "Datas externas ignoradas no modo local. Rotinas usarao suas datas padrao."
        )
    if job_id:
        logger.info("Job Promax controlado pelo bot_api: %s", job_id)

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
            nome_arquivo=f"{primeiro_dia_mes_atual_traco} (nUnidade) nomeUnidade0513",
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
            nome_arquivo=f"{primeiro_dia_mes_atual_traco} (nUnidade) 120616_nomeUnidade120616",
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
            ini_vencimento=report_start_text or primeiro_dia_mes_passado,
            fim_vencimento=report_end_text or data_ontem_formatada,
            ini_especie=4,
            fim_especie=4,
            nome_arquivo=f"{primeiro_dia_mes_atual_traco} 120601_nomeUnidade120601",
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
        page.subpasta_download = "150501"
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
            data_inicial=report_start_text or primeiro_dia_mes_atual,
            data_final=report_end_text or data_ontem_formatada,
            nome_arquivo=f"{mes_atual}-{ano_atual} nomeUnidade030237",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_030237_Giro(unidades_alvo=None):
        janela = menu_page.acessar_rotina("030237")
        page = Relatorio030237Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "030237 Giro"
        page.tracker_name = "Rotina 030237 Giro"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            quebra1="14",
            itens="s",
            data_inicial=report_start_text or primeiro_dia_mes_atual,
            data_final=report_end_text or data_hoje_formatada,
            nome_arquivo=f"{mes_atual}-{ano_atual} nomeUnidade030237",
        )
        page.fechar_e_voltar()
        return resultado
    
    def tarefa_030237_estoque(unidades_alvo=None):
        janela = menu_page.acessar_rotina("030237")
        page = Relatorio030237Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "030237 Estoque"
        page.tracker_name = "Rotina 030237 Estoque"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            quebra1="14",
            quebra2="16",
            itens="s",
            data_inicial=report_start_text or primeiro_dia_mes_passado,
            data_final=report_end_text or data_hoje_formatada,
            nome_arquivo=f"03,02,37_nomeUnidade030237estoque",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_020220_Auditool(unidades_alvo=None):
        janela = menu_page.acessar_rotina("020220")
        page = Relatorio020220Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "020220 Auditool"
        page.tracker_name = "Rotina 020220 Auditool"
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
        page.tracker_name = "Rotina 020220 Giro"
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
        page.tracker_name = "Rotina 020220 Recolhas"
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
    

    def tarefa_020502(unidades_alvo=None):
        janela = menu_page.acessar_rotina("020502")
        page = Relatorio020502Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "020502"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            opcao_rel="1",  
            listar_produtos=True,
            listar_vasilhames_garrafeiras=False,
            tipo_data="E",
            nome_arquivo="02,05,02_nomeUnidade020502",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_140506(unidades_alvo=None):
        janela = menu_page.acessar_rotina("140506")
        page = Relatorio140506Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "140506"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            opcao_rel="01",
            tipo_data="C",
            iniDat=report_start_text or primeiro_dia_mes_atual,
            fimDat=report_end_text or data_ontem_formatada,
            nome_arquivo="14,05,06_nUnidade",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_120606(unidades_alvo=None):
        janela = menu_page.acessar_rotina("120606")
        page = Relatorio120606Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "120606"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            opcao_rel="01",
            tpData="C",
            idTitulosNormais=True,
            iniDat=report_start_text or primeiro_dia_mes_atual,
            fimDat=report_end_text or data_ontem_formatada,
            nome_arquivo="12,06,06_nUnidade",
        )
        page.fechar_e_voltar()
        return resultado
    
    def tarefa_020502_fluxodecaixa(unidades_alvo=None):
        janela = menu_page.acessar_rotina("020502")
        page = Relatorio020502Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "020502 fluxo de caixa"
        page.tracker_name = "Rotina 020502 Fluxo de Caixa"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            opcao_rel="1",  
            listar_produtos=True,
            listar_vasilhames_garrafeiras=False,
            tipo_data="E",
            nome_arquivo="02,05,02_nUnidade",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_030206_bot(unidades_alvo=None):
        janela = menu_page.acessar_rotina("030206")
        page = Relatorio030206Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "030206 bot"
        page.tracker_name = "Rotina 030206 Bot"
        resultado = page.testar_pdf_intervalo_direto(
            unidade=unidades_alvo,
            banco="237",
            armazem="01",
            emissao_inicial=report_start_text or primeiro_dia_mes_passado,
            emissao_final=report_end_text or data_hoje_formatada,
            nome_arquivo="03,02,06.pdf",
        )
        page.fechar_e_voltar()
        return resultado
    
    def tarefa_150501_fluxodecaixa(unidades_alvo=None):
        janela = menu_page.acessar_rotina("150501")
        page = Relatorio150501Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "150501 fluxo de caixa"
        page.tracker_name = "Rotina 150501 Fluxo de Caixa"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            visao="01",
            periodo="M",
            mes_ano=mes_ano_atual,
            totaliza_periodo=True,
            nome_arquivo=f"{ano_atual}-{mes_atual} nomeUnidade150501",
        )
        page.fechar_e_voltar()
        return resultado
    
    def tarefa_120601_bot(unidades_alvo=None):
        janela = menu_page.acessar_rotina("120601")
        page = Relatorio120601Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "120601 bot"
        page.tracker_name = "Rotina 120601 Bot"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            opcao_rel="01",
            id_notas_tit_nao_atu=False,
            ini_especie=4,
            fim_especie=4,
            nome_arquivo=f"{primeiro_dia_mes_atual_traco} 120601_nomeUnidade120601",
        )
        page.fechar_e_voltar()
        return resultado
    
    def tarefa_020220_bot(unidades_alvo=None):
        janela = menu_page.acessar_rotina("020220")
        page = Relatorio020220Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "020220 bot"
        page.tracker_name = "Rotina 020220 Bot"
        unidade_geo = _primeira_unidade_geo(unidades_alvo)
        resultado = page.gerar_relatorio(
            unidade=unidade_geo,
            opcao_rel="01",
            mercadoria_todos=True,
            selecao_comodatos="T",
            cd_visao="2",
            nome_arquivo="020220 bot - nomeUnidade020220",
        )       
        page.fechar_e_voltar()
        return resultado

    def tarefa_0105070402_bot(unidades_alvo=None):
        janela = menu_page.acessar_rotina("0105070402")
        page = Relatorio0105070402Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "0105070402 bot"
        page.tracker_name = "Rotina 0105070402 Bot"
        resultado = page.gerar_relatorio(
            nome_arquivo="0105070402 bot - dClientes.csv",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_030111_bot(unidades_alvo=None):
        janela = menu_page.acessar_rotina("030111")
        page = Relatorio030111Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "030111 bot"
        page.tracker_name = "Rotina 030111 Bot"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            nome_arquivo="030111 bot - nomeUnidade030111",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_031702_bot(unidades_alvo=None):
        janela = menu_page.acessar_rotina("031702")
        page = Relatorio031702Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "031702 bot"
        page.tracker_name = "Rotina 031702 Bot"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            tipos_documento=["001", "003", "004", "005", "016", "019"],
            situacao_todos=True,
            toda_geografia=True,
            documentos_faltantes=True,
            nome_arquivo="031702 bot - nomeUnidade031702",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_020304_bot(unidades_alvo=None):
        janela = menu_page.acessar_rotina("020304")
        page = Relatorio020304Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "020304 bot"
        page.tracker_name = "Rotina 020304 Bot"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            nome_arquivo="020304 bot - nomeUnidade020304",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_031120_bot(unidades_alvo=None):
        janela = menu_page.acessar_rotina("031120")
        page = Relatorio031120Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "031120 bot"
        page.tracker_name = "Rotina 031120 Bot"
        resultado = page.gerar_relatorio(
            unidade=unidades_alvo,
            opcao_rel="1",
            data_inicial=report_start_text or data_duas_semanas_atras_formatada,
            data_final=report_end_text or data_hoje_formatada,
            cod_armazem="01",
            nome_arquivo="031120 bot - nomeUnidade031120",
        )
        page.fechar_e_voltar()
        return resultado

    def tarefa_03114902_bot(unidades_alvo=None):
        unidade_base = unidades_alvo[0] if isinstance(unidades_alvo, list) and unidades_alvo else unidades_alvo
        janela = menu_page.acessar_rotina("03114902")
        page = Relatorio03114902Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "03114902 bot"
        page.tracker_name = "Rotina 03114902 Geo Bot"
        resultado = page.gerar_relatorio(
            unidade=unidade_base,
            classificacao="Mapa",
            tipo_mapa_rota=True,
            tipo_mapa_as=True,
            todas_operacoes=True,
            mapas_roteirizados=True,
            data_inicial=report_start_text or data_duas_semanas_atras_formatada,
            data_final=report_end_text or data_hoje_formatada,
            roadshow_inicial="0",
            roadshow_final="99",
            transportadora_inicial="0",
            transportadora_final="999999",
            armazem="Todos",
            csv_geo=True,
            nome_arquivo="03114902 bot - geo.csv",
        )
        page.fechar_e_voltar()
        return resultado

    routine_runners = {
        "0513": tarefa_0513,
        "120616": tarefa_120616,
        "120601": tarefa_120601,
        "0512": tarefa_0512,
        "150501": tarefa_150501,
        "030237": tarefa_030237,
        "020220_AUDITOOL": tarefa_020220_Auditool,
        "020220_RECOLHAS": tarefa_020220_Recolhas,
        "030237_GIRO": tarefa_030237_Giro,
        "020220_GIRO": tarefa_020220_Giro,
        "030237_ESTOQUE": tarefa_030237_estoque,
        "020502": tarefa_020502,
        "140506": tarefa_140506,
        "120606": tarefa_120606,
        "020502_FLUXO_DE_CAIXA": tarefa_020502_fluxodecaixa,
        "150501_FLUXO_DE_CAIXA": tarefa_150501_fluxodecaixa,
        "030206_BOT": tarefa_030206_bot,
        "120601_BOT": tarefa_120601_bot,
        "020220_BOT": tarefa_020220_bot,
        "0105070402_BOT": tarefa_0105070402_bot,
        "030111_BOT": tarefa_030111_bot,
        "031702_BOT": tarefa_031702_bot,
        "020304_BOT": tarefa_020304_bot,
        "031120_BOT": tarefa_031120_bot,
        "03114902_BOT": tarefa_03114902_bot,
    }
    missing_runners = [
        routine.id
        for routine in selected_routines
        if routine.id not in routine_runners
    ]
    if missing_runners:
        raise ValueError(
            "Rotinas sem implementacao no entrypoint: " + ", ".join(missing_runners)
        )

    def bind_runner(runner):
        def selected_runner(retry_units=None):
            if retry_units is not None:
                return runner(retry_units)
            if requested_units:
                return runner(requested_units)
            return runner()

        return selected_runner

    tarefas = {
        routine.id: RoutineTask(
            key=routine.id,
            name=routine.name,
            runner=bind_runner(routine_runners[routine.id]),
        )
        for routine in selected_routines
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

    publication_mapping = {
            os.path.join(str(pasta_intermediaria), "0513"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Inadimplência\05.13",
            os.path.join(str(pasta_intermediaria), "120616"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Inadimplência\12.06.16",
            os.path.join(str(pasta_intermediaria), "120601"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Inadimplência\12.06.01",
            os.path.join(str(pasta_intermediaria), "0512"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\05.12\{ano_atual}",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_atual}-{mes_atual} Sousa.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\1. SOUSA",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_atual}-{mes_atual} Itaporanga.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\2. ITAPORANGA",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_atual}-{mes_atual} Patos.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\3. PATOS",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_atual}-{mes_atual} Sumé.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\4. SUMÉ",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_atual}-{mes_atual} Guarabira.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\5. GUARABIRA",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_atual}-{mes_atual} Brumado.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\6. BRUMADO",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_atual}-{mes_atual} Barra.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\7. BARRA",
            os.path.join(str(pasta_intermediaria), "150501", f"{ano_atual}-{mes_atual} Caculé.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\8. CACULÉ",
            os.path.join(str(pasta_intermediaria), "030237"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\ADF",
            os.path.join(str(pasta_intermediaria), "020220 Auditool"):fr"\\dc01n\publico_patos\ADMINISTRATIVO\FINANCEIRO\GERÊNCIA\Relatorios\02.02.20 - auditool",
            os.path.join(str(pasta_intermediaria), "020220 Recolhas"):fr"\\dc01n\publico_patos\ADMINISTRATIVO\FINANCEIRO\GERÊNCIA\Relatorios\02.02.20 - recolhas",
            os.path.join(str(pasta_intermediaria), "030237 Giro", f"{mes_atual}-{ano_atual} Sousa.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Giro\Fato\03.02.37\Total\{ano_atual}\01. Sousa",
            os.path.join(str(pasta_intermediaria), "030237 Giro", f"{mes_atual}-{ano_atual} Itaporanga.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Giro\Fato\03.02.37\Total\{ano_atual}\02. Itaporanga",
            os.path.join(str(pasta_intermediaria), "030237 Giro", f"{mes_atual}-{ano_atual} Patos.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Giro\Fato\03.02.37\Total\{ano_atual}\03. Patos",
            os.path.join(str(pasta_intermediaria), "030237 Giro", f"{mes_atual}-{ano_atual} Sumé.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Giro\Fato\03.02.37\Total\{ano_atual}\04. Sumé",
            os.path.join(str(pasta_intermediaria), "030237 Giro", f"{mes_atual}-{ano_atual} Guarabira.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Giro\Fato\03.02.37\Total\{ano_atual}\05. Guarabira",
            os.path.join(str(pasta_intermediaria), "030237 Giro", f"{mes_atual}-{ano_atual} Brumado.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Giro\Fato\03.02.37\Total\{ano_atual}\06. Brumado",
            os.path.join(str(pasta_intermediaria), "030237 Giro", f"{mes_atual}-{ano_atual} Barra.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Giro\Fato\03.02.37\Total\{ano_atual}\07. Barra",
            os.path.join(str(pasta_intermediaria), "030237 Giro", f"{mes_atual}-{ano_atual} Caculé.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Giro\Fato\03.02.37\Total\{ano_atual}\08. Caculé",
            os.path.join(str(pasta_intermediaria), "020220 Giro"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Giro\Fato\02.02.20",
            os.path.join(str(pasta_intermediaria), "030237 Estoque"): fr"\\dc01n\publico_patos\ADMINISTRATIVO\FINANCEIRO\GERÊNCIA\Relatorios\03.02.37\2026",
            os.path.join(str(pasta_intermediaria), "020502"): fr"\\dc01n\publico_patos\ADMINISTRATIVO\FINANCEIRO\GERÊNCIA\Relatorios\02.05.02",
            os.path.join(str(pasta_intermediaria), "140506"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Fluxo de Caixa\{ano_atual}\{mes_atual}. {nome_mes_atual}",
            os.path.join(str(pasta_intermediaria), "120606"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Fluxo de Caixa\{ano_atual}\{mes_atual}. {nome_mes_atual}",
            os.path.join(str(pasta_intermediaria), "020502 fluxo de caixa"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Fluxo de Caixa\{ano_atual}\{mes_atual}. {nome_mes_atual}",
            os.path.join(str(pasta_intermediaria), "150501 fluxo de caixa"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Fluxo de Caixa\{ano_atual}\{mes_atual}. {nome_mes_atual}",
            os.path.join(str(pasta_intermediaria), "030206 bot"): fr"\\dc01n\publico_patos\ADMINISTRATIVO\FINANCEIRO\Bot Zap\030206",
            os.path.join(str(pasta_intermediaria), "120601 bot"): fr"\\dc01n\publico_patos\ADMINISTRATIVO\FINANCEIRO\Bot Zap\120601",
            os.path.join(str(pasta_intermediaria), "020220 bot"): fr"\\dc01n\publico_patos\ADMINISTRATIVO\FINANCEIRO\Bot Zap\020220",
            os.path.join(str(pasta_intermediaria), "0105070402 bot"): fr"\\dc01n\publico_patos\ADMINISTRATIVO\FINANCEIRO\Bot Zap\0105070402",
            os.path.join(str(pasta_intermediaria), "030111 bot"): fr"\\dc01n\publico_patos\ADMINISTRATIVO\FINANCEIRO\Bot Zap\030111",
            os.path.join(str(pasta_intermediaria), "031702 bot"): fr"\\dc01n\publico_patos\ADMINISTRATIVO\FINANCEIRO\Bot Zap\031702",
            os.path.join(str(pasta_intermediaria), "020304 bot"): fr"\\dc01n\publico_patos\ADMINISTRATIVO\FINANCEIRO\Bot Zap\020304",
            os.path.join(str(pasta_intermediaria), "031120 bot"): fr"\\dc01n\publico_patos\ADMINISTRATIVO\FINANCEIRO\Bot Zap\031120",
            os.path.join(str(pasta_intermediaria), "03114902 bot"): fr"\\dc01n\publico_patos\ADMINISTRATIVO\FINANCEIRO\Bot Zap\03114902",


        }
    selected_output_folders = tuple(
        folder
        for routine in selected_routines
        for folder in routine.output_folders
    )

    def belongs_to_selected_output(source):
        try:
            relative_source = Path(source).relative_to(pasta_intermediaria)
        except ValueError:
            return False
        return any(
            relative_source == Path(folder) or Path(folder) in relative_source.parents
            for folder in selected_output_folders
        )

    publication_mapping = {
        source: destination
        for source, destination in publication_mapping.items()
        if belongs_to_selected_output(source)
    }

    publication_plan = PublicationPlan(
        mapping=publication_mapping if publish else {},
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
    result = orchestrator.run(
        tasks=tarefas,
        tracker_output_dir=LOGS_DIR / "relatorios_baixados",
        intermediate_dir=pasta_intermediaria,
        auxiliary_sheet=caminho_planilha_auxiliar,
        publication_plan=publication_plan,
        post_process_dirs=[pasta_intermediaria],
        automatic_repescagem=True,
        protect_artifacts_on_failure=True,
        download_workers=int(download_workers),
    )
    metadata = dict(result.metadata or {})
    metadata["publication_mapping"] = {
        str(source): str(destination)
        for source, destination in publication_mapping.items()
    }
    return ExecutionResult(
        status=result.status,
        message=result.message,
        retry=result.retry,
        metadata=metadata,
    )


def main_local(
    *,
    profile="fluxo_caixa",
    units=None,
    routines=None,
    publish=True,
    download_workers=5,
):
    return main(
        profile=profile,
        date_start=None,
        date_end=None,
        units=units,
        routines=routines,
        publish=publish,
        job_id="",
        download_workers=download_workers,
        use_api_dates=False,
    )

if __name__ == "__main__":
    main_local()
