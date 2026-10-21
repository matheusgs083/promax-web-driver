from __future__ import annotations

from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class CoraWelcomePage:
    """Selectors mínimos da tela inicial de seleção de localização."""

    LOCATION_SELECT = "#tenant-location-select"

    def __init__(self, driver: Any) -> None:
        self.driver = driver

    def is_loaded(self) -> bool:
        return bool(self.driver.find_elements("css selector", self.LOCATION_SELECT))

    def select_brazil(self, timeout_seconds: float = 30.0) -> None:
        control = WebDriverWait(self.driver, timeout_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, self.LOCATION_SELECT))
        )
        tag_name = str(control.tag_name or "").lower()
        if tag_name == "select":
            from selenium.webdriver.support.ui import Select

            Select(control).select_by_visible_text("Brasil")
            return
        control.click()
        option = WebDriverWait(self.driver, timeout_seconds).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//*[normalize-space()='Brasil' and not(@aria-hidden='true')]")
            )
        )
        option.click()

    def access_as_reseller(self, timeout_seconds: float = 30.0) -> None:
        option = WebDriverWait(self.driver, timeout_seconds).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//*[self::button or self::a or @role='button'][normalize-space(.)='Acessar como Revenda']",
                )
            )
        )
        option.click()

