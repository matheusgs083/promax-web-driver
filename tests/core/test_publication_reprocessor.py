from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from core.execution.execution_result import ExecutionResult, ExecutionStatus
from core.files import movimentador
from core.services import publication_service


def _criar_pendencia(raiz: Path, destino_final: Path) -> tuple[Path, Path]:
    pasta_pendencia = raiz / "publicacao_pendente" / "20260323_destino_12345678"
    pasta_pendencia.mkdir(parents=True, exist_ok=True)

    arquivo = pasta_pendencia / destino_final.name
    arquivo.write_text("coluna\nvalor\n", encoding="utf-8")

    metadata_path = pasta_pendencia / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "criado_em": datetime.now().isoformat(timespec="seconds"),
                "origem_original": str(arquivo),
                "destino_original": str(destino_final),
                "arquivo_pendente": str(arquivo),
                "status": "pendente_publicacao",
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    return pasta_pendencia, metadata_path


def test_reprocessador_publica_e_arquiva_pendencia(monkeypatch):
    raiz = Path.cwd() / ".test_tmp_reprocessador" / "sucesso"
    shutil.rmtree(raiz.parent, ignore_errors=True)
    raiz.mkdir(parents=True, exist_ok=True)
    try:
        destino_final = raiz / "rede" / "destino-final" / "relatorio.csv"
        pasta_pendencia, _metadata_path = _criar_pendencia(raiz, destino_final)

        monkeypatch.setattr(movimentador, "BASE_LOG_DIR", raiz / "logs")
        monkeypatch.setattr(movimentador, "PENDING_DIR", raiz / "publicacao_pendente")
        monkeypatch.setattr(movimentador, "EVENT_LOG_FILE", raiz / "logs" / "publicacao_eventos.jsonl")

        resultado = publication_service.reprocessar_publicacoes_pendentes(
            pending_dir=raiz / "publicacao_pendente",
            processed_dir=raiz / "publicacao_processada",
        )

        assert resultado.status == ExecutionStatus.SUCCESS
        assert destino_final.exists()

        metadata_processado = next((raiz / "publicacao_processada").glob("**/metadata.json"))
        metadata = json.loads(metadata_processado.read_text(encoding="utf-8"))
        assert metadata["status"] == "publicado"
        assert metadata["ultima_tentativa_status"] == ExecutionStatus.SUCCESS.value
        assert not pasta_pendencia.exists()
    finally:
        shutil.rmtree(raiz.parent, ignore_errors=True)


def test_reprocessador_mantem_pendencia_quando_reenvio_falha(monkeypatch):
    raiz = Path.cwd() / ".test_tmp_reprocessador" / "falha"
    shutil.rmtree(raiz.parent, ignore_errors=True)
    raiz.mkdir(parents=True, exist_ok=True)
    try:
        destino_final = raiz / "rede" / "destino-final" / "relatorio.csv"
        pasta_pendencia, metadata_path = _criar_pendencia(raiz, destino_final)

        monkeypatch.setattr(
            publication_service,
            "publicar_arquivo_na_rede",
            lambda *_args, **_kwargs: ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message="falha simulada de reprocessamento",
            ),
        )

        resultado = publication_service.reprocessar_publicacoes_pendentes(
            pending_dir=raiz / "publicacao_pendente",
            processed_dir=raiz / "publicacao_processada",
        )

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert resultado.status == ExecutionStatus.TECHNICAL_FAILURE
        assert pasta_pendencia.exists()
        assert metadata["status"] == "falha_reprocessamento"
        assert metadata["ultima_tentativa_status"] == ExecutionStatus.TECHNICAL_FAILURE.value
    finally:
        shutil.rmtree(raiz.parent, ignore_errors=True)




