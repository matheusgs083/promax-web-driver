import re
import uuid
from pathlib import Path

import pandas as pd
import pdfplumber

from core.observability.logger import get_logger


logger = get_logger("CONVERSOR_030803")

COLUMNS = [
    "Liberacao",
    "Carga",
    "Mapa",
    "Veiculo",
    "Frota",
    "Cod_Spot",
    "Motorista",
    "Origem",
    "Atual",
    "Usuario",
    "Situacao",
    "Apurado",
]

LOAD_RE = re.compile(r"^(?:(\d{2}/\d{2}/\d{4})\s+)?(\d+)\s+(.+)$")
SKIP_TERMS = (
    "CONFERENCIA DAS CARGAS",
    "Distribuidora de Bebidas",
    "Data de Liberacao:",
    "Versao:",
    "Rotina:",
    "Transportadora:",
    "--- Carga ---",
    "Liberacao Mapa Veiculo",
)


def _parse_load_line(line: str, current_release_date: str | None) -> tuple[dict | None, str | None]:
    match = LOAD_RE.match(line)
    if not match:
        return None, current_release_date

    release_date, load_number, rest = match.groups()
    if release_date:
        current_release_date = release_date

    if not current_release_date:
        return None, current_release_date

    parts = rest.split()
    if len(parts) < 8:
        return None, current_release_date

    map_code, vehicle, fleet, spot_code = parts[:4]
    if len(parts) >= 10:
        origem, atual, usuario, situacao, apurado = parts[-5:]
        driver_parts = parts[4:-5]
    else:
        origem = ""
        atual = ""
        usuario, situacao, apurado = parts[-3:]
        driver_parts = parts[4:-3]

    if not driver_parts:
        return None, current_release_date

    row = {
        "Liberacao": current_release_date,
        "Carga": load_number,
        "Mapa": map_code,
        "Veiculo": vehicle,
        "Frota": fleet,
        "Cod_Spot": spot_code,
        "Motorista": " ".join(driver_parts),
        "Origem": origem,
        "Atual": atual,
        "Usuario": usuario,
        "Situacao": situacao,
        "Apurado": apurado,
    }
    return row, current_release_date


def extrair_linhas_030803(caminho_pdf: Path) -> list[dict]:
    linhas_extraidas = []
    data_liberacao_atual = None

    with pdfplumber.open(caminho_pdf) as pdf:
        total_paginas = len(pdf.pages)
        for indice, pagina in enumerate(pdf.pages, start=1):
            texto = pagina.extract_text() or ""

            for linha_original in texto.splitlines():
                linha = linha_original.replace("|", " ").strip()
                if not linha or any(termo in linha for termo in SKIP_TERMS):
                    continue

                linha_extraida, data_liberacao_atual = _parse_load_line(linha, data_liberacao_atual)
                if linha_extraida:
                    linhas_extraidas.append(linha_extraida)

            if indice % 50 == 0 or indice == total_paginas:
                logger.info(
                    "030803: paginas processadas %s/%s; linhas extraidas %s",
                    indice,
                    total_paginas,
                    len(linhas_extraidas),
                )

    return linhas_extraidas


def salvar_030803_xlsx(linhas: list[dict], caminho_xlsx: Path) -> pd.DataFrame:
    dataframe = pd.DataFrame(linhas, columns=COLUMNS)
    caminho_xlsx.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(caminho_xlsx, engine="openpyxl") as writer:
        dataframe.to_excel(writer, sheet_name="030803", index=False)
        worksheet = writer.sheets["030803"]
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions

        for coluna in worksheet.columns:
            cabecalho = coluna[0].value or ""
            tamanho_maximo = max(len(str(celula.value or "")) for celula in coluna[:500])
            worksheet.column_dimensions[coluna[0].column_letter].width = min(
                max(tamanho_maximo, len(str(cabecalho))) + 2,
                45,
            )

    return dataframe


def converter_030803_pdf_para_xlsx(caminho_pdf: str | Path, *, apagar_pdf: bool = True) -> Path:
    pdf_path = Path(caminho_pdf)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF nao encontrado: {pdf_path}")
    if not pdf_path.is_file():
        raise RuntimeError(f"Caminho informado nao e um arquivo: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise RuntimeError(f"Arquivo informado nao e PDF: {pdf_path}")

    xlsx_path = pdf_path.with_suffix(".xlsx")
    staging_path = xlsx_path.with_name(f".{xlsx_path.stem}.{uuid.uuid4().hex}.tmp.xlsx")
    logger.info("Iniciando conversao 030803: %s -> %s", pdf_path, xlsx_path)

    try:
        linhas = extrair_linhas_030803(pdf_path)
        if not linhas:
            raise RuntimeError(f"Nenhuma linha de carga foi encontrada no PDF: {pdf_path}")

        salvar_030803_xlsx(linhas, staging_path)
        if staging_path.stat().st_size <= 0:
            raise RuntimeError(f"Arquivo XLSX gerado vazio: {staging_path}")

        staging_path.replace(xlsx_path)
        if xlsx_path.stat().st_size <= 0:
            raise RuntimeError(f"Arquivo XLSX final ficou vazio: {xlsx_path}")
    except Exception:
        staging_path.unlink(missing_ok=True)
        raise

    if apagar_pdf:
        pdf_path.unlink()
        logger.info("PDF original apagado apos conversao: %s", pdf_path)

    logger.info("Conversao 030803 concluida: %s linhas em %s", len(linhas), xlsx_path)
    return xlsx_path


def listar_pdfs_030803(caminhos: list[str | Path], *, recursivo: bool = False) -> list[Path]:
    pdfs = []

    for caminho in caminhos:
        path = Path(caminho)
        if path.is_dir():
            padrao = "**/*.pdf" if recursivo else "*.pdf"
            pdfs.extend(arquivo for arquivo in path.glob(padrao) if arquivo.is_file())
            pdfs.extend(arquivo for arquivo in path.glob(padrao.upper()) if arquivo.is_file())
        else:
            pdfs.append(path)

    vistos = set()
    resultado = []
    for pdf in pdfs:
        chave = str(pdf.resolve()).lower() if pdf.exists() else str(pdf.absolute()).lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        resultado.append(pdf)

    return resultado


def converter_multiplos_030803_pdf_para_xlsx(
    caminhos: list[str | Path],
    *,
    apagar_pdf: bool = True,
    recursivo: bool = False,
) -> list[Path]:
    pdfs = listar_pdfs_030803(caminhos, recursivo=recursivo)
    if not pdfs:
        raise FileNotFoundError("Nenhum PDF 03.08.03 encontrado para converter.")

    arquivos_gerados = []
    for pdf in pdfs:
        arquivos_gerados.append(converter_030803_pdf_para_xlsx(pdf, apagar_pdf=apagar_pdf))

    return arquivos_gerados
