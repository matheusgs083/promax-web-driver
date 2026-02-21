import os
import time
import dotenv
from datetime import datetime, timedelta

from selenium.common.exceptions import UnexpectedAlertPresentException, NoSuchWindowException, WebDriverException
from core.driver_factory import DriverFactory
from core.logger import get_logger
from pages.login_page import LoginPage

# Importação das Rotinas
from pages.rotinas.relatorio_030237_page import Relatorio030237Page
from pages.rotinas.relatorio_120601_page import Relatorio120601Page
from pages.rotinas.relatorio_0513_page import Relatorio0513Page
from pages.rotinas.relatorio_120616_page import Relatorio120616Page
from pages.rotinas.relatorio_0512_page import Relatorio0512Page
from pages.rotinas.relatorio_150501_page import Relatorio150501Page

# Carrega variáveis
dotenv.load_dotenv()
logger = get_logger("MAIN_PROMAX")

# --- VARIÁVEIS GLOBAIS DE CONTROLE ---
driver = None
menu_page = None

# --- DATAS ---
hoje = datetime.now()
ontem = hoje - timedelta(days=1)
primeiro_dia_mes = hoje.replace(day=1).strftime('%d/%m/%Y')
data_ontem_formatada = ontem.strftime('%d/%m/%Y')
mes_ano_hoje = hoje.strftime("%m/%Y")
ano_atual = hoje.strftime('%Y')
mes_atual = hoje.strftime('%m')


def iniciar_sessao():
    """
    Função auxiliar responsável apenas por abrir o navegador e logar.
    Retorna: driver (novo) e menu_page (novo)
    """
    global driver, menu_page
    
    # Se já existir um driver aberto (mas quebrado), tenta fechar
    if driver:
        try: driver.quit()
        except: pass

    logger.info(">>> Iniciando nova sessão (Browser + Login)...")
    driver = DriverFactory.get_driver()
    driver.maximize_window()

    login_page = LoginPage(driver)
    usuario = os.getenv("PROMAX_USER")
    senha = os.getenv("PROMAX_PASS")
    
    # Faz o login e retorna a página de menu atualizada
    menu_page = login_page.fazer_login(usuario, senha, nome_unidade="PATOS")
    logger.info("Sessão iniciada com sucesso.")
    return driver, menu_page


def executar_tarefa_com_retry(nome_tarefa, funcao_logica, tentativas=3):
    """
    Wrapper que executa uma função lógica. Se der erro de sessão,
    ele refaz o login e tenta de novo.
    """
    global driver, menu_page

    for tentativa in range(1, tentativas + 1):
        try:
            logger.info(f"--- Executando: {nome_tarefa} (Tentativa {tentativa}/{tentativas}) ---")
            
            # Se por acaso o driver não existir (primeira execução), cria
            if not driver:
                iniciar_sessao()

            # Executa a lógica do relatório (passada via lambda/função)
            funcao_logica()
            
            logger.info(f"Status: {nome_tarefa} CONCLUÍDA.")
            return True # Sucesso, sai da função

        except (UnexpectedAlertPresentException, NoSuchWindowException, WebDriverException) as e:
            msg_erro = str(e)
            logger.warning(f"Falha na {nome_tarefa}: {msg_erro}")

            # Verifica se é erro de sessão ou queda do browser
            erros_de_sessao = ["Sessão inválida", "Unable to get browser", "no such window"]
            eh_erro_critico = any(txt in msg_erro for txt in erros_de_sessao)

            if eh_erro_critico and tentativa < tentativas:
                logger.warning("Detecção de queda de sessão! Iniciando protocolo de Re-login...")
                try:
                    # Força reinício completo do ambiente
                    iniciar_sessao() 
                except Exception as e_login:
                    logger.critical(f"Não foi possível fazer o re-login: {e_login}")
                    raise e_login
            else:
                # Se não for erro de sessão ou acabaram as tentativas, explode o erro real
                logger.error(f"Erro irrecuperável na {nome_tarefa}.")
                raise e

def main():
    logger.info("=== INICIANDO ROBÔ PROMAX (COM AUTO-RECOVERY) ===")

    try:
        # Inicializa primeira vez
        iniciar_sessao()

        # -----------------------------------------------------------
        # DEFINIÇÃO DAS TAREFAS (Encapsuladas em funções locais)
        # -----------------------------------------------------------

        def tarefa_0513():
            janela = menu_page.acessar_rotina("0513")
            page = Relatorio0513Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                opcao_rel="12", volume_fin="F", tp_equipe="A", 
                mes_ano_inicial=mes_ano_hoje, mes_ano_final=mes_ano_hoje, 
                quantos_clientes="99999", nome_arquivo=f"{hoje.strftime('%d-%m-%Y')} (nUnidade) nomeUnidade0513"
            )
            page.fechar_e_voltar()

        def tarefa_120616():
            janela = menu_page.acessar_rotina("120616")
            page = Relatorio120616Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(opcao_rel="3", mes_ano=mes_ano_hoje, nome_arquivo=f"{hoje.strftime('%d-%m-%Y')} (nUnidade) 12.06.16_nomeUnidade120616")
            page.fechar_e_voltar()

        def tarefa_120601():
            janela = menu_page.acessar_rotina("120601")
            page = Relatorio120601Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                opcao_rel="01", id_notas_tit_nao_atu=False, 
                ini_vencimento=primeiro_dia_mes, fim_vencimento=data_ontem_formatada, 
                ini_especie=4, fim_especie=4, nome_arquivo=f"{hoje.strftime('%d-%m-%Y')} (nUnidade) 12.06.01_nomeUnidade120601"
            )
            page.fechar_e_voltar()

        def tarefa_0512():
            janela = menu_page.acessar_rotina("0512")
            page = Relatorio0512Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(opcao_rel="11", ano=ano_atual, id_converte_hecto=True, nome_arquivo=f"05.12 {ano_atual} nomeUnidade0512")
            page.fechar_e_voltar()

        def tarefa_150501():
            janela = menu_page.acessar_rotina("150501")
            page = Relatorio150501Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(periodo="M", mes_ano=mes_ano_hoje, totaliza_periodo=True, nome_arquivo=f"{ano_atual}-{mes_atual} nomeUnidade150501")
            page.fechar_e_voltar()

        def tarefa_030237():
            janela = menu_page.acessar_rotina("030237")
            page = Relatorio030237Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                quebra1="14", quebra2="12", quebra3="16", 
                data_inicial=primeiro_dia_mes, data_final=data_ontem_formatada, nome_arquivo=f"{mes_atual}-{ano_atual} nomeUnidade030237"
            )
            page.fechar_e_voltar()

        # -----------------------------------------------------------
        # EXECUÇÃO SEQUENCIAL PROTEGIDA
        # -----------------------------------------------------------
        
        # Agora chamamos cada tarefa através do wrapper com retry
        executar_tarefa_com_retry("Rotina 0513", tarefa_0513)
        executar_tarefa_com_retry("Rotina 120616", tarefa_120616)
        executar_tarefa_com_retry("Rotina 120601", tarefa_120601)
        executar_tarefa_com_retry("Rotina 0512", tarefa_0512)
        executar_tarefa_com_retry("Rotina 150501", tarefa_150501)
        executar_tarefa_com_retry("Rotina 030237", tarefa_030237)

        logger.info("=== FLUXO TOTAL CONCLUÍDO ===")

    except Exception as e:
        logger.critical(f"ERRO FATAL NÃO RECUPERÁVEL: {e}", exc_info=True)
    
    finally:
        logger.info("Finalizando execução...")
        if driver:
            try: driver.quit()
            except: pass

if __name__ == "__main__":
    main()