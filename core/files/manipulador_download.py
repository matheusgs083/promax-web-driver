import re
import shutil
import time
from pathlib import Path

import pyautogui

from core.observability.logger import get_logger
from core.tools.validador_visual import validar_elemento

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


def _houve_atividade_download(pasta_downloads: Path, arquivos_antes: set[Path]) -> bool:
    try:
        arquivos_agora = set(pasta_downloads.iterdir())
    except Exception:
        return False
    return any(arquivo not in arquivos_antes for arquivo in arquivos_agora)


def salvar_arquivo_visual(diretorio_destino, nome_arquivo_final):
    logger.info("--- INICIANDO SALVAMENTO OTIMIZADO (WATCHER DE PASTA) ---")

    pasta_downloads = Path.home() / "Downloads"
    pasta_intermediaria = Path(diretorio_destino)

    pasta_intermediaria.mkdir(parents=True, exist_ok=True)
    pasta_downloads.mkdir(parents=True, exist_ok=True)

    logger.info(f"Watcher de origem configurado em: {pasta_downloads}")
    logger.info(f"Pasta intermediaria configurada em: {pasta_intermediaria}")

    nome_limpo = re.sub(r'[\\/*?:"<>|]', "_", nome_arquivo_final)
    if not nome_limpo.lower().endswith(".csv"):
        nome_limpo += ".csv"

    caminho_final = pasta_intermediaria / nome_limpo
    arquivos_antes = set(pasta_downloads.iterdir())

    logger.info("Aguardando o servidor processar e a barra do IE aparecer...")
    box_btn = validar_elemento("botaoDownload.png", timeout=60, confidence=0.8)

    if box_btn:
        x, y = pyautogui.center(box_btn)
        logger.info("Barra do IE detectada! Movendo o mouse para clicar...")
        pyautogui.moveTo(x, y, duration=0.3)
        time.sleep(0.2)
        pyautogui.click()

        # Evita ativar duas vezes a mesma barra de download.
        tempo_limite_fallback = time.time() + 2.5
        iniciou_download = False
        while time.time() < tempo_limite_fallback:
            if _houve_atividade_download(pasta_downloads, arquivos_antes):
                iniciou_download = True
                logger.info("Atividade de download detectada após clique visual. Fallback Alt+S ignorado.")
                break
            time.sleep(0.2)

        if not iniciou_download:
            logger.info("Nenhuma atividade detectada após clique visual. Enviando Alt+S como fallback.")
            pyautogui.hotkey("alt", "s")
    else:
        logger.error("Timeout Crítico: A barra de download do IE não apareceu após 2 minutos.")
        return False, "Barra de download nativa não apareceu"

    time.sleep(1)

    timeout_segundos = 500
    tempo_limite = time.time() + timeout_segundos
    logger.info(f"Aguardando arquivo novo em: {pasta_downloads}")

    extensoes_ignoradas = {".tmp", ".crdownload", ".part", ".partial", ".ini"}

    while time.time() < tempo_limite:
        arquivos_agora = set(pasta_downloads.iterdir())
        novos_arquivos = arquivos_agora - arquivos_antes

        for arquivo in novos_arquivos:
            if not arquivo.is_file():
                continue

            extensao_atual = arquivo.suffix.lower()
            if extensao_atual in extensoes_ignoradas:
                continue

            try:
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

        time.sleep(1)

    logger.error(f"Timeout: Nenhum arquivo novo apareceu após {timeout_segundos}s.")
    return False, "Timeout na espera da rede/download do arquivo"
