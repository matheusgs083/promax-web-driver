import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from pages.rotina_page import RotinaPage


class Relatorio140510Page(RotinaPage):
    FRAME_ROTINA = 1

    def gerar_relatorio(
            self,
            unidade=None,
            opcao_rel="00",
            cd_natureza=None,
            usar_lista_natureza=True,
            vencidos=None,
            a_vencer=None,
            quebra_pagina=None,
            sintetico=None,
            pref_C=None,
            pref_V=None,
            data=None,
            acao="BotVisualizar",
            clicar_csv_apos_visualizar=True,
            timeout_csv=360,
            nome_arquivo="situacao_titulos_f7188.csv",
            **kwargs # Para capturar fornecedor_inicial, etc.
        ):

        # === LOOP MULTI-UNIDADES ===
        if unidade is None or isinstance(unidade, list):
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                unidades_alvo=unidade if isinstance(unidade, list) else None,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    unidade=cod, nome_arquivo=arq, opcao_rel=opcao_rel, cd_natureza=cd_natureza,
                    usar_lista_natureza=usar_lista_natureza, vencidos=vencidos, a_vencer=a_vencer,
                    quebra_pagina=quebra_pagina, sintetico=sintetico, pref_C=pref_C, pref_V=pref_V,
                    data=data, acao=acao, clicar_csv_apos_visualizar=clicar_csv_apos_visualizar,
                    timeout_csv=timeout_csv, **kwargs
                )
            )

        # === SETUP ===
        self.selecionar_unidade(unidade)
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)

        # Espera renderização básica
        try:
            WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.NAME, "opcaoRel")))
        except TimeoutException:
            self.logger.warning("Formulário demorou a renderizar.")

        # === PREENCHIMENTO (Utilizando os métodos da Mãe) ===
        
        # 1) Dropdowns
        if opcao_rel: self.js_set_select_by_name("opcaoRel", str(opcao_rel))
        
        if cd_natureza:
            if usar_lista_natureza:
                self.adicionar_itens_lista_por_botao("cdNatureza", "BotAdic", cd_natureza)
            else:
                self.js_set_select_by_name("cdNatureza", str(cd_natureza[0] if isinstance(cd_natureza, list) else cd_natureza))

        # 2) Checkboxes com Assert
        for campo, val in [("idVencidos", vencidos), ("idAVencer", a_vencer), 
                           ("quebraPagina", quebra_pagina), ("idSintetico", sintetico)]:
            if val is not None:
                self.js_set_checkbox_by_name(campo, bool(val), force_click=True)
                self._assert_checkbox(campo, bool(val))

        # 3) Radios (preferencias1 C/V)
        if pref_C is not None:
            self.js_set_checked_by_name_value("preferencias1", "C", bool(pref_C))
            self._assert_checked_by_name_value("preferencias1", "C", bool(pref_C))
        if pref_V is not None:
            self.js_set_checked_by_name_value("preferencias1", "V", bool(pref_V))
            self._assert_checked_by_name_value("preferencias1", "V", bool(pref_V))

        # 4) Inputs (kwargs permite passar portador_inicial, fornecedor_final, etc)
        if data: self.js_set_input_by_name("data", str(data))
        # Exemplo dinâmico para os demais inputs passados via kwargs
        for key, value in kwargs.items():
            # Converte snake_case para camelCase se necessário ou usa direto
            if value: self.js_set_input_by_name(key, str(value))

        # === AÇÃO FINAL E RETORNO ===
        resultado_final = False
        
        if acao:
            try:
                btn = self.find_element((By.NAME, acao))
                self.js_click_ie(btn)
                time.sleep(2)
                self.switch_to_default_content()

                if acao == "BotVisualizar" and clicar_csv_apos_visualizar:
                    resultado_final = self._fluxo_exportar_csv(
                        timeout_csv=timeout_csv,
                        nome_arquivo=nome_arquivo
                    )
                else:
                    resultado_final = True

            except UnexpectedAlertPresentException:
                self.lidar_com_alertas()
                raise
            finally:
                self.switch_to_default_content()
        else:
            resultado_final = True
            self.switch_to_default_content()

        return resultado_final