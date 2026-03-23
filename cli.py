import argparse
import importlib


COMMANDS: dict[str, tuple[str, str]] = {
    "relatorios": ("entrypoints.reports.relatorios", "Executa o fluxo principal de relatorios."),
    "fechamento": ("entrypoints.reports.relatorios_fechamento", "Executa o fluxo de fechamento."),
    "repescagem": ("entrypoints.reports.repescagem_relatorios", "Executa a repescagem manual de relatorios."),
    "reprocessar-publicacao": ("entrypoints.maintenance.reprocessar_publicacao", "Reprocessa itens em logs/publicacao_pendente."),
    "pedidos": ("entrypoints.processes.pedidos", "Executa a digitacao de pedidos."),
    "lote-condicao": ("entrypoints.processes.lote_condicao", "Executa a alteracao em lote de condicao/CEMC."),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Entry point unificado para os fluxos do projeto promax-web-driver.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for nome, (_, descricao) in COMMANDS.items():
        subparsers.add_parser(nome, help=descricao, description=descricao)

    return parser


def main_cli() -> None:
    parser = build_parser()
    args = parser.parse_args()
    module_name, _ = COMMANDS[args.command]
    module = importlib.import_module(module_name)
    module.main()


if __name__ == "__main__":
    main_cli()
