from pages.reports.relatorio_020220_page import Relatorio020220Page


def test_tracker_name_can_identify_a_report_variant_without_browser():
    page = object.__new__(Relatorio020220Page)
    page.tracker_name = "Rotina 020220 Auditool"

    assert page.obter_nome_tracker() == "Rotina 020220 Auditool"


def test_tracker_name_falls_back_to_page_class_without_browser():
    page = object.__new__(Relatorio020220Page)
    page.tracker_name = None

    assert page.obter_nome_tracker() == "Rotina 020220"
