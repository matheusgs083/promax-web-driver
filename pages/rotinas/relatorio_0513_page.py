import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException

from pages.rotina_page import RotinaPage

try:
    from core.manipulador_download import salvar_arquivo_visual
    from core.validador_visual import validar_elemento
except ImportError:
    salvar_arquivo_visual = None
    validar_elemento = None


class Relatorio0513Page(RotinaPage):
    """
    Rotina: Análise de Vendas
    call: 05130000000000
    interno: PW02009R
    """

    FRAME_ROTINA = 1

    # Export (igual seu padrão)
    BTN_GERA_EXCEL_1 = (By.NAME, "GerExecl")   # typo clássico
    BTN_GERA_EXCEL_2 = (By.NAME, "GeraExcel")  # padrão
    BTN_GERA_EXCEL_3 = (By.NAME, "GerExcel")   # variação rara

    def gerar_relatorio(
        self,
        unidade=None,

        # 1) SELECT
        opcao_rel=None,           # "0".."14"

        # 2) SITUAÇÃO (logo após o select)
        situacao_todos=True,
        situacao_ativo=None,
        situacao_bloqueado=None,
        situacao_inativo=None,
        situacao_temporario=None,
        situacao_duplicado=None,
        situacao_excluido=None,

        # 3) RADIOS / PREFS
        volume_fin=None,          # "V" ou "F"
        tp_equipe=None,           # "A" ou "E"
        hectolitro=None,
        quebra_pagina=None,
        selecionar_tipo_marca=None,
        selecionar_tipo_perfil=None,

        # 4) INPUTS
        mes_ano_inicial=None,     # "MM/YYYY"
        mes_ano_final=None,       # "MM/YYYY"
        codigo_inicial1=None,
        codigo_final1=None,
        codigo_inicial2=None,
        codigo_final2=None,
        marca=None,
        linha_marca=None,
        embalagem=None,
        produto=None,

        # 5) CLIENTES / %
        quantos_clientes=None,
        percentual_venda=None,

        acao="BotVisualizar",
        clicar_csv_apos_visualizar=True,
        timeout_csv=360,
        nome_arquivo="analise_vendas.csv",
    ):

        # === LOOP (MULTI-UNIDADES) via RotinaPage ===
        if unidade is None:
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    unidade=cod,
                    opcao_rel=opcao_rel,

                    situacao_todos=situacao_todos,
                    situacao_ativo=situacao_ativo,
                    situacao_bloqueado=situacao_bloqueado,
                    situacao_inativo=situacao_inativo,
                    situacao_temporario=situacao_temporario,
                    situacao_duplicado=situacao_duplicado,
                    situacao_excluido=situacao_excluido,

                    volume_fin=volume_fin,
                    tp_equipe=tp_equipe,
                    hectolitro=hectolitro,
                    quebra_pagina=quebra_pagina,
                    selecionar_tipo_marca=selecionar_tipo_marca,
                    selecionar_tipo_perfil=selecionar_tipo_perfil,

                    mes_ano_inicial=mes_ano_inicial,
                    mes_ano_final=mes_ano_final,
                    codigo_inicial1=codigo_inicial1,
                    codigo_final1=codigo_final1,
                    codigo_inicial2=codigo_inicial2,
                    codigo_final2=codigo_final2,
                    marca=marca,
                    linha_marca=linha_marca,
                    embalagem=embalagem,
                    produto=produto,

                    quantos_clientes=quantos_clientes,
                    percentual_venda=percentual_venda,

                    acao=acao,
                    clicar_csv_apos_visualizar=clicar_csv_apos_visualizar,
                    timeout_csv=timeout_csv,
                    nome_arquivo=arq,
                )
            )

        # === EXECUÇÃO ÚNICA ===
        self.selecionar_unidade(unidade)

        # entrar no frame blindado (via RotinaPage)
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=15)

        # -----------------------------
        # 1) SELECT (OpcaoRel)
        # -----------------------------
        if opcao_rel is not None:
            self.logger.info(
                f"Configurando Classificação (OpcaoRel): {opcao_rel}")
            self.js_set_select_by_name("OpcaoRel", str(opcao_rel))

        # -----------------------------
        # 2) SITUAÇÃO
        # -----------------------------
        self._aplicar_situacao(
            situacao_todos=situacao_todos,
            situacao_ativo=situacao_ativo,
            situacao_bloqueado=situacao_bloqueado,
            situacao_inativo=situacao_inativo,
            situacao_temporario=situacao_temporario,
            situacao_duplicado=situacao_duplicado,
            situacao_excluido=situacao_excluido,
        )

        # -----------------------------
        # 3) RADIOS / PREFS
        # -----------------------------
        if volume_fin is not None:
            self.js_set_radio_by_name("volumeFin", str(volume_fin))
        if tp_equipe is not None:
            self.js_set_radio_by_name("tpEquipe", str(tp_equipe))

        if hectolitro is not None:
            self.js_set_checkbox_by_name(
                "hectolitro", bool(hectolitro), force_click=True)
        if quebra_pagina is not None:
            self.js_set_checkbox_by_name(
                "quebraPagina", bool(quebra_pagina), force_click=True)
        if selecionar_tipo_marca is not None:
            self.js_set_checkbox_by_name("selecionarTipomarca", bool(
                selecionar_tipo_marca), force_click=True)
        if selecionar_tipo_perfil is not None:
            self.js_set_checkbox_by_name("selecionarTipoPerfil", bool(
                selecionar_tipo_perfil), force_click=True)

        # -----------------------------
        # 4) INPUTS
        # -----------------------------
        if mes_ano_inicial is not None:
            self.js_set_input_by_name("mesAnoInicial", mes_ano_inicial)
        if mes_ano_final is not None:
            self.js_set_input_by_name("mesAnoFinal", mes_ano_final)

        if codigo_inicial1 is not None:
            self.js_set_input_by_name("codigoInicial1", codigo_inicial1)
        if codigo_final1 is not None:
            self.js_set_input_by_name("codigoFinal1", codigo_final1)
        if codigo_inicial2 is not None:
            self.js_set_input_by_name("codigoInicial2", codigo_inicial2)
        if codigo_final2 is not None:
            self.js_set_input_by_name("codigoFinal2", codigo_final2)

        if marca is not None:
            self.js_set_input_by_name("marca", marca)
        if linha_marca is not None:
            self.js_set_input_by_name("linhaMarca", linha_marca)
        if embalagem is not None:
            self.js_set_input_by_name("embalagem", embalagem)
        if produto is not None:
            self.js_set_input_by_name("produto", produto)

        # -----------------------------
        # 5) CLIENTES / %
        # -----------------------------
        if quantos_clientes is not None:
            self.js_set_input_by_name("quantosClientes", str(quantos_clientes))
        if percentual_venda is not None:
            self.js_set_input_by_name("percentualVenda", str(percentual_venda))

        # --- AÇÃO FINAL ---
        acao = (acao or "BotVisualizar").strip()
        self.logger.info(f"Clicando em {acao}")
        btn = self.find_element((By.NAME, acao))
        self.js_click_ie(btn)

        time.sleep(2)
        self.switch_to_default_content()

        if acao == "BotVisualizar" and clicar_csv_apos_visualizar:
            self._fluxo_exportar_csv(timeout_csv, nome_arquivo)

        self.switch_to_default_content()
        return True

    # ---------------------
    # Situação (blindada)
    # ---------------------
    def _aplicar_situacao(
        self,
        situacao_todos=True,
        situacao_ativo=None,
        situacao_bloqueado=None,
        situacao_inativo=None,
        situacao_temporario=None,
        situacao_duplicado=None,
        situacao_excluido=None,
    ):
        # regra: ou marca "Todos" OU marca flags individuais
        if situacao_todos:
            self.logger.info("Situação: marcando Todos")
            self.js_set_checkbox_by_name("Todos", True, force_click=True)
            self._assert_checkbox("Todos", True, tentativas=2)
            return

        self.logger.info("Situação: desmarcando Todos e aplicando flags")
        self.js_set_checkbox_by_name("Todos", False, force_click=True)
        self._assert_checkbox("Todos", False, tentativas=2)

        if situacao_ativo is not None:
            self.js_set_checkbox_by_name(
                "Ativo", bool(situacao_ativo), force_click=True)
        if situacao_bloqueado is not None:
            self.js_set_checkbox_by_name("Bloqueado", bool(
                situacao_bloqueado), force_click=True)
        if situacao_inativo is not None:
            self.js_set_checkbox_by_name("Inativo", bool(
                situacao_inativo), force_click=True)
        if situacao_temporario is not None:
            self.js_set_checkbox_by_name("Temporario", bool(
                situacao_temporario), force_click=True)
        if situacao_duplicado is not None:
            self.js_set_checkbox_by_name("Duplicado", bool(
                situacao_duplicado), force_click=True)
        if situacao_excluido is not None:
            self.js_set_checkbox_by_name("Excluido", bool(
                situacao_excluido), force_click=True)

    def _assert_checkbox(self, name, esperado: bool, tentativas=2):
        for i in range(tentativas):
            el = self.find_element((By.NAME, name))
            atual = bool(el.is_selected())
            if atual == bool(esperado):
                return True
            self.logger.warning(
                f"Checkbox {name} não ficou {esperado}. Tentando novamente ({i+1}/{tentativas})...")
            self.js_set_checkbox_by_name(
                name, bool(esperado), force_click=True)
            time.sleep(0.3)
        raise RuntimeError(
            f"Checkbox {name} não ficou {esperado} após {tentativas} tentativas.")


"""Consolida="N" value=0>--Selecionar--     
                                                    Consolida="S" value=1>Area               
                                                    Consolida="N" value=2>Setor              
                                                    Consolida="S" value=3>Categoria          
                                                    Consolida="S" value=4>Categoria/Area     
                                                    Consolida="N" value=5>Categoria/Setor    
                                                    Consolida="S" value=6>Gerente Vendas     
                                                    Consolida="S" value=7>Geral              
                                                    Consolida="S" value=8>Gte. Vendas/Segmento
                                                    Consolida="S" value=9>Segmento           
                                                    Consolida="S" value=10>Area/Segmento     
                                                    Consolida="N" value=11>Setor/Segmento    
                                                    Consolida="S" value=12>Comercial         
                                                    Consolida="S" value=13>Gte. Vendas/Categ.
                                                    Consolida="S" value=14>Distrital         """
