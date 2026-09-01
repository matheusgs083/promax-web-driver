from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import cli
import pytest
from core.execution.execution_result import ExecutionResult, ExecutionStatus


def test_report_parser_accepts_dynamic_group_contract() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(
        [
            "relatorios",
            "--perfil",
            "outros",
            "--data-inicial",
            "2026-07-01",
            "--data-final",
            "2026-07-17",
            "--unidade",
            "2210003",
            "--rotinas",
            "020220_AUDITOOL",
            "020220_RECOLHAS",
            "--somente-baixar",
            "--job-id",
            "job-1",
        ]
    )

    assert args.perfil == "outros"
    assert args.unidade == ["2210003"]
    assert args.rotinas == ["020220_AUDITOOL", "020220_RECOLHAS"]
    assert args.publicar is False


def test_fechamento_parser_accepts_dynamic_group_contract() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(
        [
            "fechamento",
            "--perfil",
            "botzapfechamento",
            "--unidade",
            "2210003",
            "--rotinas",
            "150501",
            "--somente-baixar",
            "--job-id",
            "job-fechamento-relatorios",
        ]
    )

    assert args.perfil == "botzapfechamento"
    assert args.unidade == ["2210003"]
    assert args.rotinas == ["150501"]
    assert args.publicar is False


def test_main_cli_propagates_execution_status(monkeypatch, capsys) -> None:
    calls = []
    from core.observability.relatorio_execucao import tracker

    tracker.registros.clear()
    tracker.registros.append(
        {
            "Rotina": "Rotina 120601",
            "Unidade": "3610008",
            "Status": "FALHA DOWNLOAD",
            "Detalhes": "Resposta HTML sem URL temporaria",
        }
    )
    fake_module = SimpleNamespace(
        main=lambda **kwargs: (
            calls.append(kwargs)
            or ExecutionResult(ExecutionStatus.PARTIAL_SUCCESS, "pendencias")
        )
    )
    monkeypatch.setattr(cli.importlib, "import_module", lambda _name: fake_module)
    monkeypatch.setattr(
        sys,
        "argv",
        ["cli.py", "relatorios", "--perfil", "fluxo_caixa", "--job-id", "job-2"],
    )

    try:
        assert cli.main_cli() == 10
        assert calls[0]["profile"] == "fluxo_caixa"
        payload = json.loads(capsys.readouterr().out)
        assert payload["job_id"] == "job-2"
        assert payload["failed_units"] == ["3610008"]
        assert payload["failed_unit_details"][0]["detail"] == "Resposta HTML sem URL temporaria"
    finally:
        tracker.registros.clear()


def test_main_cli_emits_no_content_units_for_controlled_jobs(monkeypatch, capsys) -> None:
    from core.observability.relatorio_execucao import tracker

    tracker.registros.clear()
    tracker.registros.append(
        {
            "Rotina": "Rotina 030111 Bot",
            "Unidade": "2210003",
            "Status": "SEM CONTEUDO",
            "Detalhes": "Nao ha pedidos para listar",
        }
    )
    fake_module = SimpleNamespace(
        main=lambda **_kwargs: ExecutionResult(ExecutionStatus.PARTIAL_SUCCESS, "sem dados")
    )
    monkeypatch.setattr(cli.importlib, "import_module", lambda _name: fake_module)
    monkeypatch.setattr(
        sys,
        "argv",
        ["cli.py", "relatorios", "--perfil", "bot_zap", "--job-id", "job-3"],
    )

    try:
        assert cli.main_cli() == 10
        payload = json.loads(capsys.readouterr().out)
        assert payload["failed_units"] == []
        assert payload["no_content_units"] == ["2210003"]
        assert payload["no_content_unit_details"][0]["detail"] == "Nao ha pedidos para listar"
    finally:
        tracker.registros.clear()


def test_fechamento_cli_emits_worker_json(monkeypatch, capsys) -> None:
    calls = []
    fake_module = SimpleNamespace(
        main=lambda **kwargs: (
            calls.append(kwargs)
            or ExecutionResult(ExecutionStatus.SUCCESS, "fechamento ok")
        )
    )
    monkeypatch.setattr(cli.importlib, "import_module", lambda _name: fake_module)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli.py",
            "fechamento",
            "--perfil",
            "botzapfechamento",
            "--unidade",
            "2210003",
            "--rotinas",
            "150501",
            "--job-id",
            "job-fechamento-relatorios",
        ],
    )

    assert cli.main_cli() == 0
    assert calls[0]["profile"] == "botzapfechamento"
    assert calls[0]["units"] == ["2210003"]
    assert calls[0]["routines"] == ["150501"]
    payload = json.loads(capsys.readouterr().out)
    assert payload["operation"] == "fechamento"
    assert payload["job_id"] == "job-fechamento-relatorios"


def test_reprocess_publication_emits_controlled_job_summary(
    monkeypatch,
    capsys,
) -> None:
    fake_module = SimpleNamespace(
        main=lambda: ExecutionResult(
            ExecutionStatus.PARTIAL_SUCCESS,
            "Reprocessamento parcial: 2/3 publicadas; 1 permanece pendente.",
        )
    )
    monkeypatch.setattr(cli.importlib, "import_module", lambda _name: fake_module)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli.py",
            "reprocessar-publicacao",
            "--job-id",
            "job-reprocess-1",
        ],
    )

    assert cli.main_cli() == 10
    payload = json.loads(capsys.readouterr().out)
    assert payload["operation"] == "reprocessar-publicacao"
    assert payload["job_id"] == "job-reprocess-1"
    assert payload["message"].startswith("Reprocessamento parcial:")


def test_fechamento_mapa_emits_worker_json_with_serialized_metadata(
    monkeypatch,
    capsys,
) -> None:
    calls = []
    fake_module = SimpleNamespace(
        main=lambda **kwargs: (
            calls.append(kwargs)
            or ExecutionResult(
                ExecutionStatus.SUCCESS,
                "Mapa fechado.",
                metadata={
                    "mapa": "93741",
                    "resultado_financeiro": ExecutionResult(
                        ExecutionStatus.SUCCESS,
                        "Financeiro ok.",
                    ),
                },
            )
        )
    )
    monkeypatch.setattr(cli.importlib, "import_module", lambda _name: fake_module)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli.py",
            "fechamento-mapa",
            "--mapa",
            "93741",
            "--unidade",
            "PATOS",
            "--job-id",
            "job-mapa-1",
        ],
    )

    assert cli.main_cli() == 0
    assert calls[0]["mapa"] == "93741"
    assert calls[0]["unidade"] == "PATOS"
    payload = json.loads(capsys.readouterr().out)
    assert payload["operation"] == "fechamento-mapa"
    assert payload["job_id"] == "job-mapa-1"
    assert payload["metadata"]["resultado_financeiro"]["status"] == "SUCESSO"


def test_catalog_command_emits_json_without_importing_entrypoint(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        cli.importlib,
        "import_module",
        lambda _name: pytest.fail("catalogo nao deve importar entrypoints"),
    )
    monkeypatch.setattr(sys, "argv", ["cli.py", "catalogo-relatorios"])

    assert cli.main_cli() == 0
    catalog = json.loads(capsys.readouterr().out)
    assert {group["key"] for group in catalog["report_groups"]} >= {
        "outros",
        "fluxo_caixa",
    }
