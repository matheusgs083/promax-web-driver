import os
import dotenv

from selenium import webdriver
from selenium.webdriver.ie.service import Service as IEService
from selenium.webdriver.ie.options import Options as IEOptions
from webdriver_manager.microsoft import IEDriverManager

from core.logger import get_logger
logger = get_logger(__name__)

dotenv.load_dotenv()

def abrir_ie_driver():
    ie_options = IEOptions()

    # Configurações para Windows 11 / Modo IE
    ie_options.add_additional_option("ie.edgechromium", True)
    ie_options.add_additional_option("ie.edgepath", os.getenv("EDGE_PATH"))

    ie_options.attach_to_edge_chrome = False
    ie_options.force_create_process_api = True
    ie_options.ensure_clean_session = False  # Mantém dados de navegação
    ie_options.ignore_protected_mode_settings = True
    ie_options.ignore_zoom_level = True
    ie_options.require_window_focus = True
    ie_options.page_load_strategy = "none"

    caminho_local = os.getenv("DRIVER_PATH")

    if caminho_local and os.path.exists(caminho_local):
        try:
            logger.info("Iniciando com driver local: %s", caminho_local)
            service = IEService(executable_path=caminho_local)
            driver = webdriver.Ie(service=service, options=ie_options)
            logger.info("IEDriver iniciado com sucesso (local).")
            return driver
        except Exception:
            logger.exception("Falha ao usar driver local: %s", caminho_local)

    # Fallback para driver da web
    try:
        logger.warning("Driver local não disponível. Tentando baixar driver automaticamente via webdriver_manager...")
        driver_path = IEDriverManager().install()
        logger.info("Driver baixado/encontrado em: %s", driver_path)

        service_web = IEService(driver_path)
        driver = webdriver.Ie(service=service_web, options=ie_options)
        logger.info("IEDriver iniciado com sucesso (webdriver_manager).")
        return driver

    except Exception:
        logger.exception("Falha ao iniciar IEDriver via webdriver_manager.")
        raise
