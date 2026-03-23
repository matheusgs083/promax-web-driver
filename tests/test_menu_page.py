from __future__ import annotations

from pages.menu_page import MenuPage
from tests.support.fakes import FakeDriver, FakeElement


class StubWait:
    def __init__(self, element):
        self.element = element

    def until(self, _condition):
        return self.element


def test_acessar_rotina_prioriza_enter_antes_do_ok(monkeypatch):
    driver = FakeDriver()
    element = FakeElement()
    page = MenuPage(driver)
    page.wait = StubWait(element)
    initial_count = len(driver.window_handles)

    monkeypatch.setattr(page, "_entrar_no_frame_menu", lambda: None)
    monkeypatch.setattr(page, "_confirmar_atalho_preenchido", lambda *_args, **_kwargs: None)

    def execute_script(script, *_args):
        driver.script_calls.append(script)
        if script == page.JS_SET_VALUE:
            return {"ok": True}
        if script == page.JS_DISPARAR_ENTER:
            driver.open_window("rotina-1")
            return {"ok": True, "method": "enter"}
        if script == page.JS_CLICAR_OK_MENU:
            raise AssertionError("Fallback com OK nao deveria ser usado quando Enter abre a rotina")
        return {"ok": True}

    monkeypatch.setattr(driver, "execute_script", execute_script)
    monkeypatch.setattr(
        page,
        "_aguardar_abertura_rotina",
        lambda expected_count, timeout: len(driver.window_handles) > initial_count,
    )

    rotina = page.acessar_rotina("0512")

    assert driver.script_calls[:2] == [page.JS_SET_VALUE, page.JS_DISPARAR_ENTER]
    assert driver.current_window_handle == "rotina-1"
    assert rotina.handle_menu == "menu"


def test_acessar_rotina_usa_ok_como_fallback_quando_enter_nao_abre_janela(monkeypatch):
    driver = FakeDriver()
    element = FakeElement()
    page = MenuPage(driver)
    page.wait = StubWait(element)
    initial_count = len(driver.window_handles)

    monkeypatch.setattr(page, "_entrar_no_frame_menu", lambda: None)
    monkeypatch.setattr(page, "_confirmar_atalho_preenchido", lambda *_args, **_kwargs: None)

    state = {"enter_called": False, "ok_called": False}

    def execute_script(script, *_args):
        driver.script_calls.append(script)
        if script == page.JS_SET_VALUE:
            return {"ok": True}
        if script == page.JS_DISPARAR_ENTER:
            state["enter_called"] = True
            return {"ok": True, "method": "enter"}
        if script == page.JS_CLICAR_OK_MENU:
            state["ok_called"] = True
            driver.open_window("rotina-2")
            return {"ok": True, "method": "click"}
        return {"ok": True}

    monkeypatch.setattr(driver, "execute_script", execute_script)
    calls = {"count": 0}

    def fake_wait_for_open(expected_count, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            return False
        return len(driver.window_handles) > initial_count

    monkeypatch.setattr(
        page,
        "_aguardar_abertura_rotina",
        fake_wait_for_open,
    )

    rotina = page.acessar_rotina("120616")

    assert state == {"enter_called": True, "ok_called": True}
    assert driver.script_calls[:3] == [page.JS_SET_VALUE, page.JS_DISPARAR_ENTER, page.JS_CLICAR_OK_MENU]
    assert driver.current_window_handle == "rotina-2"
    assert rotina.handle_menu == "menu"
