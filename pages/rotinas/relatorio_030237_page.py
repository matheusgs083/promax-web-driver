import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from pages.rotina_page import RotinaPage

try:
    from core.manipulador_download import salvar_arquivo_visual
    from core.validador_visual import validar_elemento
except ImportError:
    salvar_arquivo_visual = None
    validar_elemento = None

class Relatorio030237Page(RotinaPage):

    # --- JAVASCRIPT LEGADO (SEU SCRIPT ORIGINAL) ---
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
            var ev3 = document.createEvent('HTMLEvents'); ev3.initEvent('blur', true, true); el.dispatchEvent(ev3);
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
        if (el.click) { el.click(); }
        else if (el.fireEvent) { el.fireEvent('onclick'); }
        return { ok: true };
    } catch (e) {
        return { ok: false, error: (e && e.message) ? e.message : String(e) };
    }
    """

    JS_RADIO_BY_NAME = """
    var name = arguments[0];
    var val = arguments[1];
    try {
        var els = document.getElementsByName(name);
        if (!els || !els.length) return { ok:false, error:"no-elements" };
        for (var i=0; i<els.length; i++) {
            var el = els[i];
            if ((el.value || "") == val) {
                try { el.scrollIntoView(true); } catch(e) {}
                try { el.focus(); } catch(e) {}
                el.checked = true;
                if (el.click) { el.click(); }
                else if (el.fireEvent) { el.fireEvent('onclick'); }
                if (document.createEvent) {
                    var ev = document.createEvent('HTMLEvents'); ev.initEvent('change', true, true); el.dispatchEvent(ev);
                } else if (el.fireEvent) {
                    try { el.fireEvent('onchange'); } catch(e) {}
                }
                return { ok:true, chosen: val };
            }
        }
        return { ok:false, error:"value-not-found", wanted: val };
    } catch(e) {
        return { ok:false, error:(e && e.message) ? e.message : String(e) };
    }
    """

    JS_SELECT_BY_NAME = """
    var name = arguments[0];
    var val = arguments[1];
    try {
        var els = document.getElementsByName(name);
        if (!els || !els.length) return { ok:false, error:"no-select" };
        var el = els[0];
        try { el.scrollIntoView(true); } catch(e) {}
        try { el.focus(); } catch(e) {}
        el.value = val;
        if (document.createEvent) {
            var ev = document.createEvent('HTMLEvents'); ev.initEvent('change', true, true); el.dispatchEvent(ev);
        } else if (el.fireEvent) {
            try { el.fireEvent('onchange'); } catch(e) {}
        }
        return { ok:true, value: el.value };
    } catch(e) {
        return { ok:false, error:(e && e.message) ? e.message : String(e) };
    }
    """

    # --- LOCATORS ---
    FRAME_ROTINA = 1
    BTN_GERA_EXCEL_1 = (By.NAME, "GerExecl")
    BTN_GERA_EXCEL_2 = (By.NAME, "GeraExcel")

    def gerar_relatorio(self,
                        data_inicial,
                        data_final,
                        tipo_nota=None,
                        itens=None,
                        quebra1=None, quebra2=None, quebra3=None,
                        quebra1_inicial=None, quebra1_final=None,
                        quebra2_inicial=None, quebra2_final=None,
                        quebra3_inicial=None, quebra3_final=None,
                        acao="BotVisualizar",
                        timeout=15,
                        clicar_csv_apos_visualizar=True,
                        timeout_csv=360,
                        nome_arquivo="030237.csv"): # NOME ORIGINAL: nome_arquivo
        """
        Gera o relatório 030237 com os mesmos parâmetros da função original.
        """
        
        self.logger.info(f"--- Gerando Relatório 030237 ({data_inicial} a {data_final}) ---")

        # Validações
        acao = (acao or "BotOk").strip()
        if acao not in ("BotOk", "BotVisualizar"):
            raise ValueError("acao deve ser 'BotOk' ou 'BotVisualizar'")

        if tipo_nota:
            tipo_nota = tipo_nota.strip().upper()
            if tipo_nota not in ("NE", "NS"): raise ValueError("tipo_nota deve ser 'NE' ou 'NS'")

        if itens:
            itens = itens.strip().upper()
            if itens not in ("S", "N", "C"): raise ValueError("itens deve ser 'S', 'N' ou 'C'")

        # Entrar no Frame
        self.switch_to_default_content()
        self.wait.until(EC.frame_to_be_available_and_switch_to_it(self.FRAME_ROTINA))
        
        # 1) QUEBRAS
        self._set_select_js("quebra1", quebra1)
        self._set_select_js("quebra2", quebra2)
        self._set_select_js("quebra3", quebra3)

        # 2) FAIXAS
        campos_faixa = [
            ("quebra1Inicial", quebra1_inicial), ("quebra1Final", quebra1_final),
            ("quebra2Inicial", quebra2_inicial), ("quebra2Final", quebra2_final),
            ("quebra3Inicial", quebra3_inicial), ("quebra3Final", quebra3_final),
        ]
        for name, val in campos_faixa:
            if val is not None:
                self._set_input_js(name, val)

        # 3) DATAS
        self._set_input_js("dataInicial", data_inicial)
        self._set_input_js("dataFinal", data_final)
        self.logger.info(f"Datas setadas: {data_inicial} -> {data_final}")

        # 4) ITENS
        if itens:
            self._set_radio_js("itens", itens)

        # 5) TIPO NOTA
        if tipo_nota:
            self._set_radio_js("notas", tipo_nota)

        # 6) CLICK AÇÃO
        botao = self.find_element((By.NAME, acao))
        res = self.driver.execute_script(self.JS_CLICK_IE, botao)
        if not res.get("ok"):
            raise RuntimeError(f"Falha click {acao}: {res}")
        self.logger.info(f"Botão clicado via JS: {acao}")

        time.sleep(2) 
        self.switch_to_default_content()

        # FLUXO EXPORTAÇÃO
        if acao == "BotVisualizar" and clicar_csv_apos_visualizar:
            self._fluxo_exportar_csv(timeout_csv, nome_arquivo)

        self.switch_to_default_content()
        return True

    def _fluxo_exportar_csv(self, timeout_csv, nome_arquivo):
        self.logger.info("Aguardando tela pós-Visualizar e botão CSV...")
        
        self.switch_to_default_content()
        WebDriverWait(self.driver, timeout_csv).until(EC.frame_to_be_available_and_switch_to_it(self.FRAME_ROTINA))

        # Tenta achar o botão de CSV (fallback de nomes)
        def _achar_botao_csv(d):
            try: return d.find_element(*self.BTN_GERA_EXCEL_1)
            except: pass
            try: return d.find_element(*self.BTN_GERA_EXCEL_2)
            except: return False

        try:
            botao_csv = WebDriverWait(self.driver, timeout_csv).until(_achar_botao_csv)
        except TimeoutException:
            raise RuntimeError(f"Botão CSV não apareceu em {timeout_csv}s.")

        res = self.driver.execute_script(self.JS_CLICK_IE, botao_csv)
        if not res.get("ok"):
            raise RuntimeError(f"Falha click CSV via JS: {res}")
        
        self.logger.info("Botão CSV clicado.")

        if validar_elemento and salvar_arquivo_visual:
            validar_elemento("botaoDownload.png", timeout=360)
            diretorio_destino = os.getenv("DOWNLOAD_DIR", "C:\\Downloads")
            salvar_arquivo_visual(diretorio_destino=diretorio_destino, nome_arquivo_final=nome_arquivo)
        else:
            self.logger.warning("Módulos visuais não carregados.")

    # --- HELPERS JS ---
    def _set_select_js(self, name, value):
        if value is None: return
        res = self.driver.execute_script(self.JS_SELECT_BY_NAME, name, value)
        if not res.get("ok"): raise RuntimeError(f"Falha select {name}={value}: {res}")

    def _set_input_js(self, name, value):
        el = self.find_element((By.NAME, name))
        res = self.driver.execute_script(self.JS_SET_VALUE_IE, el, value)
        if not res.get("ok"): raise RuntimeError(f"Falha set input {name}: {res}")

    def _set_radio_js(self, name, value):
        res = self.driver.execute_script(self.JS_RADIO_BY_NAME, name, value)
        if not res.get("ok"): raise RuntimeError(f"Falha set radio {name}={value}: {res}")