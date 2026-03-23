from __future__ import annotations

import time
from typing import Callable, Iterable

from selenium.common.exceptions import NoSuchWindowException, UnexpectedAlertPresentException, WebDriverException

from core.browser.driver_factory import DriverFactory
from core.execution.execution_result import ExecutionStatus, normalize_execution_result
from pages.auth.login_page import LoginPage


SESSION_ERROR_TOKENS = (
    "sessão inválida",
    "unable to get browser",
    "no such window",
    "timed out",
    "timeout",
    "is not a valid json object",
    "max retries exceeded",
    "10061",
    "10054",
    "connection refused",
    "invalid session id",
    "target window already closed",
    "disconnected",
    "chrome not reachable",
)


def iniciar_sessao_padrao(logger, settings, nome_unidade):
    if not settings.promax_user or not settings.promax_pass:
        raise ValueError("PROMAX_USER e/ou PROMAX_PASS não definidos no .env")

    driver = DriverFactory.get_driver()
    driver.maximize_window()

    login_page = LoginPage(driver)
    menu_page = login_page.fazer_login(
        settings.promax_user,
        settings.promax_pass,
        nome_unidade=nome_unidade,
    )

    logger.info("Sessão iniciada com sucesso.")
    return driver, menu_page


def encerrar_driver(driver) -> None:
    if not driver:
        return

    try:
        driver.quit()
    except Exception:
        pass


def executar_tarefa_com_retry(
    nome_tarefa,
    funcao_logica,
    *,
    logger,
    iniciar_sessao,
    tentativas=3,
    espera_segundos=3,
    erro_critico_tokens: Iterable[str] = SESSION_ERROR_TOKENS,
):
    for tentativa in range(1, tentativas + 1):
        try:
            logger.info(f"--- Executando: {nome_tarefa} (Tentativa {tentativa}/{tentativas}) ---")

            resultado = normalize_execution_result(
                funcao_logica(),
                success_message=f"{nome_tarefa} concluída com sucesso",
                failure_message=f"{nome_tarefa} retornou falha sem detalhamento",
            )

            if getattr(resultado, "ok", False):
                logger.info(f"Status: {nome_tarefa} CONCLUÍDA. Detalhe: {resultado.message}")
                return resultado

            logger.warning(
                f"{nome_tarefa} retornou status '{resultado.status.value}'. "
                f"Detalhe: {resultado.message}"
            )

            if resultado.status is ExecutionStatus.PARTIAL_SUCCESS:
                logger.info(
                    f"{nome_tarefa} terminou com sucesso parcial. "
                    "Retentativa ampla desabilitada para evitar reprocessar itens ja concluidos."
                )
                return resultado

            if tentativa < tentativas and getattr(resultado, "should_retry", False):
                logger.warning(
                    f"Nova tentativa agendada para {nome_tarefa} em {espera_segundos}s "
                    f"por retorno de execução não conclusivo."
                )
                time.sleep(espera_segundos)
                continue

            raise RuntimeError(f"{nome_tarefa} finalizou com status '{resultado.status.value}': {resultado.message}")

        except (UnexpectedAlertPresentException, NoSuchWindowException, WebDriverException) as e:
            msg_erro = str(e)
            logger.warning(f"Falha na {nome_tarefa}: {msg_erro}")

            msg_erro_lower = msg_erro.lower()
            eh_erro_critico = any(txt in msg_erro_lower for txt in erro_critico_tokens)

            if eh_erro_critico and tentativa < tentativas:
                logger.warning("Detecção de queda de sessão. Iniciando protocolo de re-login...")
                iniciar_sessao()
            else:
                logger.error(f"Erro irrecuperável na {nome_tarefa}.")
                raise

        except Exception as e:
            msg_erro = str(e)
            msg_erro_lower = msg_erro.lower()
            logger.exception(f"Falha na {nome_tarefa}: {msg_erro}")

            eh_erro_critico = any(txt in msg_erro_lower for txt in erro_critico_tokens)

            if tentativa < tentativas:
                if eh_erro_critico:
                    logger.warning("Detecção de queda de sessão. Iniciando protocolo de re-login...")
                    iniciar_sessao()
                else:
                    logger.warning(
                        f"Erro não crítico na {nome_tarefa}. Aguardando {espera_segundos}s para nova tentativa..."
                    )
                    time.sleep(espera_segundos)
                continue

            logger.error(f"Erro irrecuperável na {nome_tarefa} após {tentativas} tentativas.")
            raise

