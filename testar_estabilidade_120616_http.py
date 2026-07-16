from __future__ import annotations

import hashlib
import json
import os
import time
import traceback
from datetime import datetime
from pathlib import Path

from core.config.project_paths import LOGS_DIR
from core.config.settings import get_settings
from core.execution.entrypoint_helpers import encerrar_driver, iniciar_sessao_padrao
from core.observability.logger import get_logger
from pages.reports.relatorio_120616_page import Relatorio120616Page


logger = get_logger("TESTE_ESTABILIDADE_120616_HTTP")
settings = get_settings()

UNIDADES = [
    unidade.strip()
    for unidade in os.getenv(
        "PROMAX_STABILITY_UNITS",
        "0640002,2210004,3610008",
    ).split(",")
    if unidade.strip()
]
CICLOS = max(1, int(os.getenv("PROMAX_STABILITY_CYCLES", "2")))


def _salvar_relatorio(relatorio: dict) -> Path:
    pasta = Path(LOGS_DIR) / "diagnosticos_estabilidade"
    pasta.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = pasta / f"estabilidade_120616_{timestamp}.json"
    caminho.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return caminho


def main() -> int:
    driver = None
    page = None
    subpasta = f"teste_estabilidade_120616/{datetime.now():%Y%m%d_%H%M%S}"
    pasta_saida = Path(settings.download_dir) / subpasta
    relatorio = {
        "inicio": datetime.now().isoformat(timespec="seconds"),
        "rotina": "120616",
        "unidades": UNIDADES,
        "ciclos": CICLOS,
        "referencia_logs": {
            "execucoes_recentes": 11,
            "sucessos_recentes": 6,
            "falhas_recentes": 5,
            "principal_falha": "alerta após visualizar",
        },
        "resultados": [],
        "resumo": {},
        "erros_fatais": [],
    }

    try:
        driver, menu = iniciar_sessao_padrao(
            logger,
            settings,
            settings.unidade_relatorios,
        )
        janela = menu.acessar_rotina("120616")
        page = Relatorio120616Page(janela.driver, janela.handle_menu)
        page.subpasta_download = subpasta

        for ciclo in range(1, CICLOS + 1):
            for unidade in UNIDADES:
                nome = f"120616_ciclo{ciclo}_{unidade}.csv"
                caminho = pasta_saida / nome
                inicio = time.perf_counter()
                item = {
                    "ciclo": ciclo,
                    "unidade": unidade,
                    "ok": False,
                    "duracao_segundos": None,
                    "mensagem": None,
                    "arquivo": str(caminho),
                    "bytes": 0,
                    "sha256": None,
                    "unidade_preservada": False,
                    "erro": None,
                }
                try:
                    resultado = page.gerar_relatorio(
                        unidade=unidade,
                        opcao_rel="3",
                        mes_ano=datetime.now().strftime("%m/%Y"),
                        nome_arquivo=nome,
                    )
                    if isinstance(resultado, tuple):
                        item["ok"] = bool(resultado[0])
                        item["mensagem"] = str(resultado[1])
                    else:
                        item["ok"] = bool(resultado)
                        item["mensagem"] = str(resultado)

                    if caminho.is_file():
                        conteudo = caminho.read_bytes()
                        item["bytes"] = len(conteudo)
                        item["sha256"] = hashlib.sha256(conteudo).hexdigest()
                        if not conteudo:
                            item["ok"] = False
                            item["erro"] = "Arquivo vazio"
                        elif conteudo[:100].lstrip().lower().startswith(b"<html"):
                            item["ok"] = False
                            item["erro"] = "HTML salvo no lugar do CSV"
                    elif item["ok"]:
                        item["ok"] = False
                        item["erro"] = "Fluxo retornou sucesso sem criar arquivo"

                    try:
                        unidade_atual = page.obter_unidade_atual(timeout=2)
                        item["unidade_preservada"] = str(unidade_atual) == unidade
                    except Exception as exc:
                        item["erro"] = item["erro"] or (
                            f"Falha ao confirmar unidade após download: {exc}"
                        )
                except Exception as exc:
                    item["erro"] = f"{type(exc).__name__}: {exc}"
                    item["mensagem"] = traceback.format_exc()
                finally:
                    item["duracao_segundos"] = round(
                        time.perf_counter() - inicio,
                        3,
                    )
                    relatorio["resultados"].append(item)
    except Exception as exc:
        relatorio["erros_fatais"].append(
            {
                "tipo": type(exc).__name__,
                "mensagem": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        logger.exception("Teste de estabilidade 120616 falhou: %s", exc)
    finally:
        total = len(relatorio["resultados"])
        sucessos = sum(1 for item in relatorio["resultados"] if item["ok"])
        relatorio["resumo"] = {
            "total": total,
            "sucessos": sucessos,
            "falhas": total - sucessos,
            "taxa_sucesso": round(sucessos / total, 4) if total else 0,
            "todas_unidades_preservadas": all(
                item["unidade_preservada"] for item in relatorio["resultados"]
            )
            if total
            else False,
        }
        relatorio["fim"] = datetime.now().isoformat(timespec="seconds")
        caminho_relatorio = _salvar_relatorio(relatorio)
        encerrar_driver(driver)

    print(f"RELATORIO_ESTABILIDADE={caminho_relatorio}")
    print(json.dumps(relatorio["resumo"], ensure_ascii=False, indent=2))
    return 0 if not relatorio["erros_fatais"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
