import os
import sys
import time
import dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Ajuste do path para encontrar o pacote core
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.driver_factory import abrir_ie_driver
import core.limpar_alertas as limpar_alertas
import core.validador_visual as validador_visual

dotenv.load_dotenv()

def fazer_login_promax(driver, usuario, senha):
    """Executa a rotina de login no sistema AmBev Promax e valida o sucesso."""
    try:
        driver.get(os.getenv("PROMAX_ADDRESS"))
        wait = WebDriverWait(driver, 10) # Aumentei um pouco o tempo de espera inicial

        print("Aguardando carregamento e tratando janelas...")
        
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])

        # Lógica de Frames para sistemas legados
        try:
            campo_user = wait.until(EC.presence_of_element_located((By.NAME, "Usuario")))
        except:
            iframes = driver.find_elements(By.TAG_NAME, "frame") or driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                driver.switch_to.frame(0)
                campo_user = wait.until(EC.presence_of_element_located((By.NAME, "Usuario")))

        campo_pass = driver.find_element(By.NAME, "Senha")
        btn_confirma = driver.find_element(By.NAME, "cmdConfirma")

        print(f"Logando como: {usuario}")
        campo_user.clear()
        campo_user.send_keys(usuario)
        campo_pass.send_keys(senha)

        # Primeiro clique e limpeza de alertas iniciais
        btn_confirma.click()
        limpar_alertas.limpar_alertas(driver)

        # Segundo clique (comum no Promax para confirmar sessão)
        time.sleep(2)
        try:
            btn_confirma = driver.find_element(By.NAME, "cmdConfirma")
            btn_confirma.click()
        except:
            print("Segunda confirmação não necessária.")

        # Limpeza robusta pós-login
        limpar_alertas.limpar_alertas(driver, tentativas=7)

        # --- VALIDAÇÃO INTEGRADA ---
        print("Validando sucesso do login visualmente...")
        if validador_visual.validar_elemento("validacaoLogin.png", timeout=15):
            print("Login no Promax concluído e validado!")
            return True
        else:
            print("Erro: A imagem de validação não foi encontrada após o login.")
            return False

    except Exception as e:
        print(f"Erro no fluxo de login: {e}")
        return False

if __name__ == "__main__":
    PROMAX_USER = os.getenv("PROMAX_USER")
    PROMAX_PASS = os.getenv("PROMAX_PASS")
    
    driver = abrir_ie_driver()
    driver.maximize_window()

    # Agora a chamada fica muito mais simples:
    if fazer_login_promax(driver, PROMAX_USER, PROMAX_PASS):
        print("Prosseguindo com a automação...")
    else:
        print("Falha crítica: O login não pôde ser realizado.")

    time.sleep(5) 
    driver.quit()