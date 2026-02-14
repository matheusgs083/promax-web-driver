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
        if unidade is None:
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    data_inicial,
                    data_final,
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

        time.sleep(2)
        self.switch_to_default_content()

        if acao == "BotVisualizar" and clicar_csv_apos_visualizar:
            self._fluxo_exportar_csv(timeout_csv, nome_arquivo)

        self.switch_to_default_content()
        return True

"""
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
40 → VDE -"""