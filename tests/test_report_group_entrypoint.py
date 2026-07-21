from pathlib import Path
from types import SimpleNamespace

import pytest

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
    assert result.metadata["publication_mapping"] == {
        str(source): str(destination)
        for source, destination in captured["publication_plan"].mapping.items()
    }


@pytest.mark.parametrize(
    (
        "profile",
        "routine_id",
        "page_class_name",
        "start_field",
        "end_field",
        "expected_start",
        "expected_end",
    ),
    [
        (
            "inadimplencia",
            "120601",
            "Relatorio120601Page",
            "ini_vencimento",
            "fim_vencimento",
            relatorios.primeiro_dia_mes_passado,
            relatorios.data_ontem_formatada,
        ),
        (
            "adf",
            "030237",
            "Relatorio030237Page",
            "data_inicial",
            "data_final",
            relatorios.primeiro_dia_mes_atual,
            relatorios.data_ontem_formatada,
        ),
        (
            "giro",
            "030237_GIRO",
            "Relatorio030237Page",
            "data_inicial",
            "data_final",
            relatorios.primeiro_dia_mes_atual,
            relatorios.data_hoje_formatada,
        ),
        (
            "estoque",
            "030237_ESTOQUE",
            "Relatorio030237Page",
            "data_inicial",
            "data_final",
            relatorios.primeiro_dia_mes_passado,
            relatorios.data_hoje_formatada,
        ),
        (
            "fluxo_caixa",
            "140506",
            "Relatorio140506Page",
            "iniDat",
            "fimDat",
            relatorios.primeiro_dia_mes_passado,
            relatorios.primeiro_dia_mes_atual,
        ),
        (
            "fluxo_caixa",
            "120606",
            "Relatorio120606Page",
            "iniDat",
            "fimDat",
            relatorios.primeiro_dia_mes_passado,
            relatorios.ultimo_dia_util_mes_atual,
        ),
        (
            "bot_zap",
            "030206_BOT",
            "Relatorio030206Page",
            "emissao_inicial",
            "emissao_final",
            relatorios.primeiro_dia_mes_passado,
            relatorios.data_hoje_formatada,
        ),
    ],
)
def test_missing_job_period_preserves_each_routine_configured_dates(
    monkeypatch,
    tmp_path,
    profile,
    routine_id,
    page_class_name,
    start_field,
    end_field,
    expected_start,
    expected_end,
):
    captured_run = {}
    captured_report = {}

    class FakePage:
        def __init__(self, _driver, _handle_menu):
            self.subpasta_download = ""
            self.tracker_name = ""

        def gerar_relatorio(self, **kwargs):
            captured_report.update(kwargs)
            return "ok"

        def testar_pdf_intervalo_direto(self, **kwargs):
            captured_report.update(kwargs)
            return "ok"

        def fechar_e_voltar(self):
            return None

    class FakeMenuPage:
        @staticmethod
        def acessar_rotina(_routine_id):
            return SimpleNamespace(driver=object(), handle_menu=object())

    def fake_run(_self, **kwargs):
        captured_run.update(kwargs)
        return ExecutionResult(ExecutionStatus.SUCCESS, "ok")

    monkeypatch.setattr(relatorios, "settings", SimpleNamespace(download_dir=tmp_path))
    monkeypatch.setattr(relatorios, "menu_page", FakeMenuPage())
    monkeypatch.setattr(relatorios, page_class_name, FakePage)
    monkeypatch.setattr(ReportOrchestrationService, "run", fake_run)

    result = relatorios.main(
        profile=profile,
        routines=[routine_id],
        publish=False,
    )
    captured_run["tasks"][routine_id].runner()

    assert result.status == ExecutionStatus.SUCCESS
    assert captured_report[start_field] == expected_start
    assert captured_report[end_field] == expected_end


def test_explicit_job_period_overrides_routine_configured_dates(monkeypatch, tmp_path):
    captured_run = {}
    captured_report = {}

    class FakePage:
        def __init__(self, _driver, _handle_menu):
            self.subpasta_download = ""
            self.tracker_name = ""

        def gerar_relatorio(self, **kwargs):
            captured_report.update(kwargs)
            return "ok"

        def fechar_e_voltar(self):
            return None

    class FakeMenuPage:
        @staticmethod
        def acessar_rotina(_routine_id):
            return SimpleNamespace(driver=object(), handle_menu=object())

    def fake_run(_self, **kwargs):
        captured_run.update(kwargs)
        return ExecutionResult(ExecutionStatus.SUCCESS, "ok")

    monkeypatch.setattr(relatorios, "settings", SimpleNamespace(download_dir=tmp_path))
    monkeypatch.setattr(relatorios, "menu_page", FakeMenuPage())
    monkeypatch.setattr(relatorios, "Relatorio030237Page", FakePage)
    monkeypatch.setattr(ReportOrchestrationService, "run", fake_run)

    result = relatorios.main(
        profile="adf",
        routines=["030237"],
        date_start="2020-01-01",
        date_end="2020-01-02",
        publish=False,
    )
    captured_run["tasks"]["030237"].runner()

    assert result.status == ExecutionStatus.SUCCESS
    assert captured_report["data_inicial"] == "01/01/2020"
    assert captured_report["data_final"] == "02/01/2020"
