import argparse
import time
import dotenv

from core.config.settings import get_settings
from core.execution.entrypoint_helpers import encerrar_driver, iniciar_sessao_padrao
from core.execution.execution_result import ExecutionResult, ExecutionStatus, normalize_execution_result
from core.observability.logger import get_logger
from pages.processes.processo_030302_page import Processo030302Page
from pages.processes.processo_03030702_page import Processo03030702Page
from entrypoints.processes.mapa_030302 import main as main_030302
from entrypoints.processes.mapa_03030702 import main as main_03030702

dotenv.load_dotenv()
logger = get_logger("FECHAMENTO_COMPLETO_MAPA")
settings = get_settings()


def _extrair_dados_fechamento_03030702(page_03030702, etapa):
    try:
        dados = page_03030702.extrair_pagina_json(timeout_segundos=8)
        if isinstance(dados, dict):
            return {
                **dados,
                "etapa": etapa,
            }
        return {"etapa": etapa, "valor": dados}
    except Exception as exc:
        logger.warning(
            "03030702 | Nao foi possivel extrair dados estruturados do fechamento: %s",
            exc,
        )
        return {
            "rotina": "03030702",
            "etapa": etapa,
            "erro": str(exc),
        }


def _anexar_metadata_resultado(resultado, **metadata_extra):
    if resultado is None:
        return None
    metadata = {
        **(resultado.metadata or {}),
        **metadata_extra,
    }
    return ExecutionResult(
        status=resultado.status,
        message=resultado.message,
        retry=resultado.retry,
        metadata=metadata,
    )


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Executa o fechamento completo (Fisico 030302 + Financeiro 03030702) de um mapa no Promax."
    )
    parser.add_argument("--mapa", default="93491", help="Numero do mapa que sera processado. Padrao: 93491.")
    parser.add_argument(
        "--ponto-apoio",
        default=None,
        help="Ponto de apoio. Quando omitido, a rotina usa 0.",
    )
    parser.add_argument(
        "--km-atual",
        default=None,
        help="KM atual do veiculo usado na rotina fisica 030302. Opcional.",
    )
    parser.add_argument(
        "--unidade",
        default=settings.unidade_pedidos,
        help="Unidade Promax para login. Padrao: PROMAX_PEDIDOS_UNIT.",
    )
    parser.add_argument(
        "--modo",
        choices=("completo", "fisico", "financeiro"),
        default="completo",
        help="Define se executa o fechamento completo, apenas fisico ou apenas financeiro.",
    )
    parser.add_argument(
        "--nao-salvar",
        action="store_true",
        help="Apenas carrega o mapa nas rotinas sem clicar em salvar.",
    )
    parser.add_argument(
        "--sessoes-separadas",
        action="store_true",
        help="Executa o fechamento fisico e financeiro em sessoes independentes do navegador.",
    )
    parser.add_argument(
        "--fechar-ao-falhar",
        action="store_true",
        help="Fecha o navegador mesmo quando houver falha no processo.",
    )
    return parser.parse_args()


def fechar_mapa_sessao_unica(
    mapa,
    ponto_apoio=None,
    km_atual=None,
    unidade=None,
    salvar=True,
    manter_aberto_ao_falhar=True,
):
    """
    Executa a conferencia Fisico (030302) e Financeiro (03030702) em uma UNICA sessao de navegador.
    Checa se a lista do HTML da 030302 esta preenchida com codigos. Caso nao esteja preenchida,
    dispara o salvamento/segundo processo da 030302 e prossegue para a 03030702.
    """
    unidade = (unidade or settings.unidade_pedidos).strip().upper()
    driver = None
    res_fisico = None
    res_financeiro = None
    dados_fechamento_03030702 = None

    try:
        logger.info("=========================================================================")
        logger.info("FECHAMENTO COMPLETO DE MAPA | INICIO | Mapa: %s | Unidade: %s", mapa, unidade)
        logger.info("=========================================================================")

        driver, menu_page = iniciar_sessao_padrao(logger, settings, unidade)

        # ---------------------------------------------------------------------
        # PASSO 1: CONFERENCIA E FECHAMENTO FISICO (ROTINA 030302)
        # ---------------------------------------------------------------------
        logger.info("--- PASSO 1: INICIANDO ROTINA FISICA (030302) ---")
        janela_030302 = menu_page.acessar_rotina("030302")
        page_030302 = Processo030302Page(janela_030302.driver, janela_030302.handle_menu)

        carregar_030302_kwargs = {"ponto_apoio": ponto_apoio}
        if km_atual is not None and str(km_atual).strip():
            carregar_030302_kwargs["km_atual"] = km_atual
        res_fisico = normalize_execution_result(
            page_030302.carregar_mapa(mapa, **carregar_030302_kwargs)
        )

        lista_preenchida = page_030302.tem_codigos_fisicos()
        logger.info("030302 | Checagem de codigos no HTML: lista_preenchida=%s", lista_preenchida)

        if not lista_preenchida:
            logger.info("030302 | A lista do HTML nao esta preenchida com codigos. Executando o salvamento/segundo processo da 030302 para liberacao...")
        else:
            logger.info("030302 | A lista do HTML esta preenchida com codigos. Executando salvamento de acerto fisico...")

        if res_fisico.ok and salvar:
            res_fisico = normalize_execution_result(page_030302.salvar_mapa())

        logger.info("030302 | Resultado do processo na 030302: ok=%s, msg=%s", res_fisico.ok if res_fisico else None, res_fisico.message if res_fisico else None)

        if not res_fisico.ok:
            logger.error("PASSO 1 FALHOU (030302 - FISICO): %s", res_fisico.message)
            return ExecutionResult(
                status=res_fisico.status,
                message=f"Falha no Fechamento Fisico (030302): {res_fisico.message}",
                retry=res_fisico.retry,
                metadata={
                    "passo_falha": "030302",
                    "resultado_fisico": res_fisico,
                    "resultado_financeiro": None,
                    "dados_fechamento_03030702": None,
                },
            )

        # Retornar o foco para o Menu Principal antes de abrir a proxima rotina
        try:
            driver.switch_to.window(janela_030302.handle_menu)
        except Exception:
            pass

        time.sleep(1.5)

        # ---------------------------------------------------------------------
        # PASSO 2: CONFERENCIA E LIBERACAO FINANCEIRA (ROTINA 03030702)
        # ---------------------------------------------------------------------
        logger.info("--- PASSO 2: INICIANDO ROTINA FINANCEIRA (03030702) ---")
        janela_03030702 = menu_page.acessar_rotina("03030702")
        page_03030702 = Processo03030702Page(janela_03030702.driver, janela_03030702.handle_menu)

        res_financeiro = normalize_execution_result(
            page_03030702.carregar_mapa(mapa, ponto_apoio=ponto_apoio)
        )

        if res_financeiro.ok and salvar:
            res_financeiro = normalize_execution_result(page_03030702.salvar_mapa())
            dados_fechamento_03030702 = _extrair_dados_fechamento_03030702(
                page_03030702,
                etapa="apos_salvar_financeiro",
            )
            res_financeiro = _anexar_metadata_resultado(
                res_financeiro,
                dados_fechamento_03030702=dados_fechamento_03030702,
            )
        elif res_financeiro.ok:
            dados_fechamento_03030702 = _extrair_dados_fechamento_03030702(
                page_03030702,
                etapa="apos_carregar_financeiro",
            )
            res_financeiro = _anexar_metadata_resultado(
                res_financeiro,
                dados_fechamento_03030702=dados_fechamento_03030702,
            )

        if not res_financeiro.ok:
            logger.error("PASSO 2 FALHOU (03030702 - FINANCEIRO): %s", res_financeiro.message)
            return ExecutionResult(
                status=res_financeiro.status,
                message=f"Falha no Fechamento Financeiro (03030702): {res_financeiro.message}",
                metadata={
                    "passo_falha": "03030702",
                    "resultado_fisico": res_fisico,
                    "resultado_financeiro": res_financeiro,
                    "dados_fechamento_03030702": dados_fechamento_03030702,
                },
            )

        logger.info("=========================================================================")
        logger.info("FECHAMENTO COMPLETO CONCLUIDO COM SUCESSO | Mapa: %s", mapa)
        logger.info("=========================================================================")

        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message=f"Fechamento Fisico e Financeiro do Mapa {mapa} executados com sucesso.",
            metadata={
                "mapa": mapa,
                "resultado_fisico": res_fisico,
                "resultado_financeiro": res_financeiro,
                "dados_fechamento_03030702": dados_fechamento_03030702,
                "integration_code": "MAPA_LIBERADO_FINANCEIRO",
            },
        )

    except Exception as e:
        logger.error("Erro inesperado no fechamento completo do mapa %s: %s", mapa, e)
        return ExecutionResult(
            status=ExecutionStatus.TECHNICAL_FAILURE,
            message=f"Falha inesperada no fechamento do mapa: {str(e)}",
        )
    finally:
        time.sleep(0.5)
        falhou = bool(
            (res_fisico and not res_fisico.ok)
            or (res_financeiro and not res_financeiro.ok)
        )
        if manter_aberto_ao_falhar and falhou:
            logger.warning("Navegador mantido aberto para inspecao da falha no fechamento.")
        else:
            encerrar_driver(driver)


def fechar_mapa_sessoes_separadas(
    mapa,
    ponto_apoio=None,
    km_atual=None,
    unidade=None,
    salvar=True,
    manter_aberto_ao_falhar=True,
):
    """
    Executa a conferencia Fisico (030302) e Financeiro (03030702) em sessoes separadas.
    """
    logger.info("--- EXECUTANDO EM SESSOES SEPARADAS: PASSO 1 (FISICO 030302) ---")
    res_fisico = main_030302(
        mapa=mapa,
        ponto_apoio=ponto_apoio,
        km_atual=km_atual,
        unidade=unidade,
        salvar=salvar,
        manter_aberto_ao_falhar=manter_aberto_ao_falhar,
    )

    logger.info("--- EXECUTANDO EM SESSOES SEPARADAS: PASSO 2 (FINANCEIRO 03030702) ---")
    res_financeiro = main_03030702(
        mapa=mapa,
        ponto_apoio=ponto_apoio,
        unidade=unidade,
        salvar=salvar,
        manter_aberto_ao_falhar=manter_aberto_ao_falhar,
    )

    return res_financeiro


def main(
    mapa=None,
    ponto_apoio=None,
    km_atual=None,
    unidade=None,
    modo="completo",
    salvar=True,
    sessoes_separadas=False,
    manter_aberto_ao_falhar=True,
):
    args = None
    if mapa is None:
        args = _parse_args()
        mapa = args.mapa
        ponto_apoio = args.ponto_apoio
        km_atual = args.km_atual
        unidade = args.unidade
        modo = args.modo
        salvar = not args.nao_salvar
        sessoes_separadas = args.sessoes_separadas
        manter_aberto_ao_falhar = not args.fechar_ao_falhar

    modo = str(modo or "completo").strip().lower()
    if modo == "fisico":
        resultado = normalize_execution_result(
            main_030302(
                mapa=mapa,
                ponto_apoio=ponto_apoio,
                km_atual=km_atual,
                unidade=unidade,
                salvar=salvar,
                manter_aberto_ao_falhar=manter_aberto_ao_falhar,
            )
        )
        return _anexar_metadata_resultado(resultado, mapa=mapa, integration_code="MAPA_LIBERADO_FISICO")
    if modo == "financeiro":
        resultado = normalize_execution_result(
            main_03030702(
                mapa=mapa,
                ponto_apoio=ponto_apoio,
                unidade=unidade,
                salvar=salvar,
                manter_aberto_ao_falhar=manter_aberto_ao_falhar,
            )
        )
        return _anexar_metadata_resultado(resultado, mapa=mapa, integration_code="MAPA_LIBERADO_FINANCEIRO")
    if modo != "completo":
        return ExecutionResult(
            status=ExecutionStatus.BUSINESS_FAILURE,
            message="Modo de fechamento invalido. Use completo, fisico ou financeiro.",
            metadata={"mapa": mapa, "modo": modo},
        )

    if sessoes_separadas:
        return fechar_mapa_sessoes_separadas(
            mapa=mapa,
            ponto_apoio=ponto_apoio,
            km_atual=km_atual,
            unidade=unidade,
            salvar=salvar,
            manter_aberto_ao_falhar=manter_aberto_ao_falhar,
        )
    else:
        return fechar_mapa_sessao_unica(
            mapa=mapa,
            ponto_apoio=ponto_apoio,
            km_atual=km_atual,
            unidade=unidade,
            salvar=salvar,
            manter_aberto_ao_falhar=manter_aberto_ao_falhar,
        )


if __name__ == "__main__":
    main()
