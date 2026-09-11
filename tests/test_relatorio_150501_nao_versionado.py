from types import SimpleNamespace

from core.execution.execution_result import ExecutionResult, ExecutionStatus
from core.services.report_orchestration_service import ReportOrchestrationService
from entrypoints.reports import relatorio_150501_nao_versionado as entrypoint


def test_150501_nao_versionado_defaults_to_all_months_and_operations(monkeypatch, tmp_path):
    captured_run = {}
    captured_reports = []

    class Fake150501Page:
        def __init__(self, _driver, _handle_menu):
            self.subpasta_download = ""
            self.tracker_name = ""

        def gerar_relatorio(self, **kwargs):
            captured_reports.append(
                {
                    **kwargs,
                    "subpasta_download": self.subpasta_download,
                    "tracker_name": self.tracker_name,
                }
            )
            return True

        def fechar_e_voltar(self):
            return None

    class FakeMenuPage:
        @staticmethod
        def acessar_rotina(routine_id):
            assert routine_id == "150501"
            return SimpleNamespace(driver=object(), handle_menu=object())

    def fake_run(_self, **kwargs):
        captured_run.update(kwargs)
        return ExecutionResult(ExecutionStatus.SUCCESS, "ok")

    monkeypatch.setattr(entrypoint, "settings", SimpleNamespace(download_dir=tmp_path))
    monkeypatch.setattr(entrypoint, "menu_page", FakeMenuPage())
    monkeypatch.setattr(entrypoint, "Relatorio150501Page", Fake150501Page)
    monkeypatch.setattr(ReportOrchestrationService, "run", fake_run)

    result = entrypoint.main(year=2026)
    for task in captured_run["tasks"].values():
        task.runner()

    assert result.status == ExecutionStatus.SUCCESS
    assert len(captured_run["tasks"]) == 12
    assert captured_run["publication_plan"] is None
    assert len(captured_reports) == 12
    assert captured_reports[0]["unidade"] == ["3610006", "3610007", "3610008"]
    assert captured_reports[0]["mes_ano"] == "01/2026"
    assert captured_reports[-1]["mes_ano"] == "12/2026"
    assert captured_reports[0]["subpasta_download"] == "150501 nao versionado"
    assert captured_reports[0]["tracker_name"] == "Rotina 150501 Nao Versionado 01/2026"


def test_150501_nao_versionado_accepts_operation_numbers(monkeypatch, tmp_path):
    captured_run = {}
    captured_report = {}

    class Fake150501Page:
        def __init__(self, _driver, _handle_menu):
            self.subpasta_download = ""
            self.tracker_name = ""

        def gerar_relatorio(self, **kwargs):
            captured_report.update(kwargs)
            return True

        def fechar_e_voltar(self):
            return None

    class FakeMenuPage:
        @staticmethod
        def acessar_rotina(_routine_id):
            return SimpleNamespace(driver=object(), handle_menu=object())

    def fake_run(_self, **kwargs):
        captured_run.update(kwargs)
        return ExecutionResult(ExecutionStatus.SUCCESS, "ok")

    monkeypatch.setattr(entrypoint, "settings", SimpleNamespace(download_dir=tmp_path))
    monkeypatch.setattr(entrypoint, "menu_page", FakeMenuPage())
    monkeypatch.setattr(entrypoint, "Relatorio150501Page", Fake150501Page)
    monkeypatch.setattr(ReportOrchestrationService, "run", fake_run)

    entrypoint.main(year=2026, months=["9"], units=["6", "7"])
    next(iter(captured_run["tasks"].values())).runner()

    assert captured_report["unidade"] == ["3610006", "3610007"]
    assert captured_report["mes_ano"] == "09/2026"
    assert captured_report["nome_arquivo"] == "2026-09 nomeUnidade150501"
