import os
import time
import dotenv
import datetime as dt  # Importação com apelido para evitar conflitos

from selenium.common.exceptions import (
    UnexpectedAlertPresentException, 
    NoSuchWindowException, 
    WebDriverException,
    TimeoutException
)
from core.driver_factory import DriverFactory
from core.logger import get_logger
from core.relatorio_execucao import tracker
from pages.login_page import LoginPage
from pages.rotinas.processo_030104_page import Processo030104Page

dotenv.load_dotenv()
logger = get_logger("MAIN_PEDIDOS")

driver = None
menu_page = None

def iniciar_sessao():
    global driver, menu_page
    if driver:
        try: driver.quit()
        except: pass

    logger.info(">>> Iniciando sessão (Browser + Login)...")
    driver = DriverFactory.get_driver()
    driver.maximize_window()

    login_page = LoginPage(driver)
    usuario = os.getenv("PROMAX_USER")
    senha = os.getenv("PROMAX_PASS")
    
    menu_page = login_page.fazer_login(usuario, senha, nome_unidade="PATOS")
    logger.info("Sessão autenticada com sucesso.")
    return driver, menu_page

def main():
    global driver, menu_page
    logger.info("=== ROBÔ DE DIGITAÇÃO 030104 | UNIDADE PATOS ===")
    
    caminho_planilha = r"C:\Users\caixa.patos\Desktop\pedidos.xlsx"
    if not os.path.exists(caminho_planilha):
        logger.error(f"Arquivo não encontrado: {caminho_planilha}")
        return

    pasta_logs = os.path.join(os.getcwd(), "logs", "pedidos")
    os.makedirs(pasta_logs, exist_ok=True)

    # CORREÇÃO AQUI: Usando o apelido dt para acessar a classe datetime
    data_atual = dt.datetime.now().strftime('%Y%m%d')
    caminho_log_itens = os.path.join(pasta_logs, f"Detalhes_Itens_{data_atual}.csv")

    leitor = Processo030104Page(None, None) 
    pedidos_agrupados = leitor.ler_planilha_pedidos(caminho_planilha)
    
    if not pedidos_agrupados:
        logger.warning("Nenhum pedido processável encontrado.")
        return

    try:
        iniciar_sessao()
        
        for pedido in pedidos_agrupados:
            mapa = pedido.get('mapa', '0')
            cliente = pedido.get('cliente', 'Desconhecido')
            identificador = f"Mapa {mapa} | Cli {cliente}"
            
            tentativas = 2
            for tentativa in range(1, tentativas + 1):
                inicio_timer = time.time()
                
                try:
                    janela = menu_page.acessar_rotina("030104")
                    page_pedido = Processo030104Page(janela.driver, janela.handle_menu)
                    
                    logger.info(f"--- {identificador} (Tentativa {tentativa}/{tentativas}) ---")
                    
                    sucesso, resumo = page_pedido.digitar_pedido_completo(pedido, caminho_log_itens)
                    
                    status_final = "SUCESSO" if sucesso else "FALHA"
                    duracao = time.time() - inicio_timer
                    tracker.anotar("030104 - Digitação", identificador, status_final, resumo, duracao)
                    break 

                except (NoSuchWindowException, WebDriverException) as e_infra:
                    logger.warning(f"⚠️ Erro de infraestrutura: {e_infra}")
                    if tentativa < tentativas:
                        logger.info("Reiniciando navegador para auto-recuperação...")
                        iniciar_sessao()
                    else:
                        tracker.anotar("030104", identificador, "ERRO CRÍTICO", "Navegador caiu.", 0)

                except UnexpectedAlertPresentException as e_alert:
                    msg_erro = str(e_alert.alert_text)
                    logger.error(f"❌ Alerta do Promax: {msg_erro}")
                    duracao = time.time() - inicio_timer
                    tracker.anotar("030104", identificador, "FALHA SISTEMA", msg_erro, duracao)
                    
                    try: page_pedido.driver.execute_script("Cancelar();")
                    except: pass
                    break

                except Exception as e_inesperado:
                    duracao = time.time() - inicio_timer
                    logger.error(f"Erro inesperado no {identificador}: {e_inesperado}")
                    tracker.anotar("030104", identificador, "ERRO TÉCNICO", str(e_inesperado), duracao)
                    break

    except Exception as e_fatal:
        logger.critical(f"FALHA IRRECUPERÁVEL: {e_fatal}", exc_info=True)
    
    finally:
        if driver:
            try: driver.quit()
            except: pass
        
        try:
            tracker.gerar_csv(pasta_logs)
            logger.info("Processo finalizado.")
        except Exception as e:
            logger.error(f"Erro ao salvar resumo: {e}")

if __name__ == "__main__":
    main()