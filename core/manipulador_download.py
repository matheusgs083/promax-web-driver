import pyautogui
import time
import os
import shutil
from pathlib import Path
from core.logger import get_logger
from .validador_visual import validar_elemento

logger = get_logger(__name__)

def salvar_arquivo_visual(diretorio_destino, nome_arquivo_final):
    logger.info("--- INICIANDO SALVAMENTO OTIMIZADO (WATCHER DE PASTA) ---")
    
    # =========================================================================
    # 1. MAPEAMENTO DE PASTAS E SNAPSHOT INICIAL
    # =========================================================================
    # Define a pasta padrão de downloads nativa do Windows do usuário logado
    pasta_downloads = Path(os.path.expanduser("~")) / "Downloads"
    pasta_destino = Path(diretorio_destino)
    
    # Garante que as pastas de trabalho existem
    pasta_downloads.mkdir(parents=True, exist_ok=True)
    pasta_destino.mkdir(parents=True, exist_ok=True)

    # Tira uma "foto" dos arquivos que já estão lá ANTES de clicar em baixar
    arquivos_antes = set(pasta_downloads.iterdir())

   # =========================================================================
    # 2. ESPERA INTELIGENTE E DISPARO DO DOWNLOAD (BARRA DO IE)
    # =========================================================================
    logger.info("Aguardando o servidor processar e a barra do IE aparecer...")
    
    box_btn = validar_elemento("botaoDownload.png", timeout=120, confidence=0.8)
    
    if box_btn:
        x, y = pyautogui.center(box_btn)
        logger.info("Barra do IE detectada! Movendo o mouse para clicar...")
        
        # 1. Move o mouse suavemente até o botão (dá tempo do Windows registrar o hover)
        pyautogui.moveTo(x, y, duration=0.3)
        time.sleep(0.2) # Pausa dramática
        
        # 2. Executa o clique
        pyautogui.click()
        
        # 3. BACKUP DE SEGURANÇA (Trava Dupla)
        # Se o clique do mouse for ignorado pelo Windows, o Alt+S garante a ação.
        # Se o clique funcionar, a barra some e o Alt+S será inofensivo.
        time.sleep(0.5)
        pyautogui.hotkey('alt', 's')
        
    else:
        logger.error("Timeout Crítico: A barra de download do IE não apareceu após 2 minutos.")
        return False, "Barra de download nativa não apareceu"
        
    # Dá 1 segundo de respiro pro Windows começar a criar o arquivo físico na pasta
    time.sleep(1)

    # =========================================================================
    # 3. VIGIAR A PASTA, MOVER E CONVERTER PARA .CSV
    # =========================================================================
    
    # Garante que o nome final do arquivo termine explicitamente com .csv
    if not nome_arquivo_final.lower().endswith('.csv'):
        nome_arquivo_final += '.csv'
        
    caminho_final = pasta_destino / nome_arquivo_final
    
    # Extensões temporárias criadas por navegadores enquanto o download não acaba
    extensoes_ignoradas = ['.tmp', '.crdownload', '.part', '.partial']
        
    # Dá 500 segundos de tolerância para a transferência da rede concluir
    tempo_limite = time.time() + 500
    logger.info(f"Aguardando arquivo novo em: {pasta_downloads}")
    
    while time.time() < tempo_limite:
        arquivos_agora = set(pasta_downloads.iterdir())
        novos_arquivos = arquivos_agora - arquivos_antes
        
        for arquivo in novos_arquivos:
            # Pega a extensão do arquivo que acabou de aparecer
            extensao_atual = arquivo.suffix.lower()
            
            # Se não for um arquivo temporário de download, achamos o nosso relatório (.inf, .csv, etc)
            if extensao_atual not in extensoes_ignoradas:
                try:
                    # Se já houver um arquivo com esse nome nos Relatorios, apaga (sobrescreve automático)
                    if caminho_final.exists():
                        logger.warning(f"Arquivo já existe no destino. Removendo antigo: {caminho_final}")
                        caminho_final.unlink()
                        
                    # MÁGICA AQUI: Move o arquivo original e força ele a ter o nome final com .csv
                    shutil.move(str(arquivo), str(caminho_final))
                    logger.info(f"Sucesso! Relatório capturado e convertido para: {caminho_final}")
                    
                    # RETORNO ATUALIZADO PARA O RELATÓRIO
                    return True, "Download concluído com sucesso"
                    
                except PermissionError:
                    # Se der erro de permissão, o Windows/IE ainda está gravando o arquivo no disco
                    logger.debug("Arquivo bloqueado (ainda baixando). Aguardando liberação do SO...")
                    time.sleep(1)
                    continue
                    
        # Pausa breve antes de checar a pasta de novo para não sobrecarregar o processador
        time.sleep(1)
        
    logger.error("Timeout: Nenhum arquivo novo concluído apareceu na pasta Downloads após 500s.")
    # RETORNO ATUALIZADO PARA O RELATÓRIO
    return False, "Timeout na espera da rede/download do arquivo"