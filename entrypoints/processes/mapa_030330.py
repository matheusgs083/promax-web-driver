import argparse
import time

import dotenv

from core.config.settings import get_settings
from core.execution.entrypoint_helpers import encerrar_driver, iniciar_sessao_padrao
from core.execution.execution_result import ExecutionResult, ExecutionStatus, normalize_execution_result
from core.observability.logger import get_logger
from pages.processes.processo_030330_page import Processo030330Page


dotenv.load_dotenv()
logger = get_logger("PROCESSO_030330")
settings = get_settings()


def _parse_args():
    parser = argparse.ArgumentParser(description="Carrega e salva mapa na rotina 030330 (PW02141C).")
    parser.add_argument("--mapa", required=True, help="Numero do mapa que sera carregado.")
    parser.add_argument("--dt-emissao", default=None, help="Data de emissao (DD/MM/YYYY).")
    parser.add_argument(
        "--tp-mapa",
        default="COMODATO",
        help="Tipo de mapa (COMODATO, CONSIGNACAO ou AMBOS). Padrao: COMODATO.",
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
        help="Fecha o navegador mesmo quando a 030330 retornar falha.",
    )
    return parser.parse_args()


def main(
    mapa=None,
    dt_emissao=None,
    tp_mapa="COMODATO",
    unidade=None,
    salvar=True,
    manter_aberto_ao_falhar=True,
):
    args = None
    if mapa is None:
        args = _parse_args()
        mapa = args.mapa
        dt_emissao = args.dt_emissao
        tp_mapa = args.tp_mapa
        unidade = args.unidade
        salvar = not args.nao_salvar
        manter_aberto_ao_falhar = not args.fechar_ao_falhar

    unidade = (unidade or settings.unidade_pedidos).strip().upper()
    tp_mapa = str(tp_mapa or "COMODATO").strip()
    driver = None
    resultado = None

    try:
        logger.info("030330 | inicio | mapa=%s | tipo=%s | unidade=%s", mapa, tp_mapa, unidade)
        driver, menu_page = iniciar_sessao_padrao(logger, settings, unidade)

        janela = menu_page.acessar_rotina("030330")
        page = Processo030330Page(janela.driver, janela.handle_menu)

        tipos_para_processar = []
        if tp_mapa.upper() in ["AMBOS", "TODOS", "ALL"]:
            tipos_para_processar = ["COMODATO", "CONSIGNAÇÃO"]
        else:
            tipos_para_processar = [tp_mapa]

        resultados_tipos = []
        for tipo_item in tipos_para_processar:
            logger.info("030330 | Processando Tipo: %s", tipo_item)
            res_item = normalize_execution_result(
                page.carregar_mapa(mapa, dt_emissao=dt_emissao, tp_mapa=tipo_item)
            )
            metadata_carga = res_item.metadata or {}

            if res_item.ok and salvar:
                res_item = normalize_execution_result(page.salvar_mapa())
                res_item = ExecutionResult(
                    status=res_item.status,
                    message=res_item.message,
                    retry=res_item.retry,
                    metadata={
                        **metadata_carga,
                        **(res_item.metadata or {}),
                        "mapa": metadata_carga.get("mapa") or str(mapa).strip(),
                    },
                )
            resultados_tipos.append(res_item)
            page.cancelar()
            time.sleep(1.0)

        resultado = resultados_tipos[-1]
        if resultado.ok:
            codigo = (resultado.metadata or {}).get("integration_code") or "030330_OK"
            logger.info(
                "SUCESSO 030330 | codigo=%s | mensagem=%s",
                codigo,
                resultado.message,
            )
        else:
            logger.warning(
                "FALHA 030330 | status=%s | mensagem=%s",
                resultado.status.value,
                resultado.message,
            )

        return resultado
    finally:
        time.sleep(0.3)
        if manter_aberto_ao_falhar and resultado is not None and not resultado.ok:
            logger.warning("030330 | navegador mantido aberto para inspecao da falha.")
        else:
            encerrar_driver(driver)


if __name__ == "__main__":
    main()
