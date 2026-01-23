import os
import sys
import time
import dotenv
import pyautogui
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Ajuste do path para encontrar o pacote core
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.driver_factory import abrir_ie_driver
import scripts.limpar_alertas as limpar_alertas
import core.validador_visual as validador_visual

dotenv.load_dotenv()

def fazer_login_promax(driver, usuario, senha):
    """Executa a rotina de login no sistema AmBev Promax."""
    try:
        driver.get("http://paubrasil.promaxcloud.com.br/pw/")
        wait = WebDriverWait(driver, 5)

        print("Aguardando carregamento e tratando janelas...")
        
        # Foco na janela correta para evitar tela branca no modo IE
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

        # Primeiro clique
        btn_confirma.click()
        limpar_alertas.limpar_alertas(driver) # Chamada corrigida usando o módulo

        # Segundo clique
        time.sleep(2)
        try:
            btn_confirma = driver.find_element(By.NAME, "cmdConfirma")
            btn_confirma.click()
        except:
            print("Segunda confirmação não necessária.")

        # Limpeza robusta pós-login (7 tentativas conforme seu código)
        limpar_alertas.limpar_alertas(driver, tentativas=7)

        print("Login no Promax concluído!")
        return True

    except Exception as e:
        print(f"Erro no fluxo de login: {e}")
        return False

if __name__ == "__main__":
    PROMAX_USER = os.getenv("PROMAX_USER")
    PROMAX_PASS = os.getenv("PROMAX_PASS")
    
    driver = abrir_ie_driver()
    driver.maximize_window()

    if fazer_login_promax(driver, PROMAX_USER, PROMAX_PASS):
        # Validador Visual Geral
        # Mudamos de 'validar_elemento' para o nome que você definiu no seu arquivo visual
        if validador_visual.validar_elemento("validacaoLogin.png", timeout=15):
            print("Sucesso: Login confirmado.")
        else:
            print("Alerta: Login processado, mas confirmação visual falhou.")

    time.sleep(5) 
    driver.quit()