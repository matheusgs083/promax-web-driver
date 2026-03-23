import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from pages.common.rotina_page import RotinaPage


class Relatorio150501Page(RotinaPage):
    """
    Rotina: Lançamentos Detalhados OBZ
    Call: 15050100000000
    Interno: PW06011R
    """

    FRAME_ROTINA = 1

    def gerar_relatorio(
        self,
        unidade=None,
        # 1) SELECTS PRINCIPAIS
        opcao_rel=None,
        visao=None,
        periodo=None,

        # 2) LISTAS DE SELEÇÃO (Se None, assume TODOS os padrões do sistema)
        lista_nbz=None,
        lista_depto=None,
        lista_pacote=None,
        lista_vbz=None,
        lista_conta=None,

        # 3) DATAS
        data_inicial=None,
        data_final=None,
        mes_ano=None,
        ano=None,

        # 4) PREFERÊNCIAS
        totaliza_periodo=None,
        listar_historico=None,
        quebra_pagina=None,

        acao="BotVisualizar",
        clicar_csv_apos_visualizar=True,
        timeout_csv=360,
        nome_arquivo="lancamentos_obz.csv",
    ):

        if lista_nbz is None:
            lista_nbz = ["99"]
        if lista_depto is None:
            lista_depto = ["9999"]
        if lista_pacote is None:
            lista_pacote = ["9999"]
        if lista_vbz is None:
            lista_vbz = ["9999"]
        if lista_conta is None:
            lista_conta = ["9999999999"]

        if unidade is None or isinstance(unidade, list):
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                unidades_alvo=unidade if isinstance(unidade, list) else None,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    unidade=cod,
                    opcao_rel=opcao_rel,
                    visao=visao,
                    periodo=periodo,
                    lista_nbz=lista_nbz,
                    lista_depto=lista_depto,
                    lista_pacote=lista_pacote,
                    lista_vbz=lista_vbz,
                    lista_conta=lista_conta,
                    data_inicial=data_inicial,
                    data_final=data_final,
                    mes_ano=mes_ano,
                    ano=ano,
                    totaliza_periodo=totaliza_periodo,
                    listar_historico=listar_historico,
                    quebra_pagina=quebra_pagina,
                    acao=acao,
                    clicar_csv_apos_visualizar=clicar_csv_apos_visualizar,
                    timeout_csv=timeout_csv,
                    nome_arquivo=arq,
                )
            )

        self.selecionar_unidade(unidade)
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.NAME, "opcaoRel"))
            )
        except TimeoutException:
            self.logger.warning("O formulário demorou a renderizar. O preenchimento pode falhar.")

        # 1) CONFIGURAÇÕES INICIAIS
        if opcao_rel:
            self.js_set_select_by_name("opcaoRel", str(opcao_rel))
        if visao:
            self.js_set_select_by_name("visao", str(visao))
        if periodo:
            self.js_set_select_by_name("idPeriodo", str(periodo))
            self.driver.execute_script("VerificaPeriodo();")

        # 2) DATAS
        if data_inicial:
            self.js_set_input_by_name("dtInicial", str(data_inicial))
        if data_final:
            self.js_set_input_by_name("dtFinal", str(data_final))
        if mes_ano:
            self.js_set_input_by_name("dtMesAno", str(mes_ano))
        if ano:
            self.js_set_input_by_name("dtAno", str(ano))

        # 3) LISTAS MÚLTIPLAS - SEQUÊNCIA COM RELOAD
        self._adicionar_itens_lista("cdNbz", "AdicionaNbz()", lista_nbz)
        self._aguardar_reload_pagina()

        self._adicionar_itens_lista("cdDepto", "AdicionaDepto()", lista_depto)

        self._adicionar_itens_lista("cdPacote", "AdicionaPacote()", lista_pacote)
        self._aguardar_reload_pagina()

        self._adicionar_itens_lista("cdVbz", "AdicionaVbz()", lista_vbz)
        self._aguardar_reload_pagina()

        self._adicionar_itens_lista("cdConta", "AdicionaConta()", lista_conta)

        # 4) PREFERÊNCIAS
        prefs = [
            ("idTotalizaPeriodo", totaliza_periodo),
            ("resumo", listar_historico),
            ("idQuebra", quebra_pagina),
        ]
        for name, val in prefs:
            if val is not None:
                is_checked = val is True or str(val).upper() == "S"
                self.js_set_checkbox_by_name(name, is_checked, force_click=True)

        # --- AÇÃO FINAL ---
        try:
            btn = self.find_element((By.NAME, acao))
            self.js_click_ie(btn)
        except UnexpectedAlertPresentException:
            self.logger.warning("Alerta bloqueante. Limpando...")
            self.lidar_com_alertas()
            raise

        time.sleep(2)
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

    def _adicionar_itens_lista(self, nome_select, funcao_js, valor):
        """
        Helper interno para selecionar item e clicar no botão (via JS)
        """
        if valor is None:
            return

        itens = valor if isinstance(valor, list) else [valor]

        for item in itens:
            try:
                self.logger.info(f"Selecionando '{item}' em {nome_select} e chamando {funcao_js}")
                self.js_set_select_by_name(nome_select, str(item))
                self.driver.execute_script(funcao_js)
            except Exception as e:
                self.logger.warning(f"Não foi possível adicionar item {item} em {nome_select}. Erro: {e}")

    def _aguardar_reload_pagina(self):
        self.logger.info("Aguardando reload da página (Postback)...")
        time.sleep(2)
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)


