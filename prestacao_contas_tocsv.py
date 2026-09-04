import argparse
from pathlib import Path

from core.files.conversor_pw02136r import converter_pw02136r_para_csv


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Converte o relatorio Promax PW02136R (Prestacao de Contas) de PDF para CSV.",
    )
    parser.add_argument(
        "caminhos",
        nargs="+",
        help="PDFs ou pastas contendo PDFs de Prestacao de Contas (PW02136R).",
    )
    parser.add_argument(
        "--saida",
        default=None,
        help="Pasta de destino dos arquivos CSV gerados.",
    )

    args = parser.parse_args()

    for item in args.caminhos:
        p = Path(item)
        if p.is_dir():
            pdfs = list(p.glob("*.pdf")) + list(p.glob("*.PDF"))
        else:
            pdfs = [p]

        for pdf in pdfs:
            gerados = converter_pw02136r_para_csv(pdf, pasta_saida=args.saida)
            for g in gerados:
                print(f"Arquivo gerado: {g}")


if __name__ == "__main__":
    main()
