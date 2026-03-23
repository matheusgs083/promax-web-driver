from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pages.common.base_page import BasePage
from pages.common.rotina_page import RotinaPage


class MenuPage(BasePage):
    FRAME_TOP = "top"
    FRAME_INTERNO_INDEX = 0
    LOCATOR_ATALHO = (By.ID, "atalho")
    LOCATOR_BTN_LOGOFF = (By.ID, "BtLogoff")

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
        return { ok: true, method: "enter" };
    } catch(err) {
        if (e.form) {
            e.form.submit();
            return { ok: true, method: "submit" };
        }
        return { ok: false, error: String(err) };
    }
    """

    JS_CLICAR_OK_MENU = """
    var input = arguments[0];
    try {
        var form = input && input.form ? input.form : null;
        if (!form) return { ok: false, error: "form-not-found" };

        var candidatos = form.querySelectorAll("input, button");
        for (var i = 0; i < candidatos.length; i++) {
            var el = candidatos[i];
            var texto = ((el.value || el.innerText || el.textContent || "") + "").replace(/^\\s+|\\s+$/g, "").toUpperCase();
            var nome = ((el.name || "") + "").toUpperCase();
            var id = ((el.id || "") + "").toUpperCase();
            var tipo = ((el.type || "") + "").toUpperCase();

            if (
                texto === "OK" ||
                nome.indexOf("CONFIRMA") !== -1 ||
                id.indexOf("CONFIRMA") !== -1 ||
                tipo === "SUBMIT" ||
                (tipo === "BUTTON" && texto === "OK")
            ) {
                try { el.focus(); } catch (e) {}
                if (el.click) { el.click(); }
                else if (el.fireEvent) { el.fireEvent("onclick"); }
                return { ok: true, method: "click", target: nome || id || texto || tipo };
            }
        }

        if (form.submit) {
            form.submit();
            return { ok: true, method: "submit" };
        }

        return { ok: false, error: "ok-button-not-found" };
    } catch(err) {
        return { ok: false, error: String(err) };
    }
    """

    JS_CLICK = """
    arguments[0].click();
    """

    JS_VALIDAR_VALOR = """
    var el = arguments[0];
    var esperado = arguments[1];
    try {
        return { ok: true, value: String(el.value || ""), matches: String(el.value || "") === String(esperado) };
    } catch(e) {
        return { ok: false, error: String(e) };
    }
    """

    def _entrar_no_frame_menu(self):
        self.switch_to_default_content()
        try:
            self.wait.until(EC.frame_to_be_available_and_switch_to_it(self.FRAME_TOP))
            self.wait.until(EC.frame_to_be_available_and_switch_to_it(self.FRAME_INTERNO_INDEX))
        except Exception as e:
            self.logger.critical(f"Erro ao navegar nos frames do menu: {e}")
            raise

    def acessar_rotina(self, codigo_rotina):
        self.logger.info(f"--- ACESSANDO ROTINA: {codigo_rotina} ---")

        handle_menu = self.driver.current_window_handle
        handles_antes = self.driver.window_handles

        self._entrar_no_frame_menu()

        try:
            elemento_atalho = self.wait.until(EC.presence_of_element_located(self.LOCATOR_ATALHO))
        except Exception:
            self.logger.critical("Campo 'atalho' não encontrado no frame.")
            raise

        self.logger.info(f"Digitando '{codigo_rotina}' via JS...")
        resultado_digitacao = self.driver.execute_script(self.JS_SET_VALUE, elemento_atalho, codigo_rotina)
        self.logger.info(f"Resultado da digitação via JS: {resultado_digitacao}")
        self._confirmar_atalho_preenchido(elemento_atalho, codigo_rotina, timeout=0.6)

        self.logger.info("Disparando Enter via JS para acessar a rotina...")
        resultado_enter = self.driver.execute_script(self.JS_DISPARAR_ENTER, elemento_atalho)
        self.logger.info(f"Resultado do Enter via JS: {resultado_enter}")

        self.logger.info("Aguardando nova janela abrir...")
        if not self._aguardar_abertura_rotina(len(handles_antes) + 1, timeout=6):
            self.logger.info("Nova janela não abriu após Enter. Tentando OK via JS como contingência...")
            self._entrar_no_frame_menu()
            elemento_atalho = self.wait.until(EC.presence_of_element_located(self.LOCATOR_ATALHO))
            resultado_ok = self.driver.execute_script(self.JS_CLICAR_OK_MENU, elemento_atalho)
            self.logger.info(f"Resultado do clique de confirmação via JS: {resultado_ok}")

            if not self._aguardar_abertura_rotina(len(handles_antes) + 1, timeout=10):
                self.logger.error("Timeout: nova janela não abriu após Enter via JS e contingência com OK.")
                raise RuntimeError("Falha ao abrir rotina.")

        handles_agora = self.driver.window_handles
        novas_janelas = [h for h in handles_agora if h not in handles_antes]

        if not novas_janelas:
            raise RuntimeError("Nova janela não identificada.")

        handle_nova_rotina = novas_janelas[0]

        self.driver.switch_to.window(handle_nova_rotina)
        self.logger.info(f"Janela da rotina aberta e focada: {handle_nova_rotina}")

        return RotinaPage(self.driver, handle_menu_original=handle_menu)

    def _aguardar_abertura_rotina(self, expected_count, timeout):
        try:
            self.wait_for_window_count(expected_count, timeout=timeout)
            return True
        except Exception:
            return False

    def _confirmar_atalho_preenchido(self, elemento_atalho, codigo_rotina, timeout=0.6):
        codigo_rotina = str(codigo_rotina)

        def _atalho_preenchido(driver):
            try:
                resultado = driver.execute_script(self.JS_VALIDAR_VALOR, elemento_atalho, codigo_rotina)
                return bool(resultado and resultado.get("ok") and resultado.get("matches"))
            except Exception:
                return False

        try:
            WebDriverWait(self.driver, timeout, poll_frequency=0.1).until(_atalho_preenchido)
        except Exception as exc:
            raise RuntimeError(f"Falha ao confirmar preenchimento do atalho '{codigo_rotina}' via JS") from exc

    def fazer_logoff(self):
        self.logger.info("--- REALIZANDO LOGOFF ---")

        self._entrar_no_frame_menu()

        try:
            btn_logoff = self.wait.until(EC.presence_of_element_located(self.LOCATOR_BTN_LOGOFF))

            self.logger.info("Clicando no botão de Logoff via JS...")
            self.driver.execute_script(self.JS_CLICK, btn_logoff)

            try:
                alert = self.wait_until(EC.alert_is_present(), timeout=2)
                if alert:
                    self.logger.info(f"Alerta de logoff detectado: {alert.text}")
                    alert.accept()
                    self.wait_for_no_alert(timeout=2)
            except Exception:
                pass

            self.logger.info("Logoff acionado com sucesso.")
        except Exception as e:
            self.logger.critical(f"Falha ao tentar fazer logoff: {e}")
            raise


