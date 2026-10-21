import argparse
import json
import time
from pathlib import Path

import dotenv

from core.config.settings import get_settings
from core.execution.entrypoint_helpers import encerrar_driver, iniciar_sessao_padrao
from core.execution.execution_result import ExecutionResult, ExecutionStatus
from core.observability.logger import get_logger
from pages.processes.processo_020105_page import Processo020105Page


dotenv.load_dotenv()
logger = get_logger("PROCESSO_020105")
settings = get_settings()


def _parse_args():
    parser = argparse.ArgumentParser(description="Lanca uma grade de inventario na rotina 020105.")
    parser.add_argument("--arquivo", required=True, help="Arquivo JSON com armazem, deposito, data_movimento e itens.")
    parser.add_argument("--unidade", default=settings.unidade_pedidos)
    parser.add_argument("--nao-salvar", action="store_true", help="Valida e monta a grade, sem salvar o lancamento.")
    parser.add_argument(
        "--manter-aberto-ao-falhar",
        action="store_true",
        help="Mantem o navegador aberto apenas para depuracao manual.",
    )
    # Compatibilidade com o runner antigo, que ainda envia esta flag.
    parser.add_argument("--fechar-ao-falhar", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--job-id", default="")
    return parser.parse_args()


def _ler_lancamento(arquivo: str) -> dict:
    caminho = Path(arquivo).expanduser()
    if not caminho.is_file():
        raise ValueError(f"Arquivo de lancamento nao encontrado: {caminho}")
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON de lancamento invalido: {exc}") from exc
    if not isinstance(dados, dict):
        raise ValueError("O arquivo de lancamento deve conter um objeto JSON.")
    return dados


def main(arquivo=None, unidade=None, salvar=True, manter_aberto_ao_falhar=False, job_id=""):
    if arquivo is None:
        args = _parse_args()
        arquivo, unidade = args.arquivo, args.unidade
        salvar = not args.nao_salvar
        manter_aberto_ao_falhar = args.manter_aberto_ao_falhar
        job_id = args.job_id

    resultado = None
    driver = None
    try:
        dados = _ler_lancamento(arquivo)
        Processo020105Page.normalizar_lancamento(
            armazem=dados.get("armazem"), deposito=dados.get("deposito"),
            data_movimento=dados.get("data_movimento"), itens=dados.get("itens") or [],
        )
        driver, menu_page = iniciar_sessao_padrao(logger, settings, str(unidade or settings.unidade_pedidos).strip().upper())
        janela = menu_page.acessar_rotina("020105")
        page = Processo020105Page(janela.driver, janela.handle_menu)
        if salvar:
            logger.info("020105: iniciando lancamento arquivo=%s job_id=%s", arquivo, job_id or "-")
            resultado = page.lancar_grade(**dados)
        else:
            resultado = page.carregar_grade(
                armazem=dados.get("armazem"), deposito=dados.get("deposito"), data_movimento=dados.get("data_movimento"),
            )
            if resultado.ok:
                for item in dados.get("itens") or []:
                    resultado = page.adicionar_item(item)
                    if not resultado.ok:
                        break
        if resultado and isinstance(resultado.metadata, dict):
            resultado.metadata.setdefault("job_id", str(job_id or ""))
        if resultado:
            logger.info(
                "020105 resultado: ok=%s status=%s message=%s metadata=%s",
                resultado.ok,
                resultado.status,
                resultado.message,
                resultado.metadata,
            )
        return resultado
    except ValueError as exc:
        resultado = ExecutionResult(status=ExecutionStatus.BUSINESS_FAILURE, message=str(exc), retry=False)
        return resultado
    except Exception as exc:  # noqa: BLE001
        logger.exception("020105 excecao nao tratada")
        resultado = ExecutionResult(status=ExecutionStatus.TECHNICAL_FAILURE, message=f"Falha na rotina 020105: {exc}")
        return resultado
    finally:
        time.sleep(0.3)
        if not (manter_aberto_ao_falhar and resultado is not None and not resultado.ok):
            logger.info("020105: encerrando driver resultado=%s", getattr(resultado, "status", "sem resultado"))
            encerrar_driver(driver)


if __name__ == "__main__":
    main()
