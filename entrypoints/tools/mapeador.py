import os
import time
import dotenv
from datetime import datetime, timedelta

from core.browser.driver_factory import DriverFactory
from core.observability.logger import get_logger
from core.tools.mapeador import mapear_campos
from core.config.project_paths import LOGS_DIR, MAPS_DIR
from pages.auth.login_page import LoginPage


# Carrega variáveis de ambiente
dotenv.load_dotenv()

# Configuração de Logger e Datas
logger = get_logger("MAIN_PROMAX")

hoje = datetime.now()
ontem = hoje - timedelta(days=1)
primeiro_dia_mes = hoje.replace(day=1).strftime('%d/%m/%Y')
data_ontem_formatada = ontem.strftime('%d/%m/%Y')
hoje_formatada = hoje.strftime('%d/%m/%Y')
mes_atual = hoje.strftime('%m/%Y')

def main():
    logger.info("=== INICIANDO ROBÔ PROMAX ===")

    driver = None
    try:
        # 1. INICIALIZAÇÃO
        driver = DriverFactory.get_driver()
        driver.maximize_window()  # Opcional, o factory já maximiza nas options geralmente

        # 2. LOGIN
        login_page = LoginPage(driver)

        # Pega credenciais do .env
        usuario = os.getenv("PROMAX_USER")
        senha = os.getenv("PROMAX_PASS")

        menu_page = login_page.fazer_login(
            usuario, senha, nome_unidade="PATOS")

        logger.info("Login realizado com sucesso. Iniciando rotinas...")

        # --- ROTINA 5: 150501 --- OBZ
        logger.info(
            ">>> Iniciando Rotina 030104 - Lançamentos Detalhados OBZ")

        janela_rotina_5 = menu_page.acessar_rotina("030104")
        mapear_campos(janela_rotina_5.driver, str(MAPS_DIR / "mapa_030104.txt"))

        #relatorio_020220 = Relatorio020220Page(
         #   janela_rotina_5.driver, janela_rotina_5.handle_menu)

        #relatorio_030237.gerar_relatorio(quebra1="15", quebra1_final=1, quebra1_inicial=1, data_final=hoje_formatada, data_inicial=hoje_formatada, diretorio_destino=r"C:\Users\caixa.patos\Desktop\MAPEADOR", clicar_csv_apos_visualizar=True, timeout_csv=300, nome_arquivo="030237_OBZ.csv")

        #menu_page = relatorio_030237.fechar_e_voltar()


    except Exception as e:
        logger.critical(f"ERRO FATAL NA EXECUÇÃO: {e}", exc_info=True)
        # Screenshot de emergência
        if driver:
            try:
                driver.save_screenshot(str(LOGS_DIR / "erro_fatal_mainMapeador.png"))
                logger.info(
                    "Screenshot de erro salvo: erro_fatal_mainMapeador.png")
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

