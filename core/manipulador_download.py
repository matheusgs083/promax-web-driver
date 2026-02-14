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
    logger.info("--- INICIANDO SALVAMENTO VISUAL (DIRETO NA SETINHA) ---")

    # =========================================================================
    # 1. TENTATIVA PRINCIPAL: CLICAR NA SETINHA
    # =========================================================================
    # Timeout curto (5s) para ser rápido se ela estiver visível
    box_setinha = validar_elemento("setinhaDownload.png", timeout=5)
    
    if box_setinha:
        logger.info("Imagem da setinha encontrada! Clicando no centro...")
        pyautogui.click(pyautogui.center(box_setinha))
        time.sleep(1)
    
    # =========================================================================
    # 2. PLANO B: BOTÃO GRANDE (FALLBACK)
    # =========================================================================
    else:
        logger.warning("Setinha direta não detectada. Tentando cálculo no botão 'Salvar'...")
        box_btn = validar_elemento("botaoDownload.png", timeout=10)
        
        if box_btn:
            # Cálculo percentual (90%) é mais seguro que pixels fixos (-16)
            x_setinha = box_btn.left + (box_btn.width * 0.90)
            y_centro = box_btn.top + (box_btn.height / 2)

            logger.info("Clicando na extremidade direita do botão principal...")
            pyautogui.click(x_setinha, y_centro)
            time.sleep(1)
        else:
            logger.error("ERRO: Nem a setinha nem o botão de download foram encontrados.")
            return False

    # =========================================================================
    # 3. SELEÇÃO DO MENU "SALVAR COMO"
    # =========================================================================
    box_menu = validar_elemento("salvarComo.png", timeout=10)
    if box_menu:
        time.sleep(0.5)
        pyautogui.click(pyautogui.center(box_menu))
        logger.info("Opção 'Salvar como' clicada via imagem.")
    else:
        # Tenta atalho de teclado caso a imagem falhe
        logger.warning("Menu visual não achado. Tentando atalhos de teclado...")
        pyautogui.press('down') # As vezes precisa descer para selecionar
        time.sleep(0.2)
        pyautogui.press('enter')

    logger.info("Aguardando janela do Windows...")
    time.sleep(2.5)

    # =========================================================================
    # 4. JANELA DO WINDOWS (DIRETÓRIO)
    # =========================================================================
    box_dir = validar_elemento("mudarDiretorio.png", timeout=10)
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

    # =========================================================================
    # 5. NOME DO ARQUIVO E CONFIRMAÇÃO
    # =========================================================================
    box_nome = validar_elemento("mudarNome.png", timeout=10)
    if box_nome:
        # Clica um pouco a direita do label "Nome:" para focar no input
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
        # Assume que você tem essa função auxiliar definida no seu código
        if 'tratar_confirmacao_sobrescrever' in globals() and tratar_confirmacao_sobrescrever(timeout=6):
            logger.info("Arquivo já existia: confirmado sobrescrever (Sim).")

        logger.info("Enter pressionado. Fluxo de salvamento concluído.")
        return True
    else:
        logger.error("Campo 'Nome/Tipo' não encontrado. A janela do Windows abriu?")
        return False