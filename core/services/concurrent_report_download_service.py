from __future__ import annotations

import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from threading import Lock

from core.execution.execution_result import ExecutionResult, ExecutionStatus
from core.files.manipulador_download import (
    DownloadHttpPreparado,
    executar_download_http_preparado,
)
from core.observability.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ResultadoDownloadFila:
    nome_arquivo: str
    ok: bool
    motivo: str
    tentativas: int


class FilaDownloadsRelatorios:
    def __init__(
        self,
        *,
        max_workers: int = 5,
        max_retentativas_html: int = 1,
        intervalo_retentativa: float = 1.0,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers deve ser maior que zero")
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="promax-download",
        )
        self._max_retentativas_html = max(0, max_retentativas_html)
        self._intervalo_retentativa = max(0.0, intervalo_retentativa)
        self._futuros: dict[Future, str] = {}
        self._lock = Lock()
        self._aceitando = True

    def enviar(self, download: DownloadHttpPreparado) -> None:
        with self._lock:
            if not self._aceitando:
                raise RuntimeError("Fila de downloads já está em encerramento")
            futuro = self._executor.submit(self._executar_com_retentativa, download)
            self._futuros[futuro] = download.nome_arquivo

    def _executar_com_retentativa(
        self,
        download: DownloadHttpPreparado,
    ) -> ResultadoDownloadFila:
        total_tentativas = 1 + self._max_retentativas_html
        ultimo_motivo = "Falha sem detalhe"

        for tentativa in range(1, total_tentativas + 1):
            ok, motivo = executar_download_http_preparado(download)
            ultimo_motivo = motivo
            if ok:
                return ResultadoDownloadFila(
                    nome_arquivo=download.nome_arquivo,
                    ok=True,
                    motivo=motivo,
                    tentativas=tentativa,
                )

            permite_retentativa = (
                tentativa < total_tentativas
                and "resposta html sem url temporária" in motivo.lower()
            )
            if not permite_retentativa:
                break

            logger.warning(
                "Relatório %s retornou HTML sem arquivo; repetindo apenas esta requisição.",
                download.nome_arquivo,
            )
            if self._intervalo_retentativa:
                time.sleep(self._intervalo_retentativa)

        return ResultadoDownloadFila(
            nome_arquivo=download.nome_arquivo,
            ok=False,
            motivo=ultimo_motivo,
            tentativas=tentativa,
        )

    def aguardar(self) -> ExecutionResult:
        with self._lock:
            self._aceitando = False
            futuros = dict(self._futuros)

        if not futuros:
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="Nenhum download HTTP pendente.",
            )

        resultados: list[ResultadoDownloadFila] = []
        for futuro in as_completed(futuros):
            nome_arquivo = futuros[futuro]
            try:
                resultados.append(futuro.result())
            except Exception as exc:
                resultados.append(
                    ResultadoDownloadFila(
                        nome_arquivo=nome_arquivo,
                        ok=False,
                        motivo=f"Exceção no worker: {exc}",
                        tentativas=1,
                    )
                )

        falhas = [resultado for resultado in resultados if not resultado.ok]
        if not falhas:
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"{len(resultados)} download(s) HTTP concluído(s).",
            )

        detalhes = "; ".join(
            f"{resultado.nome_arquivo}: {resultado.motivo}"
            for resultado in falhas
        )
        status = (
            ExecutionStatus.PARTIAL_SUCCESS
            if len(falhas) < len(resultados)
            else ExecutionStatus.TECHNICAL_FAILURE
        )
        return ExecutionResult(
            status=status,
            message=(
                f"{len(falhas)} de {len(resultados)} download(s) HTTP falharam: "
                f"{detalhes}"
            ),
        )

    def encerrar(self) -> None:
        with self._lock:
            self._aceitando = False
        self._executor.shutdown(wait=True)
