from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.execution.execution_result import ExecutionResult, ExecutionStatus, normalize_execution_result
from core.observability.logger import get_logger
from core.files.movimentador import BASE_LOG_DIR, PENDING_DIR, publicar_arquivo_na_rede


logger = get_logger("PUBLICACAO")
PROCESSED_DIR = BASE_LOG_DIR / "publicacao_processada"


@dataclass(frozen=True)
class PublicationPlan:
    mapping: dict[str, str]
    success_message: str = "Movimentacao concluida com sucesso."
    partial_prefix: str = "Movimentacao concluida com pendencias de publicacao."
    technical_prefix: str = "Movimentacao finalizada com falha tecnica de publicacao."


def publicar_mapeamento_relatorios(
    logger,
    mapeamento_movimentacao,
    *,
    success_message: str = "Movimentacao concluida com sucesso.",
    partial_prefix: str = "Movimentacao concluida com pendencias de publicacao.",
    technical_prefix: str = "Movimentacao finalizada com falha tecnica de publicacao.",
    success_detail: str = "Publicacao concluida",
    failure_detail: str = "Publicacao sem detalhe",
):
    status_publicacao = ExecutionStatus.SUCCESS
    detalhes_publicacao: list[str] = []

    try:
        for origem, destino in mapeamento_movimentacao.items():
            logger.info(f"Movendo: {origem} -> {destino}")
            resultado_mov = normalize_execution_result(
                publicar_origem_para_destino(origem, destino),
                success_message=success_detail,
                failure_message=failure_detail,
            )

            if resultado_mov.status is ExecutionStatus.TECHNICAL_FAILURE:
                status_publicacao = ExecutionStatus.TECHNICAL_FAILURE
            elif (
                resultado_mov.status is ExecutionStatus.PARTIAL_SUCCESS
                and status_publicacao is ExecutionStatus.SUCCESS
            ):
                status_publicacao = ExecutionStatus.PARTIAL_SUCCESS

            if not resultado_mov.ok:
                detalhes_publicacao.append(resultado_mov.message)
    except Exception as exc:
        logger.error(f"Falha ao mover arquivos/pastas: {exc}", exc_info=True)
        status_publicacao = ExecutionStatus.TECHNICAL_FAILURE
        detalhes_publicacao.append(str(exc))

    if status_publicacao is ExecutionStatus.SUCCESS:
        logger.info(success_message)
        return ExecutionResult(status=ExecutionStatus.SUCCESS, message=success_message)

    if status_publicacao is ExecutionStatus.PARTIAL_SUCCESS:
        mensagem = partial_prefix
        if detalhes_publicacao:
            mensagem = f"{mensagem} " + " | ".join(detalhes_publicacao)
        logger.warning(mensagem)
        return ExecutionResult(status=ExecutionStatus.PARTIAL_SUCCESS, message=mensagem)

    mensagem = technical_prefix
    if detalhes_publicacao:
        mensagem = f"{mensagem} " + " | ".join(detalhes_publicacao)
    logger.error(mensagem)
    return ExecutionResult(status=ExecutionStatus.TECHNICAL_FAILURE, message=mensagem)


def publicar_origem_para_destino(origem, destino):
    from core.files.movimentador import mover_relatorios

    return mover_relatorios(origem, destino)


def _carregar_metadata(metadata_path: Path) -> dict:
    with metadata_path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _salvar_metadata(metadata_path: Path, metadata: dict) -> None:
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )


def _resolver_arquivo_pendente(pasta_pendencia: Path, metadata: dict) -> Path | None:
    caminho_metadata = metadata.get("arquivo_pendente")
    if caminho_metadata:
        arquivo = Path(caminho_metadata)
        if arquivo.is_file():
            return arquivo

    arquivos = [arquivo for arquivo in pasta_pendencia.iterdir() if arquivo.is_file() and arquivo.name != "metadata.json"]
    return arquivos[0] if len(arquivos) == 1 else None


def _arquivar_pasta_processada(pasta_pendencia: Path, processed_dir: Path) -> Path:
    processed_dir.mkdir(parents=True, exist_ok=True)
    destino = processed_dir / pasta_pendencia.name
    if destino.exists():
        destino = processed_dir / f"{pasta_pendencia.name}_{datetime.now().strftime('%H%M%S')}"
    shutil.move(str(pasta_pendencia), str(destino))
    return destino


def reprocessar_publicacoes_pendentes(
    *,
    logger=logger,
    pending_dir: Path | None = None,
    processed_dir: Path | None = None,
) -> ExecutionResult:
    pending_dir = Path(pending_dir or PENDING_DIR)
    processed_dir = Path(processed_dir or PROCESSED_DIR)

    if not pending_dir.exists():
        mensagem = f"Nenhuma pasta de pendencias encontrada em {pending_dir}"
        logger.info(mensagem)
        return ExecutionResult(status=ExecutionStatus.SUCCESS, message=mensagem)

    pastas_pendentes = sorted(
        pasta for pasta in pending_dir.iterdir()
        if pasta.is_dir() and (pasta / "metadata.json").is_file()
    )
    if not pastas_pendentes:
        mensagem = f"Nenhuma publicacao pendente encontrada em {pending_dir}"
        logger.info(mensagem)
        return ExecutionResult(status=ExecutionStatus.SUCCESS, message=mensagem)

    status_final = ExecutionStatus.SUCCESS
    detalhes: list[str] = []

    for pasta_pendencia in pastas_pendentes:
        metadata_path = pasta_pendencia / "metadata.json"
        metadata = _carregar_metadata(metadata_path)
        arquivo_pendente = _resolver_arquivo_pendente(pasta_pendencia, metadata)
        destino_original = Path(metadata.get("destino_original", ""))

        if not arquivo_pendente or not destino_original.name:
            metadata["status"] = "falha_reprocessamento"
            metadata["ultima_tentativa_em"] = datetime.now().isoformat(timespec="seconds")
            metadata["ultima_tentativa_detalhe"] = "Metadata incompleto ou arquivo pendente nao encontrado"
            _salvar_metadata(metadata_path, metadata)
            status_final = ExecutionStatus.TECHNICAL_FAILURE
            detalhes.append(f"Pendencia invalida em {pasta_pendencia}")
            continue

        logger.info(f"Reprocessando pendencia: {arquivo_pendente} -> {destino_original}")
        resultado = publicar_arquivo_na_rede(
            arquivo_pendente,
            destino_original,
            criar_pendencia_local=False,
        )

        metadata["ultima_tentativa_em"] = datetime.now().isoformat(timespec="seconds")
        metadata["ultima_tentativa_status"] = resultado.status.value
        metadata["ultima_tentativa_detalhe"] = resultado.message

        if resultado.status is ExecutionStatus.SUCCESS:
            metadata["status"] = "publicado"
            metadata["reprocessado_em"] = datetime.now().isoformat(timespec="seconds")
            _salvar_metadata(metadata_path, metadata)

            try:
                destino_processado = _arquivar_pasta_processada(pasta_pendencia, processed_dir)
                detalhes.append(f"Pendencia publicada e arquivada em {destino_processado}")
            except Exception as exc:
                status_final = ExecutionStatus.PARTIAL_SUCCESS
                detalhes.append(
                    f"Pendencia publicada para {destino_original}, mas falhou o arquivamento local: {exc}"
                )
        else:
            metadata["status"] = "falha_reprocessamento"
            _salvar_metadata(metadata_path, metadata)
            if resultado.status is ExecutionStatus.TECHNICAL_FAILURE:
                status_final = ExecutionStatus.TECHNICAL_FAILURE
            elif status_final is ExecutionStatus.SUCCESS:
                status_final = ExecutionStatus.PARTIAL_SUCCESS
            detalhes.append(resultado.message)

    if status_final is ExecutionStatus.SUCCESS:
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message="Reprocessamento das publicacoes pendentes concluido com sucesso.",
        )

    if status_final is ExecutionStatus.PARTIAL_SUCCESS:
        return ExecutionResult(
            status=ExecutionStatus.PARTIAL_SUCCESS,
            message="Reprocessamento concluido com pendencias: " + " | ".join(detalhes),
        )

    return ExecutionResult(
        status=ExecutionStatus.TECHNICAL_FAILURE,
        message="Reprocessamento com falhas tecnicas: " + " | ".join(detalhes),
    )


