from __future__ import annotations

import json
import shutil
from pathlib import Path

from core.execution.execution_result import ExecutionStatus
from core.files import movimentador


def _isolar_publicacao(monkeypatch, raiz: Path):
    base = raiz / "logs"
    pending = base / "publicacao_pendente"
    event = base / "publicacao_eventos.jsonl"

    monkeypatch.setattr(movimentador, "BASE_LOG_DIR", base)
    monkeypatch.setattr(movimentador, "PENDING_DIR", pending)
    monkeypatch.setattr(movimentador, "EVENT_LOG_FILE", event)

    return {
        "base": base,
        "pending": pending,
        "event": event,
    }


def test_publicacao_sucesso_com_staging_e_log(monkeypatch):
    raiz = Path.cwd() / ".test_tmp_movimentador" / "sucesso"
    shutil.rmtree(raiz.parent, ignore_errors=True)
    raiz.mkdir(parents=True, exist_ok=True)
    try:
        paths = _isolar_publicacao(monkeypatch, raiz)
        origem = raiz / "saida.csv"
        destino = raiz / "rede"
        origem.write_text("coluna\nvalor\n", encoding="utf-8")

        resultado = movimentador.mover_relatorios(str(origem), str(destino))

        destino_final = destino / "saida.csv"
        assert resultado.status == ExecutionStatus.SUCCESS
        assert resultado.ok is True
        assert not origem.exists()
        assert destino_final.exists()
        assert destino_final.read_text(encoding="utf-8") == "coluna\nvalor\n"

        linhas = paths["event"].read_text(encoding="utf-8").strip().splitlines()
        eventos = [json.loads(linha) for linha in linhas]
        assert [evento["etapa"] for evento in eventos] == ["validacao_origem", "publicacao_rede"]
        assert eventos[-1]["status"] == "ok"
    finally:
        shutil.rmtree(raiz.parent, ignore_errors=True)


def test_publicacao_falha_vai_para_fila_pendente(monkeypatch):
    raiz = Path.cwd() / ".test_tmp_movimentador" / "pendente"
    shutil.rmtree(raiz.parent, ignore_errors=True)
    raiz.mkdir(parents=True, exist_ok=True)
    try:
        paths = _isolar_publicacao(monkeypatch, raiz)
        origem = raiz / "relatorio.csv"
        destino = raiz / "rede" / "destino-final"
        origem.write_text("a,b\n1,2\n", encoding="utf-8")

        def failing_replace(src, dst):
            raise OSError("falha de rede simulada")

        monkeypatch.setattr(movimentador.os, "replace", failing_replace)

        resultado = movimentador.mover_relatorios(str(origem), str(destino))

        pendencias = list(paths["pending"].glob("**/relatorio.csv"))
        assert resultado.status == ExecutionStatus.PARTIAL_SUCCESS
        assert resultado.ok is False
        assert len(pendencias) == 1
        assert not origem.exists()

        metadata_file = pendencias[0].parent / "metadata.json"
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        assert metadata["status"] == "pendente_publicacao"
        assert metadata["destino_original"].endswith(str(Path("destino-final") / "relatorio.csv"))

        linhas = paths["event"].read_text(encoding="utf-8").strip().splitlines()
        eventos = [json.loads(linha) for linha in linhas]
        assert [evento["status"] for evento in eventos] == ["ok", "falha", "ok"]
        assert eventos[-1]["etapa"] == "fila_pendente"
    finally:
        shutil.rmtree(raiz.parent, ignore_errors=True)


