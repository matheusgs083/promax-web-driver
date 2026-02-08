import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from core.logger import get_logger

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

    def lidar_com_alertas(self, tentativas=3, timeout=2):
        for i in range(1, tentativas + 1):
            try:
                WebDriverWait(self.driver, timeout).until(EC.alert_is_present())
                alert = self.driver.switch_to.alert
                self.logger.warning(f"Alerta detectado: {alert.text}")
                alert.accept()
                time.sleep(0.5)
            except TimeoutException:
                break

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
            else:
                self.logger.warning(f"Opção '{valor_opcao}' NÃO encontrada no combo {locator}")
                
        except Exception as e:
            self.logger.error(f"Erro ao selecionar combo JS: {e}")
            raise