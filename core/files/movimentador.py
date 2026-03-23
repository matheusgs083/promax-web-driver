import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from core.execution.execution_result import ExecutionResult, ExecutionStatus
from core.observability.logger import get_logger
from core.config.project_paths import LOGS_DIR


logger = get_logger("MOVIMENTADOR")

BASE_LOG_DIR = LOGS_DIR
PENDING_DIR = BASE_LOG_DIR / "publicacao_pendente"
EVENT_LOG_FILE = BASE_LOG_DIR / "publicacao_eventos.jsonl"


def _ensure_log_dirs() -> None:
    BASE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    PENDING_DIR.mkdir(parents=True, exist_ok=True)


def _slugify_path(value: str) -> str:
    permitido = []
    for ch in str(value):
        if ch.isalnum() or ch in ("-", "_", "."):
            permitido.append(ch)
        else:
            permitido.append("_")
    return "".join(permitido).strip("_")[:80] or "destino"


def _registrar_evento(
    *,
    etapa: str,
    status: str,
    origem: Path,
    destino: Path,
    detalhe: str,
    tamanho_origem: int | None = None,
    tamanho_destino: int | None = None,
    pendencia: Path | None = None,
) -> None:
    _ensure_log_dirs()
    evento = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "etapa": etapa,
        "status": status,
        "origem": str(origem),
        "destino": str(destino),
        "detalhe": detalhe,
        "tamanho_origem": tamanho_origem,
        "tamanho_destino": tamanho_destino,
        "pendencia": str(pendencia) if pendencia else None,
    }
    with EVENT_LOG_FILE.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(evento, ensure_ascii=True) + "\n")


def _validar_origem_publicacao(origem: Path) -> int:
    if not origem.exists():
        raise FileNotFoundError(f"Arquivo de origem nao existe: {origem}")
    if not origem.is_file():
        raise RuntimeError(f"Origem nao e arquivo: {origem}")
    tamanho = origem.stat().st_size
    if tamanho <= 0:
        raise RuntimeError(f"Arquivo de origem vazio: {origem}")
    with origem.open("rb"):
        pass
    return tamanho


def _validar_arquivo_publicado(origem: Path, destino_final: Path, tamanho_origem: int) -> int:
    if not destino_final.exists():
        raise RuntimeError(f"Arquivo final nao existe apos publicacao: {destino_final}")
    if not destino_final.is_file():
        raise RuntimeError(f"Caminho final nao e arquivo: {destino_final}")
    tamanho_destino = destino_final.stat().st_size
    if tamanho_destino <= 0:
        raise RuntimeError(f"Arquivo final ficou vazio: {destino_final}")
    if tamanho_destino != tamanho_origem:
        raise RuntimeError(
            f"Tamanho divergente na publicacao. Origem={tamanho_origem} Destino={tamanho_destino}"
        )
    with destino_final.open("rb"):
        pass
    return tamanho_destino


def _criar_pendencia_local(origem: Path, destino_original: Path, motivo: str) -> Path:
    _ensure_log_dirs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta_pendencia = PENDING_DIR / f"{timestamp}_{_slugify_path(destino_original.parent)}_{uuid.uuid4().hex[:8]}"
    pasta_pendencia.mkdir(parents=True, exist_ok=True)

    arquivo_pendente = pasta_pendencia / origem.name
    metadata_path = pasta_pendencia / "metadata.json"

    shutil.copy2(str(origem), str(arquivo_pendente))
    tamanho_pendente = _validar_origem_publicacao(arquivo_pendente)

    metadata = {
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "origem_original": str(origem),
        "destino_original": str(destino_original),
        "arquivo_pendente": str(arquivo_pendente),
        "motivo": motivo,
        "tamanho": tamanho_pendente,
        "status": "pendente_publicacao",
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=True, indent=2), encoding="utf-8")
    return arquivo_pendente


def publicar_arquivo_na_rede(
    origem: Path,
    destino_final: Path,
    *,
    criar_pendencia_local: bool = True,
) -> ExecutionResult:
    staging = destino_final.parent / f".{destino_final.name}.staging-{uuid.uuid4().hex}"
    tamanho_origem = _validar_origem_publicacao(origem)

    _registrar_evento(
        etapa="validacao_origem",
        status="ok",
        origem=origem,
        destino=destino_final,
        detalhe="Arquivo local validado antes da publicacao",
        tamanho_origem=tamanho_origem,
    )

    try:
        destino_final.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(origem), str(staging))
        _validar_arquivo_publicado(origem, staging, tamanho_origem)
        os.replace(str(staging), str(destino_final))
        tamanho_destino = _validar_arquivo_publicado(origem, destino_final, tamanho_origem)
        origem.unlink()

        _registrar_evento(
            etapa="publicacao_rede",
            status="ok",
            origem=origem,
            destino=destino_final,
            detalhe="Arquivo publicado com staging e swap atomico",
            tamanho_origem=tamanho_origem,
            tamanho_destino=tamanho_destino,
        )
        logger.info("Arquivo publicado com sucesso: %s -> %s", origem, destino_final)
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message=f"Arquivo publicado em {destino_final}",
        )
    except Exception as exc:
        try:
            staging.unlink(missing_ok=True)
        except Exception:
            pass

        logger.error("Falha na publicacao em rede de '%s': %s", origem, exc)
        _registrar_evento(
            etapa="publicacao_rede",
            status="falha",
            origem=origem,
            destino=destino_final,
            detalhe=str(exc),
            tamanho_origem=tamanho_origem,
        )

        if not criar_pendencia_local:
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=f"Falha na publicacao de {origem.name}: {exc}",
            )

        try:
            arquivo_pendente = _criar_pendencia_local(origem, destino_final, str(exc))
            origem.unlink()
            _registrar_evento(
                etapa="fila_pendente",
                status="ok",
                origem=origem,
                destino=destino_final,
                detalhe="Arquivo movido para fila local de publicacao pendente",
                tamanho_origem=tamanho_origem,
                pendencia=arquivo_pendente,
            )
            logger.warning(
                "Arquivo enfileirado para publicacao pendente: %s (destino original: %s)",
                arquivo_pendente,
                destino_final,
            )
            return ExecutionResult(
                status=ExecutionStatus.PARTIAL_SUCCESS,
                message=(
                    f"Publicacao pendente criada para {origem.name} "
                    f"(destino original: {destino_final})"
                ),
            )
        except Exception as pending_exc:
            _registrar_evento(
                etapa="fila_pendente",
                status="falha",
                origem=origem,
                destino=destino_final,
                detalhe=f"Falha ao criar pendencia local: {pending_exc}",
                tamanho_origem=tamanho_origem,
            )
            logger.error(
                "Falha ao criar pendencia local para '%s'. Origem mantida no lugar: %s",
                origem,
                pending_exc,
            )
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=(
                    f"Falha na publicacao de {origem.name}: {exc}; "
                    f"falha ao criar pendencia local: {pending_exc}"
                ),
            )


def mover_relatorios(origem, destino):
    caminho_origem = Path(origem)
    caminho_destino = Path(destino)

    if not caminho_origem.exists():
        logger.debug(
            "Tarefa de movimentacao ignorada: '%s' nao encontrada (rotina provavelmente nao executada).",
            origem,
        )
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message=f"Origem nao encontrada, nada para mover: {caminho_origem}",
        )

    if caminho_origem.is_dir() and not any(caminho_origem.iterdir()):
        logger.debug("Pasta de origem '%s' esta vazia. Nada para mover.", origem)
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message=f"Origem vazia, nada para mover: {caminho_origem}",
        )

    if caminho_origem.is_file():
        return publicar_arquivo_na_rede(caminho_origem, caminho_destino / caminho_origem.name)

    if caminho_origem.is_dir():
        logger.info("Publicando conteudo da pasta '%s' para '%s'...", caminho_origem.name, destino)
        status_final = ExecutionStatus.SUCCESS
        mensagens = []
        for item in caminho_origem.iterdir():
            if not item.is_file():
                continue
            resultado = publicar_arquivo_na_rede(item, caminho_destino / item.name)
            mensagens.append(resultado.message)
            if resultado.status is ExecutionStatus.TECHNICAL_FAILURE:
                status_final = ExecutionStatus.TECHNICAL_FAILURE
            elif resultado.status is ExecutionStatus.PARTIAL_SUCCESS and status_final is ExecutionStatus.SUCCESS:
                status_final = ExecutionStatus.PARTIAL_SUCCESS

        if not mensagens:
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Nenhum arquivo elegivel para publicacao em {caminho_origem}",
            )

        return ExecutionResult(
            status=status_final,
            message="; ".join(mensagens),
        )

    return ExecutionResult(
        status=ExecutionStatus.SUCCESS,
        message=f"Origem nao processada: {caminho_origem}",
    )

