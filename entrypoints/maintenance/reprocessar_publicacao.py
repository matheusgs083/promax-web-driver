from core.observability.logger import get_logger
from core.services.publication_service import reprocessar_publicacoes_pendentes


logger = get_logger("MAIN_REPROCESSAR_PUBLICACAO")


def main():
    logger.info("=== INICIANDO REPROCESSAMENTO DE PUBLICACOES PENDENTES ===")
    return reprocessar_publicacoes_pendentes(logger=logger)


if __name__ == "__main__":
    main()




