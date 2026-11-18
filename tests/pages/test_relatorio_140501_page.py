from unittest.mock import MagicMock

import pytest

from pages.reports.relatorio_140501_page import Relatorio140501Page


def page_with_mocks(monkeypatch):
    page = Relatorio140501Page(MagicMock(), "menu")
    for name in ("selecionar_unidade", "entrar_frame_rotina_blindado", "find_element",
                 "js_click_ie", "switch_to_default_content", "js_set_select_by_name",
                 "js_set_input_by_name", "js_set_checkbox_by_name"):
        monkeypatch.setattr(page, name, MagicMock())
    monkeypatch.setattr(page, "_fluxo_exportar_csv", MagicMock(return_value=(True, "salvo")))
    return page


def test_140501_preserves_html_defaults_and_exports(monkeypatch):
    page = page_with_mocks(monkeypatch)
    assert page.gerar_relatorio(unidade="2210003", nome_arquivo="14,05,01_3.csv") == (True, "salvo")
    page.selecionar_unidade.assert_called_once_with("2210003")
    page.js_set_select_by_name.assert_called_once_with("opcaoRel", "01")
    inputs = dict(call.args for call in page.js_set_input_by_name.call_args_list)
    assert inputs == {
        "iniFornecedor": "0", "fimFornecedor": "999999",
        "iniVencimento": "00/00/0000", "fimVencimento": "99/99/9999",
        "iniEmissao": "00/00/0000", "fimEmissao": "99/99/9999",
        "iniPortador": "0", "fimPortador": "999", "iniEspecie": "0", "fimEspecie": "99",
        "iniVinculo": "0", "fimVinculo": "99", "iniValor": "0,00", "fimValor": "99999999,99",
        "iniCGC": "", "fimCGC": "ZZZZZZZZZZZZ99",
    }
    checks = dict(call.args for call in page.js_set_checkbox_by_name.call_args_list)
    assert checks == {"quebraPag": False, "idListaPrevTodas": False, "idListaPrevPendAprov": False,
                      "idListaPrevAprovadas": False, "idListaPrevRejeitadas": False}
    assert page._fluxo_exportar_csv.call_args.kwargs["nome_arquivo"] == "14,05,01_3.csv"
    assert "type='button'" in page.BTN_GERA_EXCEL_2[1]
    page.js_click_ie.assert_called_once()


def test_140501_propagates_filters_through_unit_loop(monkeypatch):
    page = page_with_mocks(monkeypatch)
    def loop(**kwargs):
        assert kwargs["unidades_alvo"] == ["2210003", "2210004"]
        return kwargs["fn_execucao_unica"]("2210004", "14,05,01_4.csv")
    monkeypatch.setattr(page, "loop_unidades", loop)
    assert page.gerar_relatorio(unidade=["2210003", "2210004"], opcao_rel="06", iniVencimento="01/11/2026") == (True, "salvo")
    page.js_set_input_by_name.assert_any_call("iniVencimento", "01/11/2026")
    page.js_set_select_by_name.assert_called_once_with("opcaoRel", "06")
    assert page._fluxo_exportar_csv.call_args.kwargs["nome_arquivo"] == "14,05,01_4.csv"


def test_140501_rejects_unselected_classification(monkeypatch):
    page = page_with_mocks(monkeypatch)
    with pytest.raises(ValueError, match="Classificação"):
        page.gerar_relatorio(unidade="2210003", opcao_rel="00")
    page.js_click_ie.assert_not_called()


def test_140501_restores_frame_after_export_failure(monkeypatch):
    page = page_with_mocks(monkeypatch)
    page._fluxo_exportar_csv.side_effect = RuntimeError("falha de download")
    with pytest.raises(RuntimeError, match="download"):
        page.gerar_relatorio(unidade="2210003")
    assert page.switch_to_default_content.call_count == 2
