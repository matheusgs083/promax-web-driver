"""Grava o que as telas PH (jQuery/AJAX) carregam, para montar o download HTTP delas.

As rotinas PH (ex.: 01.05.07.04.02 = PH050094, 03.11.49.02 = PH050158) abrem uma
"casca" com formPadrao; o formulario de verdade chega depois por AJAX
(execAjaxHtml, definido em ../scripts/jqfuncoes.js). Este script:

1. baixa os scripts do Promax que definem esse protocolo;
2. abre cada rotina e tenta carregar o conteudo AJAX com algumas variacoes
   do formPadrao, gravando cada resposta.

Nao clica em gerar, nao exporta nada.

    python -m promax_http.capturar_ph                 # 0105070402 e 03114902
    python -m promax_http.capturar_ph 03114902

Saida: data/promax_telas/_scripts/ e data/promax_telas/<codigo>/ph_*.html
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

from core.config.project_paths import DATA_DIR, LOGS_DIR
from core.config.settings import get_settings
from core.observability.logger import get_logger
from promax_http.cliente import ClientePromax
from promax_http.erros import PromaxHttpErro
from promax_http.transporte import Transporte

ROTINAS_PH = ("0105070402", "03114902")
# jqfuncoes/funcoesSiv: protocolo AJAX comum. PH0500xx.js: a logica de cada tela
# (GerarCSV etc.). Sao arquivos estaticos; baixam mesmo sem permissao na rotina.
SCRIPTS = ("jqfuncoes.js", "funcoesSiv.js", "jquery-confirm.js", "PH050094.js", "PH050158.js")

# Variacoes de como o $(document).ready() pode estar postando o formPadrao.
# (ppopcao=14 sem changeUNB derruba a sessao: nao usar.)
VARIACOES = {
    "a_opcao1": {"opcao": "1"},
    "b_opcao1_json_s": {"opcao": "1", "ajaxJson": "S"},
    "c_opcao1_json_n_pp0": {"opcao": "1", "ajaxJson": "N", "ppopcao": "0"},
}
MARCAS_CONTEUDO = ("btnGerarCSV", "botGerarCSV", "opClassificacao", "idGeo", "checkRota")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("rotinas", nargs="*", help="Codigos das rotinas PH; padrao: 0105070402 e 03114902")
    args = parser.parse_args(argv)

    logger = get_logger("PROMAX_HTTP_CAPTURA_PH")
    settings = get_settings()
    destino = Path(DATA_DIR) / "promax_telas"
    rastro = Path(LOGS_DIR) / "promax_http" / f"{datetime.now():%Y%m%d_%H%M%S}_captura_ph"
    transporte = Transporte(pasta_rastro=rastro)
    cliente = ClientePromax(settings.promax_url, transporte=transporte, logger=logger)
    achou_conteudo: list[str] = []

    try:
        cliente.login(settings.promax_user, settings.promax_pass)

        pasta_scripts = destino / "_scripts"
        pasta_scripts.mkdir(parents=True, exist_ok=True)
        for nome in SCRIPTS:
            url = urljoin(settings.promax_url, f"../scripts/{nome}")
            resposta = transporte.get(url)
            (pasta_scripts / nome).write_text(resposta.texto, encoding="utf-8")
            logger.info("Script %s: HTTP %s, %d bytes", nome, resposta.status, len(resposta.texto))

        for codigo in args.rotinas or list(ROTINAS_PH):
            logger.info("Abrindo a rotina PH %s ...", codigo)
            try:
                rotina = cliente.abrir_rotina(codigo)
            except PromaxHttpErro as exc:
                logger.error("Rotina %s nao abriu: %s", codigo, exc)
                continue
            pasta = destino / codigo
            pasta.mkdir(parents=True, exist_ok=True)
            (pasta / "ph_casca.html").write_text(rotina.html_rotina, encoding="utf-8")
            url_ajax = urljoin(rotina.url_rotina, "PP00100.exe")
            for nome, ajuste in VARIACOES.items():
                campos = {**rotina.form.campos, **ajuste}
                try:
                    resposta = transporte.post(url_ajax, campos)
                except PromaxHttpErro as exc:
                    logger.error("%s %s falhou: %s", codigo, nome, exc)
                    continue
                (pasta / f"ph_{nome}.html").write_text(resposta.texto, encoding="utf-8")
                marcas = [m for m in MARCAS_CONTEUDO if m in resposta.texto]
                logger.info(
                    "%s variacao %s: HTTP %s, %d bytes, marcas do formulario: %s",
                    codigo, nome, resposta.status, len(resposta.texto), marcas or "nenhuma",
                )
                if marcas:
                    achou_conteudo.append(f"{codigo}:{nome}")
    except PromaxHttpErro as exc:
        logger.error("Captura interrompida: %s", exc)
    finally:
        try:
            cliente.logoff()
        except Exception as exc:  # o logoff e cortesia
            logger.debug("Logoff falhou: %s", exc)

    logger.info("Conteudo do formulario encontrado em: %s", achou_conteudo or "nenhuma variacao")
    logger.info("Envie as pastas data\\promax_telas\\_scripts, data\\promax_telas\\<rotina> e %s", rastro)
    return 0


if __name__ == "__main__":
    sys.exit(main())
