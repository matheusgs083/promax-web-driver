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
