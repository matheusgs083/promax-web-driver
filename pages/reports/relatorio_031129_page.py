import time

from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pages.common.rotina_page import RotinaPage


class Relatorio031129Page(RotinaPage):
    """
    Rotina 03.11.29 (PW02225R) - Escala de equipe por mapa.

    Opcoes de opcaoRel:
    - 1: Ajudante 1
    - 2: Ajudante 2
    - 3: Geral
    - 4: Motorista
    """

    FRAME_ROTINA = 1

    def gerar_relatorio(
        self,
        unidade=None,
        opcao_rel="3",
        data_inicial=None,
        data_final=None,
        mapa_inicial="0",
        mapa_final="999999",
        placa_inicial="0",
        placa_final="ZZZZZZZ",
        regiao_inicial="0",
        regiao_final="999",
        campo_inicial="0",
        campo_final="999999",
        acao="BotVisualizar",
        clicar_csv_apos_visualizar=True,
        timeout_csv=360,
        nome_arquivo="031129.csv",
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
                    mapa_inicial=mapa_inicial,
                    mapa_final=mapa_final,
                    placa_inicial=placa_inicial,
                    placa_final=placa_final,
                    regiao_inicial=regiao_inicial,
                    regiao_final=regiao_final,
                    campo_inicial=campo_inicial,
                    campo_final=campo_final,
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
            self.logger.warning("Formulario 031129 demorou a renderizar.")

        try:
            if opcao_rel is not None:
                self.js_set_select_by_name("opcaoRel", str(opcao_rel))
                self.driver.execute_script("if (typeof Habilita === 'function') Habilita();")
                self.aguardar_loader_oculto(timeout=3)

            campos_input = [
                ("dataInicial", data_inicial),
                ("dataFinal", data_final),
                ("mapaInicial", mapa_inicial),
                ("mapaFinal", mapa_final),
                ("placaInicial", placa_inicial),
                ("placaFinal", placa_final),
                ("regiaoInicial", regiao_inicial),
                ("regiaoFinal", regiao_final),
                ("campoInicial", campo_inicial),
                ("campoFinal", campo_final),
            ]
            for name, value in campos_input:
                if value is not None:
                    self.js_set_input_by_name(name, str(value))

            acao = (acao or "BotVisualizar").strip()
            if acao != "BotVisualizar":
                raise ValueError(f"Acao invalida para 031129: {acao}")

            botao = self.find_element((By.NAME, acao))
            self.js_click_ie(botao)
            time.sleep(2)

        except UnexpectedAlertPresentException:
            self.logger.warning("Alerta durante preenchimento da rotina 031129.")
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
        return self._fluxo_exportar_csv(
            timeout_csv=timeout_csv,
            nome_arquivo=nome_arquivo,
            timeout_botao=timeout_csv,
            locators_export=locators_export,
        )
