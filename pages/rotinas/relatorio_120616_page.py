# pages/relatorio_120616_page.py

import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException

from pages.rotina_page import RotinaPage


class Relatorio120616Page(RotinaPage):
    """
    Rotina 120616

    Campos mapeados:
      - SELECT name="opcaoRel"  (Classificação)
      - INPUT  name="mesAno"
      - INPUT  name="segmentoInicial" / "segmentoFinal"
      - INPUT  name="comercialInicial" / "comercialFinal"
      - INPUT  name="distritalInicial" / "distritalFinal"
      - INPUT  name="gerenteInicial" / "gerenteFinal"
      - INPUT  name="areaInicial" / "areaFinal"

    Regra: se não passar nada (None), mantém o padrão da tela (não mexe).
    """

    FRAME_ROTINA = 1

    # mantém compatibilidade com o _fluxo_exportar_csv da RotinaPage (que tenta 1,2,3)
    BTN_GERA_EXCEL_1 = (By.NAME, "GerExecl")   # typo clássico
    BTN_GERA_EXCEL_2 = (By.NAME, "GeraExcel")  # padrão
    BTN_GERA_EXCEL_3 = (By.NAME, "GerExcel")   # variação rara

    def gerar_relatorio(
        self,
        unidade=None,

        # SELECT (Classificação)
        opcao_rel=None,           # 0..5 (ou "0".."5")

        # INPUTS
        mes_ano=None,             # "MM/YYYY"
        segmento_inicial=None,
        segmento_final=None,
        comercial_inicial=None,
        comercial_final=None,
        distrital_inicial=None,
        distrital_final=None,
        gerente_inicial=None,
        gerente_final=None,
        area_inicial=None,
        area_final=None,

        acao="BotVisualizar",
        timeout=15,
        clicar_csv_apos_visualizar=True,
        timeout_csv=360,
        nome_arquivo="120616.csv",
    ):

        # === LOOP (MULTI-UNIDADES) via RotinaPage ===
        if unidade is None:
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    unidade=cod,
                    opcao_rel=opcao_rel,
                    mes_ano=mes_ano,
                    segmento_inicial=segmento_inicial,
                    segmento_final=segmento_final,
                    comercial_inicial=comercial_inicial,
                    comercial_final=comercial_final,
                    distrital_inicial=distrital_inicial,
                    distrital_final=distrital_final,
                    gerente_inicial=gerente_inicial,
                    gerente_final=gerente_final,
                    area_inicial=area_inicial,
                    area_final=area_final,
                    acao=acao,
                    timeout=timeout,
                    clicar_csv_apos_visualizar=clicar_csv_apos_visualizar,
                    timeout_csv=timeout_csv,
                    nome_arquivo=arq,
                ),
            )

        # === EXECUÇÃO ÚNICA ===
        self.selecionar_unidade(unidade)

        acao = (acao or "BotVisualizar").strip()

        # entrar no frame blindado (abstraído)
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=timeout)

        try:
            # SELECT correto: name="opcaoRel"
            if opcao_rel is not None:
                self.js_set_select_by_name("opcaoRel", opcao_rel)

            # INPUTS (só mexe se vier valor)
            if mes_ano is not None:
                self.js_set_input_by_name("mesAno", mes_ano)

            if segmento_inicial is not None:
                self.js_set_input_by_name("segmentoInicial", segmento_inicial)
            if segmento_final is not None:
                self.js_set_input_by_name("segmentoFinal", segmento_final)

            if comercial_inicial is not None:
                self.js_set_input_by_name("comercialInicial", comercial_inicial)
            if comercial_final is not None:
                self.js_set_input_by_name("comercialFinal", comercial_final)

            if distrital_inicial is not None:
                self.js_set_input_by_name("distritalInicial", distrital_inicial)
            if distrital_final is not None:
                self.js_set_input_by_name("distritalFinal", distrital_final)

            if gerente_inicial is not None:
                self.js_set_input_by_name("gerenteInicial", gerente_inicial)
            if gerente_final is not None:
                self.js_set_input_by_name("gerenteFinal", gerente_final)

            if area_inicial is not None:
                self.js_set_input_by_name("areaInicial", area_inicial)
            if area_final is not None:
                self.js_set_input_by_name("areaFinal", area_final)

            # ação
            btn = self.find_element((By.NAME, acao))
            self.js_click_ie(btn)

        except UnexpectedAlertPresentException:
            self.logger.warning("Alerta durante preenchimento. Limpando e abortando unidade.")
            self.lidar_com_alertas()
            raise

        time.sleep(2)
        self.switch_to_default_content()

        if acao == "BotVisualizar" and clicar_csv_apos_visualizar:
            # usa o método abstraído na RotinaPage
            self._fluxo_exportar_csv(timeout_csv, nome_arquivo)

        self.switch_to_default_content()
        return True

"""
value=0 >--Selecionar--
 value=1 >Segmento
 value=2 >Comercial
 value=3 >Gerente
 value=4 >Area
 value=5 >Distrital"""