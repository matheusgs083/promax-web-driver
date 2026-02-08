import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from pages.rotina_page import RotinaPage

# Tenta importar as ferramentas visuais
try:
    from core.manipulador_download import salvar_arquivo_visual
except ImportError:
    salvar_arquivo_visual = None

class Relatorio0105070402Page(RotinaPage):

    # --- LOCATORS ---
    BTN_GERAR = (By.ID, "btnGerarCSV")

    # --- SCRIPTS JS (Lógica de Negócio Legada) ---
    JS_APLICAR_FILTROS = r"""
    try {
        // 1. Marca checkboxes idAS e idGeo
        var ids = ['idAS', 'idGeo'];
        for (var k = 0; k < ids.length; k++) {
            var el = document.getElementById(ids[k]);
            if (el) {
                if (el.type == 'checkbox' && !el.checked) { 
                    el.click();
                    el.checked = true; 
                }
            }
        }

        // 2. Clica no link 'Todos' (Iteração por texto)
        var links = document.getElementsByTagName('A');
        for (var i = 0; i < links.length; i++) {
            var texto = links[i].innerText || "";
            // Remove espaços extras e verifica
            if (texto.replace(/^\s+|\s+$/g, '') == 'Todos') {
                links[i].click();
                break;
            }
        }
        return { ok: true };
    } catch (e) {
        return { ok: false, error: String(e) };
    }
    """

    def gerar_relatorio(self, nome_arquivo="0105070402.csv", timeout_processamento=420):
        """
        Executa o fluxo completo de geração.
        :param timeout_processamento: Tempo máximo (em segundos) esperando o servidor (Padrão 7 min).
        """
        self.logger.info("--- Gerando Relatório 0105070402 ---")
        
        # 1. Aplicar Filtros (Via JS)
        self._aplicar_filtros()
        
        # 2. Clicar em Gerar
        self._clicar_botao_gerar()

        # 3. Aguardar Alerta de Sucesso e Salvar
        return self._aguardar_processamento_e_salvar(timeout_processamento, nome_arquivo)

    def _aplicar_filtros(self):
        self.logger.info("Aplicando filtros na tela (JS)...")
        # Garante foco no frame correto (se houver, adicione switch_to_frame aqui)
        # self.switch_to_frame(0) 

        res = self.driver.execute_script(self.JS_APLICAR_FILTROS)
        if res and not res.get("ok"):
            self.logger.warning(f"Erro no JS de filtros: {res.get('error')}")
        
        time.sleep(2) # Pausa visual mantida do original
        self.logger.info("Filtros aplicados.")

    def _clicar_botao_gerar(self):
        self.logger.info("Clicando no botão 'Gerar CSV'...")
        try:
            # Tenta via JS primeiro (mais seguro no legado)
            self.driver.execute_script("document.getElementById('btnGerarCSV').click();")
            self.logger.info("Clique via JS OK.")
        except Exception:
            # Fallback para Selenium
            self.click(self.BTN_GERAR)
            self.logger.info("Clique via Selenium OK.")

    def _aguardar_processamento_e_salvar(self, timeout, nome_arquivo):
        self.logger.info(f"Aguardando processamento do servidor... (Até {timeout}s)")
        
        try:
            # Espera explícita pelo Alerta (sinal de que o arquivo foi gerado)
            WebDriverWait(self.driver, timeout).until(EC.alert_is_present())
            
            alerta = self.driver.switch_to.alert
            texto = alerta.text
            self.logger.info(f"Popup detectado: '{texto}'")
            
            alerta.accept()
            self.logger.info("Alerta aceito. Iniciando fluxo de salvamento...")
            
            time.sleep(1) # Estabilidade

            # Chama o visual
            if salvar_arquivo_visual:
                diretorio = os.getenv("DOWNLOAD_DIR", "C:\\Downloads")
                salvar_arquivo_visual(diretorio, nome_arquivo)
                self.logger.info(f"Arquivo salvo: {nome_arquivo}")
                return True
            else:
                self.logger.error("Módulo visual não carregado. Download não efetuado.")
                return False

        except TimeoutException:
            self.logger.error(f"Timeout de {timeout}s esgotou. O popup não apareceu.")
            return False
        except Exception as e:
            self.logger.exception(f"Erro durante espera do arquivo: {e}")
            return False