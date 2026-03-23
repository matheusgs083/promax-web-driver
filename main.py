import os
import time
import glob
import dotenv
from datetime import datetime, timedelta

from selenium.common.exceptions import UnexpectedAlertPresentException, NoSuchWindowException, WebDriverException
from core.driver_factory import DriverFactory
from core.execution_result import normalize_execution_result
from core.logger import get_logger
from core.relatorio_execucao import tracker
from core.settings import get_settings
from pages.login_page import LoginPage

# --- IMPORTAÇÃO DO RENOMEADOR E MOVIMENTADOR ---
from core.renomeador import limpar_nomes_relatorios
from core.movimentador import mover_relatorios

# Importação das Rotinas
from pages.rotinas.relatorio_030237_page import Relatorio030237Page
from pages.rotinas.relatorio_120601_page import Relatorio120601Page
from pages.rotinas.relatorio_0513_page import Relatorio0513Page
from pages.rotinas.relatorio_120616_page import Relatorio120616Page
from pages.rotinas.relatorio_0512_page import Relatorio0512Page
from pages.rotinas.relatorio_150501_page import Relatorio150501Page
from pages.rotinas.relatorio_020220_page import Relatorio020220Page

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
    if driver:
        try: driver.quit()
        except: pass

    logger.info(">>> Iniciando nova sessão para Repescagem...")
    driver = DriverFactory.get_driver()
    driver.maximize_window()
    login_page = LoginPage(driver)
    usuario = settings.promax_user
    senha = settings.promax_pass
    
    menu_page = login_page.fazer_login(usuario, senha, nome_unidade=settings.unidade_relatorios)
    logger.info("Sessão iniciada com sucesso.")
    return driver, menu_page


def executar_tarefa_com_retry(nome_tarefa, funcao_logica, tentativas=3, espera_segundos=3):
    global driver, menu_page

    for tentativa in range(1, tentativas + 1):
        try:
            logger.info(f"--- Executando: {nome_tarefa} (Tentativa {tentativa}/{tentativas}) ---")
            if not driver: iniciar_sessao()
            resultado = normalize_execution_result(
                funcao_logica(),
                success_message=f"{nome_tarefa} concluída com sucesso",
                failure_message=f"{nome_tarefa} retornou falha sem detalhamento",
            )

            if resultado.ok:
                logger.info(f"Status: {nome_tarefa} CONCLUÍDA. Detalhe: {resultado.message}")
                return resultado

            logger.warning(
                f"{nome_tarefa} retornou status '{resultado.status.value}'. "
                f"Detalhe: {resultado.message}"
            )

            if tentativa < tentativas and resultado.should_retry:
                logger.warning(
                    f"Nova tentativa agendada para {nome_tarefa} em {espera_segundos}s "
                    f"por retorno de execução não conclusivo."
                )
                time.sleep(espera_segundos)
                continue

            raise RuntimeError(f"{nome_tarefa} finalizou com status '{resultado.status.value}': {resultado.message}")

        except (UnexpectedAlertPresentException, NoSuchWindowException, WebDriverException) as e:
            msg_erro = str(e)
            logger.warning(f"Falha na {nome_tarefa}: {msg_erro}")

            erros_de_sessao = ["Sessão inválida", "Unable to get browser", "no such window", "Timed out", "timeout"]
            eh_erro_critico = any(txt in msg_erro for txt in erros_de_sessao)

            if eh_erro_critico and tentativa < tentativas:
                logger.warning("Detecção de queda de sessão! Iniciando protocolo de Re-login...")
                try: iniciar_sessao() 
                except Exception as e_login:
                    logger.critical(f"Não foi possível fazer o re-login: {e_login}")
                    raise e_login
            else:
                logger.error(f"Erro irrecuperável na {nome_tarefa}.")
                raise e

def main():
    logger.info("=== INICIANDO ROBÔ DE REPESCAGEM PROMAX ===")

    try:
        iniciar_sessao()

        # -----------------------------------------------------------
        # DEFINIÇÃO DAS TAREFAS
        # -----------------------------------------------------------

        def tarefa_120616(unidades_alvo=None):
            janela = menu_page.acessar_rotina("120616")
            page = Relatorio120616Page(janela.driver, janela.handle_menu)
            resultado = page.gerar_relatorio(
                unidade=unidades_alvo, 
                opcao_rel="3", mes_ano=mes_ano_passado, 
                nome_arquivo=f"{ultimo_dia_mes_passado.replace('/','-')} (nUnidade) 120616_nomeUnidade120616"
            )
            page.fechar_e_voltar()
            return resultado

        def tarefa_0512(unidades_alvo=None):
            janela = menu_page.acessar_rotina("0512")
            page = Relatorio0512Page(janela.driver, janela.handle_menu)
            resultado = page.gerar_relatorio(
                unidade=unidades_alvo,
                opcao_rel="11", ano=ano_atual, id_converte_hecto=True, 
                nome_arquivo=f"0512 {ano_atual} nomeUnidade0512"
            )
            page.fechar_e_voltar()
            return resultado

        def tarefa_150501(unidades_alvo=None):
            janela = menu_page.acessar_rotina("150501")
            page = Relatorio150501Page(janela.driver, janela.handle_menu)
            resultado = page.gerar_relatorio(
                unidade=unidades_alvo,
                periodo="M", mes_ano=mes_ano_passado, totaliza_periodo=True, 
                nome_arquivo=f"{ano_mes_passado}-{mes_passado} nomeUnidade150501"
            )
            page.fechar_e_voltar()
            return resultado

        def tarefa_030237(unidades_alvo=None):
            janela = menu_page.acessar_rotina("030237")
            page = Relatorio030237Page(janela.driver, janela.handle_menu)
            resultado = page.gerar_relatorio(
                unidade=unidades_alvo,
                quebra1="14", quebra2="12", quebra3="16", 
                data_inicial=primeiro_dia_mes_passado, data_final=ultimo_dia_mes_passado, 
                nome_arquivo=f"{mes_passado}-{ano_mes_passado} nomeUnidade030237"
            )
            page.fechar_e_voltar()
            return resultado

        # -----------------------------------------------------------
        # MAPEAMENTO DOS ALVOS DA REPESCAGEM
        # -----------------------------------------------------------
        repescagem_alvos = {
            "Relatório 120616": (tarefa_120616, ["2210004"]),
            "Relatório 0512": (tarefa_0512, ["3610006"]),
            "Relatório 150501": (tarefa_150501, ["3610007"]),
            "Relatório 030237": (tarefa_030237, ["640001", "640002", "3480005", "3610006", "3610007", "3610008"]),
        }

        logger.info("================ FASE ÚNICA: REPESCAGEM MANUAL ===============")
        for nome_rotina, (func, unidades_com_erro) in repescagem_alvos.items():
            logger.info(f">>> Executando {nome_rotina} apenas para as unidades: {unidades_com_erro}")
            
            # Injeta a lista de unidades específicas na função
            func_repescagem = lambda r=nome_rotina, f=func, u=unidades_com_erro: f(unidades_alvo=u)
            executar_tarefa_com_retry(f"{nome_rotina} (REPESCAGEM)", func_repescagem)

        logger.info("=== FLUXO TOTAL DE REPESCAGEM CONCLUÍDO ===")

    except Exception as e:
        logger.critical(f"ERRO FATAL NÃO RECUPERÁVEL: {e}", exc_info=True)
    
    finally:
        logger.info("Finalizando execução e limpando navegador...")
        if driver:
            try: driver.quit()
            except: pass

        # --- HIGIENIZAÇÃO DE NOMES ---
        pasta_destino = str(settings.download_dir)
        try:
            pasta_data = os.path.join(os.getcwd(), "data")
            arquivos_excel = [f for f in glob.glob(os.path.join(pasta_data, "*.xlsx")) if not os.path.basename(f).startswith("~$")]
            
            if arquivos_excel:
                caminho_planilha_auxiliar = arquivos_excel[0]
                limpar_nomes_relatorios(pasta_destino, caminho_planilha_auxiliar)
            else:
                logger.error("Planilha auxiliar Excel não encontrada na pasta 'data'. Higienização ignorada.")
        except Exception as e:
            logger.error(f"Falha ao executar a limpeza de nomes e organização de pastas: {e}")

        # --- MOVIMENTAÇÃO FINAL DE ARQUIVOS ---
        try:
            logger.info("Iniciando movimentação de arquivos/pastas finais de repescagem...")
            pasta_origem_base = pasta_destino

            meses_pt = {
                '01': 'JANEIRO', '02': 'FEVEREIRO', '03': 'MARÇO', '04': 'ABRIL',
                '05': 'MAIO', '06': 'JUNHO', '07': 'JULHO', '08': 'AGOSTO',
                '09': 'SETEMBRO', '10': 'OUTUBRO', '11': 'NOVEMBRO', '12': 'DEZEMBRO'
            }
            nome_mes_passado = meses_pt[mes_passado]
            
            mapeamento_movimentacao = {
                # INAD
                os.path.join(pasta_origem_base, "0513"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Inadimplência\05.13\{ano_mes_passado}\{mes_passado}. {nome_mes_passado}",
                os.path.join(pasta_origem_base, "120616"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Inadimplência\12.06.16\{ano_mes_passado}\{mes_passado}. {nome_mes_passado}",
                os.path.join(pasta_origem_base, "120601"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Inadimplência\12.06.01\{ano_mes_passado}\{mes_passado}. {nome_mes_passado}",

                # OBZ - 0512
                os.path.join(pasta_origem_base, "0512"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\05.12\{ano_atual}",

                # OBZ - 150501
                os.path.join(pasta_origem_base, "150501", f"{ano_mes_passado}-{mes_passado} Sousa.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\1. SOUSA",
                os.path.join(pasta_origem_base, "150501", f"{ano_mes_passado}-{mes_passado} Itaporanga.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\2. ITAPORANGA",
                os.path.join(pasta_origem_base, "150501", f"{ano_mes_passado}-{mes_passado} Patos.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\3. PATOS",
                os.path.join(pasta_origem_base, "150501", f"{ano_mes_passado}-{mes_passado} Sumé.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\4. SUMÉ",
                os.path.join(pasta_origem_base, "150501", f"{ano_mes_passado}-{mes_passado} Guarabira.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\5. GUARABIRA",
                os.path.join(pasta_origem_base, "150501", f"{ano_mes_passado}-{mes_passado} Brumado.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\6. BRUMADO",
                os.path.join(pasta_origem_base, "150501", f"{ano_mes_passado}-{mes_passado} Barra.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\7. BARRA",
                os.path.join(pasta_origem_base, "150501", f"{ano_mes_passado}-{mes_passado} Caculé.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\8. CACULÉ",

                # ADF
                os.path.join(pasta_origem_base, "030237"): r"\\dc01n\PUBLICO\REVENDA\Power BI\ADF",

                # 020220
                os.path.join(pasta_origem_base, "020220"): r"M:\ADMINISTRATIVO\FINANCEIRO\GERÊNCIA\Relatorios\02.02.20 - Recolhas"
            }

            for origem, destino in mapeamento_movimentacao.items():
                logger.info(f"Movendo: {origem} -> {destino}")
                mover_relatorios(origem, destino)

            logger.info("Movimentação concluída com sucesso.")
            
        except Exception as e:
            logger.error(f"Falha ao mover arquivos/pastas: {e}")

if __name__ == "__main__":
    main()
