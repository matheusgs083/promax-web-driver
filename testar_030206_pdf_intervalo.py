from datetime import datetime

import dotenv

from core.config.settings import get_settings
from core.execution.entrypoint_helpers import encerrar_driver, iniciar_sessao_padrao
from core.observability.logger import get_logger
from pages.reports.relatorio_030206_page import Relatorio030206Page


dotenv.load_dotenv()

logger = get_logger("TESTE_030206")
settings = get_settings()

# Use None para todas as revendas ou uma lista para filtrar, ex: ["0640001"].
unidades_alvo = ["2210004"]


def main():
    driver = None
    try:
        driver, menu_page = iniciar_sessao_padrao(
            logger,
            settings,
            settings.unidade_relatorios,
        )

        hoje = datetime.now()
        data_inicial = "01/06/2026"
        data_final = hoje.strftime("%d/%m/%Y")

        logger.info(
            "Testando PDF direto 030206: banco=237, periodo=%s a %s",
            data_inicial,
            data_final,
        )

        janela = menu_page.acessar_rotina("030206")
        page = Relatorio030206Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "030206_teste"
        resultado = page.testar_pdf_intervalo_direto(
            unidade=unidades_alvo,
            banco="237",
            armazem="01",
            emissao_inicial=data_inicial,
            emissao_final=data_final,
            nome_arquivo=f"030206_teste_pdf_237_01-06-2026_a_{hoje.strftime('%d-%m-%Y')}.pdf",
        )
        logger.info("Resultado teste 030206: %s", resultado)
        print(resultado)
        page.fechar_e_voltar()
        return resultado
    finally:
        encerrar_driver(driver)


if __name__ == "__main__":
    main()
