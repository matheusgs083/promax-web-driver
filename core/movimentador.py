# core/movimentador.py
import shutil
from pathlib import Path
from core.logger import get_logger

logger = get_logger("MOVIMENTADOR")

def mover_relatorios(origem, destino):
    caminho_origem = Path(origem)
    caminho_destino = Path(destino)

    if not caminho_origem.exists():
        logger.error(f"Erro ao mover: A origem '{origem}' não foi encontrada.")
        return

    # Garante que a pasta de destino exista
    caminho_destino.mkdir(parents=True, exist_ok=True)

    if caminho_origem.is_file():
        # Define o caminho exato do arquivo no destino
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