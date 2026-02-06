import pyautogui
import time
import os

from core.logger import get_logger
logger = get_logger(__name__)

def validar_elemento(nome_imagem, timeout=30, confidence=0.8, pasta_data="data"):
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', pasta_data))
    caminho_completo = os.path.join(base_path, nome_imagem)

    if not os.path.exists(caminho_completo):
        logger.error("Arquivo de imagem não encontrado: %s", caminho_completo)
        return None

    logger.info("Buscando por: %s (Timeout: %ss)", nome_imagem, timeout)

    tempo_inicial = time.time()
    while time.time() - tempo_inicial < timeout:
        try:
            posicao = pyautogui.locateOnScreen(caminho_completo, confidence=confidence)
            if posicao:
                logger.info("Elemento '%s' encontrado!", nome_imagem)
                return posicao
        except Exception as e:
            # pyautogui pode falhar pontualmente; loga em debug pra não poluir
            logger.debug("Falha ao localizar '%s' na tela: %s", nome_imagem, e)

        time.sleep(1)

    logger.warning("Elemento '%s' não encontrado após %ss.", nome_imagem, timeout)
    return None
