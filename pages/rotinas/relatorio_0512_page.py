import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from pages.rotina_page import RotinaPage

class Relatorio0512Page(RotinaPage):
    """
    Rotina: Vendas no Ano
    Call: 05120000000000
    Interno: PW02008R
    """

    FRAME_ROTINA = 1

    def gerar_relatorio(
        self,
        unidade=None,
        # 1) SELECTS
        opcao_rel=None,           
        perfil_vendas=None,       
        grupo_perfil_vendas=None, 
        
        # 2) RADIOS (Se houver)
        
        # 3) CHECKBOXES (Agora tratados corretamente como Checkbox HTML)
        quebra_pagina=None,
        ano_anterior=None,
        ind_pgv=None,
        total_tipo_marca=None,
        total_embalagem=None,
        id_converte_hecto=None,

        # 4) INPUTS
        ano=None,
        mes_inicial=None,
        mes_final=None,
        tipo_marca_ini=None, tipo_marca_fim=None,
        linha_marca_ini=None, linha_marca_fim=None,
        marca_ini=None, marca_fim=None,
        embalagem_ini=None, embalagem_fim=None,
        produto_ini=None, produto_fim=None,
        cat_ini=None, cat_fim=None,
        cli_ini=None, cli_fim=None,
        area_ini=None, area_fim=None,
        setor_ini=None, setor_fim=None,
        rede_ini=None, rede_fim=None,
        gte_vendas_ini=None, gte_vendas_fim=None,
        comercial_ini=None, comercial_fim=None,
        distrital_ini=None, distrital_fim=None,
        municipio_ini=None, municipio_fim=None,

        acao="BotVisualizar",
        clicar_csv_apos_visualizar=True,
        timeout_csv=360,
        nome_arquivo="vendas_no_ano.csv",
    ):

        # === LOOP MULTI-UNIDADES ===
        if unidade is None or isinstance(unidade, list):
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                unidades_alvo=unidade if isinstance(unidade, list) else None,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    unidade=cod,
                    opcao_rel=opcao_rel,
                    perfil_vendas=perfil_vendas,
                    grupo_perfil_vendas=grupo_perfil_vendas,
                    quebra_pagina=quebra_pagina,
                    ano_anterior=ano_anterior,
                    ind_pgv=ind_pgv,
                    total_tipo_marca=total_tipo_marca,
                    total_embalagem=total_embalagem,
                    id_converte_hecto=id_converte_hecto,
                    ano=ano,
                    mes_inicial=mes_inicial,
                    mes_final=mes_final,
                    tipo_marca_ini=tipo_marca_ini, tipo_marca_fim=tipo_marca_fim,
                    linha_marca_ini=linha_marca_ini, linha_marca_fim=linha_marca_fim,
                    marca_ini=marca_ini, marca_fim=marca_fim,
                    embalagem_ini=embalagem_ini, embalagem_fim=embalagem_fim,
                    produto_ini=produto_ini, produto_fim=produto_fim,
                    cat_ini=cat_ini, cat_fim=cat_fim,
                    cli_ini=cli_ini, cli_fim=cli_fim,
                    area_ini=area_ini, area_fim=area_fim,
                    setor_ini=setor_ini, setor_fim=setor_fim,
                    rede_ini=rede_ini, rede_fim=rede_fim,
                    gte_vendas_ini=gte_vendas_ini, gte_vendas_fim=gte_vendas_fim,
                    comercial_ini=comercial_ini, comercial_fim=comercial_fim,
                    distrital_ini=distrital_ini, distrital_fim=distrital_fim,
                    municipio_ini=municipio_ini, municipio_fim=municipio_fim,
                    acao=acao,
                    clicar_csv_apos_visualizar=clicar_csv_apos_visualizar,
                    timeout_csv=timeout_csv,
                    nome_arquivo=arq,
                )
            )

        self.selecionar_unidade(unidade)
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)

        # ==========================================================
        # CORREÇÃO 1: Esperar o formulário renderizar após trocar unidade
        # Isso impede o erro "no-select" (Condição de Corrida)
        # ==========================================================
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.NAME, "ano"))
            )
        except TimeoutException:
            self.logger.warning("O formulário demorou a renderizar. O preenchimento pode falhar.")


        # 1) PREENCHIMENTO DE SELECTS
        if opcao_rel is not None:
            self.js_set_select_by_name("opcaoRel", str(opcao_rel))
        if perfil_vendas is not None:
            self.js_set_select_by_name("perfilVendas", str(perfil_vendas))
        if grupo_perfil_vendas is not None:
            self.js_set_select_by_name("grupoPerfilVendas", str(grupo_perfil_vendas))

        # 2) PREENCHIMENTO DE CHECKBOXES (USANDO JS_CHECKBOX_BY_NAME)
        # Importante: Como são inputs type="checkbox", usamos a propriedade .checked
        checkboxes = [
            ("quebraPagina", quebra_pagina),
            ("anoAnterior", ano_anterior),
            ("indPgv", ind_pgv),
            ("totalTipoMarca", total_tipo_marca),
            ("totalEmbalagem", total_embalagem),
            ("idConverteHecto", id_converte_hecto),
        ]
        
        for name, val in checkboxes:
            if val is not None:
                # Converte para booleano: True, "S", "s", 1 viram True
                deve_marcar = (val is True or str(val).strip().upper() == "S")
                
                # Usa o método da BASE PAGE que lida com .checked e dispara eventos
                self.js_set_checkbox_by_name(name, deve_marcar, force_click=True)
                self.logger.info(f"Checkbox {name} definido para: {deve_marcar}")

        # 3) PREENCHIMENTO DE INPUTS (DATAS E FAIXAS)
        if ano is not None:
            self.js_set_input_by_name("ano", str(ano))
        if mes_inicial is not None:
            self.js_set_input_by_name("mesInicial", str(mes_inicial))
        if mes_final is not None:
            self.js_set_input_by_name("mesFinal", str(mes_final))

        faixas = [
            ("tipoMarcaInicial", tipo_marca_ini), ("tipoMarcaFinal", tipo_marca_fim),
            ("linhaMarcaInicial", linha_marca_ini), ("linhaMarcaFinal", linha_marca_fim),
            ("marcaInicial", marca_ini), ("marcaFinal", marca_fim),
            ("embalagemInicial", embalagem_ini), ("embalagemFinal", embalagem_fim),
            ("produtoInicial", produto_ini), ("produtoFinal", produto_fim),
            ("catInicial", cat_ini), ("catFinal", cat_fim),
            ("cliInicial", cli_ini), ("cliFinal", cli_fim),
            ("areaInicial", area_ini), ("areaFinal", area_fim),
            ("setorInicial", setor_ini), ("setorFinal", setor_fim),
            ("redeInicial", rede_ini), ("redeFinal", rede_fim),
            ("gteVendasInicial", gte_vendas_ini), ("gteVendasFinal", gte_vendas_fim),
            ("comercialInicial", comercial_ini), ("comercialFinal", comercial_fim),
            ("distritalInicial", distrital_ini), ("distritalFinal", distrital_fim),
            ("municipioInicial", municipio_ini), ("municipioFinal", municipio_fim),
        ]

        for name, val in faixas:
            if val is not None:
                self.js_set_input_by_name(name, str(val))

        # --- CLIQUE FINAL ---
        try:
            btn = self.find_element((By.NAME, acao))
            self.js_click_ie(btn)
        except UnexpectedAlertPresentException:
            self.logger.warning("Alerta bloqueante. Limpando...")
            self.lidar_com_alertas()
            raise
        
        self.switch_to_default_content()

        resultado_final = True

        if acao == "BotVisualizar" and clicar_csv_apos_visualizar:
            # ==========================================================
            # CORREÇÃO 2: Passar timeout_botao igual ao timeout_csv
            # Evita o erro onde ele desiste do botão CSV antes do download terminar
            # ==========================================================
            resultado_final = self._fluxo_exportar_csv(
                timeout_csv=timeout_csv, 
                nome_arquivo=nome_arquivo,
                timeout_botao=timeout_csv
            )

        self.switch_to_default_content()
        
        # Retorna a tupla para que o loop_unidades registre no Tracker
        return resultado_final
    
""" value=01>Produto       
    value=02>Cliente       
    value=03>Setor         
    value=04>Categoria     
    value=05>Rede          
    value=06>Setor/Cliente 
    value=07>Rede/Cliente  
    value=08>Area          
    value=09>Categ./Cliente
    value=10>Gte. Vendas   
    value=11>Comercial     
    value=12>Distrital
    value=13>Município         """
