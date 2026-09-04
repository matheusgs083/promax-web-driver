from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import dotenv
import pandas as pd

from core.config.settings import get_settings
from core.execution.entrypoint_helpers import encerrar_driver, iniciar_sessao_padrao
from core.observability.logger import get_logger
from core.services.log_condicao_service import extrair_logs_lote_nbs

dotenv.load_dotenv()
logger = get_logger("EXTRAIR_LOGS_LOTE")
settings = get_settings()


def executar_extracao(
    lista_nbs: list[str | int],
    mes_ano: str,
    output_path: str | Path | None = None,
):
    logger.info("=== INICIANDO EXECUÇÃO DE EXTRAÇÃO DE LOGS (ROTINA 01050701 - PW01060P) ===")
    logger.info(f"NBs para consultar: {len(lista_nbs)} | Período: {mes_ano}")

    driver = None
    try:
        # Inicia a sessão padrão do Promax no Selenium
        driver, menu_page = iniciar_sessao_padrao(logger, settings, settings.unidade_lote_condicao)

        # Acessa a rotina 01050701 no Promax
        logger.info("Acessando a rotina 01050701 no menu do Promax...")
        janela = menu_page.acessar_rotina("01050701")
        driver_ativo = getattr(janela, "driver", driver) or driver

        logger.info("Rotina 01050701 aberta com sucesso no Edge IE Mode.")

        # Executa a extração em lote dos NBs diretamente via sessão ativa do navegador
        df_resultado = extrair_logs_lote_nbs(
            driver=driver_ativo,
            lista_nbs=lista_nbs,
            mes_ano=mes_ano,
        )

        if output_path is None:
            data_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = settings.download_dir
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"logs_condicao_nbs_{data_str}.xlsx"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not df_resultado.empty:
            df_resultado.to_excel(output_path, index=False)
            logger.info(f"=== SUCESSO! Relatório salvo em: {output_path} (Total: {len(df_resultado)} registros) ===")
        else:
            logger.warning("Nenhum log encontrado para os NBs especificados.")

        return df_resultado

    finally:
        encerrar_driver(driver)


def main():
    parser = argparse.ArgumentParser(description="Extração de Logs por NB via Rotina 01050701 (PW01060P)")
    parser.add_argument("--nbs", nargs="+", required=True, help="Lista de NBs para consultar (ex: --nbs 16883 16884)")
    parser.add_argument("--mes-ano", required=True, help="Mês e Ano para filtrar (ex: --mes-ano 09/2026)")
    parser.add_argument("--output", required=False, help="Caminho do arquivo Excel de saída (.xlsx)")

    args = parser.parse_args()
    executar_extracao(
        lista_nbs=args.nbs,
        mes_ano=args.mes_ano,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
