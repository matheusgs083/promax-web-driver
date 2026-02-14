import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from pages.base_page import BasePage
from pages.rotina_page import RotinaPage

class MenuPage(BasePage):
    # --- LOCATORS ---
    FRAME_TOP = "top"
    FRAME_INTERNO_INDEX = 0
    LOCATOR_ATALHO = (By.ID, "atalho")
    # Novo locator baseado no log fornecido
    LOCATOR_BTN_LOGOFF = (By.ID, "BtLogoff") 

    # --- JS PURO PARA EVITAR ERRO 'HTMLFormElement' ---
    JS_SET_VALUE = """
    var el = arguments[0];
    var val = arguments[1];
    try {
        el.value = val;
        return { ok: true };
    } catch(e) {
        return { ok: false, error: String(e) };
    }
    """

    JS_DISPARAR_ENTER = """
    var e = arguments[0];
    try {
        var event = document.createEventObject();
        event.keyCode = 13;
        e.fireEvent("onkeypress", event);
        return { ok: true };
    } catch(err) {
        if(e.form) { e.form.submit(); return { ok: true, method: 'submit' }; }
        return { ok: false, error: String(err) };
    }
    """

    # Novo JS simples para clicar (mais robusto que selenium click() em frames legados)
    JS_CLICK = """
    arguments[0].click();
    """

    def _entrar_no_frame_menu(self):
        """Helper interno para navegar até o frame correto (top > frame[0])"""
        self.switch_to_default_content()
        try:
            self.wait.until(EC.frame_to_be_available_and_switch_to_it(self.FRAME_TOP))
            self.wait.until(EC.frame_to_be_available_and_switch_to_it(self.FRAME_INTERNO_INDEX))
        except Exception as e:
            self.logger.critical(f"Erro ao navegar nos frames do Menu: {e}")
            raise e

    def acessar_rotina(self, codigo_rotina):
        """
        Digita o código da rotina, dá Enter via JS e aguarda a nova janela.
        """
        self.logger.info(f"--- ACESSANDO ROTINA: {codigo_rotina} ---")

        # 1. Guarda o ID da janela do Menu
        handle_menu = self.driver.current_window_handle
        handles_antes = self.driver.window_handles

        # 2. Navega até o frame (Refatorado para usar o helper)
        self._entrar_no_frame_menu()

        # 3. Localiza o elemento (Wait explícito)
        try:
            elemento_atalho = self.wait.until(EC.presence_of_element_located(self.LOCATOR_ATALHO))
        except Exception:
            self.logger.critical("Campo 'atalho' não encontrado no frame.")
            raise

        # 4. Digita o código VIA JS
        self.logger.info(f"Digitando '{codigo_rotina}' via JS...")
        self.driver.execute_script(self.JS_SET_VALUE, elemento_atalho, codigo_rotina)
        time.sleep(0.5)

        # 5. Dispara o Enter VIA JS
        self.logger.info("Disparando Enter via JS...")
        self.driver.execute_script(self.JS_DISPARAR_ENTER, elemento_atalho)

        self.logger.info("Aguardando nova janela abrir...")
        
        # 6. Espera explícita para o número de janelas aumentar
        try:
            self.wait.until(lambda d: len(d.window_handles) > len(handles_antes))
        except Exception:
            self.logger.error("Timeout: Nova janela não abriu após Enter.")
            raise RuntimeError("Falha ao abrir rotina.")

        # 7. Identifica e foca na nova janela
        handles_agora = self.driver.window_handles
        novas_janelas = [h for h in handles_agora if h not in handles_antes]
        
        if not novas_janelas:
            raise RuntimeError("Nova janela não identificada.")
        
        handle_nova_rotina = novas_janelas[0]
        
        self.driver.switch_to.window(handle_nova_rotina)
        self.logger.info(f"Janela da rotina aberta e focada: {handle_nova_rotina}")

        return RotinaPage(self.driver, handle_menu_original=handle_menu)

    def fazer_logoff(self):
        """
        Clica no botão de Logoff localizado no frame do menu.
        """
        self.logger.info("--- REALIZANDO LOGOFF ---")

        # 1. Garante que estamos no frame correto (Top > 0)
        self._entrar_no_frame_menu()

        try:
            # 2. Localiza o botão de Logoff
            btn_logoff = self.wait.until(EC.presence_of_element_located(self.LOCATOR_BTN_LOGOFF))
            
            # 3. Clica via JS para evitar interceptações ou erros de coordenadas
            self.logger.info("Clicando no botão de Logoff via JS...")
            self.driver.execute_script(self.JS_CLICK, btn_logoff)
            
            # 4. Tratamento opcional de Alerta (comum em logoffs legados)
            try:
                # Espera curtíssima para ver se aparece um alert "Tem certeza?"
                time.sleep(0.5) 
                alert = EC.alert_is_present()(self.driver)
                if alert:
                    self.logger.info(f"Alerta de logoff detectado: {alert.text}")
                    alert.accept()
            except Exception:
                # Se não tiver alerta, segue o fluxo
                pass

            self.logger.info("Logoff acionado com sucesso.")

        except Exception as e:
            self.logger.critical(f"Falha ao tentar fazer logoff: {e}")
            raise