from unittest.mock import MagicMock

import pytest

from pages.reports.relatorio_1706_page import Relatorio1706Page


def test_1706_fills_the_promax_form_and_uses_patos_dvs_name(monkeypatch):
    page = Relatorio1706Page(MagicMock(), "menu")
    monkeypatch.setattr(page, "selecionar_unidade", MagicMock())
    monkeypatch.setattr(page, "entrar_frame_rotina_blindado", MagicMock())
    monkeypatch.setattr(page, "find_element", MagicMock())
    monkeypatch.setattr(page, "js_click_ie", MagicMock())
    monkeypatch.setattr(page, "switch_to_default_content", MagicMock())
    monkeypatch.setattr(page, "_capturar_arquivo_gerado", MagicMock(return_value=(True, "ok")))
    selects, inputs, checks = [], [], []
    monkeypatch.setattr(page, "js_set_select_by_name", lambda name, value: selects.append((name, value)))
    monkeypatch.setattr(page, "js_set_input_by_name", lambda name, value: inputs.append((name, value)))
    monkeypatch.setattr(page, "js_set_checkbox_by_name", lambda name, value, force_click=True: checks.append((name, value)))

    assert page.gerar_relatorio(unidade="2210003", data_inicial="01/09/2026", data_final="30/09/2026") == (True, "ok")
    assert ("opcaoUnidades", "2210003") in selects
    assert ("opcaoGrupo", "4") in selects
    assert ("dtMovimentoInicial", "01/09/2026") in inputs
    assert ("dtMovimentoFinal", "30/09/2026") in inputs
    assert ("idDesempenho", True) in checks
    page.selecionar_unidade.assert_called_once_with("2210003")
    page._capturar_arquivo_gerado.assert_called_once()
    kwargs = page._capturar_arquivo_gerado.call_args.kwargs
    assert kwargs["nome_dvs"] == "id_000074753000031111111111.inf"
    assert kwargs["prefixo_dvs"] == "0000747530"
    assert kwargs["nome_final"] == "17.06_PATOS_2026_09.inf"
    assert kwargs["timeout_arquivo"] == 120


def test_1706_rejects_dates_from_different_months():
    page = object.__new__(Relatorio1706Page)
    with pytest.raises(ValueError, match="mes"):
        page.gerar_relatorio(unidade="2210003", data_inicial="30/09/2026", data_final="01/10/2026")
