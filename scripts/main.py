import os
import time
import sys
import dotenv

# garante import do projeto quando rodar via scripts/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.logger import get_logger
from core.driver_factory import abrir_ie_driver
from core.promax_login import fazer_login_promax
from core.acessar_rotina import acessar_rotina_atalho, voltar_pro_menu
from rotinas.r0105070402 import gerar_0105070401
from core.auxs.mapear_campos import mapear_campos
from datetime import date
from rotinas.r030237 import gerar_030237

dotenv.load_dotenv()  # <-- faltava o ()

logger = get_logger("PROMAX")
hoje = date.today()
primeiro_dia_mes = hoje.replace(day=1)

data_inicial = hoje.strftime("%d/%m/%Y")
data_final = hoje.strftime("%d/%m/%Y")

if __name__ == "__main__":
    PROMAX_USER = os.getenv("PROMAX_USER")
    PROMAX_PASS = os.getenv("PROMAX_PASS")

    logger.info("=== INICIANDO ROBÔ PROMAX ===")

    driver = None
    try:
        driver = abrir_ie_driver()
        driver.maximize_window()
        logger.info("Driver iniciado e janela maximizada")

        ok = fazer_login_promax(driver, PROMAX_USER, PROMAX_PASS, nome_unidade="SUME")

        if ok:
            logger.info("Login OK. Iniciando automações...")
            acessar_rotina_atalho(driver, "030237")
            gerar_030237(
            driver,
            quebra1_inicial=1,
            quebra1_final=1,
            data_inicial=data_inicial,
            data_final=data_final,
            quebra1=15,       # com itens
            acao="BotVisualizar",
            nome_arquivo="030237_quick.csv"
            )
            voltar_pro_menu(driver)
            acessar_rotina_atalho(driver, "0105070402")
            gerar_0105070401(driver)
            voltar_pro_menu(driver)

            #mapear_campos(driver, nome_arquivo="mapa_030237.txt")
            #voltar_pro_menu(driver)
            #time.sleep(160)

            logger.info("Fluxo concluído com sucesso.")
        else:
            logger.error("Login falhou, verifique os logs gerados.")

    except Exception:
        logger.exception("Erro fatal na execução")  # stacktrace completo no log

    finally:
        logger.info("Finalizando driver em 10 segundos...")
        time.sleep(10)

        if driver:
            try:
                driver.quit()
                logger.info("Driver finalizado.")
            except Exception:
                logger.exception("Falha ao finalizar o driver")
