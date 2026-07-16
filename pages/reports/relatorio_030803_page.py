import time
from pathlib import Path

from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.config.settings import get_settings
from core.files.conversor_030803 import converter_030803_pdf_para_xlsx
from pages.common.rotina_page import RotinaPage


class Relatorio030803Page(RotinaPage):
    """
    Rotina 03.08.03 - conferencia das cargas.

    Essa rotina nao disponibiliza CSV. O fluxo correto e baixar PDF e converter
    o arquivo baixado para XLSX.
    """

    FRAME_ROTINA = 1

    def gerar_relatorio(
        self,
        unidade=None,
        transportadora_inicial="0",
        transportadora_final="999",
        data_inicial="00/00/0000",
        data_final="99/99/9999",
        timeout_download=550,
        nome_arquivo="030803.pdf",
    ):
        if unidade is None or isinstance(unidade, list):
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                unidades_alvo=unidade if isinstance(unidade, list) else None,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    unidade=cod,
                    transportadora_inicial=transportadora_inicial,
                    transportadora_final=transportadora_final,
                    data_inicial=data_inicial,
                    data_final=data_final,
                    timeout_download=timeout_download,
                    nome_arquivo=arq,
                ),
            )

        self.selecionar_unidade(unidade)
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=15)

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.NAME, "transportadoraInicial"))
            )
        except TimeoutException:
            self.logger.warning("Formulario 030803 demorou a renderizar.")

        try:
            self.js_set_input_by_name("transportadoraInicial", str(transportadora_inicial))
            self.js_set_input_by_name("transportadoraFinal", str(transportadora_final))
            self.js_set_input_by_name("dataInicial", str(data_inicial))
            self.js_set_input_by_name("dataFinal", str(data_final))

            botao = self.find_element((By.NAME, "BotVisualizar"))
            self.js_click_ie(botao)
            time.sleep(2)

        except UnexpectedAlertPresentException:
            self.logger.warning("Alerta durante preenchimento da rotina 030803.")
            self.lidar_com_alertas()
            raise
        finally:
            self.switch_to_default_content()

        ok_botao, msg_botao, pdf_http = self._clicar_botao_pdf_pos_visualizacao(
            timeout_download,
            nome_arquivo,
        )
        if not ok_botao:
            return ok_botao, msg_botao

        if pdf_http is not None:
            mensagem = str(pdf_http)
        else:
            ok, mensagem = self._capturar_pdf(nome_arquivo=nome_arquivo, timeout_download=timeout_download)
            if not ok:
                return ok, mensagem

        pdf_path = Path(mensagem)
        xlsx_path = converter_030803_pdf_para_xlsx(pdf_path, apagar_pdf=True)
        return True, f"PDF convertido para XLSX: {xlsx_path}"

    def _clicar_botao_pdf_pos_visualizacao(self, timeout_download, nome_arquivo):
        self.logger.info("Aguardando tela pos-Visualizar e botao PDF da rotina 030803...")
        self.switch_to_default_content()

        try:
            WebDriverWait(self.driver, timeout_download).until(
                EC.frame_to_be_available_and_switch_to_it(self.FRAME_ROTINA)
            )
        except UnexpectedAlertPresentException:
            mensagens = self.lidar_com_alertas(tentativas=2, timeout=2, timeout_entre_alertas=1, max_alertas=10)
            detalhe = " | ".join(mensagens) if mensagens else "Alerta sem texto capturado"
            self.switch_to_default_content()
            return False, f"Alerta apos visualizar antes do PDF: {detalhe}", None
        except TimeoutException:
            self.driver.switch_to.frame(self.FRAME_ROTINA)

        try:
            WebDriverWait(self.driver, timeout_download).until(
                lambda driver: driver.execute_script(
                    "return !!(document.getElementsByName('GerPDF')"
                    " && document.getElementsByName('GerPDF').length > 0);"
                )
            )
            botao_pdf = self.find_element((By.NAME, "GerPDF"))
            diretorio_base = get_settings().download_dir
            subpasta = getattr(self, "subpasta_download", None)
            diretorio = diretorio_base / subpasta if subpasta else diretorio_base

            from core.services.report_download_service import capturar_download_por_formulario

            resultado_http = capturar_download_por_formulario(
                self.driver,
                botao_pdf,
                nome_arquivo,
                diretorio_intermediario=diretorio,
                extensao_final=".pdf",
            )
            if resultado_http[0]:
                nome_pdf = nome_arquivo if str(nome_arquivo).lower().endswith(".pdf") else f"{nome_arquivo}.pdf"
                pdf_path = diretorio / nome_pdf
                self.logger.info("PDF 030803 capturado diretamente por HTTP: %s", pdf_path)
                return True, resultado_http[1], pdf_path

            self.logger.info(
                "PDF HTTP direto indisponível na 030803 (%s). Mantendo clique e captura visual.",
                resultado_http[1],
            )
            resultado = self.driver.execute_script(
                """
                try {
                    relatorio = 0;
                    if (typeof PDF === 'function') {
                        PDF();
                        return {ok: true, method: 'PDF'};
                    }
                    var botao = document.getElementsByName('GerPDF')[0];
                    if (botao) {
                        if (botao.click) {
                            botao.click();
                        } else if (botao.fireEvent) {
                            botao.fireEvent('onclick');
                        }
                        return {ok: true, method: 'click'};
                    }
                    return {ok: false, error: 'GerPDF nao encontrado'};
                } catch (e) {
                    return {ok: false, error: (e && e.message) ? e.message : String(e)};
                }
                """
            )
            if not resultado or not resultado.get("ok"):
                return False, f"Falha ao acionar PDF da rotina 030803: {resultado}", None
            self.logger.info("Botao PDF da rotina 030803 acionado via %s.", resultado.get("method"))
            time.sleep(1)
            return True, "Botao PDF clicado", None
        except UnexpectedAlertPresentException:
            mensagens = self.lidar_com_alertas(tentativas=2, timeout=2, timeout_entre_alertas=1, max_alertas=10)
            detalhe = " | ".join(mensagens) if mensagens else "Alerta sem texto capturado"
            return False, f"Alerta ao clicar no botao PDF: {detalhe}", None
        except TimeoutException:
            return False, "Botao PDF da rotina 030803 nao apareceu apos visualizar.", None
        finally:
            self.switch_to_default_content()

    def _capturar_pdf(self, nome_arquivo, timeout_download):
        try:
            from core.services.report_download_service import capturar_download_relatorio
        except ImportError as exc:
            self.logger.warning("Servico de download nao carregado: %s", exc)
            return False, "Servico de download nao carregado"

        diretorio_base = get_settings().download_dir
        subpasta = getattr(self, "subpasta_download", None)
        diretorio = diretorio_base / subpasta if subpasta else diretorio_base
        pdf_path = diretorio / (nome_arquivo if str(nome_arquivo).lower().endswith(".pdf") else f"{nome_arquivo}.pdf")

        self.logger.info("Aguardando download PDF direto da rotina 030803.")
        resultado = capturar_download_relatorio(
            nome_arquivo_final=nome_arquivo,
            diretorio_intermediario=str(diretorio),
            extensao_final=".pdf",
            driver=self.driver,
        )
        if not resultado[0]:
            return resultado

        return True, str(pdf_path)
