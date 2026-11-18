"""Teste das rotinas que gravam arquivo no DVS do Promax (03.08.05 e 17.06).

Essas rotinas nao exportam CSV pela tela: o Visualizar faz o Promax gravar um
arquivo na pasta DVS do servidor, e o robo do Edge busca esse arquivo depois em
tres lugares (nesta ordem):

1. pasta de rede  \\\\<servidor>\\integ\\dvs\\<arquivo>
2. HTTP           /arquivos/browse/dvs/<arquivo>
3. HTTP           /arquivos/dvs/<arquivo>

Este teste faz o Visualizar por HTTP (sem Edge) e procura o arquivo nos tres
lugares, anotando qual funcionou. Os arquivos achados vao para
data/promax_telas/_dvs_teste/ (nao mexe na pasta de relatorios).

    python -m promax_http.testar_dvs                      # 030805 e 1706, Patos e Sume
    python -m promax_http.testar_dvs --rotina 030805 --unidade 2210003 --data 17/11/2026
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from core.config.project_paths import DATA_DIR, LOGS_DIR
from core.config.settings import get_settings
from core.observability.logger import get_logger
from promax_http.cliente import ClientePromax
from promax_http.dvs import BuscaDvs
from promax_http.erros import PromaxHttpErro, RelatorioSemConteudo
from promax_http.receitas import PREFIXO_DVS_1706, campos_030805, campos_1706, nome_dvs_030805
from promax_http.transporte import Transporte

ESPERA_ARQUIVO = 90
INTERVALO = 5


def _data_entrega_anterior(hoje: date) -> date:
    # Igual a Liga: segunda busca sabado; nos outros dias, o dia anterior.
    return hoje - timedelta(days=2 if hoje.weekday() == 0 else 1)


def _esperar(buscar, logger, descricao: str):
    prazo = time.time() + ESPERA_ARQUIVO
    while True:
        achado = buscar()
        if achado or time.time() >= prazo:
            return achado
        logger.info("... aguardando %s no DVS", descricao)
        time.sleep(INTERVALO)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rotina", action="append", choices=["030805", "1706"], help="padrao: as duas")
    parser.add_argument("--unidade", action="append", help="padrao: 2210003 e 2210004")
    parser.add_argument("--data", help="030805: data de entrega dd/mm/aaaa (padrao: entrega anterior, como a Liga)")
    args = parser.parse_args(argv)

    logger = get_logger("PROMAX_HTTP_TESTE_DVS")
    settings = get_settings()
    hoje = datetime.now().date()
    data_030805 = args.data or _data_entrega_anterior(hoje).strftime("%d/%m/%Y")
    referencia_1706 = hoje - timedelta(days=1)
    periodo_1706 = (referencia_1706.replace(day=1).strftime("%d/%m/%Y"), referencia_1706.strftime("%d/%m/%Y"))
    rotinas = args.rotina or ["030805", "1706"]
    unidades = args.unidade or ["2210003", "2210004"]

    saida = Path(DATA_DIR) / "promax_telas" / "_dvs_teste"
    saida.mkdir(parents=True, exist_ok=True)
    rastro = Path(LOGS_DIR) / "promax_http" / f"{datetime.now():%Y%m%d_%H%M%S}_teste_dvs"
    transporte = Transporte(pasta_rastro=rastro)
    cliente = ClientePromax(settings.promax_url, transporte=transporte, logger=logger)
    # Busca com timeout curto: a porta 8080 pode nem responder.
    busca = BuscaDvs(Transporte(timeout=20, pasta_rastro=rastro / "busca"), settings.promax_url, logger)
    resumo: list[str] = []

    try:
        cliente.login(settings.promax_user, settings.promax_pass, unidade_preferida=settings.unidade_relatorios)
        for codigo_rotina in rotinas:
            for unidade in unidades:
                rotulo = f"{codigo_rotina} {unidade}"
                try:
                    rotina = cliente.abrir_rotina(codigo_rotina)
                    rotina = cliente.trocar_unidade(rotina, unidade)
                    if codigo_rotina == "030805":
                        campos = campos_030805(data=data_030805)
                        nome = nome_dvs_030805(data=data_030805, unidade=unidade)
                        inicio = time.time()
                        buscar = lambda nome=nome, inicio=inicio: busca.por_nome(nome, inicio)
                        descricao, trecho = nome, nome[:7]
                    else:
                        campos = campos_1706(unidade=unidade, data_inicial=periodo_1706[0], data_final=periodo_1706[1])
                        prefixo = PREFIXO_DVS_1706.get(unidade)
                        if not prefixo:
                            resumo.append(f"{rotulo}\tPULADA\tunidade sem prefixo DVS mapeado")
                            continue
                        inicio = time.time()
                        buscar = lambda prefixo=prefixo, inicio=inicio: busca.por_prefixo(prefixo, inicio)
                        descricao, trecho = f"arquivo com prefixo {prefixo}", prefixo
                    tela = cliente.visualizar(rotina, campos)
                    (saida / f"visualizar_{codigo_rotina}_{unidade}.html").write_text(tela.texto, encoding="utf-8")
                    achado = _esperar(buscar, logger, descricao)
                    if achado:
                        origem, conteudo = achado
                        arquivo = saida / f"{codigo_rotina}_{unidade}_{origem.rsplit('/', 1)[-1].rsplit(chr(92), 1)[-1]}"
                        arquivo.write_bytes(conteudo)
                        logger.info("%s: ACHOU %s (%d bytes) -> %s", rotulo, origem, len(conteudo), arquivo.name)
                        resumo.append(f"{rotulo}\tOK\t{origem}\t{len(conteudo)} bytes")
                    else:
                        listados = busca.nomes_na_listagem(trecho)
                        logger.error("%s: arquivo nao achado. Na listagem HTTP: %s", rotulo, listados[:10])
                        resumo.append(f"{rotulo}\tNAO ACHOU\t{descricao}\tlistagem: {listados[:10]}")
                except RelatorioSemConteudo as exc:
                    resumo.append(f"{rotulo}\tSEM MOVIMENTO\t{exc}")
                except PromaxHttpErro as exc:
                    logger.error("%s falhou: %s", rotulo, exc)
                    resumo.append(f"{rotulo}\tERRO\t{exc}")
    finally:
        try:
            cliente.logoff()
        except Exception as exc:  # o logoff e cortesia
            logger.debug("Logoff falhou: %s", exc)

    texto = f"Teste DVS de {datetime.now():%d/%m/%Y %H:%M} (030805 data {data_030805}; 1706 {periodo_1706[0]} a {periodo_1706[1]})\n"
    texto += "\n".join(resumo) + "\n"
    (saida / "resumo.txt").write_text(texto, encoding="utf-8")
    logger.info("Resumo do teste DVS:\n%s", texto)
    return 0 if all("\tOK\t" in linha or "SEM MOVIMENTO" in linha for linha in resumo) else 1


if __name__ == "__main__":
    sys.exit(main())
