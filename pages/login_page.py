import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from pages.base_page import BasePage
from pages.menu_page import MenuPage

try:
    from core.validador_visual import validar_elemento
except ImportError:
    validar_elemento = None

class LoginPage(BasePage):
    # --- CONFIGURAÇÕES ---
    URL_PROMAX = os.getenv("PROMAX_URL")
    
    # Locators
    LOCATOR_USUARIO = (By.NAME, "Usuario")
    LOCATOR_SENHA = (By.NAME, "Senha")
    LOCATOR_BTN_CONFIRMA = (By.NAME, "cmdConfirma")
    LOCATOR_UNIDADE = (By.NAME, "unidade")

    # --- JAVASCRIPT (Mantido idêntico) ---
    JS_SET_VALUE_IE = """
    var el = arguments[0];
    var val = arguments[1];
    try {
        try { el.scrollIntoView(true); } catch(e) {}
        try { el.focus(); } catch(e) {}
        el.value = val;
        if (document.createEvent) {
            var ev1 = document.createEvent('HTMLEvents'); ev1.initEvent('input', true, true); el.dispatchEvent(ev1);
            var ev2 = document.createEvent('HTMLEvents'); ev2.initEvent('change', true, true); el.dispatchEvent(ev2);
            var ev3 = document.createEvent('HTMLEvents'); ev3.initEvent('blur', true, true);  el.dispatchEvent(ev3);
        } else if (el.fireEvent) {
            try { el.fireEvent('oninput'); } catch(e) {}
            try { el.fireEvent('onchange'); } catch(e) {}
            try { el.fireEvent('onblur'); } catch(e) {}
        }
        return { ok: true, value: el.value };
    } catch (e) {
        return { ok: false, error: (e && e.message) ? e.message : String(e) };
    }
    """

    JS_CLICK_IE = """
    var el = arguments[0];
    try {
        try { el.scrollIntoView(true); } catch(e) {}
        try { el.focus(); } catch(e) {}
        if (el.click) { el.click(); } else if (el.fireEvent) { el.fireEvent('onclick'); }
        return { ok: true };
    } catch (e) {
        return { ok: false, error: (e && e.message) ? e.message : String(e) };
    }
    """

    def __init__(self, driver):
        super().__init__(driver)
        self._carregar_mapa_unidades()

    def _carregar_mapa_unidades(self):
        self.mapa_unidades = {}
        excluir = {"PROMAX_URL", "DRIVER_PATH", "DOWNLOAD_DIR", "PROMAX_USER", "PROMAX_PASS"}
        for k, v in os.environ.items():
            if k in excluir or not v: continue
            v_norm = v.strip()
            if v_norm.isdigit() and 6 <= len(v_norm) <= 10:
                self.mapa_unidades[k.strip().upper()] = v_norm

    def fazer_login(self, usuario, senha, nome_unidade=None):
        self.logger.info(f"--- LOGIN PROMAX (Unidade: {nome_unidade}) ---")
        self.driver.get(self.URL_PROMAX)
        
        # Tratamento de múltiplas janelas
        if len(self.driver.window_handles) > 1:
            self.logger.warning(f"Janelas detectadas: {len(self.driver.window_handles)}. Focando na última.")
            self.driver.switch_to.window(self.driver.window_handles[-1])

        self.logger.info("Aguardando carregamento inicial...")

        # =========================================================
        # PARTE 1: ENTRAR NO FRAME
        # =========================================================
        frames = self.driver.find_elements(By.TAG_NAME, "iframe") or self.driver.find_elements(By.TAG_NAME, "frame")
        frame_index = None
        
        try:
            if frames:
                frame_index = 0
                self.wait.until(EC.frame_to_be_available_and_switch_to_it(frame_index))
                self.logger.info(f"Entrou no frame index={frame_index}")
            else:
                self.logger.info("Nenhum frame detectado. Tentando login na raiz.")
        except Exception:
            self.logger.warning("Falha ao entrar no frame, tentando seguir na raiz...")

        # =========================================================
        # PARTE 2: PREENCHIMENTO
        # =========================================================
        try:
            campo_usuario = self.wait.until(EC.presence_of_element_located(self.LOCATOR_USUARIO))
            campo_senha = self.wait.until(EC.presence_of_element_located(self.LOCATOR_SENHA))
            botao_confirma = self.wait.until(EC.presence_of_element_located(self.LOCATOR_BTN_CONFIRMA))
            
            # Executa JS
            self.driver.execute_script(self.JS_SET_VALUE_IE, campo_usuario, usuario)
            self.driver.execute_script(self.JS_SET_VALUE_IE, campo_senha, senha)
            self.driver.execute_script(self.JS_CLICK_IE, botao_confirma)
            
            self.logger.info("Credenciais enviadas.")
            
        except Exception as e:
            self.logger.error("Erro ao localizar/interagir com campos de login.")
            raise e

        # =========================================================
        # PARTE 3: UNIDADE E CONFIRMAÇÃO FINAL
        # =========================================================
        codigo_unidade = self.mapa_unidades.get(nome_unidade.upper()) if nome_unidade else None

        if codigo_unidade:
            self.logger.info(f"Selecionando unidade: {nome_unidade} ({codigo_unidade})")
            
            # Proteção: Se houver frame, garante que estamos nele
            if frame_index is not None:
                self.switch_to_default_content()
                try:
                    self.wait.until(EC.frame_to_be_available_and_switch_to_it(frame_index))
                except:
                    pass

            try:
                # Usa método JS da BasePage
                self.selecionar_combo_js(self.LOCATOR_UNIDADE, codigo_unidade)
                self.logger.info("Unidade selecionada via JS.")
                
                # Pequena pausa para o sistema processar a troca no combo
                time.sleep(1)

                # Segunda Confirmação (Botão Entrar Final)
                try:
                    botao_final = self.find_element(self.LOCATOR_BTN_CONFIRMA)
                    self.driver.execute_script(self.JS_CLICK_IE, botao_final)
                    self.logger.info("Segunda confirmação clicada via JS.")
                except Exception:
                    pass

            except Exception as e:
                self.logger.warning(f"Erro no fluxo de unidade: {e}")

        # ====================================================================
        # PARTE 4: TRATAMENTO DE ALERTAS (A CORREÇÃO DO CRASH)
        # ====================================================================
        self.logger.info("Aguardando alertas de sistema (Dia 15, Estoque, etc)...")
        
        # 1. Pausa vital para o navegador renderizar o alerta
        time.sleep(2)

        # 2. Limpa todos os alertas em sequência
        # Se o alerta estiver ativo, qualquer comando do Selenium (como switch_to) falharia.
        # Por isso chamamos isso ANTES de tentar sair do frame.
        self.lidar_com_alertas(tentativas=5, timeout=1.5)

        # 3. Pausa para o sistema carregar a próxima página (Menu)
        time.sleep(2)
        
        # ====================================================================
        # PARTE 5: FINALIZAÇÃO
        # ====================================================================
        
        # Tenta sair do frame com segurança (se houver alerta residual, ele captura)
        try:
            self.switch_to_default_content()
        except UnexpectedAlertPresentException:
            self.logger.warning("Alerta detectado ao sair do frame. Aceitando...")
            try:
                self.driver.switch_to.alert.accept()
                self.switch_to_default_content()
            except:
                pass

        self._limpar_janelas_extras()

        # Validação Visual
        if validar_elemento:
            self.logger.info("Buscando validação visual (validacaoLogin.png)...")
            # Tenta validar com timeout maior, pois o carregamento do menu pode ser lento
            if validar_elemento("validacaoLogin.png", timeout=20):
                self.logger.info("LOGIN VALIDADO COM SUCESSO!")
                return MenuPage(self.driver)
        
        self.logger.warning("Seguindo fluxo sem validação visual positiva.")
        return MenuPage(self.driver)

    def _limpar_janelas_extras(self):
        try:
            # Verifica se o driver ainda está ativo
            if not self.driver.window_handles: return

            atual = self.driver.current_window_handle
            for h in self.driver.window_handles:
                if h != atual:
                    self.driver.switch_to.window(h)
                    self.driver.close()
            self.driver.switch_to.window(atual)
        except Exception:
            pass