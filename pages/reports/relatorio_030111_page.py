from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pages.common.rotina_page import RotinaPage


class Relatorio030111Page(RotinaPage):
    """Rotina 030111 - Relatorio de pedidos com exportacao CSV padrao."""

    FRAME_ROTINA = 1
    BTN_GERA_EXCEL_1 = (By.NAME, "GeraExcel")
    BTN_GERA_EXCEL_2 = (By.NAME, "GerExecl")

    def gerar_relatorio(
        self,
        unidade=None,
        opcao_rel="6",
        grupo_perfil_vendas=None,
        origem=None,
        campo1_inicial=None,
        campo1_final=None,
        campo2_inicial=None,
        campo2_final=None,
        data_pedido=None,
        lista_pedidos=True,
        somente_resumo=False,
        quebra_pagina=False,
        somente_pedidos_ca=False,
        pedidos_agendados_hoje=True,
        somente_data_futura=False,
        somente_pedidos_excecao=False,
        resumo="P",
        ttv="P",
        acao="BotVisualizar",
        clicar_csv_apos_visualizar=True,
        nome_arquivo="030111.csv",
        timeout=20,
        timeout_csv=600,
    ):
        if unidade is None or isinstance(unidade, list):
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                unidades_alvo=unidade if isinstance(unidade, list) else None,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    unidade=cod,
                    opcao_rel=opcao_rel,
                    grupo_perfil_vendas=grupo_perfil_vendas,
                    origem=origem,
                    campo1_inicial=campo1_inicial,
                    campo1_final=campo1_final,
                    campo2_inicial=campo2_inicial,
                    campo2_final=campo2_final,
                    data_pedido=data_pedido,
                    lista_pedidos=lista_pedidos,
                    somente_resumo=somente_resumo,
                    quebra_pagina=quebra_pagina,
                    somente_pedidos_ca=somente_pedidos_ca,
                    pedidos_agendados_hoje=pedidos_agendados_hoje,
                    somente_data_futura=somente_data_futura,
                    somente_pedidos_excecao=somente_pedidos_excecao,
                    resumo=resumo,
                    ttv=ttv,
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
                EC.presence_of_element_located((By.NAME, "opcaoRel"))
            )
        except TimeoutException:
            self.logger.warning("Formulario 030111 demorou a renderizar.")

        self.js_set_select_by_name("opcaoRel", str(opcao_rel))
        self.aguardar_loader_oculto(timeout=5)

        if grupo_perfil_vendas is not None:
            self.js_set_select_by_name("grupoPerfilVendas", str(grupo_perfil_vendas))
        if origem is not None:
            self.js_set_select_by_name("indPalmtop", str(origem))

        inputs = [
            ("campo1Inicial", campo1_inicial),
            ("campo1Final", campo1_final),
            ("campo2Inicial", campo2_inicial),
            ("campo2Final", campo2_final),
            ("dtPedido", data_pedido),
        ]
        for name, value in inputs:
            if value is not None:
                self.js_set_input_by_name(name, value)

        checkboxes = [
            ("listaPedidos", lista_pedidos),
            ("somenteResumo", somente_resumo),
            ("quebraPagina", quebra_pagina),
            ("idSomentePedCa", somente_pedidos_ca),
            ("idPedAgenHoje", pedidos_agendados_hoje),
            ("idSoPedDtFutura", somente_data_futura),
            ("idSoPedExcecao", somente_pedidos_excecao),
        ]
        for name, value in checkboxes:
            if value is not None:
                self.js_set_checkbox_by_name(name, bool(value), force_click=True)

        if resumo is not None:
            self.js_set_radio_by_name("resumo", str(resumo))
        if ttv is not None:
            self.js_set_radio_by_name("ttv", str(ttv))

        acao = (acao or "BotVisualizar").strip()
        self.logger.info("Clicando em %s na rotina 030111", acao)
        self.js_click_ie(self.find_element((By.NAME, acao)))

        self.switch_to_default_content()

        resultado_final = True
        if acao == "BotVisualizar" and clicar_csv_apos_visualizar:
            locators_export = [
                (By.XPATH, "//*[@name='GeraExcel' and @type='hidden']"),
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
