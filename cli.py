import argparse
import importlib


COMMANDS: dict[str, tuple[str, str]] = {
    "relatorios": ("mainRelatorios", "Executa o fluxo principal de relatorios."),
    "fechamento": ("mainRelatoriosFechamento", "Executa o fluxo de fechamento."),
    "repescagem": ("main", "Executa a repescagem manual de relatorios."),
    "pedidos": ("mainPedidos", "Executa a digitacao de pedidos."),
    "lote-condicao": ("alterarCEMC", "Executa a alteracao em lote de condicao/CEMC."),
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
