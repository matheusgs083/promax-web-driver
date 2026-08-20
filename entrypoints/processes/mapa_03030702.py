import argparse
import json
import time
from pathlib import Path

import dotenv

from core.execution.entrypoint_helpers import encerrar_driver, iniciar_sessao_padrao
from core.execution.execution_result import ExecutionResult, normalize_execution_result
from core.observability.logger import get_logger
from core.config.settings import get_settings
from pages.processes.processo_03030702_page import Processo03030702Page


dotenv.load_dotenv()
logger = get_logger("PROCESSO_03030702")
settings = get_settings()


def _extrair_dados_fechamento_03030702(page_03030702, etapa):
    try:
        dados = page_03030702.extrair_pagina_json(timeout_segundos=8)
        if isinstance(dados, dict):
            return {**dados, "etapa": etapa}
        return {"etapa": etapa, "valor": dados}
    except Exception as exc:
        logger.warning("03030702 | Nao foi possivel extrair dados estruturados do fechamento: %s", exc)
        return {"rotina": "03030702", "etapa": etapa, "erro": str(exc)}


def _parse_args():
    parser = argparse.ArgumentParser(description="Carrega mapa na rotina 03030702.")
    parser.add_argument("--mapa", required=True, help="Numero do mapa que sera carregado.")
    parser.add_argument(
        "--ponto-apoio",
        default=None,
        help="Ponto de apoio. Quando omitido, a rotina usa 0.",
    )
    parser.add_argument(
        "--unidade",
        default=settings.unidade_pedidos,
        help="Unidade Promax para login. Padrao: PROMAX_PEDIDOS_UNIT.",
    )
    parser.add_argument(
        "--nao-salvar",
        action="store_true",
        help="Apenas carrega o mapa, sem clicar em salvar.",
    )
    parser.add_argument(
        "--nao-equilibrar",
        action="store_true",
        help="Carrega o mapa sem digitar contas faltantes automaticamente.",
    )
    parser.add_argument(
        "--fechar-ao-falhar",
        action="store_true",
        help="Fecha o navegador mesmo quando a 03030702 retornar falha.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime o JSON estruturado da pagina apos carregar o mapa.",
    )
    parser.add_argument(
        "--json-arquivo",
        default=None,
        help="Salva o JSON estruturado da pagina no caminho informado.",
    )
    parser.add_argument(
        "--incluir-html",
        action="store_true",
        help="Inclui HTML completo dos frames no JSON. Por padrao, exporta campos e tabelas.",
    )
    return parser.parse_args()


def main(
    mapa=None,
    ponto_apoio=None,
    unidade=None,
    salvar=True,
    manter_aberto_ao_falhar=True,
    retornar_json=False,
    caminho_json=None,
    incluir_html=False,
    auto_equilibrar=True,
):
    args = None
    if mapa is None:
        args = _parse_args()
        mapa = args.mapa
        ponto_apoio = args.ponto_apoio
        unidade = args.unidade
        salvar = not args.nao_salvar
        auto_equilibrar = not args.nao_equilibrar
        manter_aberto_ao_falhar = not args.fechar_ao_falhar
        retornar_json = args.json
        caminho_json = args.json_arquivo
        incluir_html = args.incluir_html

    unidade = (unidade or settings.unidade_pedidos).strip().upper()
    driver = None
    resultado = None
    pagina_json = None

    try:
        logger.info("03030702 | inicio | mapa=%s | unidade=%s", mapa, unidade)
        driver, menu_page = iniciar_sessao_padrao(logger, settings, unidade)

        janela = menu_page.acessar_rotina("03030702")
        page = Processo03030702Page(janela.driver, janela.handle_menu)

        resultado = normalize_execution_result(
            page.carregar_mapa(
                mapa,
                ponto_apoio=ponto_apoio,
                auto_equilibrar=auto_equilibrar,
            )
        )

        if resultado.ok and (retornar_json or caminho_json):
            pagina_json = page.extrair_pagina_json(incluir_html=incluir_html)

            if caminho_json:
                destino_json = Path(caminho_json).expanduser().resolve()
                destino_json.parent.mkdir(parents=True, exist_ok=True)
                destino_json.write_text(
                    json.dumps(pagina_json, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                logger.info("03030702 | JSON estruturado salvo em: %s", destino_json)

            if retornar_json:
                print(json.dumps(pagina_json, ensure_ascii=False, indent=2))

            metadata = dict(resultado.metadata or {})
            metadata["pagina_json"] = pagina_json
            resultado = ExecutionResult(
                status=resultado.status,
                message=resultado.message,
                retry=resultado.retry,
                metadata=metadata,
            )

        if resultado.ok and salvar:
            resultado_salvar = normalize_execution_result(page.salvar_mapa())
            dados_fechamento = _extrair_dados_fechamento_03030702(
                page,
                etapa="apos_salvar_financeiro",
            )
            metadata = dict(resultado_salvar.metadata or {})
            metadata["dados_fechamento_03030702"] = dados_fechamento
            if pagina_json:
                metadata["pagina_json"] = pagina_json
            resultado_salvar = ExecutionResult(
                status=resultado_salvar.status,
                message=resultado_salvar.message,
                retry=resultado_salvar.retry,
                metadata=metadata,
            )
            resultado = resultado_salvar

        if resultado.ok:
            codigo = (resultado.metadata or {}).get("integration_code") or "03030702_OK"
            logger.info(
                "SUCESSO 03030702 | codigo=%s | mensagem=%s",
                codigo,
                resultado.message,
            )
        else:
            logger.warning(
                "FALHA 03030702 | status=%s | mensagem=%s",
                resultado.status.value,
                resultado.message,
            )

        return resultado
    finally:
        time.sleep(0.3)
        if manter_aberto_ao_falhar and resultado is not None and not resultado.ok:
            logger.warning("03030702 | navegador mantido aberto para inspecao da falha.")
        else:
            encerrar_driver(driver)


if __name__ == "__main__":
    main()
