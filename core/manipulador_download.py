import pyautogui
import time
import os
from core.logger import get_logger

logger = get_logger(__name__)
from .validador_visual import validar_elemento

def tratar_confirmacao_sobrescrever(timeout=6):
    """
    Verifica se apareceu a janela de 'Substituir arquivo existente' e clica em Sim.
    """
    # Tenta achar o botão "Sim" ou o texto de confirmação
    # Recomendo ter um print apenas do botão "Sim" destacado
    box_sim = validar_elemento("substituirArquivo.png", timeout=timeout, confidence=0.9)
    
    if box_sim:
        logger.warning("Arquivo já existe. Sobrescrevendo...")
        x, y = pyautogui.center(box_sim)
        pyautogui.click(x, y)
        time.sleep(1)
        return True
    return False

def salvar_arquivo_visual(diretorio_destino, nome_arquivo_final):
    logger.info("--- INICIANDO SALVAMENTO VISUAL OTIMIZADO ---")

    # =========================================================================
    # 1. CLICAR NA SETINHA (BAIXAR)
    # =========================================================================
    # Tenta localizar a setinha com 90% de precisão (ignora pequenas mudanças de pixel)
    # Requer: pip install opencv-python
    box_setinha = validar_elemento("setinhaDownload.png", timeout=5, confidence=0.9)
    
    if box_setinha:
        logger.info("Setinha detectada. Movendo e clicando...")
        x, y = pyautogui.center(box_setinha)
        # Move suavemente em 0.5s para garantir que o sistema detecte o hover
        pyautogui.moveTo(x, y, duration=0.5)
        pyautogui.click()
        time.sleep(1)
    
    else:
        # --- FALLBACK: CÁLCULO NO BOTÃO GRANDE ---
        logger.warning("Setinha não encontrada. Usando fallback no botão principal.")
        box_btn = validar_elemento("botaoDownload.png", timeout=5, confidence=0.8)
        
        if box_btn:
            # Ajuste matemático: Clicar 15 pixels a menos que a largura total (canto direito)
            # É mais seguro que porcentagem em botões pequenos
            x_setinha = (box_btn.left + box_btn.width) - 15 
            y_centro = box_btn.top + (box_btn.height / 2)

            logger.info("Clicando na borda direita do botão principal (Fallback)...")
            pyautogui.moveTo(x_setinha, y_centro, duration=0.5)
            pyautogui.click()
            time.sleep(1)
        else:
            logger.error("ERRO CRÍTICO: Nenhum botão de download encontrado.")
            return False

    # =========================================================================
    # 2. MENU "SALVAR COMO"
    # =========================================================================
    # Aqui a imagem deve ser APENAS o texto "Salvar como" destacado no menu
    box_menu = validar_elemento("salvarComo.png", timeout=5, confidence=0.9)
    
    if box_menu:
        x, y = pyautogui.center(box_menu)
        pyautogui.moveTo(x, y, duration=0.3)
        pyautogui.click()
        logger.info("Menu 'Salvar como' clicado.")
    else:
        # Fallback de teclado cego: Baixo + Enter
        logger.warning("Menu visual falhou. Tentando setas do teclado...")
        pyautogui.press('down')
        time.sleep(0.3)
        pyautogui.press('enter')

    # Espera a janela do Windows abrir
    logger.info("Aguardando diálogo do Windows...")
    time.sleep(3) 

    # =========================================================================
    # 3. JANELA DO WINDOWS - PREENCHIMENTO VIA ATALHOS (MAIS SEGURO)
    # =========================================================================
    
    # --- Definir Diretório (Alt + D foca na barra de endereço) ---
    logger.info(f"Definindo diretório: {diretorio_destino}")
    pyautogui.hotkey('alt', 'd') 
    time.sleep(0.5)
    pyautogui.write(diretorio_destino, interval=0.01)
    pyautogui.press('enter')
    
    # Tempo para o Windows processar a troca de pasta
    time.sleep(1.5) 
    
    # Clica no centro da tela (área neutra) para tirar foco da barra de endereço
    # Isso evita bugs onde o nome do arquivo é digitado na barra de endereço
    pyautogui.press('tab') 
    
    # --- Definir Nome do Arquivo (Alt + N foca no campo Nome) ---
    logger.info(f"Definindo nome: {nome_arquivo_final}")
    pyautogui.hotkey('alt', 'n')
    time.sleep(0.5)
    
    # Limpa e escreve
    pyautogui.hotkey('ctrl', 'a')
    pyautogui.press('backspace')
    pyautogui.write(nome_arquivo_final, interval=0.01)
    time.sleep(1)
    
    # --- Salvar (Enter) ---
    pyautogui.press('enter')
    time.sleep(1)

    # --- Checar Sobrescrita ---
    if tratar_confirmacao_sobrescrever():
        logger.info("Sobrescrita tratada.")
    
    logger.info("Processo de salvamento finalizado.")
    return True