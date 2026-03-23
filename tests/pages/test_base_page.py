from __future__ import annotations

import pytest
from selenium.common.exceptions import TimeoutException

from pages.common.base_page import BasePage
from tests.support.fakes import FakeDriver


class FakeWebDriverWait:
    def __init__(self, driver, _timeout, poll_frequency=0.5):
        self.driver = driver
        self.poll_frequency = poll_frequency

    def until(self, condition, message=None):
        result = condition(self.driver)
        if result:
            return result
        raise TimeoutException(message or "timeout")


def test_lidar_com_alertas_drena_alertas_em_cascata(monkeypatch):
    driver = FakeDriver()
    driver.alert_texts = [
        "Fechamento Financeiro nao realizado ha 7 dias",
        "Fechamento do Estoque nao realizado ha 6 dias",
    ]

    monkeypatch.setattr("pages.common.base_page.WebDriverWait", FakeWebDriverWait)

    page = BasePage(driver)
    monkeypatch.setattr(page, "wait_for_no_alert", lambda timeout=0: True)

    mensagens = page.lidar_com_alertas(tentativas=2, timeout=1, timeout_entre_alertas=1, max_alertas=5)

    assert driver.accepted_alerts == [
        "Fechamento Financeiro nao realizado ha 7 dias",
        "Fechamento do Estoque nao realizado ha 6 dias",
    ]
    assert driver.alert_texts == []
    assert mensagens == [
        "Fechamento Financeiro nao realizado ha 7 dias",
        "Fechamento do Estoque nao realizado ha 6 dias",
    ]


