"""Grava a tela de cada rotina de relatorio para montar as receitas HTTP.

Faz um login so, abre cada rotina, salva a pagina (com o JavaScript) e um
resumo dos campos, e fecha a rotina. Nao gera relatorio nenhum.

    python -m promax_http.capturar_telas            # todas as rotinas conhecidas
    python -m promax_http.capturar_telas 140501     # so as informadas

Saida: data/promax_telas/<codigo>/ (rotina.html, topo.html, campos.txt) e
data/promax_telas/resumo.txt.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from core.config.project_paths import DATA_DIR, LOGS_DIR
from core.config.settings import get_settings
from core.observability.logger import get_logger
from promax_http.cliente import ClientePromax, Rotina
from promax_http.erros import PromaxHttpErro
from promax_http.transporte import Transporte

# Rotinas de relatorio usadas hoje pelos entrypoints de entrypoints/reports/,
# mais a 140501 (nova).
ROTINAS_RELATORIO = (
    "0105070402", "020220", "020304", "020502", "030111", "030206", "030224", "030237",
    "030312", "030803", "030805", "031120", "031129", "03114902", "031702", "0512",
    "0513", "120601", "120606", "120616", "140501", "140506", "140510", "150501", "1706",
)


def resumo_campos(rotina: Rotina) -> str:
    linhas = [
        f"Rotina: {rotina.codigo}",
        f"Programa: {rotina.programa}",
        f"MenuID: {rotina.menu_id}",
        f"Unidade ativa: {rotina.unidade_ativa}",
        "Unidades: " + ", ".join(f"{o.valor} ({o.texto})" for o in rotina.unidades),
        "",
        "Campos do formulario (valor inicial):",
    ]
    for nome, valor in rotina.form.campos.items():
        linhas.append(f"  {nome} = {valor!r}")
        for opcao in rotina.form.opcoes.get(nome, []):
            marca = " *" if opcao.selecionada else ""
            linhas.append(f"      {opcao.valor!r}: {opcao.texto}{marca}")
    linhas += ["", "Botoes:"]
    for nome, attrs in rotina.form.botoes.items():
        linhas.append(f"  {nome}  onclick={attrs.get('onclick', '')!r}")
    return "\n".join(linhas) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("rotinas", nargs="*", help="Codigos de rotina; padrao: todas as de relatorio")
    parser.add_argument("--unidade", help="Unidade do login (padrao: a primeira da lista)")
    args = parser.parse_args(argv)

    logger = get_logger("PROMAX_HTTP_CAPTURA")
    settings = get_settings()
    destino = Path(DATA_DIR) / "promax_telas"
    rastro = Path(LOGS_DIR) / "promax_http" / f"{datetime.now():%Y%m%d_%H%M%S}_captura"
    cliente = ClientePromax(settings.promax_url, transporte=Transporte(pasta_rastro=rastro), logger=logger)
    codigos = args.rotinas or list(ROTINAS_RELATORIO)
    resumo: list[str] = []

    try:
        cliente.login(settings.promax_user, settings.promax_pass, unidade=args.unidade)
        for indice, codigo in enumerate(codigos, start=1):
            logger.info("[%d/%d] Capturando a tela da rotina %s ...", indice, len(codigos), codigo)
            inicio = time.time()
            try:
                rotina = cliente.abrir_rotina(codigo)
            except PromaxHttpErro as exc:
                logger.error("Rotina %s nao abriu: %s", codigo, exc)
                resumo.append(f"{codigo}\tFALHOU\t{exc}")
                continue
            pasta = destino / codigo
            pasta.mkdir(parents=True, exist_ok=True)
            (pasta / "rotina.html").write_text(rotina.html_rotina, encoding="utf-8")
            (pasta / "topo.html").write_text(rotina.html_topo, encoding="utf-8")
            (pasta / "campos.txt").write_text(resumo_campos(rotina), encoding="utf-8")
            try:
                cliente.fechar_rotina(rotina)
            except PromaxHttpErro as exc:
                logger.debug("Fechamento da rotina %s falhou: %s", codigo, exc)
            resumo.append(
                f"{codigo}\tOK\t{rotina.programa}\t{len(rotina.form.campos)} campos"
                f"\t{len(rotina.unidades)} unidades\t{time.time() - inicio:.1f}s"
            )
            logger.info("Rotina %s salva em %s (%s)", codigo, pasta, rotina.programa)
    except PromaxHttpErro as exc:
        logger.error("Captura interrompida: %s", exc)
        resumo.append(f"LOGIN\tFALHOU\t{exc}")
    finally:
        try:
            cliente.logoff()
        except Exception as exc:  # o logoff e cortesia
            logger.debug("Logoff falhou: %s", exc)

    destino.mkdir(parents=True, exist_ok=True)
    (destino / "resumo.txt").write_text(
        f"Captura de {datetime.now():%d/%m/%Y %H:%M}\n" + "\n".join(resumo) + "\n", encoding="utf-8"
    )
    falhas = [linha for linha in resumo if "\tFALHOU\t" in linha]
    logger.info("Captura concluida: %d ok, %d com falha. Resumo em %s", len(resumo) - len(falhas), len(falhas), destino / "resumo.txt")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
