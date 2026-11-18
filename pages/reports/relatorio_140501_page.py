from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pages.common.rotina_page import RotinaPage


class Relatorio140501Page(RotinaPage):
    """14.05.01 (PW04210R): Visualizar seguido da exportação CSV padrão."""

    FRAME_ROTINA = 1
    # O formulário inicial contém um GeraExcel hidden; só aceitar botões.
    BTN_GERA_EXCEL_1 = (By.CSS_SELECTOR, "button[name='GerExecl'],input[type='button'][name='GerExecl']")
    BTN_GERA_EXCEL_2 = (By.CSS_SELECTOR, "button[name='GeraExcel'],input[type='button'][name='GeraExcel']")
    BTN_GERA_EXCEL_3 = (By.CSS_SELECTOR, "button[name='GerExcel'],input[type='button'][name='GerExcel']")

    def gerar_relatorio(
        self, unidade=None, opcao_rel="01", quebra_pagina=False,
        iniFornecedor="0", fimFornecedor="999999",
        iniVencimento="00/00/0000", fimVencimento="99/99/9999",
        iniEmissao="00/00/0000", fimEmissao="99/99/9999",
        iniPortador="0", fimPortador="999", iniEspecie="0", fimEspecie="99",
        iniVinculo="0", fimVinculo="99", iniValor="0,00", fimValor="99999999,99",
        iniCGC="", fimCGC="ZZZZZZZZZZZZ99",
        idListaPrevTodas=False, idListaPrevPendAprov=False,
        idListaPrevAprovadas=False, idListaPrevRejeitadas=False,
        timeout_csv=360, nome_arquivo="140501.csv",
    ):
        inputs = {
            "iniFornecedor": iniFornecedor, "fimFornecedor": fimFornecedor,
            "iniVencimento": iniVencimento, "fimVencimento": fimVencimento,
            "iniEmissao": iniEmissao, "fimEmissao": fimEmissao,
            "iniPortador": iniPortador, "fimPortador": fimPortador,
            "iniEspecie": iniEspecie, "fimEspecie": fimEspecie,
            "iniVinculo": iniVinculo, "fimVinculo": fimVinculo,
            "iniValor": iniValor, "fimValor": fimValor,
            "iniCGC": iniCGC, "fimCGC": fimCGC,
        }
        preferences = {
            "idListaPrevTodas": idListaPrevTodas,
            "idListaPrevPendAprov": idListaPrevPendAprov,
            "idListaPrevAprovadas": idListaPrevAprovadas,
            "idListaPrevRejeitadas": idListaPrevRejeitadas,
        }
        if unidade is None or isinstance(unidade, list):
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                unidades_alvo=unidade if isinstance(unidade, list) else None,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    unidade=cod, opcao_rel=opcao_rel, quebra_pagina=quebra_pagina,
                    **inputs, **preferences, timeout_csv=timeout_csv, nome_arquivo=arq,
                ),
            )

        if opcao_rel not in {"01", "02", "03", "04", "05", "06", "08", "09", "11", "12", "16"}:
            raise ValueError("Classificação inválida para a rotina 140501.")
        self.selecionar_unidade(unidade)
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
        try:
            WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.NAME, "opcaoRel")))
            self.js_set_select_by_name("opcaoRel", opcao_rel)
            for name, value in inputs.items():
                self.js_set_input_by_name(name, str(value))
            self.js_set_checkbox_by_name("quebraPag", bool(quebra_pagina), force_click=False)
            for name, value in preferences.items():
                self.js_set_checkbox_by_name(name, bool(value), force_click=False)
            self.driver.execute_script("if(typeof VerificaOpcao==='function'){VerificaOpcao();}")
            self.js_click_ie(self.find_element((By.NAME, "BotVisualizar")))
            self.switch_to_default_content()
            return self._fluxo_exportar_csv(
                timeout_csv=timeout_csv, nome_arquivo=nome_arquivo,
                timeout_botao=timeout_csv,
                locators_export=(self.BTN_GERA_EXCEL_1, self.BTN_GERA_EXCEL_2, self.BTN_GERA_EXCEL_3),
            )
        finally:
            self.switch_to_default_content()
