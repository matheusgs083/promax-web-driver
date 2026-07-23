from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pages.common.rotina_page import RotinaPage


class Relatorio031702Page(RotinaPage):
    """Rotina 031702 - Relatorio de documentos de clientes com CSV padrao."""

    FRAME_ROTINA = 1
    BTN_GERA_EXCEL_1 = (By.NAME, "GeraExcel")
    BTN_GERA_EXCEL_2 = (By.NAME, "GerExecl")

    def gerar_relatorio(
        self,
        unidade=None,
        cliente_inicial="0",
        cliente_final="9999999",
        tipos_documento=None,
        data_inicial=None,
        data_final=None,
        toda_geografia=False,
        documentos_faltantes=False,
        documentos_existentes=True,
        situacao_todos=False,
        ativos=True,
        bloqueados=False,
        duplicados=False,
        inativos=False,
        temporarios=False,
        em_cadastramento=False,
        acao="BotVisualizar",
        clicar_csv_apos_visualizar=True,
        nome_arquivo="031702.csv",
        timeout=20,
        timeout_csv=600,
    ):
        if tipos_documento is None:
            tipos_documento = ["001", "003", "004", "005", "016", "019"]

        if unidade is None or isinstance(unidade, list):
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                unidades_alvo=unidade if isinstance(unidade, list) else None,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    unidade=cod,
                    cliente_inicial=cliente_inicial,
                    cliente_final=cliente_final,
                    tipos_documento=tipos_documento,
                    data_inicial=data_inicial,
                    data_final=data_final,
                    toda_geografia=toda_geografia,
                    documentos_faltantes=documentos_faltantes,
                    documentos_existentes=documentos_existentes,
                    situacao_todos=situacao_todos,
                    ativos=ativos,
                    bloqueados=bloqueados,
                    duplicados=duplicados,
                    inativos=inativos,
                    temporarios=temporarios,
                    em_cadastramento=em_cadastramento,
                    acao=acao,
                    clicar_csv_apos_visualizar=clicar_csv_apos_visualizar,
                    nome_arquivo=arq,
                    timeout=timeout,
                    timeout_csv=timeout_csv,
                ),
            )

        self.selecionar_unidade(unidade)
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=timeout)

        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.NAME, "cdTpDocumento"))
            )
        except TimeoutException:
            self.logger.warning("Formulario 031702 demorou a renderizar.")

        self.js_set_checkbox_by_name("idTodaGeo", bool(toda_geografia), force_click=True)
        self.js_set_input_by_name("cdClienteInicial", cliente_inicial)
        self.js_set_input_by_name("cdClienteFinal", cliente_final)

        self._adicionar_tipos_documento(tipos_documento)

        if data_inicial is not None:
            self.js_set_input_by_name("dtInicial", data_inicial)
        if data_final is not None:
            self.js_set_input_by_name("dtFinal", data_final)

        checkboxes = [
            ("idFaltantes", documentos_faltantes),
            ("idExistentes", documentos_existentes),
            ("idTodos", situacao_todos),
            ("idAtivos", ativos),
            ("idBloqueados", bloqueados),
            ("idDuplicados", duplicados),
            ("idInativos", inativos),
            ("idTemporarios", temporarios),
            ("idEmCadastramento", em_cadastramento),
        ]
        for name, value in checkboxes:
            if value is not None:
                self.js_set_checkbox_by_name(name, bool(value), force_click=True)

        acao = (acao or "BotVisualizar").strip()
        self.logger.info("Clicando em %s na rotina 031702", acao)
        self.js_click_ie(self.find_element((By.NAME, acao)))

        self.switch_to_default_content()

        resultado_final = True
        if acao == "BotVisualizar" and clicar_csv_apos_visualizar:
            locators_export = [
                (By.XPATH, "//*[@name='GeraExcel' and @type='hidden']"),
                (By.XPATH, "//*[@name='GeraExcel']"),
                (By.XPATH, "//*[@name='GerExecl']"),
                (By.XPATH, "//*[@name='GerExcel']"),
            ]
            resultado_final = self._fluxo_exportar_csv(
                timeout_csv=timeout_csv,
                nome_arquivo=nome_arquivo,
                timeout_botao=timeout_csv,
                locators_export=locators_export,
            )

        self.switch_to_default_content()
        return resultado_final

    def _adicionar_tipos_documento(self, tipos_documento):
        itens = tipos_documento if isinstance(tipos_documento, list) else [tipos_documento]
        for item in itens:
            self.js_set_select_by_name("cdTpDocumento", str(item))
            resultado = self.driver.execute_script(
                """
                try {
                    if (typeof AdicionaTpDocumento == 'function') {
                        return {ok: AdicionaTpDocumento() !== false};
                    }
                    var btn = document.getElementsByName('BotAdic')[0];
                    if (btn) {
                        if (btn.click) btn.click();
                        else if (btn.fireEvent) btn.fireEvent('onclick');
                        return {ok: true};
                    }
                    return {ok: false, error: 'Botao BotAdic nao encontrado'};
                } catch (e) {
                    return {ok: false, error: String(e)};
                }
                """
            )
            if not resultado or not resultado.get("ok"):
                raise RuntimeError(f"Falha ao adicionar tipo de documento {item}: {resultado}")
            self.aguardar_loader_oculto(timeout=3)
