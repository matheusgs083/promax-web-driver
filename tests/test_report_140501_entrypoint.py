from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from core.execution.execution_result import ExecutionResult, ExecutionStatus
from core.services.report_orchestration_service import ReportOrchestrationService
from entrypoints.reports import relatorios
from core.config.report_group_loader import load_report_groups, select_report_group


def test_140501_is_selected_in_cashflow_group_only():
    groups = load_report_groups()
    _, selected = select_report_group(groups, 'fluxo_caixa', ['140501'])
    assert selected[0].output_folders == ('140501',)
    assert all('140501' not in group.routine_ids for key, group in groups.items() if key != 'fluxo_caixa')


def test_cashflow_140501_runner_and_publication(monkeypatch, tmp_path):
    captured, execution = {}, {}
    class Page:
        def __init__(self, *args):
            captured["page"] = self
        def gerar_relatorio(self, **kwargs):
            captured.update(kwargs)
            return True
        def fechar_e_voltar(self):
            captured["closed"] = True
    class Menu:
        def acessar_rotina(self, routine):
            assert routine == "140501"
            return SimpleNamespace(driver=object(), handle_menu=object())
    monkeypatch.setattr(relatorios, "hoje", datetime(2026, 11, 17))
    monkeypatch.setattr(relatorios, "settings", SimpleNamespace(download_dir=tmp_path))
    monkeypatch.setattr(relatorios, "Relatorio140501Page", Page)
    monkeypatch.setattr(relatorios, "menu_page", Menu())
    monkeypatch.setattr(ReportOrchestrationService, "run", lambda self, **kw: execution.update(kw) or ExecutionResult(ExecutionStatus.SUCCESS, "ok"))
    relatorios.main(profile="fluxo_caixa", routines=["140501"], units=["2210003", "2210004"], publish=True)
    execution["tasks"]["140501"].runner()
    assert captured["page"].subpasta_download == "140501"
    assert captured["nome_arquivo"] == "14,05,01_nUnidade"
    assert captured["unidade"] == ["2210003", "2210004"]
    assert captured["opcao_rel"] == "01"
    assert captured["closed"]
    mapping = execution["publication_plan"].mapping
    assert list(map(Path, mapping)) == [tmp_path / "140501"]
    assert list(mapping.values()) == [r"\\dc01n\PUBLICO\REVENDA\Power BI\Fluxo de Caixa\2026\11. Novembro"]
