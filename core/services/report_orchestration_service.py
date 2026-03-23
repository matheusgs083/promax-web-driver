from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from core.execution.execution_result import ExecutionResult, ExecutionStatus
from core.services.publication_service import PublicationPlan, publicar_mapeamento_relatorios
from core.services.report_post_processing_service import exportar_tracker_csv, higienizar_relatorios_intermediarios


@dataclass(frozen=True)
class RoutineTask:
    key: str
    name: str
    runner: Callable[[list[str] | None], object]


class ReportOrchestrationService:
    def __init__(
        self,
        *,
        logger,
        tracker,
        iniciar_sessao,
        executar_tarefa_com_retry,
        encerrar_sessao,
    ) -> None:
        self.logger = logger
        self.tracker = tracker
        self.iniciar_sessao = iniciar_sessao
        self.executar_tarefa_com_retry = executar_tarefa_com_retry
        self.encerrar_sessao = encerrar_sessao

    def run(
        self,
        *,
        tasks: dict[str, RoutineTask],
        tracker_output_dir,
        intermediate_dir,
        auxiliary_sheet=None,
        publication_plan: PublicationPlan | None = None,
        run_initial_execution: bool = True,
        automatic_repescagem: bool = False,
        manual_repescagem: dict[str, list[str]] | None = None,
        protect_artifacts_on_failure: bool = False,
    ) -> ExecutionResult:
        execution_result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message="Execucao principal concluida.",
        )

        try:
            if tasks or manual_repescagem:
                self.iniciar_sessao()

            if run_initial_execution:
                execution_result = self.executar_rotinas(tasks)

            if automatic_repescagem:
                automatic_result = self.executar_repescagem_automatica(tasks)
                execution_result = self._merge_results(
                    execution_result,
                    automatic_result,
                    success_message="Execucao e repescagem automatica concluidas.",
                )

            if manual_repescagem:
                manual_result = self.executar_repescagem_manual(tasks, manual_repescagem)
                execution_result = self._merge_results(
                    execution_result,
                    manual_result,
                    success_message="Execucao manual de repescagem concluida.",
                )
        except Exception as exc:
            self.logger.critical(f"ERRO FATAL NA ORQUESTRACAO DE RELATORIOS: {exc}", exc_info=True)
            execution_result = ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=f"Falha critica na execucao das rotinas: {exc}",
            )
        finally:
            self.encerrar_sessao()

        tracker_result = exportar_tracker_csv(self.tracker, tracker_output_dir, self.logger)

        if protect_artifacts_on_failure and not execution_result.ok:
            self.logger.warning(
                "Execucao abortada precocemente. Pos-processamento e publicacao foram cancelados para proteger os artefatos."
            )
            return self._merge_results(
                execution_result,
                tracker_result,
                success_message="Job finalizado sem pos-processamento.",
            )

        post_process_result = higienizar_relatorios_intermediarios(
            intermediate_dir,
            auxiliary_sheet,
            self.logger,
        )
        publication_result = self.publicar(publication_plan)
        return self._merge_results(
            execution_result,
            tracker_result,
            post_process_result,
            publication_result,
            success_message="Job concluido com sucesso, incluindo pos-processamento e publicacao.",
        )

    def executar_rotinas(self, tasks: dict[str, RoutineTask]) -> ExecutionResult:
        if not tasks:
            mensagem = "Nenhuma rotina configurada para execucao."
            self.logger.info(mensagem)
            return ExecutionResult(status=ExecutionStatus.SUCCESS, message=mensagem)

        self.logger.info("================ FASE: EXECUCAO DAS ROTINAS ================")
        for task in tasks.values():
            self.executar_tarefa_com_retry(task.name, lambda runner=task.runner: runner())

        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message=f"{len(tasks)} rotina(s) executada(s) com sucesso.",
        )

    def executar_repescagem_automatica(self, tasks: dict[str, RoutineTask]) -> ExecutionResult:
        falhas_por_rotina = self._coletar_falhas_por_rotina(tasks)
        if not falhas_por_rotina:
            mensagem = "Nenhuma falha detectada para repescagem automatica."
            self.logger.info(mensagem)
            return ExecutionResult(status=ExecutionStatus.SUCCESS, message=mensagem)

        self.logger.info("================ FASE: REPESCAGEM AUTOMATICA ===============")
        self.logger.info(f"Falhas detectadas! Iniciando retentativas: {falhas_por_rotina}")

        for key, unidades_com_erro in falhas_por_rotina.items():
            task = tasks[key]
            if unidades_com_erro == ["TODAS"] or len(unidades_com_erro) == 0:
                self.logger.info(f">>> Retentando {task.name} para TODAS as unidades")
                self.executar_tarefa_com_retry(f"{task.name} (REPESCAGEM)", lambda runner=task.runner: runner())
                continue

            self.logger.info(f">>> Retentando {task.name} apenas para as unidades: {unidades_com_erro}")
            self.executar_tarefa_com_retry(
                f"{task.name} (REPESCAGEM)",
                lambda runner=task.runner, unidades=unidades_com_erro: runner(unidades),
            )

        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message=f"Repescagem automatica executada para {len(falhas_por_rotina)} rotina(s).",
        )

    def executar_repescagem_manual(
        self,
        tasks: dict[str, RoutineTask],
        manual_repescagem: dict[str, list[str]],
    ) -> ExecutionResult:
        if not manual_repescagem:
            mensagem = "Nenhum alvo configurado para repescagem manual."
            self.logger.info(mensagem)
            return ExecutionResult(status=ExecutionStatus.SUCCESS, message=mensagem)

        faltantes = [key for key in manual_repescagem if key not in tasks]
        if faltantes:
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=f"Rotinas nao encontradas para repescagem manual: {faltantes}",
            )

        self.logger.info("================ FASE: REPESCAGEM MANUAL ===============")
        for key, unidades_alvo in manual_repescagem.items():
            task = tasks[key]
            self.logger.info(f">>> Executando {task.name} apenas para as unidades: {unidades_alvo}")
            self.executar_tarefa_com_retry(
                f"{task.name} (REPESCAGEM)",
                lambda runner=task.runner, unidades=unidades_alvo: runner(unidades),
            )

        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message=f"Repescagem manual executada para {len(manual_repescagem)} rotina(s).",
        )

    def publicar(self, publication_plan: PublicationPlan | None) -> ExecutionResult:
        if not publication_plan or not publication_plan.mapping:
            mensagem = "Nenhum mapeamento de publicacao configurado."
            self.logger.info(mensagem)
            return ExecutionResult(status=ExecutionStatus.SUCCESS, message=mensagem)

        self.logger.info("================ FASE: PUBLICACAO ===============")
        return publicar_mapeamento_relatorios(
            self.logger,
            publication_plan.mapping,
            success_message=publication_plan.success_message,
            partial_prefix=publication_plan.partial_prefix,
            technical_prefix=publication_plan.technical_prefix,
        )

    def _coletar_falhas_por_rotina(self, tasks: dict[str, RoutineTask]) -> dict[str, list[str]]:
        falhas_por_rotina: dict[str, list[str]] = {}
        for registro in getattr(self.tracker, "registros", []):
            status = str(registro.get("Status", "")).strip().upper()
            rotina_registrada = registro.get("Rotina", "")
            unidade_falhou = str(registro.get("Unidade", "TODAS")).strip()

            if status == "SUCESSO" or rotina_registrada == "RESUMO FINAL":
                continue

            key = self._extrair_chave_rotina(rotina_registrada)
            if not key or key not in tasks:
                continue

            falhas_por_rotina.setdefault(key, [])

            if unidade_falhou == "TODAS":
                falhas_por_rotina[key] = ["TODAS"]
                continue

            if "TODAS" in falhas_por_rotina[key]:
                continue

            if unidade_falhou not in falhas_por_rotina[key]:
                falhas_por_rotina[key].append(unidade_falhou)

        return falhas_por_rotina

    @staticmethod
    def _extrair_chave_rotina(nome_rotina) -> str | None:
        if not nome_rotina:
            return None
        match = re.search(r"\b(\d{4,6})\b", str(nome_rotina))
        return match.group(1) if match else None

    @staticmethod
    def _merge_results(*results: ExecutionResult, success_message: str) -> ExecutionResult:
        status_final = ExecutionStatus.SUCCESS
        detalhes: list[str] = []

        for result in results:
            if not result:
                continue

            if result.status in {ExecutionStatus.ABORTED, ExecutionStatus.TECHNICAL_FAILURE}:
                status_final = ExecutionStatus.TECHNICAL_FAILURE
            elif (
                result.status is ExecutionStatus.BUSINESS_FAILURE
                and status_final is not ExecutionStatus.TECHNICAL_FAILURE
            ):
                status_final = ExecutionStatus.BUSINESS_FAILURE
            elif (
                result.status is ExecutionStatus.PARTIAL_SUCCESS
                and status_final is ExecutionStatus.SUCCESS
            ):
                status_final = ExecutionStatus.PARTIAL_SUCCESS

            if result.message and (not result.ok or result.status is not ExecutionStatus.SUCCESS):
                detalhes.append(result.message)

        if status_final is ExecutionStatus.SUCCESS:
            return ExecutionResult(status=ExecutionStatus.SUCCESS, message=success_message)

        prefix = {
            ExecutionStatus.PARTIAL_SUCCESS: "Job concluido com pendencias:",
            ExecutionStatus.BUSINESS_FAILURE: "Job concluido com falhas de negocio:",
            ExecutionStatus.TECHNICAL_FAILURE: "Job concluido com falhas tecnicas:",
        }[status_final]
        mensagem = prefix if not detalhes else f"{prefix} " + " | ".join(detalhes)
        return ExecutionResult(status=status_final, message=mensagem)



