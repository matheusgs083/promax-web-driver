import time
import os
import shutil
import win32gui
from pathlib import Path
from core.logger import get_logger
from pywinauto import Application

logger = get_logger(__name__)

def _get_ie_notification_bar_hwnd():
    """
    Varre as janelas rapidamente via Win32 API para achar a barra amarela.
    Isso é instantâneo e impede que o Python trave tentando ler o HTML do site.
    """
    bar_hwnds = []
    
    def enum_child_cb(hwnd, _):
        try:
            # Procura especificamente pela classe da barra amarela do IE
            if win32gui.GetClassName(hwnd) == "Frame Notification Bar":
                bar_hwnds.append(hwnd)
        except Exception:
            pass
        return True

    def enum_windows_cb(hwnd, _):
        try:
            class_name = win32gui.GetClassName(hwnd)
            # O IE Mode roda dentro da estrutura do Edge ou IEFrame
            if class_name in ["Chrome_WidgetWin_1", "IEFrame"]:
                win32gui.EnumChildWindows(hwnd, enum_child_cb, None)
        except Exception:
            pass
        return True

    # Executa a varredura
    win32gui.EnumWindows(enum_windows_cb, None)
    
    # Retorna o identificador da barra (se encontrada)
    return bar_hwnds[0] if bar_hwnds else None


def salvar_arquivo_visual(diretorio_destino, nome_arquivo_final):
    logger.info("--- INICIANDO SALVAMENTO OTIMIZADO (SNIPER API WIN32) ---")
    
    # =========================================================================
    # 1. MAPEAMENTO DE PASTAS E SNAPSHOT INICIAL
    # =========================================================================
    pasta_downloads = Path(os.path.expanduser("~")) / "Downloads"
    pasta_destino = Path(diretorio_destino)
    
    pasta_downloads.mkdir(parents=True, exist_ok=True)
    pasta_destino.mkdir(parents=True, exist_ok=True)

    arquivos_antes = set(pasta_downloads.iterdir())

    # =========================================================================
    # 2. CAÇADOR DA BARRA AMARELA DO IE (ANTI-TRAVAMENTO)
    # =========================================================================
    logger.info("Aguardando a barra amarela do IE (Busca ultra-rápida nativa)...")
    tempo_limite_btn = time.time() + 120 # Timeout de 2 minutos
    clicou_salvar = False
    
    while time.time() < tempo_limite_btn and not clicou_salvar:
        # Pega a "identidade" exata apenas da barra amarela
        hwnd_barra = _get_ie_notification_bar_hwnd()
        
        if hwnd_barra:
            try:
                # Conecta o robô APENAS na barra amarela (Ignora o relatório pesado)
                app = Application(backend="uia").connect(handle=hwnd_barra)
                barra = app.window(handle=hwnd_barra)
                
                # Procura o botão Salvar DENTRO da barra
                btn_salvar = barra.child_window(title_re=".*Salvar.*", control_type="SplitButton")
                if btn_salvar.exists(timeout=1):
                    btn_salvar.invoke() # Clica internamente via código
                    logger.info("✅ Botão Salvar (SplitButton) acionado em 2º plano!")
                    clicou_salvar = True
                    break
                
                # Caso seja um botão normal sem a setinha
                btn_salvar_simples = barra.child_window(title_re=".*Salvar.*", control_type="Button")
                if btn_salvar_simples.exists(timeout=1):
                    btn_salvar_simples.invoke()
                    logger.info("✅ Botão Salvar (Button) acionado em 2º plano!")
                    clicou_salvar = True
                    break
            except Exception as e:
                logger.debug(f"A barra apareceu, aguardando botão ficar clicável...")
                
        time.sleep(1) # Espera 1 segundo e tenta de novo

    if not clicou_salvar:
        logger.error("Timeout Crítico: A barra de download do IE não apareceu após 2 minutos.")
        return False, "Barra de download nativa não apareceu"
        
    # Dá 2 segundos de respiro pro Windows criar o arquivo temporário na pasta
    time.sleep(2)

    # =========================================================================
    # 3. VIGIAR A PASTA, MOVER E CONVERTER PARA .CSV
    # =========================================================================
    
    # Garante que o arquivo final sairá como .csv, matando o maldito .inf
    if not nome_arquivo_final.lower().endswith('.csv'):
        nome_arquivo_final += '.csv'
        
    caminho_final = pasta_destino / nome_arquivo_final
    extensoes_ignoradas = ['.tmp', '.crdownload', '.part', '.partial']
        
    tempo_limite = time.time() + 720
    logger.info(f"Aguardando arquivo novo na pasta nativa de Downloads...")
    
    while time.time() < tempo_limite:
        arquivos_agora = set(pasta_downloads.iterdir())
        novos_arquivos = arquivos_agora - arquivos_antes
        
        for arquivo in novos_arquivos:
            extensao_atual = arquivo.suffix.lower()
            
            if extensao_atual not in extensoes_ignoradas:
                try:
                    if caminho_final.exists():
                        logger.warning(f"Arquivo já existe no destino. Removendo antigo: {caminho_final}")
                        caminho_final.unlink()
                        
                    # Move e renomeia (Removendo o .inf e garantindo o .csv final)
                    shutil.move(str(arquivo), str(caminho_final))
                    logger.info(f"Sucesso! Relatório capturado para: {caminho_final}")
                    
                    return True, "Download concluído com sucesso"
                    
                except PermissionError:
                    logger.debug("Arquivo bloqueado (ainda baixando). Aguardando liberação do SO...")
                    time.sleep(1)
                    continue
                    
        time.sleep(1)
        
    logger.error("Timeout: Nenhum arquivo novo concluído apareceu na pasta Downloads após 720s.")
    return False, "Timeout na espera da rede/download do arquivo"