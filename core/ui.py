from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, InvalidSelectorException, StaleElementReferenceException

from core.logger import get_logger
logger = get_logger(__name__)

@dataclass
class UIResult:
    ok: bool
    message: str
    element: Optional[object] = None  # WebElement

def wait_presence(driver, locator: Tuple[str, str], timeout=10, desc="elemento") -> UIResult:
    try:
        el = WebDriverWait(driver, timeout).until(EC.presence_of_element_located(locator))
        return UIResult(True, f"{desc} encontrado", el)
    except TimeoutException:
        return UIResult(False, f"Página não carregou: {desc} não apareceu em {timeout}s")
    except (InvalidSelectorException, WebDriverException) as e:
        logger.debug("Detalhe técnico wait_presence:", exc_info=e)
        return UIResult(False, f"Página não carregou: falha ao localizar {desc}")

def click(driver, locator: Tuple[str, str], timeout=10, desc="botão") -> UIResult:
    try:
        el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator))
        el.click()
        return UIResult(True, f"{desc} clicado", el)
    except TimeoutException:
        return UIResult(False, f"Página não carregou: {desc} não ficou clicável em {timeout}s")
    except (InvalidSelectorException, WebDriverException, StaleElementReferenceException) as e:
        logger.debug("Detalhe técnico click:", exc_info=e)
        return UIResult(False, f"Página não carregou: erro ao clicar em {desc}")

def type_and_confirm(
    driver,
    locator: Tuple[str, str],
    text: str,
    timeout=10,
    desc="campo",
    attempts=3,
    pause=0.2,
) -> UIResult:
    """
    Digita e confirma lendo o atributo value.
    Se digitar 'errado', tenta de novo (sem retry global, só pra digitação).
    """
    last_err = None
    for i in range(1, attempts + 1):
        res = wait_presence(driver, locator, timeout=timeout, desc=desc)
        if not res.ok:
            return res

        try:
            el = res.element
            el.click()
            el.clear()
            el.send_keys(text)

            time.sleep(pause)
            value = (el.get_attribute("value") or "").strip()
            expected = (text or "").strip()

            if value == expected:
                return UIResult(True, f"{desc} preenchido e validado", el)

            last_err = f"texto diferente do esperado (tentativa {i}/{attempts})"
            logger.warning("Falha ao digitar em %s: value='%s' esperado='%s' (%s)", desc, value, expected, last_err)

        except (WebDriverException, StaleElementReferenceException) as e:
            logger.debug("Detalhe técnico type_and_confirm:", exc_info=e)
            last_err = f"erro ao digitar (tentativa {i}/{attempts})"

    return UIResult(False, f"Falha ao preencher {desc}: {last_err or 'não validou o texto'}")
