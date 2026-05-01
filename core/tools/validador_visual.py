import os
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

from core.config.project_paths import DATA_DIR
from core.config.project_paths import LOGS_DIR
from core.observability.logger import get_logger
from core.tools.windows_display import ensure_windows_dpi_aware

ensure_windows_dpi_aware()

import pyautogui

logger = get_logger(__name__)
VISUAL_DEBUG_DIR = LOGS_DIR / "visual_debug"


def _gerar_confidences(confidence: float) -> list[float]:
    candidatos = [confidence, confidence - 0.05, confidence - 0.10]
    normalizados = []
    for valor in candidatos:
        valor = round(max(0.6, min(0.99, valor)), 2)
        if valor not in normalizados:
            normalizados.append(valor)
    return normalizados


def _obter_tamanho_template(caminho_completo: str) -> tuple[int, int] | None:
    try:
        with Image.open(caminho_completo) as imagem:
            return imagem.size
    except Exception as exc:
        logger.debug("Falha ao ler tamanho do template '%s': %s", caminho_completo, exc)
        return None


def _salvar_screenshot_debug(nome_imagem: str) -> Path | None:
    try:
        VISUAL_DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho_saida = VISUAL_DEBUG_DIR / f"{timestamp}_{Path(nome_imagem).stem}_debug.png"
        pyautogui.screenshot(str(caminho_saida))
        return caminho_saida
    except Exception as exc:
        logger.warning("Falha ao salvar screenshot de debug para '%s': %s", nome_imagem, exc)
        return None


def validar_elemento(nome_imagem, timeout=30, confidence=0.8, pasta_data="data"):
    base_path = DATA_DIR if pasta_data == "data" else os.path.abspath(pasta_data)
    caminho_completo = os.path.join(str(base_path), nome_imagem)

    if not os.path.exists(caminho_completo):
        logger.error("Arquivo de imagem não encontrado: %s", caminho_completo)
        return None

    template_size = _obter_tamanho_template(caminho_completo)
    screen_size = pyautogui.size()
    confidence_levels = _gerar_confidences(confidence)

    logger.info(
        "Buscando por: %s (Timeout: %ss, tela=%sx%s, template=%s, confidences=%s)",
        nome_imagem,
        timeout,
        screen_size.width,
        screen_size.height,
        template_size,
        confidence_levels,
    )

    tempo_inicial = time.time()
    while time.time() - tempo_inicial < timeout:
        for confidence_atual in confidence_levels:
            try:
                posicao = pyautogui.locateOnScreen(
                    caminho_completo,
                    confidence=confidence_atual,
                    grayscale=True,
                )
                if posicao:
                    logger.info(
                        "Elemento '%s' encontrado com confidence=%s!",
                        nome_imagem,
                        confidence_atual,
                    )
                    return posicao
            except Exception as exc:
                logger.debug(
                    "Falha ao localizar '%s' na tela com confidence=%s: %s",
                    nome_imagem,
                    confidence_atual,
                    exc,
                )

        time.sleep(1)

    screenshot_debug = _salvar_screenshot_debug(nome_imagem)
    if screenshot_debug is not None:
        logger.warning(
            "Elemento '%s' não encontrado após %ss. Screenshot salvo em: %s",
            nome_imagem,
            timeout,
            screenshot_debug,
        )
    else:
        logger.warning("Elemento '%s' não encontrado após %ss.", nome_imagem, timeout)
    return None
