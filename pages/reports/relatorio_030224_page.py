import time

from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.config.settings import get_settings
from pages.common.rotina_page import RotinaPage


class Relatorio030224Page(RotinaPage):
    """
    Rotina 03.02.24 (PW02084R) - Devolucoes.

    Opcoes principais de opcaoRel:
    - 02: Setor
    - 03: Mapa
    - 08: Motorista
    - 10: Ajudante 1 / Ajudante 2
    """

    FRAME_ROTINA = 1

    def gerar_relatorio(
        self,
        unidade=None,
        opcao_rel="03",
        data_inicial=None,
        data_final=None,
        campo_inicial="0",
        campo_final="999999",
        nr_road_inicial="0",
        nr_road_final="99",
        classe_inicial="0",
        classe_final="Z",
        quebra_pagina=None,
        lista_itens=None,
        somente_resumo=None,
        endereco_cliente=None,
        setores_inativos=None,
        converte=None,
        resumo_visao=None,
        selecionou_rota=None,
        selecionou_as=None,
        responsab_processo=None,
        todas_operacoes=None,
        resumo=None,
        visao_multi_cdd=None,
        selecao_multi_cdd=None,
        cd_visao=None,
        tp_consolidacao=None,
        acao="BotVisualizar",
        clicar_csv_apos_visualizar=True,
        formato_saida="csv",
        timeout_csv=360,
        timeout_pdf=550,
        nome_arquivo="030224.csv",
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
                    campo_inicial=campo_inicial,
                    campo_final=campo_final,
                    nr_road_inicial=nr_road_inicial,
                    nr_road_final=nr_road_final,
                    classe_inicial=classe_inicial,
                    classe_final=classe_final,
                    quebra_pagina=quebra_pagina,
                    lista_itens=lista_itens,
                    somente_resumo=somente_resumo,
                    endereco_cliente=endereco_cliente,
                    setores_inativos=setores_inativos,
                    converte=converte,
                    resumo_visao=resumo_visao,
                    selecionou_rota=selecionou_rota,
                    selecionou_as=selecionou_as,
                    responsab_processo=responsab_processo,
                    todas_operacoes=todas_operacoes,
                    resumo=resumo,
                    visao_multi_cdd=visao_multi_cdd,
                    selecao_multi_cdd=selecao_multi_cdd,
                    cd_visao=cd_visao,
                    tp_consolidacao=tp_consolidacao,
                    acao=acao,
                    clicar_csv_apos_visualizar=clicar_csv_apos_visualizar,
                    formato_saida=formato_saida,
                    timeout_csv=timeout_csv,
                    timeout_pdf=timeout_pdf,
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
            self.logger.warning("Formulario 030224 demorou a renderizar.")

        try:
            if opcao_rel is not None:
                self.js_set_select_by_name("opcaoRel", str(opcao_rel))
                self.driver.execute_script("if (typeof Habilita === 'function') Habilita();")
                self.aguardar_loader_oculto(timeout=3)

            campos_input = [
                ("dataInicial", data_inicial),
                ("dataFinal", data_final),
                ("campoInicial", campo_inicial),
                ("campoFinal", campo_final),
                ("nrRoadInicial", nr_road_inicial),
                ("nrRoadFinal", nr_road_final),
                ("classeInicial", classe_inicial),
                ("classeFinal", classe_final),
                ("cdVisao", cd_visao),
            ]
            for name, value in campos_input:
                if value is not None:
                    self.js_set_input_by_name(name, str(value))

            checkboxes = [
                ("quebraPagina", quebra_pagina),
                ("listaItens", lista_itens),
                ("somenteResumo", somente_resumo),
                ("enderecoCliente", endereco_cliente),
                ("setoresInativos", setores_inativos),
                ("selecionouROTA", selecionou_rota),
                ("selecionouAS", selecionou_as),
                ("responsabProcesso", responsab_processo),
                ("todasOperacoes", todas_operacoes),
            ]
            for name, value in checkboxes:
                if value is not None:
                    self.js_set_checkbox_by_name(name, bool(value), force_click=True)
                    if name == "somenteResumo":
                        self.driver.execute_script("if (typeof TestaSomenteResumo === 'function') TestaSomenteResumo();")

            radios = [
                ("converte", converte),
                ("resumoVisao", resumo_visao),
                ("resumo", resumo),
                ("idVisaoMultiCdd", visao_multi_cdd),
                ("tpConsolidacao", tp_consolidacao),
            ]
            for name, value in radios:
                if value is not None:
                    self.js_set_radio_by_name(name, str(value))

            if selecao_multi_cdd is not None:
                self.js_set_select_by_name("idSelecaoMultiCdd", str(selecao_multi_cdd))

            acao = (acao or "BotVisualizar").strip()
            if acao != "BotVisualizar":
                raise ValueError(f"Acao invalida para 030224: {acao}")

            botao = self.find_element((By.NAME, acao))
            self.js_click_ie(botao)
            time.sleep(2)

        except UnexpectedAlertPresentException:
            self.logger.warning("Alerta durante preenchimento da rotina 030224.")
            self.lidar_com_alertas()
            raise
        finally:
            self.switch_to_default_content()

        if str(formato_saida or "csv").strip().lower() == "pdf":
            return self._fluxo_exportar_pdf(
                timeout_pdf=timeout_pdf,
                nome_arquivo=nome_arquivo,
            )

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

    def _fluxo_exportar_pdf(self, *, timeout_pdf=550, nome_arquivo="030224.pdf"):
        """Exporta o resultado visualizado pelo botao GerPDF da 03.02.24."""

        self.logger.info("Aguardando tela pos-Visualizar e botao PDF da rotina 030224...")
        self.switch_to_default_content()
        try:
            WebDriverWait(self.driver, timeout_pdf).until(
                EC.frame_to_be_available_and_switch_to_it(self.FRAME_ROTINA)
            )
        except UnexpectedAlertPresentException:
            mensagens = self.lidar_com_alertas(tentativas=2, timeout=2, timeout_entre_alertas=1, max_alertas=10)
            detalhe = " | ".join(mensagens) if mensagens else "Alerta sem texto capturado"
            self.switch_to_default_content()
            return False, f"Alerta antes da exportacao PDF: {detalhe}"
        except TimeoutException:
            self.driver.switch_to.frame(self.FRAME_ROTINA)

        try:
            botao_pdf = WebDriverWait(self.driver, timeout_pdf).until(
                lambda driver: driver.find_element(By.NAME, "GerPDF")
            )
            diretorio_base = get_settings().download_dir
            subpasta = getattr(self, "subpasta_download", None)
            diretorio = diretorio_base / subpasta if subpasta else diretorio_base
            nome_pdf = str(nome_arquivo or "030224.pdf")
            if not nome_pdf.lower().endswith(".pdf"):
                nome_pdf = f"{nome_pdf}.pdf"

            from core.services.report_download_service import (
                capturar_download_por_formulario,
                capturar_download_relatorio,
            )

            resultado_http = capturar_download_por_formulario(
                self.driver,
                botao_pdf,
                nome_pdf,
                diretorio_intermediario=diretorio,
                extensao_final=".pdf",
            )
            if resultado_http[0]:
                self.logger.info("PDF 030224 capturado diretamente por HTTP: %s", resultado_http[1])
                return resultado_http

            self.logger.info("PDF HTTP indisponivel na 030224 (%s); mantendo fluxo visual.", resultado_http[1])
            self.js_click_ie(botao_pdf)
            pdf_path = diretorio / nome_pdf
            resultado_visual = capturar_download_relatorio(
                nome_arquivo_final=nome_pdf,
                diretorio_intermediario=str(diretorio),
                extensao_final=".pdf",
                driver=self.driver,
            )
            if resultado_visual[0]:
                return True, str(pdf_path)
            return resultado_visual
        except UnexpectedAlertPresentException:
            mensagens = self.lidar_com_alertas(tentativas=2, timeout=2, timeout_entre_alertas=1, max_alertas=10)
            detalhe = " | ".join(mensagens) if mensagens else "Alerta sem texto capturado"
            return False, f"Alerta ao clicar no botao PDF: {detalhe}"
        except TimeoutException:
            return False, "Botao PDF da rotina 030224 nao apareceu apos visualizar."
        finally:
            self.switch_to_default_content()
