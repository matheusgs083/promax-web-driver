from core.config.settings import get_settings
from core.execution.entrypoint_helpers import encerrar_driver, iniciar_sessao_padrao
from core.observability.logger import get_logger
from pages.reports.relatorio_020220_page import Relatorio020220Page


logger = get_logger("TESTE_DOWNLOAD_HTTP_020220")
settings = get_settings()


def main():
    driver = None
    page = None
    try:
        driver, menu = iniciar_sessao_padrao(
            logger,
            settings,
            settings.unidade_relatorios,
        )
        janela = menu.acessar_rotina("020220")
        page = Relatorio020220Page(janela.driver, janela.handle_menu)
        page.subpasta_download = "teste_download_http_020220"
        resultado = page.gerar_relatorio(
            unidade=["3610006"],
            opcao_rel="01",
            mercadoria_todos=False,
            mercadoria_garrafeira=True,
            mercadoria_vasilhame=True,
            selecao_comodatos="T",
            nome_arquivo="teste_http_020220_nomeUnidade020220",
        )
        logger.info("Resultado do teste HTTP 020220: %s", resultado)
        print("RESULTADO_TESTE_HTTP=", resultado)
        return resultado
    finally:
        try:
            if page is not None:
                page.fechar_e_voltar()
        finally:
            encerrar_driver(driver)


if __name__ == "__main__":
    main()
