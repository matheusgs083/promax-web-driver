import argparse
from pathlib import Path

from core.files.conversor_030803 import converter_multiplos_030803_pdf_para_xlsx


PDF_PADRAO = Path(r"C:\Users\cadcom.patos\Desktop\03.08.03\030803_3.PDF")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Converte o relatorio Promax 03.08.03 de PDF para XLSX.",
    )
    parser.add_argument(
        "caminhos",
        nargs="*",
        default=None,
        help="PDFs ou pastas com PDFs 03.08.03. Sem argumento, usa o caminho padrao.",
    )
    parser.add_argument(
        "--manter-pdf",
        action="store_true",
        help="Nao apaga o PDF original apos gerar o XLSX.",
    )
    parser.add_argument(
        "--recursivo",
        action="store_true",
        help="Quando receber uma pasta, procura PDFs tambem nas subpastas.",
    )
    args = parser.parse_args()

    caminhos = args.caminhos or [PDF_PADRAO]
    arquivos = converter_multiplos_030803_pdf_para_xlsx(
        caminhos,
        apagar_pdf=not args.manter_pdf,
        recursivo=args.recursivo,
    )

    for xlsx_path in arquivos:
        print(f"Arquivo gerado: {xlsx_path}")


if __name__ == "__main__":
    main()
