import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from pages.common.rotina_page import RotinaPage

try:
    from core.services.report_download_service import capturar_download_relatorio as salvar_arquivo_visual
    from core.observability.relatorio_execucao import tracker
except ImportError:
    salvar_arquivo_visual = None

    class MockTracker:
        def anotar(self, *args, **kwargs):
            pass

    tracker = MockTracker()


class Relatorio0105070402Page(RotinaPage):

    BTN_GERAR = (By.ID, "btnGerarCSV")

    JS_APLICAR_FILTROS = r"""
    try {
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

        inicio_unidade = time.time()
        rotina_nome = "Rotina 0105070402"

        try:
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located(self.BTN_GERAR)
                )
            except TimeoutException:
                self.logger.warning("Botão Gerar CSV demorou a aparecer. O script pode falhar.")

            self._aplicar_filtros()
            self._clicar_botao_gerar()

            resultado = self._aguardar_processamento_e_salvar(timeout_processamento, nome_arquivo)

            duracao_unidade = time.time() - inicio_unidade

            if isinstance(resultado, tuple):
                ok, motivo = resultado
            elif resultado is False:
                ok, motivo = False, "Falha na execução"
            else:
                ok, motivo = True, "Download concluído"

            if ok:
                tracker.anotar(rotina_nome, "TODAS", "SUCESSO", motivo, duracao_unidade)
            else:
                tracker.anotar(rotina_nome, "TODAS", "FALHA DOWNLOAD", motivo, duracao_unidade)

            return resultado

        except Exception as e:
            duracao_unidade = time.time() - inicio_unidade
            msg_erro = str(e).split("\n")[0]
            self.logger.error(f"Erro fatal: {msg_erro}")
            tracker.anotar(rotina_nome, "TODAS", "ERRO SISTEMA", msg_erro, duracao_unidade)
            raise

    def _aplicar_filtros(self):
        self.logger.info("Aplicando filtros na tela (JS)...")

        res = self.driver.execute_script(self.JS_APLICAR_FILTROS)
        if res and not res.get("ok"):
            self.logger.warning(f"Erro no JS de filtros: {res.get('error')}")

        self.aguardar_loader_oculto(timeout=5)
        self.logger.info("Filtros aplicados.")

    def _clicar_botao_gerar(self):
        self.logger.info("Clicando no botão 'Gerar CSV'...")

        try:
            btn = self.find_element(self.BTN_GERAR)
            self.js_click_ie(btn)
            self.logger.info("Clique via JS helper OK.")
        except Exception as e:
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
            self.wait_for_no_alert(timeout=2)

            if salvar_arquivo_visual:
                return salvar_arquivo_visual(nome_arquivo)

            self.logger.error("Módulo visual não carregado. Download não efetuado.")
            return False, "Módulos visuais ausentes"

        except TimeoutException:
            self.logger.error(f"Timeout de {timeout}s esgotou. O popup não apareceu.")
            return False, "Timeout esperando alerta de processamento"
        except Exception as e:
            self.logger.exception(f"Erro durante espera do arquivo: {e}")
            return False, str(e).split("\n")[0]




