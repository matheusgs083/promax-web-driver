import pyautogui
import time
import os

from core.logger import get_logger
logger = get_logger(__name__)

from .validador_visual import validar_elemento


def tratar_confirmacao_sobrescrever(timeout=6):
    box_sim = validar_elemento("substituirArquivo.png", timeout=timeout)
    if box_sim:
        pyautogui.click(pyautogui.center(box_sim))
        time.sleep(0.6)
        logger.info("Confirmação de sobrescrever detectada e clicada (Sim).")
        return True
    return False


def salvar_arquivo_visual(diretorio_destino, nome_arquivo_final):
    logger.info("--- INICIANDO SALVAMENTO VISUAL (AJUSTADO) ---")

    box_btn = validar_elemento("botaoDownload.png", timeout=10)
    if box_btn:
        x_setinha = box_btn.left + box_btn.width - 15
        y_centro = box_btn.top + (box_btn.height / 2)

        logger.info("Clicando na setinha do botão Salvar...")
        pyautogui.click(x_setinha, y_centro)
        time.sleep(1)
    else:
        logger.error("Botão de download não apareceu.")
        return False

    box_menu = validar_elemento("salvarComo.png", timeout=5)
    if box_menu:
        time.sleep(0.5)
        pyautogui.click(pyautogui.center(box_menu))
        logger.info("Opção 'Salvar como' clicada via imagem.")
    else:
        logger.warning("Menu visual não achado. Tentando atalho 'A' + Enter...")
        pyautogui.press('a')
        pyautogui.press('enter')

    logger.info("Aguardando janela do Windows...")
    time.sleep(2.5)

    box_dir = validar_elemento("mudarDiretorio.png", timeout=5)
    if box_dir:
        pyautogui.click(pyautogui.center(box_dir))
        time.sleep(0.5)
        pyautogui.write(diretorio_destino, interval=0.01)
        pyautogui.press('enter')
        time.sleep(1.5)
        logger.info("Diretório definido via UI (mudarDiretorio.png).")
    else:
        logger.warning("mudarDiretorio.png não encontrado. Usando Alt+D...")
        pyautogui.hotkey('alt', 'd')
        pyautogui.write(diretorio_destino)
        pyautogui.press('enter')
        time.sleep(1)

    box_nome = validar_elemento("mudarNome.png", timeout=10)
    if box_nome:
        target_x = box_nome.left + box_nome.width + 80
        target_y = box_nome.top + 10

        logger.info("Clicando no campo Nome em: X=%s, Y=%s", target_x, target_y)
        pyautogui.click(target_x, target_y)

        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.2)
        pyautogui.press('backspace')

        logger.info("Digitando nome do arquivo: %s", nome_arquivo_final)
        pyautogui.write(nome_arquivo_final, interval=0.01)
        time.sleep(1)
        pyautogui.press('enter')

        time.sleep(1)
        if tratar_confirmacao_sobrescrever(timeout=6):
            logger.info("Arquivo já existia: confirmado sobrescrever (Sim).")

        logger.info("Enter pressionado. Fluxo de salvamento concluído.")
        return True
    else:
        logger.error("Campo 'Nome/Tipo' não encontrado. Verifique se a janela abriu.")
        return False
