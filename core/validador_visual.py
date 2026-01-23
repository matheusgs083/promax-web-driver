import pyautogui
import time
import os
import logging


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def validar_elemento(nome_imagem, timeout=30, confidence=0.8, pasta_data="data"):

    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', pasta_data))
    caminho_completo = os.path.join(base_path, nome_imagem)

    if not os.path.exists(caminho_completo):
        logging.error(f"Arquivo de imagem não encontrado: {caminho_completo}")
        return None

    logging.info(f"Buscando por: {nome_imagem} (Timeout: {timeout}s)")
    
    tempo_inicial = time.time()
    while time.time() - tempo_inicial < timeout:
        try:
            posicao = pyautogui.locateOnScreen(caminho_completo, confidence=confidence)
            if posicao:
                logging.info(f"Elemento '{nome_imagem}' encontrado!")
                return posicao
        except Exception:
            pass
        
        time.sleep(1)

    logging.warning(f"Elemento '{nome_imagem}' não encontrado após {timeout}s.")
    return None