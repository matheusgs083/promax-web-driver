import pytest
from unittest.mock import MagicMock
from pages.reports.relatorio_030237_page import Relatorio030237Page


def test_relatorio_030237_gerar_relatorio_preenchimento_completo(monkeypatch):
    driver = MagicMock()
    page = Relatorio030237Page(driver, "handle_123")

    monkeypatch.setattr(page, "selecionar_unidade", MagicMock())
    monkeypatch.setattr(page, "entrar_frame_rotina_blindado", MagicMock())
    monkeypatch.setattr(page, "find_element", MagicMock())
    monkeypatch.setattr(page, "js_click_ie", MagicMock())
    monkeypatch.setattr(page, "switch_to_default_content", MagicMock())
    monkeypatch.setattr(page, "_fluxo_exportar_csv", MagicMock(return_value=True))

    set_select_calls = []
    set_input_calls = []
    set_radio_calls = []
    set_checkbox_calls = []
    execute_script_calls = []

    monkeypatch.setattr(page, "js_set_select_by_name", lambda name, val: set_select_calls.append((name, val)))
    monkeypatch.setattr(page, "js_set_input_by_name", lambda name, val: set_input_calls.append((name, val)))
    monkeypatch.setattr(page, "js_set_radio_by_name", lambda name, val: set_radio_calls.append((name, val)))
    monkeypatch.setattr(page, "js_set_checkbox_by_name", lambda name, val, force_click=True: set_checkbox_calls.append((name, val)))
    driver.execute_script = lambda script, *args: execute_script_calls.append(script)

    res = page.gerar_relatorio(
        unidade="1",
        data_inicial="01/09/2026",
        data_final="04/09/2026",
        quebra1="14",
        quebra2="12",
        quebra3="16",
        quebra1_inicial="0",
        quebra1_final="999",
        ind_palmtop="V",
        status_nota="E",
        converte_caixas=True,
        quebra_pagina=False,
        itens="S",
        pis_cofins=True,
        tipo_nota="NS",
        lista_nota_compra=True,
        lista_notas_apagar=True,
        id_notas_transf=True,
        visao="E",
        id_agrupar_televendas=True,
        id_somente_venda_bonif=True,
        id_somente_metalfrio=False,
        id_visao_ipi_bonif=False,
        valor_inicial="100,00",
        valor_final="500,00",
        embalagem_inicial="1",
        embalagem_final="5",
        mercadoria_inicial="10",
        mercadoria_final="20",
        cd_visao="001",
        tp_consolidacao="1",
        visao_multi_cdd="G",
        selecao_multi_cdd="T",
        st_nfe_todos=False,
        st_nfe_autorizada=True,
        st_nfe_denegada=False,
        clicar_csv_apos_visualizar=True,
    )

    assert res is True
    assert ("quebra1", "14") in set_select_calls
    assert ("indPalmtop", "V") in set_select_calls
    assert ("dataInicial", "01/09/2026") in set_input_calls
    assert ("dataFinal", "04/09/2026") in set_input_calls
    assert ("valorInicial", "100,00") in set_input_calls
    assert ("valorFinal", "500,00") in set_input_calls
    assert ("statusNota", "E") in set_radio_calls
    assert ("itens", "S") in set_radio_calls
    assert ("notas", "NS") in set_radio_calls
    assert ("converteCaixas", True) in set_checkbox_calls
    assert ("quebraPagina", False) in set_checkbox_calls
    assert ("pisCofins", True) in set_checkbox_calls
    assert ("idStTodos", False) in set_checkbox_calls
    assert ("idStAutorizada", True) in set_checkbox_calls


def test_relatorio_030237_configurar_status_nfe_com_lista(monkeypatch):
    driver = MagicMock()
    page = Relatorio030237Page(driver, "handle_123")

    set_checkbox_calls = []
    execute_script_calls = []

    monkeypatch.setattr(page, "js_set_checkbox_by_name", lambda name, val, force_click=True: set_checkbox_calls.append((name, val)))
    driver.execute_script = lambda script, *args: execute_script_calls.append(script)

    page._configurar_status_nfe(status_nfe=["autorizada", "denegada"])

    assert ("idStTodos", False) in set_checkbox_calls
    assert ("idStAutorizada", True) in set_checkbox_calls
    assert ("idStDenegada", True) in set_checkbox_calls
