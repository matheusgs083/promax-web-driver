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

    # --- LOCATORS ---
    FRAME_ROTINA = 1
    BTN_GERA_EXCEL_1 = (By.NAME, "GerExecl")
    BTN_GERA_EXCEL_2 = (By.NAME, "GeraExcel")

    def gerar_relatorio(
        self,
        data_inicial,
        data_final,
        unidade=None,
        tipo_nota=None,
        itens=None,
        quebra1=None,
        quebra2=None,
        quebra3=None,
        quebra1_inicial=None,
        quebra1_final=None,
        quebra2_inicial=None,
        quebra2_final=None,
        quebra3_inicial=None,
        quebra3_final=None,
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
                    acao=acao,
                    timeout=timeout,
                    clicar_csv_apos_visualizar=clicar_csv_apos_visualizar,
                    timeout_csv=timeout_csv,
                    nome_arquivo=arq,
                ),
            )

        # === EXECUÇÃO ÚNICA ===
        self.selecionar_unidade(unidade)

        # Validações
        acao = (acao or "BotOk").strip()
        if tipo_nota:
            tipo_nota = tipo_nota.strip().upper()
        if itens:
            itens = itens.strip().upper()

        # 2) Entrar no frame (abstraído)
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=timeout)

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.NAME, "dataInicial"))
            )
        except TimeoutException:
            self.logger.warning("O formulário demorou a renderizar. O preenchimento pode falhar.")

        # 3) Preenchimento
        try:
            self.js_set_select_by_name("quebra1", quebra1)
            self.js_set_select_by_name("quebra2", quebra2)
            self.js_set_select_by_name("quebra3", quebra3)

            campos_faixa = [
                ("quebra1Inicial", quebra1_inicial),
                ("quebra1Final", quebra1_final),
                ("quebra2Inicial", quebra2_inicial),
                ("quebra2Final", quebra2_final),
                ("quebra3Inicial", quebra3_inicial),
                ("quebra3Final", quebra3_final),
            ]
            for name, val in campos_faixa:
                if val is not None:
                    self.js_set_input_by_name(name, val)

            self.js_set_input_by_name("dataInicial", data_inicial)
            self.js_set_input_by_name("dataFinal", data_final)

            if itens:
                self.js_set_radio_by_name("itens", itens)
            if tipo_nota:
                self.js_set_radio_by_name("notas", tipo_nota)

            # Click Botão
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
                timeout_botao=timeout_csv  # <-- Isso impede a queda nos 30s
            )

        self.switch_to_default_content()
        
        # Retorna a tupla (ou True) para que o loop_unidades possa registrar no Tracker
        return resultado_final
"""
00 â†’ --Selecionar--
01 â†’ Geral
02 â†’ Comercial - NF
03 â†’ Gte Vendas - NF
04 â†’ Area - NF
05 â†’ Setor - NF
06 â†’ Vendedor
07 â†’ Cliente
08 â†’ Municipio
09 â†’ Categoria
10 â†’ Segmto Cerv
11 â†’ Rede
12 â†’ Tipo Movto
13 â†’ CTO
14 â†’ Operacao
15 â†’ Forma Pagto
16 â†’ Cond Pagto
17 â†’ Transp.
18 â†’ Nivel
19 â†’ Mapa
20 â†’ Comercial - Cli
21 â†’ Gte Vendas - Cli
22 â†’ Area - Cli
23 â†’ Setor - Cli
24 â†’ Grupo de Rede
25 â†’ Motorista
26 â†’ Cli Corporativo
27 â†’ NR Roadashow
28 â†’ Classe Road
29 â†’ Codigo Fiscal
30 â†’ Cli Chave SAP
31 â†’ Conferencia SAP
32 â†’ F A D
33 → Armazém
34 â†’ Distrital - NF
35 â†’ Distrital - Cli
36 â†’ Ajudante 1
37 â†’ Ajudante 2
38 â†’ Codigo Contabil
39 â†’ Veiculo
40 â†’ VDE -"""


