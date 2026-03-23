from __future__ import annotations

import shutil
from pathlib import Path

from core.execution.execution_result import ExecutionResult, ExecutionStatus
from core.services.publication_service import PublicationPlan
from core.services.report_orchestration_service import ReportOrchestrationService, RoutineTask


class DummyLogger:
    def info(self, *_args, **_kwargs):
        return None

    def warning(self, *_args, **_kwargs):
        return None

    def error(self, *_args, **_kwargs):
        return None

    def critical(self, *_args, **_kwargs):
        return None


class FakeTracker:
    def __init__(self, registros=None):
        self.registros = list(registros or [])

    def gerar_csv(self, _destino):
        return None


def test_repescagem_automatica_reexecuta_apenas_unidades_falhas():
    chamadas_runner = []
    chamadas_retry = []
    tracker = FakeTracker(
        [
            {"Status": "FALHA DOWNLOAD", "Rotina": "Rotina 120601", "Unidade": "3610007"},
            {"Status": "SUCESSO", "Rotina": "Rotina 120601", "Unidade": "3610008"},
        ]
    )

    service = ReportOrchestrationService(
        logger=DummyLogger(),
        tracker=tracker,
        iniciar_sessao=lambda: None,
        executar_tarefa_com_retry=lambda nome, funcao: chamadas_retry.append((nome, funcao())),
        encerrar_sessao=lambda: None,
    )
    tarefas = {
        "120601": RoutineTask(
            key="120601",
            name="Rotina 120601",
            runner=lambda unidades=None: chamadas_runner.append(unidades),
        )
    }

    resultado = service.executar_repescagem_automatica(tarefas)

    assert resultado.status == ExecutionStatus.SUCCESS
    assert chamadas_retry == [("Rotina 120601 (REPESCAGEM)", None)]
    assert chamadas_runner == [["3610007"]]


def test_execucao_normal_preserva_defaults_do_runner():
    chamadas_runner = []
    service = ReportOrchestrationService(
        logger=DummyLogger(),
        tracker=FakeTracker(),
        iniciar_sessao=lambda: None,
        executar_tarefa_com_retry=lambda _nome, funcao: funcao(),
        encerrar_sessao=lambda: None,
    )
    tarefas = {
        "030237": RoutineTask(
            key="030237",
            name="Rotina 030237 Giro",
            runner=lambda unidades=("3610006", "3610007"): chamadas_runner.append(unidades),
        )
    }

    resultado = service.executar_rotinas(tarefas)

    assert resultado.status == ExecutionStatus.SUCCESS
    assert chamadas_runner == [("3610006", "3610007")]


def test_run_protege_artefatos_quando_execucao_falha(monkeypatch):
    pasta_base = Path.cwd() / ".test_tmp_orquestrador"
    shutil.rmtree(pasta_base, ignore_errors=True)
    pasta_base.mkdir(parents=True, exist_ok=True)
    try:
        tracker = FakeTracker()
        service = ReportOrchestrationService(
            logger=DummyLogger(),
            tracker=tracker,
            iniciar_sessao=lambda: None,
            executar_tarefa_com_retry=lambda _nome, funcao: funcao(),
            encerrar_sessao=lambda: None,
        )
        tarefas = {
            "120601": RoutineTask(
                key="120601",
                name="Rotina 120601",
                runner=lambda _unidades=None: (_ for _ in ()).throw(RuntimeError("falha fatal")),
            )
        }
        chamadas = {"pos": 0, "pub": 0}

        monkeypatch.setattr(
            "core.services.report_orchestration_service.exportar_tracker_csv",
            lambda *_args, **_kwargs: ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="tracker exportado",
            ),
        )

        def fake_higienizar(*_args, **_kwargs):
            chamadas["pos"] += 1
            return ExecutionResult(status=ExecutionStatus.SUCCESS, message="ok")

        monkeypatch.setattr(
            "core.services.report_orchestration_service.higienizar_relatorios_intermediarios",
            fake_higienizar,
        )

        def fake_publicar(_self, _plan):
            chamadas["pub"] += 1
            return ExecutionResult(status=ExecutionStatus.SUCCESS, message="ok")

        monkeypatch.setattr(ReportOrchestrationService, "publicar", fake_publicar)

        resultado = service.run(
            tasks=tarefas,
            tracker_output_dir=pasta_base / "tracker",
            intermediate_dir=pasta_base / "intermediario",
            publication_plan=PublicationPlan(mapping={"origem": "destino"}),
            protect_artifacts_on_failure=True,
        )

        assert resultado.status == ExecutionStatus.TECHNICAL_FAILURE
        assert chamadas == {"pos": 0, "pub": 0}
    finally:
        shutil.rmtree(pasta_base, ignore_errors=True)




