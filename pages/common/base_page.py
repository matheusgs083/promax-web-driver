import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoAlertPresentException
from core.observability.logger import get_logger

class BasePage:
    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 15)
        self.logger = get_logger(self.__class__.__name__)

    def find_element(self, locator):
        return self.wait.until(EC.presence_of_element_located(locator))

    def click(self, locator):
        try:
            self.wait.until(EC.element_to_be_clickable(locator)).click()
            self.logger.info(f"Clicou em: {locator}")
        except Exception as e:
            self.logger.error(f"Erro ao clicar em {locator}: {e}")
            raise

    def send_keys(self, locator, text):
        try:
            element = self.wait.until(EC.visibility_of_element_located(locator))
            element.clear()
            element.send_keys(text)
            log_text = "*****" if "senha" in str(locator).lower() else text
            self.logger.info(f"Digitou '{log_text}' em: {locator}")
        except Exception as e:
            self.logger.error(f"Erro ao escrever: {e}")
            raise

    def switch_to_frame(self, locator):
        self.wait.until(EC.frame_to_be_available_and_switch_to_it(locator))

    def switch_to_default_content(self):
        self.driver.switch_to.default_content()

    def wait_until(self, condition, timeout=15, message=None):
        return WebDriverWait(self.driver, timeout).until(condition, message)

    def wait_for_js_condition(self, script, timeout=15, poll_frequency=0.2, description="condição JS"):
        def _condition(driver):
            try:
                return bool(driver.execute_script(script))
            except Exception:
                return False

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=poll_frequency).until(_condition)
        except TimeoutException as exc:
            raise TimeoutException(f"Timeout aguardando {description}") from exc

    def wait_for_element_value(self, locator, expected_value, timeout=10):
        expected = str(expected_value)

        def _condition(driver):
            try:
                value = driver.find_element(*locator).get_attribute("value")
                return str(value).strip() == expected
            except Exception:
                return False

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.2).until(_condition)
        except TimeoutException as exc:
            raise TimeoutException(f"Timeout aguardando valor '{expected}' em {locator}") from exc

    def wait_for_window_count(self, expected_count, timeout=15):
        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.2).until(
                lambda d: len(d.window_handles) >= expected_count
            )
        except TimeoutException as exc:
            raise TimeoutException(
                f"Timeout aguardando ao menos {expected_count} janela(s). Atual: {len(self.driver.window_handles)}"
            ) from exc

    def wait_for_no_alert(self, timeout=5):
        def _condition(driver):
            try:
                driver.switch_to.alert
                return False
            except NoAlertPresentException:
                return True
            except Exception:
                return False

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.2).until(_condition)
        except TimeoutException as exc:
            raise TimeoutException("Timeout aguardando limpeza de alertas") from exc

    def lidar_com_alertas(self, tentativas=2, timeout=2, timeout_entre_alertas=1, max_alertas=10):
        alertas_tratados = 0
        tentativas_sem_alerta = 0
        mensagens_alerta = []

        while tentativas_sem_alerta < tentativas and alertas_tratados < max_alertas:
            try:
                WebDriverWait(self.driver, timeout if alertas_tratados == 0 else timeout_entre_alertas).until(
                    EC.alert_is_present()
                )
                alert = self.driver.switch_to.alert
                texto_alerta = str(alert.text)
                self.logger.warning(f"Alerta detectado: {texto_alerta}")
                mensagens_alerta.append(texto_alerta)
                alert.accept()
                self.wait_for_no_alert(timeout=max(timeout_entre_alertas, 1))
                alertas_tratados += 1
                tentativas_sem_alerta = 0
            except TimeoutException:
                tentativas_sem_alerta += 1

        if alertas_tratados:
            self.logger.info(f"Tratamento de alertas concluido. Total aceito(s): {alertas_tratados}")
        return mensagens_alerta

    # --- NOVO MÉTODO (INTEGRADO AQUI) ---
    def selecionar_combo_js(self, locator, valor_opcao):
        """
        Seleciona item no <select> e força evento onchange (Vital para o Promax).
        """
        try:
            # 1. Acha o elemento usando o Wait padrão da BasePage
            elemento_select = self.find_element(locator)
            
            # 2. O seu Script JS (Levemente ajustado para logar via Logger da classe)
            js_cmd = """
            var sel = arguments[0];
            var val = arguments[1];
            var encontrou = false;

            for (var i = 0; i < sel.options.length; i++) {
                if (sel.options[i].value == val) {
                    sel.selectedIndex = i;
                    encontrou = true;
                    break;
                }
            }

            if (encontrou) {
                if (sel.fireEvent) {
                    sel.fireEvent("onchange"); 
                } else if ("createEvent" in document) {
                    var evt = document.createEvent("HTMLEvents");
                    evt.initEvent("change", false, true);
                    sel.dispatchEvent(evt);
                }
            }
            return encontrou;
            """
            
            resultado = self.driver.execute_script(js_cmd, elemento_select, valor_opcao)
            
            if resultado:
                self.logger.info(f"Opção '{valor_opcao}' selecionada com sucesso em {locator}")
                return True

            self.logger.warning(f"Opção '{valor_opcao}' NÃO encontrada no combo {locator}")
            return False
                
        except Exception as e:
            self.logger.error(f"Erro ao selecionar combo JS: {e}")
            raise


