from __future__ import annotations

import json
from pathlib import Path

from core import movimentador


def test_publicacao_sucesso_com_staging_e_log(tmp_path, isolated_publication_paths):
    origem = tmp_path / "saida.csv"
    destino = tmp_path / "rede"
    origem.write_text("coluna\nvalor\n", encoding="utf-8")

    movimentador.mover_relatorios(str(origem), str(destino))

    destino_final = destino / "saida.csv"
    assert not origem.exists()
    assert destino_final.exists()
    assert destino_final.read_text(encoding="utf-8") == "coluna\nvalor\n"

    linhas = isolated_publication_paths["event"].read_text(encoding="utf-8").strip().splitlines()
    eventos = [json.loads(linha) for linha in linhas]
    assert [evento["etapa"] for evento in eventos] == ["validacao_origem", "publicacao_rede"]
    assert eventos[-1]["status"] == "ok"


def test_publicacao_falha_vai_para_fila_pendente(tmp_path, isolated_publication_paths, monkeypatch):
    origem = tmp_path / "relatorio.csv"
    destino = tmp_path / "rede" / "destino-final"
    origem.write_text("a,b\n1,2\n", encoding="utf-8")

    original_replace = movimentador.os.replace

    def failing_replace(src, dst):
        raise OSError("falha de rede simulada")

    monkeypatch.setattr(movimentador.os, "replace", failing_replace)

    movimentador.mover_relatorios(str(origem), str(destino))

    pendencias = list(isolated_publication_paths["pending"].glob("**/relatorio.csv"))
    assert len(pendencias) == 1
    assert not origem.exists()

    metadata_file = pendencias[0].parent / "metadata.json"
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert metadata["status"] == "pendente_publicacao"
    assert metadata["destino_original"].endswith(str(Path("destino-final") / "relatorio.csv"))

    linhas = isolated_publication_paths["event"].read_text(encoding="utf-8").strip().splitlines()
    eventos = [json.loads(linha) for linha in linhas]
    assert [evento["status"] for evento in eventos] == ["ok", "falha", "ok"]
    assert eventos[-1]["etapa"] == "fila_pendente"
