import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from pages.common.rotina_page import RotinaPage

try:
    from core.files.manipulador_download import salvar_arquivo_visual
    from core.tools.validador_visual import validar_elemento
except ImportError:
    salvar_arquivo_visual = None
    validar_elemento = None


class Relatorio030237Page(RotinaPage):
    """
    Rotina 03.02.37 (PW02099R) - Relatório de Vendas / Faturamento / Quebras.

    Mapeamento de Quebras (quebra1, quebra2, quebra3):
    00 → --Selecionar--
    01 → Geral
    02 → Comercial - NF
    03 → Gte Vendas - NF
    04 → Area - NF
    05 → Setor - NF
    06 → Vendedor
    07 → Cliente
    08 → Municipio
    09 → Categoria
    10 → Segmto Cerv
    11 → Rede
    12 → Tipo Movto
    13 → CTO
    14 → Operacao
    15 → Forma Pagto
    16 → Cond Pagto
    17 → Transp.
    18 → Nivel
    19 → Mapa
    20 → Comercial - Cli
    21 → Gte Vendas - Cli
    22 → Area - Cli
    23 → Setor - Cli
    24 → Grupo de Rede
    25 → Motorista
    26 → Cli Corporativo
    27 → NR Roadashow
    28 → Classe Road
    29 → Codigo Fiscal
    30 → Cli Chave SAP
    31 → Conferencia SAP
    32 → F A D
    33 → Armazém
    34 → Distrital - NF
    35 → Distrital - Cli
    36 → Ajudante 1
    37 → Ajudante 2
    38 → Codigo Contabil
    39 → Veiculo
    40 → VDE - Remuneração

    Mapeamento de Origem (indPalmtop):
    ""  → --Todos--
    "S" → Palmtop
    "D" → Digitado
    "R" → Descarga Remota
    "E" → EDI
    "T" → Telemarketing
    "B" → Balcão
    "P" → PCA
    "G" → Reprogramação de Pedido
    "H" → Pedidos Agendados
    "F" → Venda para Funcionários
    "V" → Televendas
    "Y" → Site
    "C" → GCAD
    "J" → Evento
    "I" → Digitado Televendas
    """

    # --- LOCATORS ---
    FRAME_ROTINA = 1
    BTN_GERA_EXCEL_1 = (By.NAME, "GerExecl")
    BTN_GERA_EXCEL_2 = (By.NAME, "GeraExcel")

    def gerar_relatorio(
        self,
        data_inicial,
        data_final,
        unidade=None,
        tipo_nota=None,          # 'notas' ('NE'=Entrada, 'NS'=Saída)
        notas=None,              # alias para tipo_nota
        itens=None,              # 'itens' ('S'=Sim, 'N'=Não, 'C'=Caneta)
        quebra1=None,            # 'quebra1' ('00'..'40')
        quebra2=None,            # 'quebra2' ('00'..'40')
        quebra3=None,            # 'quebra3' ('00'..'40')
        quebra1_inicial=None,
        quebra1_final=None,
        quebra2_inicial=None,
        quebra2_final=None,
        quebra3_inicial=None,
        quebra3_final=None,
        ind_palmtop=None,        # 'indPalmtop' (Origem)
        origem=None,             # alias para ind_palmtop
        status_nota=None,        # 'statusNota' ('E'=Emitida, 'L'=Liberada)
        converte_caixas=None,    # 'converteCaixas' (bool/'S')
        quebra_pagina=None,      # 'quebraPagina' (bool/'S')
        pis_cofins=None,         # 'pisCofins' (bool/'S')
        lista_nota_compra=None,  # 'listaNotaCompra' (bool/'S')
        lista_nfs_compra=None,   # alias para lista_nota_compra
        lista_notas_apagar=None, # 'listaNotasApagar' (bool/'S')
        id_notas_transf=None,    # 'idNotasTransf' (bool/'S')
        somente_nfs_transf=None, # alias para id_notas_transf
        visao=None,              # 'visao' ('F'=Fiscal, 'E'=Entrega, 'P'=Pedido, 'V'=2V)
        id_agrupar_televendas=None, # 'idAgruparTelevendas' (bool/'S')
        agrupar_televendas=None,    # alias para id_agrupar_televendas
        id_somente_venda_bonif=None,# 'idSomenteVendaBonif' (bool/'S')
        somente_venda_bonif=None,   # alias para id_somente_venda_bonif
        id_somente_metalfrio=None,  # 'idSomenteMetalfrio' (bool/'S')
        visao_metalfrio=None,       # alias para id_somente_metalfrio
        id_visao_ipi_bonif=None,    # 'idVisaoIpiBonif' (bool/'S')
        visao_ipi_bonif=None,       # alias para id_visao_ipi_bonif
        valor_inicial=None,      # 'valorInicial'
        valor_final=None,        # 'valorFinal'
        embalagem_inicial=None,  # 'embalagemInicial'
        embalagem_final=None,    # 'embalagemFinal'
        mercadoria_inicial=None, # 'mercadoriaInicial'
        mercadoria_final=None,   # 'mercadoriaFinal'
        cd_visao=None,           # 'cdVisao'
        tp_consolidacao=None,    # 'tpConsolidacao' ('1', '2', '3', '4', '5')
        visao_multi_cdd=None,    # 'idVisaoMultiCdd' ('C', 'G')
        selecao_multi_cdd=None,  # 'idSelecaoMultiCdd' ('T', 'S', 'M')
        # --- Status NF-e (Modal DivStatusNfe) ---
        st_nfe_todos=None,
        st_nfe_autorizada=None,
        st_nfe_denegada=None,
        st_nfe_contingencia=None,
        st_nfe_enviada=None,
        st_nfe_nao_enviada=None,
        st_nfe_rejeitada=None,
        st_nfe_conting_autoriz=None,
        st_nfe_conting_denegada=None,
        st_nfe_conting_enviada=None,
        st_nfe_conting_nao_env=None,
        st_nfe_conting_rejeitada=None,
        status_nfe=None,
        acao="BotVisualizar",
        timeout=15,
        clicar_csv_apos_visualizar=True,
        timeout_csv=360,
        nome_arquivo="030237.csv",
    ):

        # === LOOP (MULTI-UNIDADES) via RotinaPage ===
        if unidade is None or isinstance(unidade, list):
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                unidades_alvo=unidade if isinstance(unidade, list) else None,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    data_inicial=data_inicial,
                    data_final=data_final,
                    unidade=cod,
                    tipo_nota=tipo_nota,
                    notas=notas,
                    itens=itens,
                    quebra1=quebra1,
                    quebra2=quebra2,
                    quebra3=quebra3,
                    quebra1_inicial=quebra1_inicial,
                    quebra1_final=quebra1_final,
                    quebra2_inicial=quebra2_inicial,
                    quebra2_final=quebra2_final,
                    quebra3_inicial=quebra3_inicial,
                    quebra3_final=quebra3_final,
                    ind_palmtop=ind_palmtop,
                    origem=origem,
                    status_nota=status_nota,
                    converte_caixas=converte_caixas,
                    quebra_pagina=quebra_pagina,
                    pis_cofins=pis_cofins,
                    lista_nota_compra=lista_nota_compra,
                    lista_nfs_compra=lista_nfs_compra,
                    lista_notas_apagar=lista_notas_apagar,
                    id_notas_transf=id_notas_transf,
                    somente_nfs_transf=somente_nfs_transf,
                    visao=visao,
                    id_agrupar_televendas=id_agrupar_televendas,
                    agrupar_televendas=agrupar_televendas,
                    id_somente_venda_bonif=id_somente_venda_bonif,
                    somente_venda_bonif=somente_venda_bonif,
                    id_somente_metalfrio=id_somente_metalfrio,
                    visao_metalfrio=visao_metalfrio,
                    id_visao_ipi_bonif=id_visao_ipi_bonif,
                    visao_ipi_bonif=visao_ipi_bonif,
                    valor_inicial=valor_inicial,
                    valor_final=valor_final,
                    embalagem_inicial=embalagem_inicial,
                    embalagem_final=embalagem_final,
                    mercadoria_inicial=mercadoria_inicial,
                    mercadoria_final=mercadoria_final,
                    cd_visao=cd_visao,
                    tp_consolidacao=tp_consolidacao,
                    visao_multi_cdd=visao_multi_cdd,
                    selecao_multi_cdd=selecao_multi_cdd,
                    st_nfe_todos=st_nfe_todos,
                    st_nfe_autorizada=st_nfe_autorizada,
                    st_nfe_denegada=st_nfe_denegada,
                    st_nfe_contingencia=st_nfe_contingencia,
                    st_nfe_enviada=st_nfe_enviada,
                    st_nfe_nao_enviada=st_nfe_nao_enviada,
                    st_nfe_rejeitada=st_nfe_rejeitada,
                    st_nfe_conting_autoriz=st_nfe_conting_autoriz,
                    st_nfe_conting_denegada=st_nfe_conting_denegada,
                    st_nfe_conting_enviada=st_nfe_conting_enviada,
                    st_nfe_conting_nao_env=st_nfe_conting_nao_env,
                    st_nfe_conting_rejeitada=st_nfe_conting_rejeitada,
                    status_nfe=status_nfe,
                    acao=acao,
                    timeout=timeout,
                    clicar_csv_apos_visualizar=clicar_csv_apos_visualizar,
                    timeout_csv=timeout_csv,
                    nome_arquivo=arq,
                ),
            )

        # === EXECUÇÃO ÚNICA ===
        self.selecionar_unidade(unidade)

        # Normalizações de parâmetros/aliases
        acao = (acao or "BotOk").strip()
        tipo_nota_final = (tipo_nota or notas)
        if tipo_nota_final:
            tipo_nota_final = tipo_nota_final.strip().upper()
        if itens:
            itens = itens.strip().upper()
        if visao:
            visao = visao.strip().upper()
        if status_nota:
            status_nota = status_nota.strip().upper()

        ind_palmtop_final = ind_palmtop if ind_palmtop is not None else origem
        val_nota_compra = lista_nota_compra if lista_nota_compra is not None else lista_nfs_compra
        val_transf = id_notas_transf if id_notas_transf is not None else somente_nfs_transf
        val_televendas = id_agrupar_televendas if id_agrupar_televendas is not None else agrupar_televendas
        val_venda_bonif = id_somente_venda_bonif if id_somente_venda_bonif is not None else somente_venda_bonif
        val_metalfrio = id_somente_metalfrio if id_somente_metalfrio is not None else visao_metalfrio
        val_ipi_bonif = id_visao_ipi_bonif if id_visao_ipi_bonif is not None else visao_ipi_bonif

        # Entrar no frame
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=timeout)

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.NAME, "dataInicial"))
            )
        except TimeoutException:
            self.logger.warning("O formulário demorou a renderizar. O preenchimento pode falhar.")

        # Preenchimento
        try:
            # 1) Quebras
            self.js_set_select_by_name("quebra1", quebra1)
            if quebra1 is not None:
                self.driver.execute_script("if (typeof Carrega === 'function') Carrega('1');")
            self.js_set_select_by_name("quebra2", quebra2)
            if quebra2 is not None:
                self.driver.execute_script("if (typeof Carrega === 'function') Carrega('2');")
            self.js_set_select_by_name("quebra3", quebra3)
            if quebra3 is not None:
                self.driver.execute_script("if (typeof Carrega === 'function') Carrega('3');")

            # 2) Origem (indPalmtop)
            if ind_palmtop_final is not None:
                self.js_set_select_by_name("indPalmtop", str(ind_palmtop_final))

            # 3) Faixas de valores/filtros
            campos_faixa = [
                ("quebra1Inicial", quebra1_inicial),
                ("quebra1Final", quebra1_final),
                ("quebra2Inicial", quebra2_inicial),
                ("quebra2Final", quebra2_final),
                ("quebra3Inicial", quebra3_inicial),
                ("quebra3Final", quebra3_final),
                ("valorInicial", valor_inicial),
                ("valorFinal", valor_final),
                ("embalagemInicial", embalagem_inicial),
                ("embalagemFinal", embalagem_final),
                ("mercadoriaInicial", mercadoria_inicial),
                ("mercadoriaFinal", mercadoria_final),
            ]
            for name, val in campos_faixa:
                if val is not None:
                    self.js_set_input_by_name(name, str(val))

            # 4) Datas
            self.js_set_input_by_name("dataInicial", data_inicial)
            self.js_set_input_by_name("dataFinal", data_final)

            # 5) Radios de Preferência
            if status_nota:
                self.js_set_radio_by_name("statusNota", status_nota)
            if itens:
                self.js_set_radio_by_name("itens", itens)
                self.driver.execute_script("if (typeof HabilitaEmbalagem === 'function') HabilitaEmbalagem();")
            if tipo_nota_final:
                self.js_set_radio_by_name("notas", tipo_nota_final)
                self.driver.execute_script("if (typeof TrataCampoCompra === 'function') TrataCampoCompra();")
            if visao:
                self.js_set_radio_by_name("visao", visao)

            # 6) Checkboxes de Preferência
            if converte_caixas is not None:
                self.js_set_checkbox_by_name("converteCaixas", bool(converte_caixas), force_click=True)
            if quebra_pagina is not None:
                self.js_set_checkbox_by_name("quebraPagina", bool(quebra_pagina), force_click=True)
            if pis_cofins is not None:
                self.js_set_checkbox_by_name("pisCofins", bool(pis_cofins), force_click=True)
            if val_nota_compra is not None:
                self.js_set_checkbox_by_name("listaNotaCompra", bool(val_nota_compra), force_click=True)
                self.driver.execute_script("if (typeof AlteraData === 'function') AlteraData();")
            if lista_notas_apagar is not None:
                self.js_set_checkbox_by_name("listaNotasApagar", bool(lista_notas_apagar), force_click=True)
            if val_transf is not None:
                self.js_set_checkbox_by_name("idNotasTransf", bool(val_transf), force_click=True)
            if val_televendas is not None:
                self.js_set_checkbox_by_name("idAgruparTelevendas", bool(val_televendas), force_click=True)
            if val_venda_bonif is not None:
                self.js_set_checkbox_by_name("idSomenteVendaBonif", bool(val_venda_bonif), force_click=True)
            if val_metalfrio is not None:
                self.js_set_checkbox_by_name("idSomenteMetalfrio", bool(val_metalfrio), force_click=True)
            if val_ipi_bonif is not None:
                self.js_set_checkbox_by_name("idVisaoIpiBonif", bool(val_ipi_bonif), force_click=True)

            # 7) Consolidação & Multi CDD
            if cd_visao is not None:
                self.js_set_input_by_name("cdVisao", str(cd_visao))
            if tp_consolidacao is not None:
                self.driver.execute_script(
                    "if (typeof Disabled === 'function') Disabled('blocoConsolidacao', false);"
                )
                self.js_set_radio_by_name("tpConsolidacao", str(tp_consolidacao))
            if visao_multi_cdd is not None:
                self.js_set_radio_by_name("idVisaoMultiCdd", str(visao_multi_cdd))
            if selecao_multi_cdd is not None:
                self.js_set_select_by_name("idSelecaoMultiCdd", str(selecao_multi_cdd))

            # 8) Status NF-e (DivStatusNfe)
            self._configurar_status_nfe(
                st_nfe_todos=st_nfe_todos,
                st_nfe_autorizada=st_nfe_autorizada,
                st_nfe_denegada=st_nfe_denegada,
                st_nfe_contingencia=st_nfe_contingencia,
                st_nfe_enviada=st_nfe_enviada,
                st_nfe_nao_enviada=st_nfe_nao_enviada,
                st_nfe_rejeitada=st_nfe_rejeitada,
                st_nfe_conting_autoriz=st_nfe_conting_autoriz,
                st_nfe_conting_denegada=st_nfe_conting_denegada,
                st_nfe_conting_enviada=st_nfe_conting_enviada,
                st_nfe_conting_nao_env=st_nfe_conting_nao_env,
                st_nfe_conting_rejeitada=st_nfe_conting_rejeitada,
                status_nfe=status_nfe,
            )

            # 9) Click Botão de Ação
            botao = self.find_element((By.NAME, acao))
            self.js_click_ie(botao)
            self.logger.info(f"Botão clicado via JS: {acao}")

        except UnexpectedAlertPresentException:
            self.logger.warning("Alerta durante preenchimento. Limpando e abortando unidade.")
            self.lidar_com_alertas()
            raise

        self.switch_to_default_content()

        resultado_final = True

        if acao == "BotVisualizar" and clicar_csv_apos_visualizar:
            resultado_final = self._fluxo_exportar_csv(
                timeout_csv=timeout_csv,
                nome_arquivo=nome_arquivo,
                timeout_botao=timeout_csv,
            )

        self.switch_to_default_content()

        return resultado_final

    def _configurar_status_nfe(
        self,
        st_nfe_todos=None,
        st_nfe_autorizada=None,
        st_nfe_denegada=None,
        st_nfe_contingencia=None,
        st_nfe_enviada=None,
        st_nfe_nao_enviada=None,
        st_nfe_rejeitada=None,
        st_nfe_conting_autoriz=None,
        st_nfe_conting_denegada=None,
        st_nfe_conting_enviada=None,
        st_nfe_conting_nao_env=None,
        st_nfe_conting_rejeitada=None,
        status_nfe=None,
    ):
        st_map = {
            "idStTodos": st_nfe_todos,
            "idStAutorizada": st_nfe_autorizada,
            "idStDenegada": st_nfe_denegada,
            "idStContingencia": st_nfe_contingencia,
            "idStEnviada": st_nfe_enviada,
            "idStNaoEnviada": st_nfe_nao_enviada,
            "idStRejeitada": st_nfe_rejeitada,
            "idStContingAutoriz": st_nfe_conting_autoriz,
            "idStContingDenegada": st_nfe_conting_denegada,
            "idStContingEnviada": st_nfe_conting_enviada,
            "idStContingNaoEnv": st_nfe_conting_nao_env,
            "idStContingRejeitada": st_nfe_conting_rejeitada,
        }

        if isinstance(status_nfe, dict):
            for k, v in status_nfe.items():
                k_clean = k.lower().replace("_", "").replace("idst", "").replace("stnfe", "")
                for field_name in st_map:
                    if field_name.lower().endswith(k_clean) or k_clean in field_name.lower():
                        st_map[field_name] = v

        elif isinstance(status_nfe, (list, set, tuple)):
            items_lower = [str(x).lower() for x in status_nfe]
            if "todos" not in items_lower and "idsttodos" not in items_lower:
                st_map["idStTodos"] = False
            for item in status_nfe:
                k_clean = str(item).lower().replace("_", "").replace("idst", "").replace("stnfe", "")
                for field_name in st_map:
                    if field_name.lower().endswith(k_clean) or k_clean in field_name.lower():
                        st_map[field_name] = True

        if all(v is None for v in st_map.values()):
            return

        if st_map["idStTodos"] is False:
            self.js_set_checkbox_by_name("idStTodos", False, force_click=True)
            self.driver.execute_script("if (typeof Disabled === 'function') Disabled('', '', ['bloco1', false, 'bloco2', false]);")

        for field_name, val in st_map.items():
            if val is not None and field_name != "idStTodos":
                self.js_set_checkbox_by_name(field_name, bool(val), force_click=True)

        if st_map["idStTodos"] is True:
            self.js_set_checkbox_by_name("idStTodos", True, force_click=True)
            self.driver.execute_script("if (typeof Disabled === 'function') Disabled('', '', ['bloco1', false, 'bloco2', true]);")

        self.driver.execute_script("if (typeof VerificaStatus === 'function') VerificaStatus();")
