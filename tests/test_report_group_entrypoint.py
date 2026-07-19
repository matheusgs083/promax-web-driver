from pathlib import Path
from types import SimpleNamespace

from core.execution.execution_result import ExecutionResult, ExecutionStatus
from core.services.report_orchestration_service import ReportOrchestrationService
from entrypoints.reports import relatorios


def test_entrypoint_selects_routine_and_output_from_group_without_browser(
    monkeypatch,
    tmp_path,
):
    captured = {}

    def fake_run(_self, **kwargs):
        captured.update(kwargs)
        return ExecutionResult(ExecutionStatus.SUCCESS, "ok")

    monkeypatch.setattr(
        relatorios,
        "settings",
        SimpleNamespace(download_dir=tmp_path),
    )
    monkeypatch.setattr(ReportOrchestrationService, "run", fake_run)

    result = relatorios.main(
        profile="outros",
        routines=["020220_RECOLHAS"],
    )

    assert result.status == ExecutionStatus.SUCCESS
    assert list(captured["tasks"]) == ["020220_RECOLHAS"]
    assert captured["tasks"]["020220_RECOLHAS"].name == "Rotina 020220 Recolhas"
    assert captured["post_process_dirs"] == [tmp_path / "020220 Recolhas"]
    assert {
        source.relative_to(tmp_path).parts[0]
        for source in map(Path, captured["publication_plan"].mapping)
    } == {"020220 Recolhas"}
