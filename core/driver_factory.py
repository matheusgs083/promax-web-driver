from selenium import webdriver

def abrir_ie_driver():
    """
    Abre o Internet Explorer Driver (modo de compatibilidade real).
    """
    from selenium.webdriver.ie.service import Service as IEService
    from selenium.webdriver.ie.options import Options as IEOptions
    import os

    # --- CONFIGURAÇÃO HARDCODE ---
    # Coloque o caminho completo para o seu IEDriverServer.exe aqui
    # Use 'r' antes das aspas para evitar problemas com as barras invertidas do Windows
    CAMINHO_DRIVER_HARDCODE = r"C:\\caminho\\para\\seu\\IEDriverServer.exe"
    # -----------------------------

    ie_options = IEOptions()
    ie_options.ignore_protected_mode_settings = True
    ie_options.ignore_zoom_level = True
    ie_options.require_window_focus = True
    
    # 1. Tentar primeiro o caminho Hardcoded se o arquivo existir
    if os.path.exists(CAMINHO_DRIVER_HARDCODE):
        try:
            service = IEService(CAMINHO_DRIVER_HARDCODE)
            driver = webdriver.Ie(service=service, options=ie_options)
            print(f"Sucesso: Driver carregado via hardcode em: {CAMINHO_DRIVER_HARDCODE}")
            return driver
        except Exception as e:
            print(f"Falha ao carregar driver fixo: {e}")

    # 2. Fallback: Tentar baixar automaticamente se o hardcode falhar ou não existir
    print("Tentando carregar via WebDriver Manager ou Sistema...")
    try:
        try:
            from webdriver_manager.microsoft import IEDriverManager
            service = IEService(IEDriverManager().install())
            driver = webdriver.Ie(service=service, options=ie_options)
            print("Sucesso: Driver baixado automaticamente.")
            return driver
        except Exception:
            # 3. Última tentativa: Driver no PATH do sistema
            driver = webdriver.Ie(options=ie_options)
            print("Sucesso: Usando driver do PATH do sistema.")
            return driver
    except Exception as e:
        print(f"Erro crítico: {e}")
        raise