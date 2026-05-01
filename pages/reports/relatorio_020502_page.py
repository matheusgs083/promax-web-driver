from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pages.common.rotina_page import RotinaPage


class Relatorio020502Page(RotinaPage):
    """
    Rotina: Relatorio 02.05.02
    interno: PW03064R
    """

    FRAME_ROTINA = 1
    BTN_GERA_EXCEL_1 = (By.NAME, "GerExecl")
    BTN_GERA_EXCEL_2 = (By.NAME, "GeraExcel")
    BTN_GERA_EXCEL_3 = (By.NAME, "GerExcel")

    def gerar_relatorio(
        self,
        unidade=None,
        opcao_rel="1",
        consolida_armazens=None,
        somente_carregado=None,
        diferenca_consolidada_por_armazem_item=None,
        listar_produtos=True,
        listar_vasilhames_garrafeiras=True,
        tipo_data="E",
        periodo_inicial=None,
        periodo_final=None,
        mercadoria_inicial=None,
        mercadoria_final=None,
        armazem_inicial=None,
        armazem_final=None,
        deposito_inicial=None,
        deposito_final=None,
        acao="BotVisualizar",
        clicar_csv_apos_visualizar=True,
        timeout_csv=360,
        nome_arquivo="020502.csv",
    ):
        if unidade is None or isinstance(unidade, list):
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                unidades_alvo=unidade if isinstance(unidade, list) else None,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    unidade=cod,
                    opcao_rel=opcao_rel,
                    consolida_armazens=consolida_armazens,
                    somente_carregado=somente_carregado,
                    diferenca_consolidada_por_armazem_item=diferenca_consolidada_por_armazem_item,
                    listar_produtos=listar_produtos,
                    listar_vasilhames_garrafeiras=listar_vasilhames_garrafeiras,
                    tipo_data=tipo_data,
                    periodo_inicial=periodo_inicial,
                    periodo_final=periodo_final,
                    mercadoria_inicial=mercadoria_inicial,
                    mercadoria_final=mercadoria_final,
                    armazem_inicial=armazem_inicial,
                    armazem_final=armazem_final,
                    deposito_inicial=deposito_inicial,
                    deposito_final=deposito_final,
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
            self.logger.warning("O formulario demorou a renderizar. O preenchimento pode falhar.")

        try:
            if opcao_rel is not None:
                self.logger.info(f"Configurando Classificacao (opcaoRel): {opcao_rel}")
                self.js_set_select_by_name("opcaoRel", str(opcao_rel))
                self.driver.execute_script("if (typeof Habilita === 'function') Habilita();")

            if consolida_armazens is not None:
                self.js_set_checkbox_by_name("idConsolida", bool(consolida_armazens), force_click=True)
            if somente_carregado is not None:
                self.js_set_checkbox_by_name("idSomenteCarregado", bool(somente_carregado), force_click=True)
            if diferenca_consolidada_por_armazem_item is not None:
                self.js_set_checkbox_by_name(
                    "idDifConsolidaArmazem",
                    bool(diferenca_consolidada_por_armazem_item),
                    force_click=True,
                )

            if listar_produtos is not None:
                self.js_set_checkbox_by_name("idListarProdutos", bool(listar_produtos), force_click=True)
            if listar_vasilhames_garrafeiras is not None:
                self.js_set_checkbox_by_name("idListarVasGarraf", bool(listar_vasilhames_garrafeiras), force_click=True)

            if tipo_data is not None:
                self.js_set_radio_by_name("tpData", str(tipo_data).upper())

            campos_input = [
                ("periodoInicial", periodo_inicial),
                ("periodoFinal", periodo_final),
                ("cdMercadoriaInicial", mercadoria_inicial),
                ("cdMercadoriaFinal", mercadoria_final),
                ("cdArmazemInicial", armazem_inicial),
                ("cdArmazemFinal", armazem_final),
                ("cdDepositoInicial", deposito_inicial),
                ("cdDepositoFinal", deposito_final),
            ]
            for name, value in campos_input:
                if value is not None:
                    self.js_set_input_by_name(name, str(value))

            acao = (acao or "BotVisualizar").strip()
            self.logger.info(f"Clicando em {acao}")
            btn = self.find_element((By.NAME, acao))
            self.js_click_ie(btn)

        except UnexpectedAlertPresentException:
            self.logger.warning("Alerta durante preenchimento. Limpando e abortando unidade.")
            self.lidar_com_alertas()
            raise

        self.switch_to_default_content()

        resultado_final = True

        if acao == "BotVisualizar" and clicar_csv_apos_visualizar:
            locators_export = [
                (By.XPATH, "//*[@name='GerExecl' and @type!='hidden']"),
                (By.XPATH, "//*[@name='GeraExcel' and @type!='hidden']"),
                (By.XPATH, "//*[@name='GerExcel' and @type!='hidden']"),
            ]
            resultado_final = self._fluxo_exportar_csv(
                timeout_csv=timeout_csv,
                nome_arquivo=nome_arquivo,
                timeout_botao=timeout_csv,
                locators_export=locators_export,
            )

        self.switch_to_default_content()
        return resultado_final
