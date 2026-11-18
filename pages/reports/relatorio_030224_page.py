import time

from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pages.common.rotina_page import RotinaPage
from core.config.settings import get_settings


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
        classe_inicial=None,
        classe_final=None,
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
        timeout_csv=360,
        nome_arquivo="030224.csv",
        subpasta_download=None,
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
                # A faixa de Classe Road fica intencionalmente sem alteracao:
                # o Promax aplica o padrao da tela e qualquer preenchimento
                # artificial pode restringir o relatorio indevidamente.
                ("cdVisao", cd_visao),
            ]
            for name, value in campos_input:
                if value is not None:
                    self.js_set_input_by_name(name, str(value))

            if data_inicial is not None or data_final is not None:
                filtros_data = self.driver.execute_script(
                    """
                    var campos = document.getElementsByTagName('*');
                    var dados = [];
                    for (var i = 0; i < campos.length; i++) {
                        var campo = campos[i];
                        var nome = String(campo.name || '');
                        if (/data|dt/i.test(nome)) dados.push([nome, String(campo.value || '')]);
                    }
                    return dados;
                    """
                ) or []
                self.logger.info(
                    "030224 filtros de data antes de visualizar: solicitado=%s a %s; formulario=%s",
                    data_inicial,
                    data_final,
                    filtros_data,
                )
                valores = {str(nome): str(valor) for nome, valor in filtros_data}
                if (
                    (data_inicial is not None and valores.get("dataInicial") != str(data_inicial))
                    or (data_final is not None and valores.get("dataFinal") != str(data_final))
                ):
                    raise RuntimeError(
                        "A rotina 030224 não manteve o período solicitado no formulário: "
                        f"{valores}"
                    )

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

        if not clicar_csv_apos_visualizar:
            return True

        locators_export = [
            (By.XPATH, "//*[@name='GerExecl' and @type!='hidden']"),
            (By.XPATH, "//*[@name='GeraExcel' and @type!='hidden']"),
            (By.XPATH, "//*[@name='GerExcel' and @type!='hidden']"),
        ]
        # A 03.02.24 da Liga tem uma pasta de publicação específica para cada
        # visão. Reaplicamos o destino imediatamente antes da exportação: a
        # rotina abre/fecha janelas a cada unidade e o atributo herdado pode
        # voltar a ``None`` nesse fluxo, fazendo o arquivo cair na raiz de
        # Relatorios e ser ignorado pela importação automática da Liga.
        if subpasta_download is not None:
            self.subpasta_download = subpasta_download
        self.logger.info(
            "030224 destino de exportação: %s",
            getattr(self, "subpasta_download", None) or "<raiz>",
        )

        return self._fluxo_exportar_csv(
            timeout_csv=timeout_csv,
            nome_arquivo=nome_arquivo,
            timeout_botao=timeout_csv,
            locators_export=locators_export,
            # A exportação HTTP direta da 03.02.24 perde o contexto da
            # consulta visualizada e pode reutilizar um período anterior.
            # Pelo clique visual, o Promax mantém os filtros aplicados.
            usar_download_http=False,
            # A publicacao automatica da Liga monitora estas subpastas. O
            # destino explicito evita que a captura HTTP use a raiz de
            # Relatorios e o renomeador descarte a visao correspondente.
            diretorio_destino=(
                get_settings().download_dir / subpasta_download
                if subpasta_download
                else None
            ),
        )
