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
    assert captured["post_process_dirs"] == [tmp_path]
    assert {
        source.relative_to(tmp_path).parts[0]
        for source in map(Path, captured["publication_plan"].mapping)
    } == {"020220 Recolhas"}
    assert result.metadata["publication_mapping"] == {
        str(source): str(destination)
        for source, destination in captured["publication_plan"].mapping.items()
    }


def test_bot_zap_geo_routines_use_single_download_without_unit_loop(monkeypatch, tmp_path):
    captured_run = {}
    captured_reports = {}

    class Fake020220Page:
        def __init__(self, _driver, _handle_menu):
            self.subpasta_download = ""
            self.tracker_name = ""

        def gerar_relatorio(self, **kwargs):
            captured_reports["020220_BOT"] = kwargs
            return "ok"

        def fechar_e_voltar(self):
            return None

    class Fake0105070402Page:
        def __init__(self, _driver, _handle_menu):
            self.subpasta_download = ""
            self.tracker_name = ""

        def gerar_relatorio(self, **kwargs):
            captured_reports["0105070402_BOT"] = kwargs
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
    monkeypatch.setattr(relatorios, "Relatorio020220Page", Fake020220Page)
    monkeypatch.setattr(relatorios, "Relatorio0105070402Page", Fake0105070402Page)
    monkeypatch.setattr(ReportOrchestrationService, "run", fake_run)

    relatorios.main(
        profile="bot_zap",
        routines=["020220_BOT", "0105070402_BOT"],
        units=["0640001", "2210003"],
        publish=False,
    )
    captured_run["tasks"]["020220_BOT"].runner()
    captured_run["tasks"]["0105070402_BOT"].runner()

    assert captured_reports["020220_BOT"]["unidade"] == "0640001"
    assert "unidade" not in captured_reports["0105070402_BOT"]


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


def test_030111_bot_is_registered_for_worker_catalog_and_runner(monkeypatch, tmp_path):
    captured_run = {}
    captured_report = {}

    class Fake030111Page:
        def __init__(self, _driver, _handle_menu):
            self.subpasta_download = ""
            self.tracker_name = ""

        def gerar_relatorio(self, **kwargs):
            captured_report.update(kwargs)
            captured_report["subpasta_download"] = self.subpasta_download
            captured_report["tracker_name"] = self.tracker_name
            return "ok"

        def fechar_e_voltar(self):
            return None

    class FakeMenuPage:
        @staticmethod
        def acessar_rotina(routine_id):
            assert routine_id == "030111"
            return SimpleNamespace(driver=object(), handle_menu=object())

    def fake_run(_self, **kwargs):
        captured_run.update(kwargs)
        return ExecutionResult(ExecutionStatus.SUCCESS, "ok")

    monkeypatch.setattr(relatorios, "settings", SimpleNamespace(download_dir=tmp_path))
    monkeypatch.setattr(relatorios, "menu_page", FakeMenuPage())
    monkeypatch.setattr(relatorios, "Relatorio030111Page", Fake030111Page)
    monkeypatch.setattr(ReportOrchestrationService, "run", fake_run)

    result = relatorios.main(
        profile="bot_zap",
        routines=["030111_BOT"],
        units=["2210003"],
        publish=True,
    )
    captured_run["tasks"]["030111_BOT"].runner()

    assert result.status == ExecutionStatus.SUCCESS
    assert captured_report["unidade"] == ["2210003"]
    assert captured_report["subpasta_download"] == "030111 bot"
    assert captured_report["tracker_name"] == "Rotina 030111 Bot"
    assert captured_report["nome_arquivo"] == "030111 bot - nomeUnidade030111"
    assert {
        source.relative_to(tmp_path).parts[0]
        for source in map(Path, captured_run["publication_plan"].mapping)
    } == {"030111 bot"}


def test_031702_bot_is_registered_for_worker_catalog_and_runner(monkeypatch, tmp_path):
    captured_run = {}
    captured_report = {}

    class Fake031702Page:
        def __init__(self, _driver, _handle_menu):
            self.subpasta_download = ""
            self.tracker_name = ""

        def gerar_relatorio(self, **kwargs):
            captured_report.update(kwargs)
            captured_report["subpasta_download"] = self.subpasta_download
            captured_report["tracker_name"] = self.tracker_name
            return "ok"

        def fechar_e_voltar(self):
            return None

    class FakeMenuPage:
        @staticmethod
        def acessar_rotina(routine_id):
            assert routine_id == "031702"
            return SimpleNamespace(driver=object(), handle_menu=object())

    def fake_run(_self, **kwargs):
        captured_run.update(kwargs)
        return ExecutionResult(ExecutionStatus.SUCCESS, "ok")

    monkeypatch.setattr(relatorios, "settings", SimpleNamespace(download_dir=tmp_path))
    monkeypatch.setattr(relatorios, "menu_page", FakeMenuPage())
    monkeypatch.setattr(relatorios, "Relatorio031702Page", Fake031702Page)
    monkeypatch.setattr(ReportOrchestrationService, "run", fake_run)

    result = relatorios.main(
        profile="bot_zap",
        routines=["031702_BOT"],
        units=["2210003"],
        publish=True,
    )
    captured_run["tasks"]["031702_BOT"].runner()

    assert result.status == ExecutionStatus.SUCCESS
    assert captured_report["unidade"] == ["2210003"]
    assert captured_report["tipos_documento"] == ["001", "003", "004", "005", "016", "019"]
    assert captured_report["subpasta_download"] == "031702 bot"
    assert captured_report["tracker_name"] == "Rotina 031702 Bot"
    assert captured_report["nome_arquivo"] == "031702 bot - nomeUnidade031702"
    assert {
        source.relative_to(tmp_path).parts[0]
        for source in map(Path, captured_run["publication_plan"].mapping)
    } == {"031702 bot"}


def test_020304_bot_is_registered_for_worker_catalog_and_runner(monkeypatch, tmp_path):
    captured_run = {}
    captured_report = {}

    class Fake020304Page:
        def __init__(self, _driver, _handle_menu):
            self.subpasta_download = ""
            self.tracker_name = ""

        def gerar_relatorio(self, **kwargs):
            captured_report.update(kwargs)
            captured_report["subpasta_download"] = self.subpasta_download
            captured_report["tracker_name"] = self.tracker_name
            return "ok"

        def fechar_e_voltar(self):
            return None

    class FakeMenuPage:
        @staticmethod
        def acessar_rotina(routine_id):
            assert routine_id == "020304"
            return SimpleNamespace(driver=object(), handle_menu=object())

    def fake_run(_self, **kwargs):
        captured_run.update(kwargs)
        return ExecutionResult(ExecutionStatus.SUCCESS, "ok")

    monkeypatch.setattr(relatorios, "settings", SimpleNamespace(download_dir=tmp_path))
    monkeypatch.setattr(relatorios, "menu_page", FakeMenuPage())
    monkeypatch.setattr(relatorios, "Relatorio020304Page", Fake020304Page)
    monkeypatch.setattr(ReportOrchestrationService, "run", fake_run)

    result = relatorios.main(
        profile="bot_zap",
        routines=["020304_BOT"],
        units=["2210003"],
        publish=True,
    )
    captured_run["tasks"]["020304_BOT"].runner()

    assert result.status == ExecutionStatus.SUCCESS
    assert captured_report["unidade"] == ["2210003"]
    assert captured_report["subpasta_download"] == "020304 bot"
    assert captured_report["tracker_name"] == "Rotina 020304 Bot"
    assert captured_report["nome_arquivo"] == "020304 bot - nomeUnidade020304"
    assert {
        source.relative_to(tmp_path).parts[0]
        for source in map(Path, captured_run["publication_plan"].mapping)
    } == {"020304 bot"}


def test_031120_bot_uses_map_central_warehouse_defaults(monkeypatch, tmp_path):
    captured_report = {}
    captured_run = {}

    class Fake031120Page:
        def __init__(self, driver, handle_menu):
            self.subpasta_download = None
            self.tracker_name = None

        def gerar_relatorio(self, **kwargs):
            captured_report.update(kwargs)
            captured_report["subpasta_download"] = self.subpasta_download
            captured_report["tracker_name"] = self.tracker_name
            return True

        def fechar_e_voltar(self):
            return None

    class FakeMenuPage:
        @staticmethod
        def acessar_rotina(routine_id):
            assert routine_id == "031120"
            return SimpleNamespace(driver=object(), handle_menu=object())

    def fake_run(_self, **kwargs):
        captured_run.update(kwargs)
        return ExecutionResult(ExecutionStatus.SUCCESS, "ok")

    monkeypatch.setattr(relatorios, "settings", SimpleNamespace(download_dir=tmp_path))
    monkeypatch.setattr(relatorios, "menu_page", FakeMenuPage())
    monkeypatch.setattr(relatorios, "Relatorio031120Page", Fake031120Page)
    monkeypatch.setattr(ReportOrchestrationService, "run", fake_run)

    result = relatorios.main(
        profile="bot_zap",
        routines=["031120_BOT"],
        units=["2210003"],
        publish=True,
    )
    captured_run["tasks"]["031120_BOT"].runner()

    assert result.status == ExecutionStatus.SUCCESS
    assert captured_report["unidade"] == ["2210003"]
    assert captured_report["opcao_rel"] == "1"
    assert captured_report["cod_armazem"] == "01"
    assert captured_report["data_final"] == relatorios.data_hoje_formatada
    assert captured_report["data_inicial"] == relatorios.data_duas_semanas_atras_formatada
    assert captured_report["subpasta_download"] == "031120 bot"
    assert captured_report["tracker_name"] == "Rotina 031120 Bot"
    assert captured_report["nome_arquivo"] == "031120 bot - nomeUnidade031120"
    assert {
        source.relative_to(tmp_path).parts[0]
        for source in map(Path, captured_run["publication_plan"].mapping)
    } == {"031120 bot"}


def test_03114902_bot_uses_single_geo_csv_for_all_operations(monkeypatch, tmp_path):
    captured_report = {}
    captured_run = {}

    class Fake03114902Page:
        def __init__(self, driver, handle_menu):
            self.subpasta_download = None
            self.tracker_name = None

        def gerar_relatorio(self, **kwargs):
            captured_report.update(kwargs)
            captured_report["subpasta_download"] = self.subpasta_download
            captured_report["tracker_name"] = self.tracker_name
            return True

        def fechar_e_voltar(self):
            return None

    class FakeMenuPage:
        @staticmethod
        def acessar_rotina(routine_id):
            assert routine_id == "03114902"
            return SimpleNamespace(driver=object(), handle_menu=object())

    def fake_run(_self, **kwargs):
        captured_run.update(kwargs)
        return ExecutionResult(ExecutionStatus.SUCCESS, "ok")

    monkeypatch.setattr(relatorios, "settings", SimpleNamespace(download_dir=tmp_path))
    monkeypatch.setattr(relatorios, "menu_page", FakeMenuPage())
    monkeypatch.setattr(relatorios, "Relatorio03114902Page", Fake03114902Page)
    monkeypatch.setattr(ReportOrchestrationService, "run", fake_run)

    result = relatorios.main(
        profile="bot_zap",
        routines=["03114902_BOT"],
        units=["2210003", "2210004"],
        publish=True,
    )
    captured_run["tasks"]["03114902_BOT"].runner()

    assert result.status == ExecutionStatus.SUCCESS
    assert captured_report["unidade"] == "2210003"
    assert captured_report["classificacao"] == "Mapa"
    assert captured_report["todas_operacoes"] is True
    assert captured_report["csv_geo"] is True
    assert captured_report["armazem"] == "Todos"
    assert captured_report["data_final"] == relatorios.data_hoje_formatada
    assert captured_report["data_inicial"] == relatorios.data_duas_semanas_atras_formatada
    assert captured_report["subpasta_download"] == "03114902 bot"
    assert captured_report["tracker_name"] == "Rotina 03114902 Geo Bot"
    assert captured_report["nome_arquivo"] == "03114902 bot - geo.csv"
    assert {
        source.relative_to(tmp_path).parts[0]
        for source in map(Path, captured_run["publication_plan"].mapping)
    } == {"03114902 bot"}
