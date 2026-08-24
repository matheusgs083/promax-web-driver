import argparse
import time

import dotenv

from core.execution.entrypoint_helpers import encerrar_driver, iniciar_sessao_padrao
from core.execution.execution_result import normalize_execution_result
from core.observability.logger import get_logger
from core.config.settings import get_settings
from pages.processes.processo_030302_page import Processo030302Page


dotenv.load_dotenv()
logger = get_logger("PROCESSO_030302")
settings = get_settings()


def _parse_args():
    parser = argparse.ArgumentParser(description="Carrega mapa na rotina 030302.")
    parser.add_argument("--mapa", required=True, help="Numero do mapa que sera carregado.")
    parser.add_argument(
        "--ponto-apoio",
        default=None,
        help="Ponto de apoio. Quando omitido, a rotina usa 0.",
    )
    parser.add_argument(
        "--km-atual",
        default=None,
        help="KM atual do veiculo. Opcional; quando omitido, o campo nao e alterado.",
    )
    parser.add_argument(
        "--km-inicial",
        default=None,
        help="KM inicial do veiculo. Usado com --km-prev se o alerta de KM for disparado.",
    )
    parser.add_argument(
        "--km-prev",
        default=None,
        help="KM previsto do veiculo. Usado com --km-inicial se o alerta de KM for disparado.",
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
        "--fechar-ao-falhar",
        action="store_true",
        help="Fecha o navegador mesmo quando a 030302 retornar falha.",
    )
    return parser.parse_args()


def main(
    mapa=None,
    ponto_apoio=None,
    km_atual=None,
    km_inicial=None,
    km_prev=None,
    unidade=None,
    salvar=True,
    manter_aberto_ao_falhar=True,
):
    args = None
    if mapa is None:
        args = _parse_args()
        mapa = args.mapa
        ponto_apoio = args.ponto_apoio
        km_atual = args.km_atual
        km_inicial = args.km_inicial
        km_prev = args.km_prev
        unidade = args.unidade
        salvar = not args.nao_salvar
        manter_aberto_ao_falhar = not args.fechar_ao_falhar

    unidade = (unidade or settings.unidade_pedidos).strip().upper()
    driver = None
    resultado = None

    try:
        logger.info("030302 | inicio | mapa=%s | unidade=%s", mapa, unidade)
        driver, menu_page = iniciar_sessao_padrao(logger, settings, unidade)

        janela = menu_page.acessar_rotina("030302")
        page = Processo030302Page(janela.driver, janela.handle_menu)

        resultado = normalize_execution_result(
            page.carregar_mapa(
                mapa,
                ponto_apoio=ponto_apoio,
                km_atual=km_atual,
                km_inicial=km_inicial,
                km_prev=km_prev,
            )
        )

        if resultado.ok and salvar:
            resultado = normalize_execution_result(page.salvar_mapa())

        if resultado.ok:
            codigo = (resultado.metadata or {}).get("integration_code") or "030302_OK"
            logger.info(
                "SUCESSO 030302 | codigo=%s | mensagem=%s",
                codigo,
                resultado.message,
            )
        else:
            logger.warning(
                "FALHA 030302 | status=%s | mensagem=%s",
                resultado.status.value,
                resultado.message,
            )

        return resultado
    finally:
        time.sleep(0.3)
        if manter_aberto_ao_falhar and resultado is not None and not resultado.ok:
            logger.warning("030302 | navegador mantido aberto para inspecao da falha.")
        else:
            encerrar_driver(driver)


if __name__ == "__main__":
    main()
