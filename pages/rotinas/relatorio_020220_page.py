import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from pages.rotina_page import RotinaPage


class Relatorio020220Page(RotinaPage):
    """
    Rotina: Relatório de Comodatos (Situação / Clientes)
    call: 02022000000000
    """

    FRAME_ROTINA = 1

    # Export
    BTN_GERA_EXCEL_1 = (By.NAME, "GerExecl")
    BTN_GERA_EXCEL_2 = (By.NAME, "GeraExcel")

    def gerar_relatorio(
        self,
        unidade=None,

        # 1) SELECTS PRINCIPAIS
        opcao_rel="01",           # OBRIGATÓRIO: "01" (Geral) definido como padrão para evitar 'Informação inválida'
        perfil_vendas=None,
        grupo_perfil_vendas=None,

        # 2) PREFERÊNCIAS (Checkboxes)
        somente_resumo=None,
        id_sintetico=None,
        ordem_vencto=None,
        id_np_historico=None,     
        simular_baixa=None,
        omitir_mapa=None,         
        exibe_inf_documentos=None,

        # 3) TIPO DE MERCADORIA
        mercadoria_todos=True,
        mercadoria_vasilhame=None,
        mercadoria_garrafeira=None,
        mercadoria_sopi_visa=None,
        mercadoria_outros_mat=None,
        mercadoria_barril_cilindro=None,
        mercadoria_chopp_post=None,
        mercadoria_outros_ref=None,
        mercadoria_pit_stop=None,

        # 4) SITUAÇÃO COMODATOS E CLIENTES (Radios)
        selecao_comodatos=None,
        situacao_clientes=None,

        # 5) SELEÇÕES (Inputs de Intervalo)
        data_inicial=None,
        data_final=None,
        area_inicial=None,
        area_final=None,
        setor_inicial=None,
        setor_final=None,
        campo_inicial=None,
        campo_final=None,
        rota_inicial=None,
        rota_final=None,
        segmento_inicial=None,
        segmento_final=None,
        cliente_inicial=None,
        cliente_final=None,
        material_inicial=None,
        material_final=None,

        # 6) MULTI CDD & CONSOLIDAÇÃO
        visao_multi_cdd=None,
        selecao_multi_cdd=None,
        cd_visao=None,
        tp_consolidacao=None,

        acao="BotVisualizar",
        clicar_csv_apos_visualizar=True,
        timeout_csv=600,
        nome_arquivo="relatorio_comodatos.csv",
    ):

        # === LOOP (MULTI-UNIDADES) ===
        if unidade is None or isinstance(unidade, list):
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                unidades_alvo=unidade if isinstance(unidade, list) else None,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    unidade=cod,
                    opcao_rel=opcao_rel,
                    perfil_vendas=perfil_vendas,
                    grupo_perfil_vendas=grupo_perfil_vendas,
                    somente_resumo=somente_resumo,
                    id_sintetico=id_sintetico,
                    ordem_vencto=ordem_vencto,
                    id_np_historico=id_np_historico,
                    simular_baixa=simular_baixa,
                    omitir_mapa=omitir_mapa,
                    exibe_inf_documentos=exibe_inf_documentos,
                    mercadoria_todos=mercadoria_todos,
                    mercadoria_vasilhame=mercadoria_vasilhame,
                    mercadoria_garrafeira=mercadoria_garrafeira,
                    mercadoria_sopi_visa=mercadoria_sopi_visa,
                    mercadoria_outros_mat=mercadoria_outros_mat,
                    mercadoria_barril_cilindro=mercadoria_barril_cilindro,
                    mercadoria_chopp_post=mercadoria_chopp_post,
                    mercadoria_outros_ref=mercadoria_outros_ref,
                    mercadoria_pit_stop=mercadoria_pit_stop,
                    selecao_comodatos=selecao_comodatos,
                    situacao_clientes=situacao_clientes,
                    data_inicial=data_inicial,
                    data_final=data_final,
                    area_inicial=area_inicial,
                    area_final=area_final,
                    setor_inicial=setor_inicial,
                    setor_final=setor_final,
                    campo_inicial=campo_inicial,
                    campo_final=campo_final,
                    rota_inicial=rota_inicial,
                    rota_final=rota_final,
                    segmento_inicial=segmento_inicial,
                    segmento_final=segmento_final,
                    cliente_inicial=cliente_inicial,
                    cliente_final=cliente_final,
                    material_inicial=material_inicial,
                    material_final=material_final,
                    visao_multi_cdd=visao_multi_cdd,
                    selecao_multi_cdd=selecao_multi_cdd,
                    cd_visao=cd_visao,
                    tp_consolidacao=tp_consolidacao,
                    acao=acao,
                    clicar_csv_apos_visualizar=clicar_csv_apos_visualizar,
                    timeout_csv=timeout_csv,
                    nome_arquivo=arq,
                )
            )

        # === EXECUÇÃO ÚNICA ===
        self.selecionar_unidade(unidade)
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=20)

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.NAME, "opcaoRel"))
            )
        except TimeoutException:
            self.logger.warning("Formulário demorou a renderizar. Pode haver falha no preenchimento.")

        # -----------------------------
        # 1) SELECTS PRINCIPAIS (OBRIGATÓRIO)
        # -----------------------------
        if not opcao_rel:
            opcao_rel = "01" # Prevenção extra caso seja passado None vazio
            
        self.logger.info(f"Configurando Classificação (opcaoRel): {opcao_rel}")
        self.js_set_select_by_name("opcaoRel", str(opcao_rel))
        
        # OBRIGATÓRIO: Dar tempo ao JS do IE para executar o Habilitar() e destravar os demais campos
        time.sleep(1)

        if perfil_vendas is not None:
            self.js_set_select_by_name("perfilVendas", str(perfil_vendas))
        if grupo_perfil_vendas is not None:
            self.js_set_select_by_name("grupoPerfilVendas", str(grupo_perfil_vendas))

        # -----------------------------
        # O restante do código segue idêntico a partir daqui...
        # -----------------------------
        
        # 2) PREFERÊNCIAS E FLAGS SOLTAS
        if somente_resumo is not None: self.js_set_checkbox_by_name("somenteResumo", bool(somente_resumo), force_click=True)
        if id_sintetico is not None: self.js_set_checkbox_by_name("idSintetico", bool(id_sintetico), force_click=True)
        if ordem_vencto is not None: self.js_set_checkbox_by_name("ordemVencto", bool(ordem_vencto), force_click=True)
        if id_np_historico is not None: self.js_set_checkbox_by_name("idNpHistorico", bool(id_np_historico), force_click=True)
        if simular_baixa is not None: self.js_set_checkbox_by_name("simularBaixa", bool(simular_baixa), force_click=True)
        if omitir_mapa is not None: self.js_set_checkbox_by_name("omitirMapa", bool(omitir_mapa), force_click=True)
        if exibe_inf_documentos is not None: self.js_set_checkbox_by_name("idExibeInfDocumentos", bool(exibe_inf_documentos), force_click=True)

        if visao_multi_cdd is not None: self.js_set_radio_by_name("idVisaoMultiCdd", str(visao_multi_cdd))
        if selecao_multi_cdd is not None: self.js_set_select_by_name("idSelecaoMultiCdd", str(selecao_multi_cdd))

        # 3) TIPO DE MERCADORIA
        self._aplicar_tipo_mercadoria(
            mercadoria_todos, mercadoria_vasilhame, mercadoria_garrafeira,
            mercadoria_sopi_visa, mercadoria_outros_mat, mercadoria_barril_cilindro,
            mercadoria_chopp_post, mercadoria_outros_ref, mercadoria_pit_stop
        )

        # 4) RADIOS (Situações)
        if selecao_comodatos is not None: self.js_set_radio_by_name("selecao", str(selecao_comodatos))
        if situacao_clientes is not None: self.js_set_radio_by_name("situacao", str(situacao_clientes))

        # 5) INPUTS DE SELEÇÃO
        if data_inicial is not None: self.js_set_input_by_name("dataInicial", data_inicial)
        if data_final is not None: self.js_set_input_by_name("dataFinal", data_final)

        if area_inicial is not None: self.js_set_input_by_name("areaInicial", area_inicial)
        if area_final is not None: self.js_set_input_by_name("areaFinal", area_final)
        if setor_inicial is not None: self.js_set_input_by_name("setorInicial", setor_inicial)
        if setor_final is not None: self.js_set_input_by_name("setorFinal", setor_final)
        if campo_inicial is not None: self.js_set_input_by_name("campoInicial", campo_inicial)
        if campo_final is not None: self.js_set_input_by_name("campoFinal", campo_final)
        if rota_inicial is not None: self.js_set_input_by_name("rotaInicial", rota_inicial)
        if rota_final is not None: self.js_set_input_by_name("rotaFinal", rota_final)
        if segmento_inicial is not None: self.js_set_input_by_name("segmentoInicial", segmento_inicial)
        if segmento_final is not None: self.js_set_input_by_name("segmentoFinal", segmento_final)
        if cliente_inicial is not None: self.js_set_input_by_name("clienteInicial", cliente_inicial)
        if cliente_final is not None: self.js_set_input_by_name("clienteFinal", cliente_final)
        if material_inicial is not None: self.js_set_input_by_name("materialInicial", material_inicial)
        if material_final is not None: self.js_set_input_by_name("materialFinal", material_final)

        # 6) CONSOLIDAÇÃO
        if cd_visao is not None: self.js_set_input_by_name("cdVisao", str(cd_visao))
        if tp_consolidacao is not None: self.js_set_radio_by_name("tpConsolidacao", str(tp_consolidacao))

        #------------------------------
        # 7) AÇÃO FINAL E EXPORTAÇÃO
        # -----------------------------
        acao = (acao or "BotVisualizar").strip()
        self.logger.info(f"Clicando em {acao}")
        btn = self.find_element((By.NAME, acao))
        self.js_click_ie(btn)

        time.sleep(2)
        self.switch_to_default_content()

        resultado_final = True

        if acao == "BotVisualizar" and clicar_csv_apos_visualizar:
            # Filtra os locators para IGNORAR inputs ocultos que têm o mesmo nome do botão
            locators_reais = [
                (By.XPATH, "//*[@name='GerExecl' and @type!='hidden']"),
                (By.XPATH, "//*[@name='GeraExcel' and @type!='hidden']"),
                (By.XPATH, "//*[@name='GerExcel' and @type!='hidden']")
            ]
            
            resultado_final = self._fluxo_exportar_csv(
                timeout_csv=timeout_csv,
                nome_arquivo=nome_arquivo,
                timeout_botao=timeout_csv,
                locators_export=locators_reais  # <--- Injetamos os locators blindados aqui
            )

        self.switch_to_default_content()
        return resultado_final
    def _aplicar_tipo_mercadoria(self, todos, vasilhame, garrafeira, sopi_visa, 
                                 outros_mat, barril, chopp, outros_ref, pitstop):
        if todos:
            self.logger.info("Mercadoria: marcando 'Todos' (limpa os restantes)")
            self.js_set_checkbox_by_name("todos", True, force_click=True)
            return

        self.logger.info("Mercadoria: desmarcando 'Todos' para ativar os específicos")
        self.js_set_checkbox_by_name("todos", False, force_click=True)
        time.sleep(0.5) 

        if vasilhame is not None: self.js_set_checkbox_by_name("vasilhame", bool(vasilhame), force_click=True)
        if garrafeira is not None: self.js_set_checkbox_by_name("garrafeira", bool(garrafeira), force_click=True)
        if sopi_visa is not None: self.js_set_checkbox_by_name("idSopiVisa", bool(sopi_visa), force_click=True)
        if outros_mat is not None: self.js_set_checkbox_by_name("idOutrosMat", bool(outros_mat), force_click=True)
        if barril is not None: self.js_set_checkbox_by_name("idBarrilCilindro", bool(barril), force_click=True)
        if chopp is not None: self.js_set_checkbox_by_name("idChoppPost", bool(chopp), force_click=True)
        if outros_ref is not None: self.js_set_checkbox_by_name("idOutrosRef", bool(outros_ref), force_click=True)
        if pitstop is not None: self.js_set_checkbox_by_name("idPitStop", bool(pitstop), force_click=True)