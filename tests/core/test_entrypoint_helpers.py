from __future__ import annotations

from types import SimpleNamespace

import pytest
from selenium.common.exceptions import UnexpectedAlertPresentException, WebDriverException

from core.execution import entrypoint_helpers
from core.execution.execution_result import ExecutionResult, ExecutionStatus
from pages.common.rotina_page import RotinaPage
from tests.support.fakes import FakeDriver


class DummyLogger:
    def info(self, *_args, **_kwargs):
        return None

    def warning(self, *_args, **_kwargs):
        return None

    def error(self, *_args, **_kwargs):
        return None

    def exception(self, *_args, **_kwargs):
        return None

    def critical(self, *_args, **_kwargs):
        return None


def test_iniciar_sessao_padrao_realiza_login_e_maximiza(monkeypatch):
    driver = FakeDriver()
    estado = {"maximized": False, "login_args": None}

    def maximize_window():
        estado["maximized"] = True

    driver.maximize_window = maximize_window

    class FakeLoginPage:
        def __init__(self, received_driver):
            estado["driver"] = received_driver

        def fazer_login(self, usuario, senha, nome_unidade=None):
            estado["login_args"] = (usuario, senha, nome_unidade)
            return "menu_page"

    monkeypatch.setattr(entrypoint_helpers.DriverFactory, "get_driver", staticmethod(lambda: driver))
    monkeypatch.setattr(entrypoint_helpers, "LoginPage", FakeLoginPage)

    settings = SimpleNamespace(promax_user="usuario_teste", promax_pass="senha_teste")
    driver_retornado, menu_page = entrypoint_helpers.iniciar_sessao_padrao(DummyLogger(), settings, "UNIDADE_01")

    assert driver_retornado is driver
    assert menu_page == "menu_page"
    assert estado["driver"] is driver
    assert estado["maximized"] is True
    assert estado["login_args"] == ("usuario_teste", "senha_teste", "UNIDADE_01")


def test_selecionar_unidade_reexecuta_fluxo_de_troca(monkeypatch):
    driver = FakeDriver()
    page = RotinaPage(driver, handle_menu_original="menu")
    chamadas = []

    monkeypatch.setattr(page, "obter_unidade_atual", lambda: "000001")
    monkeypatch.setattr(page, "_entrar_frame_topo", lambda: chamadas.append("frame"))
    monkeypatch.setattr(
        page,
        "selecionar_combo_js",
        lambda locator, valor: chamadas.append(("combo", locator, valor)) or True,
    )
    monkeypatch.setattr(page, "lidar_com_alertas", lambda *args, **kwargs: chamadas.append(("alertas", args, kwargs)))
    monkeypatch.setattr(page, "_confirmar_unidade_ativa", lambda valor, timeout=5: chamadas.append(("confirmar", valor, timeout)))

    page.selecionar_unidade("3610007")

    assert chamadas[0] == "frame"
    assert chamadas[1][0] == "combo"
    assert chamadas[1][2] == "3610007"
    assert chamadas[2][0] == "alertas"
    assert chamadas[3] == ("confirmar", "3610007", 10)


def test_executar_tarefa_com_retry_refaz_login_em_queda_de_sessao(monkeypatch):
    chamadas = {"iniciar_sessao": 0, "func": 0}

    def iniciar_sessao():
        chamadas["iniciar_sessao"] += 1

    def funcao_logica():
        chamadas["func"] += 1
        if chamadas["func"] == 1:
            raise WebDriverException("invalid session id")
        return True

    monkeypatch.setattr(entrypoint_helpers.time, "sleep", lambda *_args, **_kwargs: None)

    resultado = entrypoint_helpers.executar_tarefa_com_retry(
        "Rotina teste",
        funcao_logica,
        logger=DummyLogger(),
        iniciar_sessao=iniciar_sessao,
        tentativas=2,
        espera_segundos=0,
    )

    assert chamadas == {"iniciar_sessao": 1, "func": 2}
    assert resultado.status == ExecutionStatus.SUCCESS


def test_executar_tarefa_com_retry_nao_reexecuta_lote_inteiro_em_sucesso_parcial(monkeypatch):
    chamadas = {"iniciar_sessao": 0, "func": 0}

    def iniciar_sessao():
        chamadas["iniciar_sessao"] += 1

    def funcao_logica():
        chamadas["func"] += 1
        return ExecutionResult(
            status=ExecutionStatus.PARTIAL_SUCCESS,
            message="1 unidade falhou, 7 concluídas",
        )

    monkeypatch.setattr(entrypoint_helpers.time, "sleep", lambda *_args, **_kwargs: None)

    resultado = entrypoint_helpers.executar_tarefa_com_retry(
        "Rotina teste",
        funcao_logica,
        logger=DummyLogger(),
        iniciar_sessao=iniciar_sessao,
        tentativas=3,
        espera_segundos=0,
    )

    assert chamadas == {"iniciar_sessao": 0, "func": 1}
    assert resultado.status == ExecutionStatus.PARTIAL_SUCCESS


def test_selecionar_unidade_falha_rapido_quando_alerta_indica_erro(monkeypatch):
    driver = FakeDriver()
    page = RotinaPage(driver, handle_menu_original="menu")

    monkeypatch.setattr(page, "obter_unidade_atual", lambda: "000001")
    monkeypatch.setattr(page, "_entrar_frame_topo", lambda: None)
    monkeypatch.setattr(page, "selecionar_combo_js", lambda locator, valor: True)
    monkeypatch.setattr(
        page,
        "lidar_com_alertas",
        lambda *args, **kwargs: ["Erro: unidade 3610007 nao autorizada para o usuario"],
    )

    with pytest.raises(RuntimeError, match="nao autorizada"):
        page.selecionar_unidade("3610007")


def test_confirmacao_de_unidade_aborta_quando_alerta_indica_falha(monkeypatch):
    driver = FakeDriver()
    page = RotinaPage(driver, handle_menu_original="menu")

    monkeypatch.setattr(
        page,
        "obter_unidade_atual",
        lambda: (_ for _ in ()).throw(UnexpectedAlertPresentException("bloqueado")),
    )
    monkeypatch.setattr(
        page,
        "lidar_com_alertas",
        lambda *args, **kwargs: ["Falha: unidade nao encontrada para troca"],
    )
    monkeypatch.setattr(page, "switch_to_default_content", lambda: None)

    with pytest.raises(RuntimeError, match="unidade nao encontrada"):
        page._confirmar_unidade_ativa("3610007", timeout=1)


