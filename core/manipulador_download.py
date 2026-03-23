import pyautogui
import time
import os
import shutil
import re
from pathlib import Path
from core.logger import get_logger
from core.settings import get_settings
from .validador_visual import validar_elemento

logger = get_logger(__name__)


def _arquivo_pronto_para_mover(arquivo: Path) -> bool:
    if not arquivo.is_file():
        return False
    if arquivo.stat().st_size <= 0:
        return False
    try:
        with arquivo.open("rb"):
            return True
    except PermissionError:
        return False


def _validar_arquivo_final(caminho_final: Path) -> tuple[bool, str]:
    if not caminho_final.exists():
        return False, "Arquivo final não existe após a movimentação"
    if not caminho_final.is_file():
        return False, "Caminho final não é um arquivo"
    if caminho_final.suffix.lower() != ".csv":
        return False, f"Extensão final inválida: {caminho_final.suffix}"
    tamanho = caminho_final.stat().st_size
    if tamanho <= 0:
        return False, "Arquivo final foi gerado vazio"
    return True, f"Download validado com sucesso ({tamanho} bytes)"

def salvar_arquivo_visual(diretorio_destino, nome_arquivo_final):
    logger.info("--- INICIANDO SALVAMENTO OTIMIZADO (WATCHER DE PASTA) ---")
    
    # =========================================================================
    # 1. MAPEAMENTO DE PASTAS E SNAPSHOT INICIAL
    # =========================================================================
    # CORREÇÃO 1: Forma correta de pegar o path e não gerar erro de 'str'
    settings = get_settings()
    pasta_downloads = Path.home() / "Downloads"
    pasta_destino = Path(diretorio_destino) if diretorio_destino else settings.download_dir
    
    # Garante que as pastas de trabalho existem
    pasta_destino.mkdir(parents=True, exist_ok=True)
    pasta_downloads.mkdir(parents=True, exist_ok=True)

    logger.info(f"Watcher de origem configurado em: {pasta_downloads}")
    logger.info(f"Destino final configurado em: {pasta_destino}")

    # CORREÇÃO 2 (WinError 3): Limpar caracteres proibidos do Windows no nome do arquivo (ex: / de datas)
    nome_limpo = re.sub(r'[\\/*?:"<>|]', "_", nome_arquivo_final)
    
    if not nome_limpo.lower().endswith('.csv'):
        nome_limpo += '.csv'
        
    caminho_final = pasta_destino / nome_limpo

    # Tira uma "foto" dos arquivos que já estão lá
    arquivos_antes = set(pasta_downloads.iterdir())

    # =========================================================================
    # 2. ESPERA INTELIGENTE E DISPARO DO DOWNLOAD (BARRA DO IE)
    # =========================================================================
    logger.info("Aguardando o servidor processar e a barra do IE aparecer...")
    box_btn = validar_elemento("botaoDownload.png", timeout=120, confidence=0.8)
    
    if box_btn:
        x, y = pyautogui.center(box_btn)
        logger.info("Barra do IE detectada! Movendo o mouse para clicar...")
        pyautogui.moveTo(x, y, duration=0.3)
        time.sleep(0.2)
        pyautogui.click()
        
        # O Alt+S mantido, mas cuidado se ele estiver tirando o foco do IE em outras rotinas
        time.sleep(0.5)
        pyautogui.hotkey('alt', 's')
    else:
        logger.error("Timeout Crítico: A barra de download do IE não apareceu após 2 minutos.")
        return False, "Barra de download nativa não apareceu"
        
    time.sleep(1)

    # =========================================================================
    # 3. VIGIAR A PASTA, MOVER E SALVAR
    # =========================================================================
    timeout_segundos = 500
    tempo_limite = time.time() + timeout_segundos
    logger.info(f"Aguardando arquivo novo em: {pasta_downloads}")
    
    # Adicionamos .ini para ignorar o desktop.ini que o Windows cria do nada
    extensoes_ignoradas = {'.tmp', '.crdownload', '.part', '.partial', '.ini'}
    
    while time.time() < tempo_limite:
        arquivos_agora = set(pasta_downloads.iterdir())
        novos_arquivos = arquivos_agora - arquivos_antes
        
        for arquivo in novos_arquivos:
            # Ignora se for uma pasta temporária em vez de um arquivo
            if not arquivo.is_file():
                continue

            extensao_atual = arquivo.suffix.lower()
            
            # Se não for um arquivo ignorado, tenta interagir
            if extensao_atual not in extensoes_ignoradas:
                try:
                    # TRUQUE DE MESTRE: Tenta renomear o arquivo para ele mesmo. 
                    # Se o IE ainda estiver baixando, o Windows bloqueia e cai no PermissionError.
                    if not _arquivo_pronto_para_mover(arquivo):
                        continue
                    
                    if caminho_final.exists():
                        logger.warning(f"Arquivo já existe no destino. Removendo antigo: {caminho_final}")
                        caminho_final.unlink()
                        
                    shutil.move(str(arquivo), str(caminho_final))
                    ok_validacao, motivo_validacao = _validar_arquivo_final(caminho_final)
                    if not ok_validacao:
                        logger.error(f"Arquivo movido, mas inválido: {motivo_validacao}")
                        return False, motivo_validacao

                    logger.info(f"Sucesso! Relatório capturado e salvo em: {caminho_final}")
                    return True, motivo_validacao
                    
                except PermissionError:
                    logger.debug("Arquivo bloqueado (ainda baixando). Aguardando liberação do SO...")
                except Exception as e:
                    logger.error(f"Erro inesperado ao mover o arquivo: {e}")
                    
        # Pausa antes de checar a pasta de novo
        time.sleep(1)
        
    logger.error(f"Timeout: Nenhum arquivo novo apareceu após {timeout_segundos}s.")
    return False, "Timeout na espera da rede/download do arquivo"
