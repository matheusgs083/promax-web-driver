import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from pages.rotina_page import RotinaPage

try:
    from core.manipulador_download import salvar_arquivo_visual
    from core.relatorio_execucao import tracker
except ImportError:
    salvar_arquivo_visual = None
    class MockTracker:
        def anotar(self, *args, **kwargs): pass
    tracker = MockTracker()


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
        self.logger.info("--- Gerando Relatório 0105070402 ---")
        
        # INICIA CRONÔMETRO E TRACKER (Pois não usa loop_unidades)
        inicio_unidade = time.time()
        rotina_nome = "Rotina 0105070402"

        try:
            # ==========================================================
            # CORREÇÃO 1: Esperar a página renderizar (Anti Condição de Corrida)
            # ==========================================================
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located(self.BTN_GERAR)
                )
            except TimeoutException:
                self.logger.warning("Botão Gerar CSV demorou a aparecer. O script pode falhar.")

            self._aplicar_filtros()
            self._clicar_botao_gerar()
            
            # Captura a tupla (Sucesso, Motivo) retornada pelo manipulador
            resultado = self._aguardar_processamento_e_salvar(timeout_processamento, nome_arquivo)
            
            duracao_unidade = time.time() - inicio_unidade
            
            # Desempacota o resultado
            if isinstance(resultado, tuple):
                ok, motivo = resultado
            elif resultado is False:
                ok, motivo = False, "Falha na execução"
            else:
                ok, motivo = True, "Download concluído"

            # Registra no Tracker (Marcando Unidade como "TODAS")
            if ok:
                tracker.anotar(rotina_nome, "TODAS", "SUCESSO", motivo, duracao_unidade)
            else:
                tracker.anotar(rotina_nome, "TODAS", "FALHA DOWNLOAD", motivo, duracao_unidade)

            return resultado

        except Exception as e:
            duracao_unidade = time.time() - inicio_unidade
            msg_erro = str(e).split('\n')[0]
            self.logger.error(f"Erro fatal: {msg_erro}")
            tracker.anotar(rotina_nome, "TODAS", "ERRO SISTEMA", msg_erro, duracao_unidade)
            raise

    def _aplicar_filtros(self):
        self.logger.info("Aplicando filtros na tela (JS)...")

        res = self.driver.execute_script(self.JS_APLICAR_FILTROS)
        if res and not res.get("ok"):
            self.logger.warning(f"Erro no JS de filtros: {res.get('error')}")

        time.sleep(2)
        self.logger.info("Filtros aplicados.")

    def _clicar_botao_gerar(self):
        self.logger.info("Clicando no botão 'Gerar CSV'...")

        # tenta achar o elemento e clicar via helper IE (mais estável no legado)
        try:
            btn = self.find_element(self.BTN_GERAR)
            self.js_click_ie(btn)  # usa JS_CLICK_IE da RotinaPage
            self.logger.info("Clique via JS helper OK.")
        except Exception as e:
            # fallback (mesmo comportamento do seu original)
            self.logger.warning(f"Falha no clique via helper, tentando Selenium click. Motivo: {e}")
            self.click(self.BTN_GERAR)
            self.logger.info("Clique via Selenium OK.")

    def _aguardar_processamento_e_salvar(self, timeout, nome_arquivo):
        self.logger.info(f"Aguardando processamento do servidor... (Até {timeout}s)")

        try:
            WebDriverWait(self.driver, timeout).until(EC.alert_is_present())

            alerta = self.driver.switch_to.alert
            texto = alerta.text
            self.logger.info(f"Popup detectado: '{texto}'")

            alerta.accept()
            self.logger.info("Alerta aceito. Iniciando fluxo de salvamento...")

            time.sleep(1)

            # ==========================================================
            # CORREÇÃO 2: Retornar a tupla do manipulador de download
            # ==========================================================
            if salvar_arquivo_visual:
                diretorio = os.getenv("DOWNLOAD_DIR", r"C:\Users\caixa.patos\Documents\Relatorios")
                return salvar_arquivo_visual(diretorio, nome_arquivo)

            self.logger.error("Módulo visual não carregado. Download não efetuado.")
            return False, "Módulos visuais ausentes"

        except TimeoutException:
            self.logger.error(f"Timeout de {timeout}s esgotou. O popup não apareceu.")
            return False, "Timeout esperando alerta de processamento"
        except Exception as e:
            self.logger.exception(f"Erro durante espera do arquivo: {e}")
            return False, str(e).split('\n')[0]