import argparse
import time

import dotenv

from core.config.settings import get_settings
from core.execution.entrypoint_helpers import encerrar_driver, iniciar_sessao_padrao
from core.execution.execution_result import ExecutionResult, normalize_execution_result
from core.observability.logger import get_logger
from pages.processes.processo_030303_page import Processo030303Page


dotenv.load_dotenv()
logger = get_logger("PROCESSO_030303")
settings = get_settings()


def _parse_args():
    parser = argparse.ArgumentParser(description="Carrega e salva mapa na rotina 030303.")
    parser.add_argument("--mapa", required=True, help="Numero do mapa que sera carregado.")
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
        help="Fecha o navegador mesmo quando a 030303 retornar falha.",
    )
    return parser.parse_args()


def main(
    mapa=None,
    unidade=None,
    salvar=True,
    manter_aberto_ao_falhar=True,
):
    args = None
    if mapa is None:
        args = _parse_args()
        mapa = args.mapa
        unidade = args.unidade
        salvar = not args.nao_salvar
        manter_aberto_ao_falhar = not args.fechar_ao_falhar

    unidade = (unidade or settings.unidade_pedidos).strip().upper()
    driver = None
    resultado = None

    try:
        logger.info("030303 | inicio | mapa=%s | unidade=%s", mapa, unidade)
        driver, menu_page = iniciar_sessao_padrao(logger, settings, unidade)

        janela = menu_page.acessar_rotina("030303")
        page = Processo030303Page(janela.driver, janela.handle_menu)

        resultado = normalize_execution_result(page.carregar_mapa(mapa))
        metadata_carga = resultado.metadata or {}

        if resultado.ok and salvar:
            resultado = normalize_execution_result(page.salvar_mapa())
            resultado = normalize_execution_result(resultado)
            resultado = ExecutionResult(
                status=resultado.status,
                message=resultado.message,
                retry=resultado.retry,
                metadata={
                    **metadata_carga,
                    **(resultado.metadata or {}),
                    "mapa": metadata_carga.get("mapa") or str(mapa).strip(),
                },
            )

        if resultado.ok:
            codigo = (resultado.metadata or {}).get("integration_code") or "030303_OK"
            logger.info(
                "SUCESSO 030303 | codigo=%s | mensagem=%s",
                codigo,
                resultado.message,
            )
        else:
            logger.warning(
                "FALHA 030303 | status=%s | mensagem=%s",
                resultado.status.value,
                resultado.message,
            )

        return resultado
    finally:
        time.sleep(0.3)
        if manter_aberto_ao_falhar and resultado is not None and not resultado.ok:
            logger.warning("030303 | navegador mantido aberto para inspecao da falha.")
        else:
            encerrar_driver(driver)


if __name__ == "__main__":
    main()
