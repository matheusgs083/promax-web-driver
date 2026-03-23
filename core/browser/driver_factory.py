import os
import subprocess
import time

import dotenv
from selenium import webdriver
from selenium.webdriver.ie.options import Options as IEOptions
from selenium.webdriver.ie.service import Service as IEService
from webdriver_manager.microsoft import IEDriverManager

from core.observability.logger import get_logger
from core.config.settings import get_settings


dotenv.load_dotenv()
logger = get_logger(__name__)


class DriverFactory:
    STARTUP_RETRY_ATTEMPTS = 2
    STARTUP_RETRY_DELAY_SECONDS = 2

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
    def _iniciar_ie_driver(*, executable_path, ie_options, origem):
        ultima_exc = None

        for tentativa in range(1, DriverFactory.STARTUP_RETRY_ATTEMPTS + 1):
            try:
                service = IEService(executable_path=executable_path)
                driver = webdriver.Ie(service=service, options=ie_options)
                logger.info("IEDriver iniciado com sucesso (%s).", origem)
                return driver
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                ultima_exc = exc
                if tentativa >= DriverFactory.STARTUP_RETRY_ATTEMPTS:
                    logger.exception(
                        "Falha ao iniciar IEDriver (%s) apos %s tentativa(s).",
                        origem,
                        DriverFactory.STARTUP_RETRY_ATTEMPTS,
                    )
                    break

                logger.warning(
                    "Falha ao iniciar IEDriver (%s) na tentativa %s/%s: %s. "
                    "Nova tentativa em %ss.",
                    origem,
                    tentativa,
                    DriverFactory.STARTUP_RETRY_ATTEMPTS,
                    exc,
                    DriverFactory.STARTUP_RETRY_DELAY_SECONDS,
                )
                time.sleep(DriverFactory.STARTUP_RETRY_DELAY_SECONDS)

        raise ultima_exc

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
        ie_options.require_window_focus = settings.require_window_focus
        ie_options.page_load_strategy = "none"

        logger.info(
            "Configuracao do driver IE Mode: require_window_focus=%s",
            settings.require_window_focus,
        )

        caminho_local = settings.driver_path

        if caminho_local and os.path.exists(caminho_local):
            try:
                logger.info("Iniciando com driver local: %s", caminho_local)
                return DriverFactory._iniciar_ie_driver(
                    executable_path=caminho_local,
                    ie_options=ie_options,
                    origem="local",
                )
            except Exception:
                logger.exception("Falha ao usar driver local: %s", caminho_local)

        try:
            logger.warning("Driver local nao disponivel. Tentando baixar via webdriver_manager...")
            driver_path = IEDriverManager().install()
            logger.info("Driver baixado/encontrado em: %s", driver_path)

            return DriverFactory._iniciar_ie_driver(
                executable_path=driver_path,
                ie_options=ie_options,
                origem="webdriver_manager",
            )
        except Exception:
            logger.exception("Falha ao iniciar IEDriver via webdriver_manager.")
            raise

