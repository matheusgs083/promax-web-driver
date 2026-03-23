import os
import subprocess

import dotenv
from selenium import webdriver
from selenium.webdriver.ie.options import Options as IEOptions
from selenium.webdriver.ie.service import Service as IEService
from webdriver_manager.microsoft import IEDriverManager

from core.logger import get_logger
from core.settings import get_settings


dotenv.load_dotenv()
logger = get_logger(__name__)


class DriverFactory:
    @staticmethod
    def _limpar_processos_zumbis():
        """
        Faz uma limpeza conservadora antes de iniciar o driver.

        Por padrao, finaliza apenas IEDriverServer.exe, evitando encerrar
        navegadores do usuario fora do escopo do robo. Se necessario,
        PROMAX_DRIVER_CLEANUP_MODE=aggressive reabilita a limpeza ampla.
        """
        modo_limpeza = os.getenv("PROMAX_DRIVER_CLEANUP_MODE", "safe").strip().lower()
        if modo_limpeza == "aggressive":
            processos = ["IEDriverServer.exe", "iexplore.exe", "msedge.exe"]
            logger.warning(
                "Limpeza agressiva habilitada por PROMAX_DRIVER_CLEANUP_MODE=aggressive."
            )
        else:
            processos = ["IEDriverServer.exe"]
            logger.info("Limpeza segura habilitada. Apenas IEDriverServer sera finalizado.")

        create_no_window = 0x08000000
        for proc in processos:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", proc, "/T"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=create_no_window,
                    check=False,
                )
            except Exception as e:
                logger.debug("Nao foi possivel finalizar '%s' na limpeza pre-driver: %s", proc, e)

    @staticmethod
    def get_driver():
        settings = get_settings()
        DriverFactory._limpar_processos_zumbis()

        ie_options = IEOptions()
        ie_options.add_additional_option("ie.edgechromium", True)
        ie_options.add_additional_option("ie.edgepath", settings.edge_path)

        ie_options.attach_to_edge_chrome = False
        ie_options.force_create_process_api = True
        ie_options.ensure_clean_session = False
        ie_options.ignore_protected_mode_settings = True
        ie_options.ignore_zoom_level = True
        ie_options.require_window_focus = True
        ie_options.page_load_strategy = "none"

        caminho_local = settings.driver_path

        if caminho_local and os.path.exists(caminho_local):
            try:
                logger.info("Iniciando com driver local: %s", caminho_local)
                service = IEService(executable_path=caminho_local)
                driver = webdriver.Ie(service=service, options=ie_options)
                logger.info("IEDriver iniciado com sucesso (local).")
                return driver
            except Exception:
                logger.exception("Falha ao usar driver local: %s", caminho_local)

        try:
            logger.warning("Driver local nao disponivel. Tentando baixar via webdriver_manager...")
            driver_path = IEDriverManager().install()
            logger.info("Driver baixado/encontrado em: %s", driver_path)

            service_web = IEService(driver_path)
            driver = webdriver.Ie(service=service_web, options=ie_options)
            logger.info("IEDriver iniciado com sucesso (webdriver_manager).")
            return driver
        except Exception:
            logger.exception("Falha ao iniciar IEDriver via webdriver_manager.")
            raise
