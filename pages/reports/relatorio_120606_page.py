import time

from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pages.common.rotina_page import RotinaPage


class Relatorio120606Page(RotinaPage):
    FRAME_ROTINA = 1

    BTN_GERA_EXCEL_1 = (By.NAME, "GerExecl")
    BTN_GERA_EXCEL_2 = (By.NAME, "GeraExcel")
    BTN_GERA_EXCEL_3 = (By.NAME, "GerExcel")

    def gerar_relatorio(
        self,
        unidade=None,
        opcao_rel=None,
        tpData=None,
        idTitulosNormais=None,
        idTitulosAluguel=None,
        idTitulosCobrancaCa=None,
        idTitulosValeFisico=None,
        idTitulosRefugo=None,
        idTitulosQuebras=None,
        iniCli=None,
        fimCli=None,
        iniDat=None,
        fimDat=None,
        iniEmi=None,
        fimEmi=None,
        iniPor=None,
        fimPor=None,
        iniEsp=None,
        fimEsp=None,
        iniVin=None,
        fimVin=None,
        acao="BotVisualizar",
        clicar_csv_apos_visualizar=True,
        timeout_csv=360,
        nome_arquivo="120606.csv",
    ):
        if unidade is None or isinstance(unidade, list):
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                unidades_alvo=unidade if isinstance(unidade, list) else None,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    unidade=cod,
                    opcao_rel=opcao_rel,
                    tpData=tpData,
                    idTitulosNormais=idTitulosNormais,
                    idTitulosAluguel=idTitulosAluguel,
                    idTitulosCobrancaCa=idTitulosCobrancaCa,
                    idTitulosValeFisico=idTitulosValeFisico,
                    idTitulosRefugo=idTitulosRefugo,
                    idTitulosQuebras=idTitulosQuebras,
                    iniCli=iniCli,
                    fimCli=fimCli,
                    iniDat=iniDat,
                    fimDat=fimDat,
                    iniEmi=iniEmi,
                    fimEmi=fimEmi,
                    iniPor=iniPor,
                    fimPor=fimPor,
                    iniEsp=iniEsp,
                    fimEsp=fimEsp,
                    iniVin=iniVin,
                    fimVin=fimVin,
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
            self.logger.warning("Formulario demorou a renderizar.")

        if opcao_rel is not None:
            self.js_set_select_by_name("opcaoRel", str(opcao_rel))
            self.aguardar_loader_oculto(timeout=3)

        if tpData is not None:
            self.js_set_select_by_name("tpData", str(tpData))
            self.aguardar_loader_oculto(timeout=3)
            self.driver.execute_script(
                "if (typeof CarregaCampo === 'function') CarregaCampo();"
            )

        checkboxes = [
            ("idTitulosNormais", idTitulosNormais),
            ("idTitulosAluguel", idTitulosAluguel),
            ("idTitulosCobrancaCa", idTitulosCobrancaCa),
            ("idTitulosValeFisico", idTitulosValeFisico),
            ("idTitulosRefugo", idTitulosRefugo),
            ("idTitulosQuebras", idTitulosQuebras),
        ]
        for name, value in checkboxes:
            if value is not None:
                try:
                    self.js_set_checkbox_by_name(name, bool(value), force_click=True)
                except Exception as exc:
                    self.logger.warning(f"[SKIP] Nao foi possivel setar {name}={value}: {exc}")

        campos_input = [
            ("iniCli", iniCli),
            ("fimCli", fimCli),
            ("iniDat", iniDat),
            ("fimDat", fimDat),
            ("iniEmi", iniEmi),
            ("fimEmi", fimEmi),
            ("iniPor", iniPor),
            ("fimPor", fimPor),
            ("iniEsp", iniEsp),
            ("fimEsp", fimEsp),
            ("iniVin", iniVin),
            ("fimVin", fimVin),
        ]
        for name, value in campos_input:
            if value is not None:
                self.js_set_input_by_name(name, str(value))

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
                        nome_arquivo=nome_arquivo,
                        timeout_botao=timeout_csv,
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
