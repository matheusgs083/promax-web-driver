import argparse
import time
import unicodedata
import dotenv

from core.config.settings import get_settings
from core.execution.entrypoint_helpers import encerrar_driver, iniciar_sessao_padrao
from core.execution.execution_result import ExecutionResult, ExecutionStatus, normalize_execution_result
from core.observability.logger import get_logger
from pages.processes.processo_030303_page import Processo030303Page
from pages.processes.processo_030302_page import Processo030302Page
from pages.processes.processo_030330_page import Processo030330Page
from pages.processes.processo_030322_page import Processo030322Page
from pages.processes.processo_03030702_page import Processo03030702Page
from entrypoints.processes.mapa_030303 import main as main_030303
from entrypoints.processes.mapa_030302 import main as main_030302
from entrypoints.processes.mapa_03030702 import main as main_03030702

dotenv.load_dotenv()
logger = get_logger("FECHAMENTO_COMPLETO_MAPA")
settings = get_settings()


def _normalizar_ponto_apoio(ponto_apoio):
    valor = "" if ponto_apoio is None else str(ponto_apoio).strip()
    return "" if valor in {"0", "00", "000"} else valor


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


def _metadata_resultado(resultado):
    if resultado is None:
        return None
    return {
        "status": resultado.status.value if hasattr(resultado.status, "value") else str(resultado.status),
        "message": resultado.message,
        "retry": resultado.retry,
        **(resultado.metadata or {}),
    }


def _km_fallback_reabertura_030302(resultado):
    metadata = (resultado.metadata or {}) if resultado else {}
    if not metadata.get("reabrir_030302_com_km_fallback"):
        return None
    km_fallback = str(metadata.get("km_atual_fallback") or "").strip()
    return km_fallback or None


def _normalizar_texto_fluxo(texto):
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(char for char in texto if not unicodedata.combining(char))


def _resultado_pede_030330_por_comodato(resultado):
    if not resultado:
        return False
    metadata = resultado.metadata or {}
    textos = [resultado.message]
    textos.extend(metadata.get("alertas") or [])
    texto = _normalizar_texto_fluxo(" | ".join(str(item or "") for item in textos))
    return (
        "comodato" in texto
        and ("030330" in texto or "03.03.30" in texto)
        and ("nao foi fechado" in texto or "nao fechado" in texto)
    )


def _fechar_rotina_030302_para_reabrir(page_030302, driver, janela_030302):
    try:
        return page_030302.fechar_e_voltar()
    except Exception as exc:
        logger.warning("030302 | Falha ao fechar rotina pelo helper antes da reabertura: %s", exc)
        try:
            driver.switch_to.window(janela_030302.handle_menu)
        except Exception:
            pass
        return None


def _tipos_para_processar_030330(tp_mapa="COMODATO"):
    tp_mapa = str(tp_mapa or "COMODATO").strip()
    if tp_mapa.upper() in {"AMBOS", "TODOS", "ALL"}:
        return ["COMODATO", "CONSIGNACAO"]
    return [tp_mapa]


def _executar_030330_sessao_unica(menu_page, mapa, dt_emissao=None, tp_mapa="COMODATO"):
    logger.warning(
        "030302 | Comodato pendente detectado. Executando 030330 antes de retentar o fechamento fisico do mapa %s.",
        mapa,
    )
    janela_030330 = menu_page.acessar_rotina("030330")
    page_030330 = Processo030330Page(janela_030330.driver, janela_030330.handle_menu)
    resultados_tipos = []

    for tipo_item in _tipos_para_processar_030330(tp_mapa):
        logger.info("030330 | Processando Tipo: %s", tipo_item)
        resultado_carga = normalize_execution_result(
            page_030330.carregar_mapa(mapa, dt_emissao=dt_emissao, tp_mapa=tipo_item)
        )
        metadata_carga = resultado_carga.metadata or {}
        resultado_item = resultado_carga

        if resultado_carga.ok:
            resultado_salvar = normalize_execution_result(page_030330.salvar_mapa())
            resultado_item = ExecutionResult(
                status=resultado_salvar.status,
                message=resultado_salvar.message,
                retry=resultado_salvar.retry,
                metadata={
                    **metadata_carga,
                    **(resultado_salvar.metadata or {}),
                    "mapa": metadata_carga.get("mapa") or str(mapa).strip(),
                    "resultado_carga_030330": _metadata_resultado(resultado_carga),
                },
            )
        resultados_tipos.append(resultado_item)
        try:
            page_030330.cancelar()
        except Exception as exc:
            logger.warning("030330 | Falha ao cancelar rotina apos processamento: %s", exc)
        time.sleep(1.0)

    resultado_final = resultados_tipos[-1] if resultados_tipos else ExecutionResult(
        status=ExecutionStatus.TECHNICAL_FAILURE,
        message="Nenhum tipo de mapa foi processado na 030330.",
        retry=False,
    )
    try:
        novo_menu = page_030330.fechar_e_voltar()
    except Exception as exc:
        logger.warning("030330 | Falha ao fechar rotina e voltar ao menu: %s", exc)
        novo_menu = menu_page
    return resultado_final, novo_menu


def _extrair_prestacao_030322_sessao_unica(menu_page, mapa, data=None):
    logger.info("--- PASSO 3: EXTRAINDO PRESTACAO DE CONTAS (030322) ---")
    janela_030322 = menu_page.acessar_rotina("030322")
    page_030322 = Processo030322Page(janela_030322.driver, janela_030322.handle_menu)
    try:
        resultado = normalize_execution_result(
            page_030322.visualizar(
                mapa_inicial=mapa,
                mapa_final=mapa,
                data=data,
                mapas="liberados",
                lista_produtos=True,
            )
        )
        if not resultado.ok:
            return {
                "rotina": "030322",
                "mapa": str(mapa).strip(),
                "erro": resultado.message,
                "resultado_030322": _metadata_resultado(resultado),
            }
        dados = page_030322.extrair_relatorio_json(timeout_segundos=12)
        logger.info(
            "030322 | Prestacao extraida: mapa=%s | notas=%s | vasilhames=%s",
            mapa,
            (dados.get("resumo") or {}).get("notas"),
            (dados.get("resumo") or {}).get("vasilhames"),
        )
        return dados
    except Exception as exc:
        logger.warning("030322 | Falha ao extrair prestacao do mapa %s: %s", mapa, exc)
        return {"rotina": "030322", "mapa": str(mapa).strip(), "erro": str(exc)}
    finally:
        try:
            page_030322.fechar_e_voltar()
        except Exception as exc:
            logger.warning("030322 | Falha ao fechar rotina: %s", exc)


def _extrair_prestacao_030322_sessao_separada(mapa, data=None, unidade=None, manter_aberto_ao_falhar=True):
    unidade = (unidade or settings.unidade_pedidos).strip().upper()
    driver = None
    dados = None
    try:
        logger.info("--- EXECUTANDO EM SESSAO SEPARADA: PRESTACAO DE CONTAS 030322 ---")
        driver, menu_page = iniciar_sessao_padrao(logger, settings, unidade)
        dados = _extrair_prestacao_030322_sessao_unica(menu_page, mapa, data=data)
        return dados
    except Exception as exc:
        logger.warning("030322 | Falha ao extrair prestacao em sessao separada do mapa %s: %s", mapa, exc)
        return {"rotina": "030322", "mapa": str(mapa).strip(), "erro": str(exc)}
    finally:
        if manter_aberto_ao_falhar and isinstance(dados, dict) and dados.get("erro"):
            logger.warning("030322 | navegador mantido aberto para inspecao da falha.")
        else:
            encerrar_driver(driver)


def _escolher_dados_030303(dados_carga, dados_salvar):
    validar = getattr(Processo030303Page, "_dados_equipe_validos", None)
    if callable(validar):
        if validar(dados_salvar):
            return dados_salvar
        if validar(dados_carga):
            return dados_carga
        return dados_salvar or dados_carga
    if dados_salvar:
        return dados_salvar
    return dados_carga


def _executar_030303_sessao_unica(menu_page, mapa, salvar=True):
    logger.info("--- PASSO 0: INICIANDO ROTINA 030303 ---")
    janela_030303 = menu_page.acessar_rotina("030303")
    page_030303 = Processo030303Page(janela_030303.driver, janela_030303.handle_menu)

    resultado = normalize_execution_result(page_030303.carregar_mapa(mapa))
    metadata_carga = resultado.metadata or {}
    if resultado.ok and salvar:
        resultado = normalize_execution_result(page_030303.salvar_mapa())
        dados_carga = metadata_carga.get("dados_030303")
        dados_salvar = (resultado.metadata or {}).get("dados_030303")
        resultado = _anexar_metadata_resultado(
            resultado,
            mapa=metadata_carga.get("mapa") or str(mapa).strip(),
            dados_030303=_escolher_dados_030303(dados_carga, dados_salvar),
        )

    logger.info(
        "030303 | Resultado do processo: ok=%s, msg=%s",
        resultado.ok,
        resultado.message,
    )
    return resultado, janela_030303


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
        "--km-inicial",
        default=None,
        help="KM inicial do veiculo. Usado com --km-prev se o alerta de KM for disparado na 030302.",
    )
    parser.add_argument(
        "--km-prev",
        default=None,
        help="KM previsto do veiculo. Usado com --km-inicial se o alerta de KM for disparado na 030302.",
    )
    parser.add_argument(
        "--unidade",
        default=settings.unidade_pedidos,
        help="Unidade Promax para login. Padrao: PROMAX_PEDIDOS_UNIT.",
    )
    parser.add_argument(
        "--data",
        default=None,
        help="Data usada na rotina 030322. Aceita YYYY-MM-DD, DD/MM/AAAA ou DDMMAAAA.",
    )
    parser.add_argument(
        "--modo",
        choices=["completo", "fisico", "financeiro"],
        default="completo",
        help="Modo de execucao: completo (030303 + 030302 + 03030702), fisico (apenas 030303 + 030302) ou financeiro (apenas 03030702).",
    )
    parser.add_argument(
        "--nao-salvar",
        action="store_true",
        help="Executa a carga e validacoes sem clicar nos botoes finais de salvar.",
    )
    parser.add_argument(
        "--sessoes-separadas",
        action="store_true",
        help="Executa cada rotina em uma sessao separada do navegador.",
    )
    parser.add_argument(
        "--fechar-ao-falhar",
        action="store_true",
        help="Fecha o navegador mesmo em caso de falha.",
    )
    return parser.parse_args()


def fechar_mapa_sessao_unica(
    mapa,
    ponto_apoio=None,
    km_atual=None,
    km_inicial=None,
    km_prev=None,
    data=None,
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
    res_030303 = None
    res_030330 = None
    res_fisico = None
    res_financeiro = None
    dados_fechamento_03030702 = None
    dados_030322 = None

    try:
        logger.info("=========================================================================")
        logger.info("FECHAMENTO COMPLETO DE MAPA | INICIO | Mapa: %s | Unidade: %s", mapa, unidade)
        logger.info("=========================================================================")

        driver, menu_page = iniciar_sessao_padrao(logger, settings, unidade)

        # ---------------------------------------------------------------------
        # PASSO 0: PREPARACAO DO MAPA (ROTINA 030303)
        # ---------------------------------------------------------------------
        res_030303, janela_030303 = _executar_030303_sessao_unica(menu_page, mapa, salvar=salvar)
        if not res_030303.ok:
            logger.error("PASSO 0 FALHOU (030303): %s", res_030303.message)
            return ExecutionResult(
                status=res_030303.status,
                message=f"Falha na rotina 030303 antes do Fechamento Fisico: {res_030303.message}",
                retry=res_030303.retry,
                metadata={
                    "mapa": mapa,
                    "passo_falha": "030303",
                    "resultado_030303": _metadata_resultado(res_030303),
                    "resultado_fisico": None,
                    "resultado_financeiro": None,
                    "dados_fechamento_03030702": None,
                },
            )

        try:
            driver.switch_to.window(janela_030303.handle_menu)
        except Exception:
            pass

        time.sleep(1.0)

        # ---------------------------------------------------------------------
        # PASSO 1: CONFERENCIA E FECHAMENTO FISICO (ROTINA 030302)
        # ---------------------------------------------------------------------
        page_030302 = None
        janela_030302 = None
        km_atual_030302 = km_atual
        reabriu_por_km = False
        comodato_030330_executado = False
        tentativa_030302 = 1
        while tentativa_030302 <= 3:
            sufixos = []
            if reabriu_por_km:
                sufixos.append("REABERTURA COM KM FALLBACK")
            if comodato_030330_executado:
                sufixos.append("APOS 030330")
            sufixo_tentativa = f" | {' | '.join(sufixos)}" if sufixos else ""
            logger.info("--- PASSO 1: INICIANDO ROTINA FISICA (030302)%s ---", sufixo_tentativa)
            janela_030302 = menu_page.acessar_rotina("030302")
            page_030302 = Processo030302Page(janela_030302.driver, janela_030302.handle_menu)

            carregar_030302_kwargs = {"ponto_apoio": ponto_apoio}
            if km_atual_030302 is not None and str(km_atual_030302).strip():
                carregar_030302_kwargs["km_atual"] = km_atual_030302
            if km_inicial is not None and str(km_inicial).strip():
                carregar_030302_kwargs["km_inicial"] = km_inicial
            if km_prev is not None and str(km_prev).strip():
                carregar_030302_kwargs["km_prev"] = km_prev
            res_fisico = normalize_execution_result(
                page_030302.carregar_mapa(mapa, **carregar_030302_kwargs)
            )
            if _resultado_pede_030330_por_comodato(res_fisico) and not comodato_030330_executado:
                logger.warning(
                    "030302 | Mapa %s pediu fechamento de comodato pela 030330. Fechando 030302 e executando 030330.",
                    mapa,
                )
                novo_menu = _fechar_rotina_030302_para_reabrir(page_030302, driver, janela_030302)
                if novo_menu is not None:
                    menu_page = novo_menu
                res_030330, novo_menu = _executar_030330_sessao_unica(menu_page, mapa)
                if novo_menu is not None:
                    menu_page = novo_menu
                if not res_030330.ok:
                    res_fisico = ExecutionResult(
                        status=res_030330.status,
                        message=f"Falha na rotina 030330 antes do Fechamento Fisico: {res_030330.message}",
                        retry=res_030330.retry,
                        metadata={
                            "mapa": mapa,
                            "passo_falha": "030330",
                            "resultado_030330": _metadata_resultado(res_030330),
                        },
                    )
                    break
                comodato_030330_executado = True
                tentativa_030302 += 1
                time.sleep(1.0)
                continue
            km_fallback = _km_fallback_reabertura_030302(res_fisico)
            if km_fallback and not reabriu_por_km:
                logger.warning(
                    "030302 | Alerta de KM pediu reabertura. Fechando rotina e reabrindo mapa %s com KM %s.",
                    mapa,
                    km_fallback,
                )
                novo_menu = _fechar_rotina_030302_para_reabrir(page_030302, driver, janela_030302)
                if novo_menu is not None:
                    menu_page = novo_menu
                km_atual_030302 = km_fallback
                reabriu_por_km = True
                tentativa_030302 += 1
                time.sleep(1.0)
                continue
            break

        if res_fisico.ok:
            lista_preenchida = page_030302.tem_codigos_fisicos()
            logger.info("030302 | Checagem de codigos no HTML: lista_preenchida=%s", lista_preenchida)

            if not lista_preenchida:
                logger.info("030302 | A lista do HTML nao esta preenchida com codigos. Executando o salvamento/segundo processo da 030302 para liberacao...")
            else:
                logger.info("030302 | A lista do HTML esta preenchida com codigos. Executando salvamento de acerto fisico...")

        if res_fisico.ok and salvar:
            res_fisico = normalize_execution_result(page_030302.salvar_mapa())
            if reabriu_por_km:
                res_fisico = _anexar_metadata_resultado(
                    res_fisico,
                    reabriu_030302_por_km=True,
                    km_atual_reabertura=km_atual_030302,
                )

        logger.info("030302 | Resultado do processo na 030302: ok=%s, msg=%s", res_fisico.ok if res_fisico else None, res_fisico.message if res_fisico else None)

        if not res_fisico.ok:
            logger.error("PASSO 1 FALHOU (030302 - FISICO): %s", res_fisico.message)
            return ExecutionResult(
                status=res_fisico.status,
                message=f"Falha no Fechamento Fisico (030302): {res_fisico.message}",
                retry=res_fisico.retry,
                metadata={
                    "passo_falha": "030302",
                    "resultado_030303": _metadata_resultado(res_030303),
                    "resultado_030330": _metadata_resultado(res_030330),
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
                    "resultado_030303": _metadata_resultado(res_030303),
                    "resultado_030330": _metadata_resultado(res_030330),
                    "resultado_fisico": res_fisico,
                    "resultado_financeiro": res_financeiro,
                    "dados_fechamento_03030702": dados_fechamento_03030702,
                },
            )

        try:
            driver.switch_to.window(janela_03030702.handle_menu)
        except Exception:
            pass

        time.sleep(1.0)
        dados_030322 = _extrair_prestacao_030322_sessao_unica(menu_page, mapa, data=data)

        logger.info("=========================================================================")
        logger.info("FECHAMENTO COMPLETO CONCLUIDO COM SUCESSO | Mapa: %s", mapa)
        logger.info("=========================================================================")

        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message=f"Fechamento Fisico e Financeiro do Mapa {mapa} executados com sucesso.",
            metadata={
                "mapa": mapa,
                "resultado_030303": _metadata_resultado(res_030303),
                "resultado_030330": _metadata_resultado(res_030330),
                "resultado_fisico": res_fisico,
                "resultado_financeiro": res_financeiro,
                "dados_fechamento_03030702": dados_fechamento_03030702,
                "dados_030322": dados_030322,
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
            (res_030303 and not res_030303.ok)
            or (res_fisico and not res_fisico.ok)
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
    km_inicial=None,
    km_prev=None,
    data=None,
    unidade=None,
    salvar=True,
    manter_aberto_ao_falhar=True,
):
    """
    Executa a conferencia Fisico (030302) e Financeiro (03030702) em sessoes separadas.
    """
    logger.info("--- EXECUTANDO EM SESSOES SEPARADAS: PASSO 0 (030303) ---")
    res_030303 = normalize_execution_result(
        main_030303(
            mapa=mapa,
            unidade=unidade,
            salvar=salvar,
            manter_aberto_ao_falhar=manter_aberto_ao_falhar,
        )
    )
    if not res_030303.ok:
        return ExecutionResult(
            status=res_030303.status,
            message=f"Falha na rotina 030303 antes do Fechamento Fisico: {res_030303.message}",
            retry=res_030303.retry,
            metadata={
                "mapa": mapa,
                "passo_falha": "030303",
                "resultado_030303": _metadata_resultado(res_030303),
                "resultado_fisico": None,
                "resultado_financeiro": None,
            },
        )

    logger.info("--- EXECUTANDO EM SESSOES SEPARADAS: PASSO 1 (FISICO 030302) ---")
    res_fisico = normalize_execution_result(
        main_030302(
            mapa=mapa,
            ponto_apoio=ponto_apoio,
            km_atual=km_atual,
            km_inicial=km_inicial,
            km_prev=km_prev,
            unidade=unidade,
            salvar=salvar,
            manter_aberto_ao_falhar=manter_aberto_ao_falhar,
        )
    )
    if not res_fisico.ok:
        return _anexar_metadata_resultado(
            res_fisico,
            mapa=mapa,
            passo_falha="030302",
            resultado_030303=_metadata_resultado(res_030303),
            resultado_fisico=_metadata_resultado(res_fisico),
            resultado_financeiro=None,
        )

    logger.info("--- EXECUTANDO EM SESSOES SEPARADAS: PASSO 2 (FINANCEIRO 03030702) ---")
    res_financeiro = normalize_execution_result(
        main_03030702(
            mapa=mapa,
            ponto_apoio=ponto_apoio,
            unidade=unidade,
            salvar=salvar,
            manter_aberto_ao_falhar=manter_aberto_ao_falhar,
        )
    )
    dados_030322 = None
    if res_financeiro.ok:
        dados_030322 = _extrair_prestacao_030322_sessao_separada(
            mapa,
            data=data,
            unidade=unidade,
            manter_aberto_ao_falhar=manter_aberto_ao_falhar,
        )

    return _anexar_metadata_resultado(
        res_financeiro,
        mapa=mapa,
        resultado_030303=_metadata_resultado(res_030303),
        resultado_fisico=_metadata_resultado(res_fisico),
        dados_030322=dados_030322,
    )


def main(
    mapa=None,
    ponto_apoio=None,
    km_atual=None,
    km_inicial=None,
    km_prev=None,
    data=None,
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
        km_inicial = args.km_inicial
        km_prev = args.km_prev
        data = args.data
        unidade = args.unidade
        modo = args.modo
        salvar = not args.nao_salvar
        sessoes_separadas = args.sessoes_separadas
        manter_aberto_ao_falhar = not args.fechar_ao_falhar

    ponto_apoio = _normalizar_ponto_apoio(ponto_apoio)
    modo = str(modo or "completo").strip().lower()
    if modo == "fisico":
        resultado_030303 = normalize_execution_result(
            main_030303(
                mapa=mapa,
                unidade=unidade,
                salvar=salvar,
                manter_aberto_ao_falhar=manter_aberto_ao_falhar,
            )
        )
        if not resultado_030303.ok:
            return _anexar_metadata_resultado(
                resultado_030303,
                mapa=mapa,
                passo_falha="030303",
                resultado_030303=_metadata_resultado(resultado_030303),
            )
        resultado = normalize_execution_result(
            main_030302(
                mapa=mapa,
                ponto_apoio=ponto_apoio,
                km_atual=km_atual,
                km_inicial=km_inicial,
                km_prev=km_prev,
                unidade=unidade,
                salvar=salvar,
                manter_aberto_ao_falhar=manter_aberto_ao_falhar,
            )
        )
        return _anexar_metadata_resultado(
            resultado,
            mapa=mapa,
            resultado_030303=_metadata_resultado(resultado_030303),
            integration_code="MAPA_LIBERADO_FISICO",
        )
    if modo == "financeiro":
        resultado_030303 = normalize_execution_result(
            main_030303(
                mapa=mapa,
                unidade=unidade,
                salvar=salvar,
                manter_aberto_ao_falhar=manter_aberto_ao_falhar,
            )
        )
        if not resultado_030303.ok:
            return _anexar_metadata_resultado(
                resultado_030303,
                mapa=mapa,
                passo_falha="030303",
                resultado_030303=_metadata_resultado(resultado_030303),
                resultado_financeiro=None,
            )
        resultado = normalize_execution_result(
            main_03030702(
                mapa=mapa,
                ponto_apoio=ponto_apoio,
                unidade=unidade,
                salvar=salvar,
                manter_aberto_ao_falhar=manter_aberto_ao_falhar,
            )
        )
        dados_030322 = None
        if resultado.ok:
            dados_030322 = _extrair_prestacao_030322_sessao_separada(
                mapa,
                data=data,
                unidade=unidade,
                manter_aberto_ao_falhar=manter_aberto_ao_falhar,
            )
        return _anexar_metadata_resultado(
            resultado,
            mapa=mapa,
            resultado_030303=_metadata_resultado(resultado_030303),
            dados_030322=dados_030322,
            integration_code="MAPA_LIBERADO_FINANCEIRO",
        )
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
            km_inicial=km_inicial,
            km_prev=km_prev,
            data=data,
            unidade=unidade,
            salvar=salvar,
            manter_aberto_ao_falhar=manter_aberto_ao_falhar,
        )
    else:
        return fechar_mapa_sessao_unica(
            mapa=mapa,
            ponto_apoio=ponto_apoio,
            km_atual=km_atual,
            km_inicial=km_inicial,
            km_prev=km_prev,
            data=data,
            unidade=unidade,
            salvar=salvar,
            manter_aberto_ao_falhar=manter_aberto_ao_falhar,
        )


if __name__ == "__main__":
    main()
