import time

from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pages.common.rotina_page import RotinaPage


class Relatorio031120Page(RotinaPage):
    """
    Rotina 03.11.20.

    HTML base: PW02227R.
    Campos principais:
    - opcaoRel
    - dataInicial / dataFinal
    - veiculoInicial / veiculoFinal
    - cdCampoInicial / cdCampoFinal
    - rtInicial / rtFinal
    - codArmazem
    - BotVisualizar
    """

    FRAME_ROTINA = 1

    def gerar_relatorio(
        self,
        unidade=None,
        opcao_rel="1",
        data_inicial=None,
        data_final=None,
        veiculo_inicial="0",
        veiculo_final="999",
        campo_inicial="0",
        campo_final="999999",
        rt_inicial="0",
        rt_final="99999999999999999999",
        cod_armazem=None,
        incluir_mapa_puxada=None,
        mostrar_ultima_fase=None,
        mostrar_conf_cega=None,
        acao="BotVisualizar",
        clicar_csv_apos_visualizar=True,
        timeout_csv=360,
        nome_arquivo="031120.csv",
    ):
        if unidade is None or isinstance(unidade, list):
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                unidades_alvo=unidade if isinstance(unidade, list) else None,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    unidade=cod,
                    opcao_rel=opcao_rel,
                    data_inicial=data_inicial,
                    data_final=data_final,
                    veiculo_inicial=veiculo_inicial,
                    veiculo_final=veiculo_final,
                    campo_inicial=campo_inicial,
                    campo_final=campo_final,
                    rt_inicial=rt_inicial,
                    rt_final=rt_final,
                    cod_armazem=cod_armazem,
                    incluir_mapa_puxada=incluir_mapa_puxada,
                    mostrar_ultima_fase=mostrar_ultima_fase,
                    mostrar_conf_cega=mostrar_conf_cega,
                    acao=acao,
                    clicar_csv_apos_visualizar=clicar_csv_apos_visualizar,
                    timeout_csv=timeout_csv,
                    nome_arquivo=arq,
                ),
            )

        self.selecionar_unidade(unidade)
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=15)

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.NAME, "opcaoRel"))
            )
        except TimeoutException:
            self.logger.warning("Formulario 031120 demorou a renderizar.")

        try:
            if opcao_rel is not None:
                self.js_set_select_by_name("opcaoRel", str(opcao_rel))
                self.driver.execute_script(
                    "if (typeof HabilitaCheckbox === 'function') HabilitaCheckbox();"
                    "if (typeof TrataArmazem === 'function') TrataArmazem();"
                )
                self.aguardar_loader_oculto(timeout=3)

            campos_input = [
                ("dataInicial", data_inicial),
                ("dataFinal", data_final),
                ("veiculoInicial", veiculo_inicial),
                ("veiculoFinal", veiculo_final),
                ("cdCampoInicial", campo_inicial),
                ("cdCampoFinal", campo_final),
                ("rtInicial", rt_inicial),
                ("rtFinal", rt_final),
            ]
            for name, value in campos_input:
                if value is not None:
                    self.js_set_input_by_name(name, str(value))

            if cod_armazem is not None:
                self.js_set_select_by_name("codArmazem", str(cod_armazem))

            checkboxes = [
                ("idMapaPuxada", incluir_mapa_puxada),
                ("idMostrarUltFase", mostrar_ultima_fase),
                ("idMostrarCnfCega", mostrar_conf_cega),
            ]
            for name, value in checkboxes:
                if value is not None:
                    self.js_set_checkbox_by_name(name, bool(value), force_click=True)

            acao = (acao or "BotVisualizar").strip()
            if acao != "BotVisualizar":
                raise ValueError(f"Acao invalida para 031120: {acao}")

            botao = self.find_element((By.NAME, acao))
            self.js_click_ie(botao)
            time.sleep(2)

        except UnexpectedAlertPresentException:
            self.logger.warning("Alerta durante preenchimento da rotina 031120.")
            self.lidar_com_alertas()
            raise
        finally:
            self.switch_to_default_content()

        if not clicar_csv_apos_visualizar:
            return True

        locators_export = [
            (By.XPATH, "//*[@name='GerExecl' and @type!='hidden']"),
            (By.XPATH, "//*[@name='GeraExcel' and @type!='hidden']"),
            (By.XPATH, "//*[@name='GerExcel' and @type!='hidden']"),
        ]
        return self._fluxo_exportar_csv(
            timeout_csv=timeout_csv,
            nome_arquivo=nome_arquivo,
            timeout_botao=timeout_csv,
            locators_export=locators_export,
        )
