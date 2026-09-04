import re
import uuid
from pathlib import Path
import pandas as pd
import pdfplumber

from core.observability.logger import get_logger

logger = get_logger("CONVERSOR_PW02136R")

COLUMNS_NOTAS = [
    "UNB_Codigo",
    "Razao_Social",
    "Nota",
    "Sit",
    "Op",
    "Condicao_Pagto",
    "Valor_Nota",
    "Devolucao",
    "Valor_Liquido",
]

COLUMNS_VASILHAME = [
    "Codigo",
    "Un",
    "Denominacao",
    "Preco",
    "Saida_Qtde",
    "Saida_Valor",
    "Retorno_Qtde",
    "Retorno_Valor",
    "Diferenca_Qtde",
    "Diferenca_Valor",
]

COLUMNS_RESUMO = [
    "Forma_Pagamento",
    "Saida",
    "Retorno",
]


def _limpar_valor(val_str: str) -> float:
    if not val_str:
        return 0.0
    val_clean = val_str.replace(".", "").replace(",", ".").replace("-", "").strip()
    try:
        val = float(val_clean)
        return -val if "-" in val_str else val
    except ValueError:
        return 0.0


def extrair_dados_pw02136r(caminho_pdf: Path) -> tuple[dict, list[dict], list[dict], list[dict]]:
    """
    Extrai cabecalho, notas/titulos, vasilhames e resumo financeiro do PDF de Prestacao de Contas PW02136R.
    """
    cabecalho = {}
    notas = []
    vasilhames = []
    resumo = []

    em_vasilhame = False
    em_resumo = False
    ultimo_cliente = {"code": "", "razao": ""}

    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""
            linhas = texto.splitlines()

            for line in linhas:
                line_str = line.strip()
                if not line_str:
                    continue

                # Extrai cabecalho
                if "Mapa:" in line_str and "de" in line_str:
                    m = re.search(r"Mapa:\s*([\d\.]+)\s+de\s+([\d/]+)", line_str)
                    if m:
                        cabecalho["mapa"] = m.group(1)
                        cabecalho["data_mapa"] = m.group(2)
                if "Veiculo" in line_str and "Motorista" in line_str:
                    m_veic = re.search(r"Veiculo\s*\.\.:\s*(\S+.*?)\s+Transp", line_str)
                    m_mot = re.search(r"Motorista\s*\.\.\.\.:\s*(.+)", line_str)
                    if m_veic:
                        cabecalho["veiculo"] = m_veic.group(1).strip()
                    if m_mot:
                        cabecalho["motorista"] = m_mot.group(1).strip()

                # Marca secoes
                if "VASILHAME" in line_str:
                    em_vasilhame = True
                    em_resumo = False
                    continue
                if "RESUMO FINANCEIRO" in line_str:
                    em_resumo = True
                    em_vasilhame = False
                    continue

                # Ignora titulos de coluna e rodapes de pagina
                if any(x in line_str for x in ["PW02136R-t-Promax", "Distribuidora de Bebidas", "UNB/Codigo Razao Social", "Codigo Un Denominacao", "Totais ..........:"]):
                    continue

                # Processa Resumo Financeiro
                if em_resumo:
                    if "Subtotal" in line_str or "Total Saida" in line_str or "Vasilhame" in line_str:
                        continue
                    m_res = re.search(r"^([A-Z\*\s]+)\s+([\d\.,]+)(?:\s+([\d\.,]+))?$", line_str)
                    if m_res:
                        forma = m_res.group(1).strip()
                        saida = _limpar_valor(m_res.group(2))
                        retorno = _limpar_valor(m_res.group(3)) if m_res.group(3) else 0.0
                        resumo.append({"Forma_Pagamento": forma, "Saida": saida, "Retorno": retorno})
                    continue

                # Processa Vasilhame
                if em_vasilhame:
                    m_vas = re.search(r"^(\d+)\s+([a-z]+)\s+(.+?)\s+([\d\.,]+)\s+(\S+)\s+([\d\.,]+)\s+(\S+)\s+([\d\.,]+)\s+(\S+)\s+([\d\.,]+-?)$", line_str)
                    if m_vas:
                        vasilhames.append({
                            "Codigo": m_vas.group(1),
                            "Un": m_vas.group(2),
                            "Denominacao": m_vas.group(3).strip(),
                            "Preco": _limpar_valor(m_vas.group(4)),
                            "Saida_Qtde": m_vas.group(5),
                            "Saida_Valor": _limpar_valor(m_vas.group(6)),
                            "Retorno_Qtde": m_vas.group(7),
                            "Retorno_Valor": _limpar_valor(m_vas.group(8)),
                            "Diferenca_Qtde": m_vas.group(9),
                            "Diferenca_Valor": _limpar_valor(m_vas.group(10)),
                        })
                    continue

                # Processa Notas / Titulos
                # Exemplo linha normal: 19193 FILIPE SILVA RODRIGUES 204.500 003 1 CREDITO EM CONTAS 215,97 215,97
                # Exemplo linha sub-item: 2 BONIFICACAO 396,57 396,57
                m_nota = re.search(r"^(\d+)\s+(.+?)\s+(\d{3}\.\d{3})\s+(\d{3})\s+(\d+)\s+(.+?)\s+([\d\.,]+)(?:\s+([\d\.,]+))?\s+([\d\.,]+)$", line_str)
                if m_nota:
                    cod, razao, nota, sit, op, cond, val_nota, dev, val_liq = m_nota.groups()
                    ultimo_cliente = {"code": cod, "razao": razao}
                    notas.append({
                        "UNB_Codigo": cod,
                        "Razao_Social": razao.strip(),
                        "Nota": nota,
                        "Sit": sit,
                        "Op": op,
                        "Condicao_Pagto": cond.strip(),
                        "Valor_Nota": _limpar_valor(val_nota),
                        "Devolucao": _limpar_valor(dev) if dev else 0.0,
                        "Valor_Liquido": _limpar_valor(val_liq),
                    })
                    continue

                m_sub = re.search(r"^(\d+)\s+([A-Z\s]+)\s+([\d\.,]+)(?:\s+([\d\.,]+))?\s+([\d\.,]+)$", line_str)
                if m_sub and ultimo_cliente["code"]:
                    op, cond, val_nota, dev, val_liq = m_sub.groups()
                    # Busca ultima nota para herdar numero de nota e situacao
                    nota_ref = notas[-1]["Nota"] if notas else ""
                    sit_ref = notas[-1]["Sit"] if notas else "003"
                    notas.append({
                        "UNB_Codigo": ultimo_cliente["code"],
                        "Razao_Social": ultimo_cliente["razao"].strip(),
                        "Nota": nota_ref,
                        "Sit": sit_ref,
                        "Op": op,
                        "Condicao_Pagto": cond.strip(),
                        "Valor_Nota": _limpar_valor(val_nota),
                        "Devolucao": _limpar_valor(dev) if dev else 0.0,
                        "Valor_Liquido": _limpar_valor(val_liq),
                    })

    return cabecalho, notas, vasilhames, resumo


def converter_pw02136r_para_csv(caminho_pdf: str | Path, pasta_saida: str | Path | None = None) -> list[Path]:
    """
    Converte relatorio PW02136R (Prestacao de Contas) em arquivos CSV.
    """
    pdf_path = Path(caminho_pdf)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF nao encontrado: {pdf_path}")

    out_dir = Path(pasta_saida) if pasta_saida else pdf_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    cabecalho, notas, vasilhames, resumo = extrair_dados_pw02136r(pdf_path)

    stem = pdf_path.stem
    arquivos_gerados = []

    if notas:
        f_notas = out_dir / f"{stem}_notas.csv"
        pd.DataFrame(notas, columns=COLUMNS_NOTAS).to_csv(f_notas, index=False, sep=";", encoding="utf-8-sig")
        arquivos_gerados.append(f_notas)

    if vasilhames:
        f_vas = out_dir / f"{stem}_vasilhame.csv"
        pd.DataFrame(vasilhames, columns=COLUMNS_VASILHAME).to_csv(f_vas, index=False, sep=";", encoding="utf-8-sig")
        arquivos_gerados.append(f_vas)

    if resumo:
        f_res = out_dir / f"{stem}_resumo.csv"
        pd.DataFrame(resumo, columns=COLUMNS_RESUMO).to_csv(f_res, index=False, sep=";", encoding="utf-8-sig")
        arquivos_gerados.append(f_res)

    logger.info("Conversao PW02136R concluida para %s: %s arquivos gerados", pdf_path, len(arquivos_gerados))
    return arquivos_gerados
