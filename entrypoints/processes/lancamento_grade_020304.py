import json
import time
from pathlib import Path

from core.config.settings import get_settings
from core.execution.entrypoint_helpers import encerrar_driver, iniciar_sessao_padrao
from core.execution.execution_result import ExecutionResult, ExecutionStatus
from core.observability.logger import get_logger
from pages.processes.processo_020301_grade_020304_page import Processo020301Grade020304Page

logger = get_logger("PROCESSO_020301")
settings = get_settings()


def main(arquivo=None, unidade=None, job_id=""):
    driver = resultado = None
    try:
        dados = json.loads(Path(str(arquivo)).read_text(encoding="utf-8-sig"))
        if not isinstance(dados, dict):
            raise ValueError("O arquivo de lançamento deve conter um objeto JSON.")
        Processo020301Grade020304Page.normalizar(dados.get("grade"), dados.get("itens") or [])
        driver, menu = iniciar_sessao_padrao(logger, settings, str(unidade or settings.unidade_pedidos).strip().upper())
        janela = menu.acessar_rotina("020301")
        resultado = Processo020301Grade020304Page(janela.driver, janela.handle_menu).lancar(**dados)
        if isinstance(resultado.metadata, dict): resultado.metadata["job_id"] = str(job_id or "")
        return resultado
    except ValueError as exc:
        return ExecutionResult(status=ExecutionStatus.BUSINESS_FAILURE, message=str(exc), retry=False)
    except Exception as exc:
        return ExecutionResult(status=ExecutionStatus.TECHNICAL_FAILURE, message=f"Falha na rotina 02.03.01: {exc}")
    finally:
        time.sleep(.3)
        if not (resultado and not resultado.ok): encerrar_driver(driver)
