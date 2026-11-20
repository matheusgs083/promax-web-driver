from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import dotenv

dotenv.load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from config import CoraSettings
from browser import CoraBrowser
from pages.welcome_page import CoraWelcomePage
from pages.critica_page import CoraCriticaPage, next_delivery_date
from cora_http import ClienteCora


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Driver de automação do portal Cora.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("health", help="Valida a configuração sem abrir o navegador.")
    executar = subparsers.add_parser("executar", help="Executa uma operação Cora registrada.")
    executar.add_argument("--operacao", required=True)
    executar.add_argument("--job-id", default="")
    executar.add_argument("--filial", action="append", default=[],
                          help="Filial da grade de estoque (ex.: 747530). Repita para varias; vazio = todas.")
    executar.add_argument("--data", default="", help="Data da grade de estoque (AAAA-MM-DD); vazio = hoje.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        settings = CoraSettings.from_env()
        if args.command == "health":
            print(json.dumps({"site": "cora", "url": settings.url, "headless": settings.headless}))
            return 0
        operation = str(args.operacao or "").strip().lower()
        if operation in {"abrir_revenda", "acessar_revenda"}:
            with CoraBrowser(settings) as browser:
                browser.start()
                welcome = CoraWelcomePage(browser.driver)
                welcome.select_brazil(settings.timeout_seconds)
                welcome.access_as_reseller(settings.timeout_seconds)
                browser.login()
            print(json.dumps({"event": "cora_job_result", "status": "success", "message": "Cora aberto como revenda."}), flush=True)
            return 0
        if operation in {"critica", "consulta_critica"}:
            # Sem navegador: login no Keycloak e API do Cora direto por HTTP.
            delivery_date = next_delivery_date(date.today(), settings.holidays)
            cliente = ClienteCora(log=lambda msg: print(msg, flush=True))
            cliente.login(settings.username, settings.password)
            arquivo = cliente.baixar_critica(delivery_date, settings.download_dir)
            print(json.dumps({
                "event": "cora_job_result",
                "status": "success",
                "message": "Relatório Critica do Cora baixado (HTTP, sem navegador).",
                "delivery_date": delivery_date.isoformat(),
                "downloaded_files": [str(arquivo)],
            }), flush=True)
            return 0
        if operation in {"grade_estoque", "estoque"}:
            data_grade = date.fromisoformat(args.data) if args.data else date.today()
            cliente = ClienteCora(log=lambda msg: print(msg, flush=True))
            cliente.login(settings.username, settings.password)
            unidades = cliente.baixar_grade_estoque_detalhada(
                data_grade,
                settings.estoque_download_dir,
                filiais=args.filial,
            )
            print(json.dumps({
                "event": "cora_job_result",
                "status": "success",
                "message": f"Grade de estoque do Cora baixada ({len(unidades)} filial(is)).",
                "grid_date": data_grade.isoformat(),
                "downloaded_files": [item["file"] for item in unidades],
                "units": unidades,
                "ignored_units": sorted(set(args.filial) - {item["code"] for item in unidades}),
            }), flush=True)
            return 0
        if operation == "critica_navegador":
            with CoraBrowser(settings) as browser:
                browser.start()
                welcome = CoraWelcomePage(browser.driver)
                welcome.select_brazil(settings.timeout_seconds)
                welcome.access_as_reseller(settings.timeout_seconds)
                browser.login()
                critica = CoraCriticaPage(browser.driver, settings.download_dir)
                critica.open_consulta_pedidos()
                critica.open_critica()
                delivery_date = next_delivery_date(date.today(), settings.holidays)
                critica.set_delivery_date(delivery_date)
                # A tela da Crítica carrega as unidades/revendas de forma
                # assíncrona. Aguarde a conclusão desse carregamento antes de
                # solicitar o relatório, evitando gerar apenas a primeira
                # revenda disponível.
                time.sleep(4)
                critica.generate_report()
                critica.open_report_manager()
                files = critica.download_latest_report()
            print(json.dumps({
                "event": "cora_job_result",
                "status": "success",
                "message": "Relatório Critica do Cora baixado.",
                "delivery_date": delivery_date.isoformat(),
                "downloaded_files": [str(path) for path in files],
            }), flush=True)
            return 0
        raise NotImplementedError(
            f"Operação Cora ainda não implementada: {operation or '<vazia>'}. "
            "Defina o primeiro fluxo do portal antes de habilitar o job."
        )
    except (ValueError, RuntimeError, NotImplementedError) as exc:
        print(json.dumps({"event": "cora_job_result", "status": "failed", "message": str(exc)}), flush=True)
        return 30


if __name__ == "__main__":
    sys.exit(main())
