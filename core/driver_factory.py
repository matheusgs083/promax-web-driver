import os
import time
from selenium import webdriver
from selenium.webdriver.ie.service import Service as IEService
from selenium.webdriver.ie.options import Options as IEOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.microsoft import IEDriverManager
import dotenv

dotenv.load_dotenv()

# --- FUNÇÃO 1: CORE (Configuração do Navegador) ---
def abrir_ie_driver():
    ie_options = IEOptions()
    
    # Configurações para Windows 11 / Modo IE
    ie_options.add_additional_option("ie.edgechromium", True)
    ie_options.add_additional_option("ie.edgepath", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    
    ie_options.attach_to_edge_chrome = False 
    ie_options.force_create_process_api = True 
    ie_options.ensure_clean_session = False  # Mantém dados de navegação
    ie_options.ignore_protected_mode_settings = True
    ie_options.ignore_zoom_level = True
    ie_options.require_window_focus = True
    ie_options.page_load_strategy = "none" # Evita travar no carregamento lento

    caminho_local = os.getenv("DRIVER_PATH")

    # Prioriza o driver local conforme solicitado
    if os.path.exists(caminho_local):
        try:
            print(f"Iniciando com driver local: {caminho_local}")
            service = IEService(executable_path=caminho_local)
            return webdriver.Ie(service=service, options=ie_options)
        except Exception as e:
            print(f"Falha ao usar driver local: {e}")

    # Fallback para driver da web
    print("Tentando baixar driver automaticamente...")
    service_web = IEService(IEDriverManager().install())
    return webdriver.Ie(service=service_web, options=ie_options)