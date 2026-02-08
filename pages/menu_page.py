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

    def acessar_rotina(self, codigo_rotina):
        """
        Digita o código da rotina, dá Enter via JS e aguarda a nova janela.
        """
        self.logger.info(f"--- ACESSANDO ROTINA: {codigo_rotina} ---")

        # 1. Guarda o ID da janela do Menu
        handle_menu = self.driver.current_window_handle
        handles_antes = self.driver.window_handles

        # 2. Navega até o input (Resetando contexto antes)
        self.switch_to_default_content()
        
        try:
            # Entra no frame "top"
            self.wait.until(EC.frame_to_be_available_and_switch_to_it(self.FRAME_TOP))
            # Entra no frame interno (index 0)
            self.wait.until(EC.frame_to_be_available_and_switch_to_it(self.FRAME_INTERNO_INDEX))
        except Exception as e:
            self.logger.critical(f"Erro ao navegar nos frames do Menu: {e}")
            raise e

        # 3. Localiza o elemento (Wait explícito)
        try:
            # Usamos presence_of_element_located para evitar verificação de visibilidade que quebra o JS
            elemento_atalho = self.wait.until(EC.presence_of_element_located(self.LOCATOR_ATALHO))
        except Exception:
            self.logger.critical("Campo 'atalho' não encontrado no frame.")
            raise

        # 4. Digita o código VIA JS (Evita send_keys do Selenium)
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
        
        # Aguarda carregamento inicial da rotina (Delay de segurança do legado)
        time.sleep(2)

        return RotinaPage(self.driver, handle_menu_original=handle_menu)