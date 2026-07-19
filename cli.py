import argparse
import importlib
import json
import sys

from core.config.report_group_loader import (
    load_report_groups,
    report_group_catalog,
)
from core.execution.execution_result import (
    ExecutionResult,
    ExecutionStatus,
    normalize_execution_result,
)


COMMANDS: dict[str, tuple[str, str]] = {
    "relatorios": ("entrypoints.reports.relatorios", "Executa o fluxo principal de relatorios."),
    "fechamento": ("entrypoints.reports.relatorios_fechamento", "Executa o fluxo de fechamento."),
    "repescagem": ("entrypoints.reports.repescagem_relatorios", "Executa a repescagem manual de relatorios."),
    "reprocessar-publicacao": ("entrypoints.maintenance.reprocessar_publicacao", "Reprocessa itens em logs/publicacao_pendente."),
    "pedidos": ("entrypoints.processes.pedidos", "Executa a digitacao de pedidos."),
    "lote-condicao": ("entrypoints.processes.lote_condicao", "Executa a alteracao em lote de condicao/CEMC."),
}
REPORT_CATALOG_COMMAND = "catalogo-relatorios"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Entry point unificado para os fluxos do projeto promax-web-driver.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for nome, (_, descricao) in COMMANDS.items():
        command_parser = subparsers.add_parser(nome, help=descricao, description=descricao)
        if nome == "relatorios":
            command_parser.add_argument(
                "--perfil",
                "--grupo",
                dest="perfil",
                default="fluxo_caixa",
            )
            command_parser.add_argument("--data-inicial")
            command_parser.add_argument("--data-final")
            command_parser.add_argument("--unidade", action="append", default=[])
            command_parser.add_argument("--rotinas", nargs="+", default=[])
            publication_group = command_parser.add_mutually_exclusive_group()
            publication_group.add_argument("--publicar", action="store_true", dest="publicar")
            publication_group.add_argument("--somente-baixar", action="store_false", dest="publicar")
            command_parser.set_defaults(publicar=True)
            command_parser.add_argument("--job-id", default="")
            command_parser.add_argument("--download-workers", type=int, default=5)
        elif nome == "reprocessar-publicacao":
            command_parser.add_argument("--job-id", default="")

    subparsers.add_parser(
        REPORT_CATALOG_COMMAND,
        help="Exibe o catalogo JSON dos grupos de relatorios.",
        description="Le os manifests de grupos e exibe o catalogo sem iniciar Selenium.",
    )
    return parser


def _exit_code(result: ExecutionResult) -> int:
    return {
        ExecutionStatus.SUCCESS: 0,
        ExecutionStatus.PARTIAL_SUCCESS: 10,
        ExecutionStatus.BUSINESS_FAILURE: 20,
        ExecutionStatus.TECHNICAL_FAILURE: 30,
        ExecutionStatus.ABORTED: 130,
    }[result.status]


def main_cli() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == REPORT_CATALOG_COMMAND:
        print(
            json.dumps(
                report_group_catalog(),
                ensure_ascii=True,
                indent=2,
            )
        )
        return 0

    module_name, _ = COMMANDS[args.command]
    module = importlib.import_module(module_name)
    kwargs = {}
    job_id = str(getattr(args, "job_id", "") or "").strip()
    is_controlled_job = bool(job_id) and args.command in {
        "relatorios",
        "reprocessar-publicacao",
    }
    if args.command == "relatorios":
        kwargs = {
            "profile": args.perfil,
            "date_start": args.data_inicial,
            "date_end": args.data_final,
            "units": args.unidade,
            "routines": args.rotinas,
            "publish": args.publicar,
            "job_id": args.job_id,
            "download_workers": args.download_workers,
        }
    try:
        result = normalize_execution_result(module.main(**kwargs))
    except ValueError as exc:
        result = ExecutionResult(
            status=ExecutionStatus.BUSINESS_FAILURE,
            message=str(exc),
        )
    except KeyboardInterrupt:
        result = ExecutionResult(
            status=ExecutionStatus.ABORTED,
            message="Execucao cancelada.",
        )
    except Exception as exc:
        result = ExecutionResult(
            status=ExecutionStatus.TECHNICAL_FAILURE,
            message=f"Falha tecnica ao executar o comando: {exc}",
        )
    if is_controlled_job:
        print(
            json.dumps(
                {
                    "event": "promax_job_result",
                    "job_id": job_id,
                    "operation": args.command,
                    "status": result.status.value,
                    "message": result.message,
                    "exit_code": _exit_code(result),
                },
                ensure_ascii=True,
            ),
            flush=True,
        )
    return _exit_code(result)


if __name__ == "__main__":
    sys.exit(main_cli())
