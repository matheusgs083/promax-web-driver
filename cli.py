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
    "fechamento-mapa": ("entrypoints.processes.fechamento_mapa", "Executa o fechamento fisico/financeiro de um mapa."),
    "repescagem": ("entrypoints.reports.repescagem_relatorios", "Executa a repescagem manual de relatorios."),
    "reprocessar-publicacao": ("entrypoints.maintenance.reprocessar_publicacao", "Reprocessa itens em logs/publicacao_pendente."),
    "pedidos": ("entrypoints.processes.pedidos", "Executa a digitacao de pedidos."),
    "lote-condicao": ("entrypoints.processes.lote_condicao", "Executa a alteracao em lote de condicao/CEMC."),
    "mapa-030303": ("entrypoints.processes.mapa_030303", "Executa o carregamento e salvamento de mapa na rotina 030303."),
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
        elif nome == "fechamento-mapa":
            command_parser.add_argument("--mapa", required=True)
            command_parser.add_argument("--ponto-apoio", default=None)
            command_parser.add_argument("--km-atual", default=None)
            command_parser.add_argument("--km-inicial", default=None)
            command_parser.add_argument("--km-prev", default=None)
            command_parser.add_argument("--unidade", default=None)
            command_parser.add_argument(
                "--modo",
                choices=("completo", "fisico", "financeiro"),
                default="completo",
            )
            command_parser.add_argument("--nao-salvar", action="store_true")
            command_parser.add_argument("--sessoes-separadas", action="store_true")
            command_parser.add_argument("--fechar-ao-falhar", action="store_true")
            command_parser.add_argument("--job-id", default="")
        elif nome == "reprocessar-publicacao":
            command_parser.add_argument("--job-id", default="")
        elif nome == "mapa-030303":
            command_parser.add_argument("--mapa", required=True)
            command_parser.add_argument("--unidade", default=None)
            command_parser.add_argument("--nao-salvar", action="store_true")
            command_parser.add_argument("--fechar-ao-falhar", action="store_true")
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


def _tracker_failed_units() -> tuple[list[str], list[dict[str, str]]]:
    try:
        from core.observability.relatorio_execucao import tracker
    except Exception:
        return [], []

    failed_units: list[str] = []
    failed_details: list[dict[str, str]] = []
    statuses_without_retry = {"SEM CONTEUDO", "SEM CONTEÚDO", "SEM DADOS"}
    for row in getattr(tracker, "registros", []) or []:
        status = str(row.get("Status", "")).strip().upper()
        routine = str(row.get("Rotina", "")).strip()
        unit = str(row.get("Unidade", "")).strip()
        if not unit or unit == "TODAS" or status == "SUCESSO" or status in statuses_without_retry:
            continue
        if routine == "RESUMO FINAL":
            continue
        if unit not in failed_units:
            failed_units.append(unit)
        failed_details.append(
            {
                "unit": unit,
                "routine": routine,
                "status": status,
                "detail": str(row.get("Detalhes", "")).strip(),
            }
        )
    return failed_units, failed_details


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
        "fechamento-mapa",
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
    elif args.command == "fechamento-mapa":
        kwargs = {
            "mapa": args.mapa,
            "ponto_apoio": args.ponto_apoio,
            "km_atual": args.km_atual,
            "km_inicial": args.km_inicial,
            "km_prev": args.km_prev,
            "unidade": args.unidade,
            "modo": args.modo,
            "salvar": not args.nao_salvar,
            "sessoes_separadas": args.sessoes_separadas,
            "manter_aberto_ao_falhar": not args.fechar_ao_falhar,
        }
    elif args.command == "mapa-030303":
        kwargs = {
            "mapa": args.mapa,
            "unidade": args.unidade,
            "salvar": not args.nao_salvar,
            "manter_aberto_ao_falhar": not args.fechar_ao_falhar,
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
        failed_units, failed_unit_details = _tracker_failed_units()
        print(
            json.dumps(
                {
                    "event": "promax_job_result",
                    "job_id": job_id,
                    "operation": args.command,
                    "status": result.status.value,
                    "message": result.message,
                    "metadata": _json_safe(result.metadata or {}),
                    "failed_units": failed_units,
                    "failed_unit_details": failed_unit_details,
                    "exit_code": _exit_code(result),
                },
                ensure_ascii=True,
            ),
            flush=True,
        )
    return _exit_code(result)


def _json_safe(value):
    if isinstance(value, ExecutionResult):
        return {
            "status": value.status.value,
            "message": value.message,
            "retry": value.retry,
            "metadata": _json_safe(value.metadata or {}),
        }
    if isinstance(value, ExecutionStatus):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


if __name__ == "__main__":
    sys.exit(main_cli())
