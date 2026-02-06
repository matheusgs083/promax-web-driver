import time
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.logger import get_logger
logger = get_logger(__name__)

def limpar_alertas(driver, tentativas=3, timeout=2):

    for i in range(1, tentativas + 1):
        try:
            WebDriverWait(driver, timeout).until(EC.alert_is_present())
            alert = driver.switch_to.alert

            texto = ""
            try:
                texto = alert.text
            except Exception:
                texto = "<não foi possível ler o texto do alerta>"

            logger.warning("Pop-up aceito (%d/%d): %s", i, tentativas, texto)

            alert.accept()
            time.sleep(0.5)

        except TimeoutException:
            logger.debug("Nenhum pop-up detectado (tentativa %d/%d).", i, tentativas)
            break

        except Exception as e:
            logger.exception("Erro ao tentar tratar pop-up (tentativa %d/%d): %s", i, tentativas, e)
            # não quebra o fluxo por causa de popup; segue tentando
            time.sleep(0.3)
