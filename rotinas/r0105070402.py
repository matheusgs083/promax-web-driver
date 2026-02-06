import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import sys
import os
import dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.download import salvar_arquivo_visual
from core.validador_visual import validar_elemento



def gerar_0105070401(driver):
    print(f"\n--- ETAPA 1: PREPARAR E GERAR RELATÓRIO ---")
    
    # --- 1. APLICAR FILTROS (JS SEGURO) ---
    print("1. Selecionando filtros na tela...")
    
    js_cmd = """
    // Marca checkboxes idAS e idGeo
    var ids = ['idAS', 'idGeo'];
    for (var k = 0; k < ids.length; k++) {
        var el = document.getElementById(ids[k]);
        if (el) { 
            el.click(); 
            if (el.type == 'checkbox') { el.checked = true; }
        }
    }

    // Clica no link 'Todos' (Regex para compatibilidade IE)
    var links = document.getElementsByTagName('A');
    for (var i = 0; i < links.length; i++) {
        var texto = links[i].innerText || "";
        if (texto.replace(/^\\s+|\\s+$/g, '') == 'Todos') {
            links[i].click();
            break; 
        }
    }
    """
    try:
        driver.execute_script(js_cmd)
        time.sleep(2) # Pequena pausa para a tela atualizar visualmente
    except Exception as e:
        print(f"ERRO nos filtros: {e}")
        return False

    # --- 2. CLICAR NO BOTÃO GERAR ---
    print("2. Clicando no botão 'Gerar CSV'...")
    try:
        # Tenta via JS primeiro (mais garantido em sistemas legados)
        driver.execute_script("document.getElementById('btnGerarCSV').click();")
    except:
        # Se falhar, tenta o clique nativo do Selenium
        try:
            driver.find_element(By.ID, "btnGerarCSV").click()
        except Exception as e:
            print(f"ERRO: Não foi possível clicar no botão. {e}")
            return False

    # --- 3. AGUARDAR POPUP (ATÉ 7 MINUTOS) ---
    print("\n3. Aguardando processamento do servidor...")
    print("   Tempo limite: 7 minutos. O script ficará parado aqui.")
    
    tempo_maximo_segundos = 420 # 7 minutos * 60 seg
    
    try:
        # O WebDriverWait vigia a tela até o alerta aparecer ou o tempo acabar
        WebDriverWait(driver, tempo_maximo_segundos).until(EC.alert_is_present())
        
        # --- 4. CLICAR NO OK ---
        alerta = driver.switch_to.alert
        texto_alerta = alerta.text
        print(f" > SUCESSO! Popup detectado: '{texto_alerta}'")
        
        alerta.accept() # Clica no OK
        print(" > OK clicado. A barra de download deve aparecer agora.")
        time.sleep(1) # Pequena pausa para a barra de download aparecer

        salvar_arquivo_visual(dotenv.get_key(dotenv.find_dotenv(), "DOWNLOAD_DIR"), "0105070401.csv")
        return True 
        
    except TimeoutException:
        print(f"\nERRO: O tempo limite de {tempo_maximo_segundos}s esgotou!")
        print("O popup não apareceu. Verifique se o sistema travou.")
        return False
