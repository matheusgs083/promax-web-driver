# core/movimentador.py
import shutil
import os
from pathlib import Path
from core.logger import get_logger

logger = get_logger("MOVIMENTADOR")

def mover_relatorios(origem, destino):
    caminho_origem = Path(origem)
    caminho_destino = Path(destino)

    # --- ALTERAÇÃO AQUI ---
    # Se a origem não existe, apenas ignora silenciosamente. 
    # Isso evita erros quando você roda apenas uma parte das rotinas.
    if not caminho_origem.exists():
        logger.debug(f"Tarefa de movimentação ignorada: '{origem}' não encontrada (rotina provavelmente não executada).")
        return

    # Se a origem for uma pasta, mas estiver vazia, também não faz sentido continuar
    if caminho_origem.is_dir() and not any(caminho_origem.iterdir()):
        logger.debug(f"Pasta de origem '{origem}' está vazia. Nada para mover.")
        return
    # -----------------------

    # Garante que a pasta de destino exista
    caminho_destino.mkdir(parents=True, exist_ok=True)

    if caminho_origem.is_file():
        destino_final = caminho_destino / caminho_origem.name
        
        if destino_final.exists():
            logger.info(f"Arquivo '{destino_final.name}' já existe no destino. Substituindo...")
            destino_final.unlink()
            
        logger.info(f"Movendo arquivo '{caminho_origem.name}' para '{destino}'...")
        shutil.move(str(caminho_origem), str(destino_final))
        
    elif caminho_origem.is_dir():
        logger.info(f"Movendo e substituindo conteúdo da pasta '{caminho_origem.name}' para '{destino}'...")
        
        for item in caminho_origem.iterdir():
            if item.is_file():
                destino_final = caminho_destino / item.name
                
                if destino_final.exists():
                    logger.info(f"Substituindo '{destino_final.name}' no destino...")
                    destino_final.unlink()
                    
                shutil.move(str(item), str(destino_final))