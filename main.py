import os
import time
import dotenv
from datetime import date

from core.driver_factory import DriverFactory
from core.logger import get_logger
from pages.login_page import LoginPage
from pages.rotinas.relatorio_030237_page import Relatorio030237Page
from pages.rotinas.relatorio_0105070402_page import Relatorio0105070402Page


# Carrega variáveis de ambiente
dotenv.load_dotenv()

# Configuração de Logger e Datas
logger = get_logger("MAIN_PROMAX")
hoje = date(2026,2,9) # ou force uma data: date(2026, 2, 9)
data_formatada = hoje.strftime("%d/%m/%Y")

def main():
    logger.info("=== INICIANDO ROBÔ PROMAX ===")
    
    driver = None
    try:
        # 1. INICIALIZAÇÃO
        driver = DriverFactory.get_driver()
        driver.maximize_window() # Opcional, o factory já maximiza nas options geralmente

        # 2. LOGIN
        # Instancia a página de login
        login_page = LoginPage(driver)
        
        # Pega credenciais do .env
        usuario = os.getenv("PROMAX_USER")
        senha = os.getenv("PROMAX_PASS")
        
        menu_page = login_page.fazer_login(usuario, senha, nome_unidade="SUME")
        
        logger.info("Login realizado com sucesso. Iniciando rotinas...")

        # --- ROTINA 1: 030237 ---
        logger.info(">>> Iniciando Rotina 030237")
        
        # Acessa a rotina e faz o 'Cast' para a classe específica
        janela_rotina_1 = menu_page.acessar_rotina("030237")
        relatorio_030237 = Relatorio030237Page(janela_rotina_1.driver, janela_rotina_1.handle_menu)
       
        relatorio_030237.gerar_relatorio(
            data_inicial=data_formatada,
            data_final=data_formatada,
            quebra1="15",     # Exemplo: Vendedor/Itens (verifique o código correto no HTML)
            quebra1_inicial="1",
            quebra1_final="1",
            nome_arquivo="030237_quick.csv",
        )
        
        menu_page = relatorio_030237.fechar_e_voltar()
        
        # --- ROTINA 2: 0105070402 ---
        logger.info(">>> Iniciando Rotina 0105070402")

        janela_rotina_2 = menu_page.acessar_rotina("0105070402") 
        relatorio_0105070402 = Relatorio0105070402Page(janela_rotina_2.driver, janela_rotina_2.handle_menu)
        
        relatorio_0105070402.gerar_relatorio(
            nome_arquivo="0105070402.csv",
            timeout_processamento=420 # 7 minutos
        )
        
        menu_page = relatorio_0105070402.fechar_e_voltar()

        logger.info("Fluxo concluído com sucesso!")
        
    except Exception as e:
        logger.critical(f"ERRO FATAL NA EXECUÇÃO: {e}", exc_info=True)
        # Screenshot de emergência
        if driver:
            try:
                driver.save_screenshot("logs\erro_fatal_main.png")
                logger.info("Screenshot de erro salvo: erro_fatal_main.png")
            except:
                pass

    finally:
        logger.info("Finalizando driver em 5 segundos...")
        time.sleep(5)
        if driver:
            try:
                driver.quit()
                logger.info("Driver encerrado.")
            except Exception:
                pass

if __name__ == "__main__":
    main()