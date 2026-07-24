from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pages.common.rotina_page import RotinaPage


class Relatorio020304Page(RotinaPage):
    """Rotina 020304 - CSV padrao."""

    FRAME_ROTINA = 1
    BTN_GERA_EXCEL_1 = (By.NAME, "GeraExcel")
    BTN_GERA_EXCEL_2 = (By.NAME, "GerExecl")

    def gerar_relatorio(
        self,
        unidade=None,
        acao="BotVisualizar",
        clicar_csv_apos_visualizar=True,
        nome_arquivo="020304.csv",
        timeout=20,
        timeout_csv=600,
    ):
        if unidade is None or isinstance(unidade, list):
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                unidades_alvo=unidade if isinstance(unidade, list) else None,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    unidade=cod,
                    acao=acao,
                    clicar_csv_apos_visualizar=clicar_csv_apos_visualizar,
                    nome_arquivo=arq,
                    timeout=timeout,
                    timeout_csv=timeout_csv,
                ),
            )

        self.selecionar_unidade(unidade)
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=timeout)

        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.NAME, acao))
            )
        except TimeoutException:
            self.logger.warning("Formulario 020304 demorou a renderizar.")

        acao = (acao or "BotVisualizar").strip()
        self.logger.info("Clicando em %s na rotina 020304", acao)
        self.js_click_ie(self.find_element((By.NAME, acao)))

        self.switch_to_default_content()

        resultado_final = True
        if acao == "BotVisualizar" and clicar_csv_apos_visualizar:
            locators_export = [
                (By.XPATH, "//*[@name='GeraExcel']"),
                (By.XPATH, "//*[@name='GerExecl']"),
                (By.XPATH, "//*[@name='GerExcel']"),
            ]
            resultado_final = self._fluxo_exportar_csv(
                timeout_csv=timeout_csv,
                nome_arquivo=nome_arquivo,
                timeout_botao=timeout_csv,
                locators_export=locators_export,
            )

        self.switch_to_default_content()
        return resultado_final
