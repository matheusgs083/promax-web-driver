import re
import shutil
import time
from pathlib import Path

from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.config.settings import get_settings
from core.tools.validador_visual import validar_elemento
from pages.common.rotina_page import RotinaPage

import pyautogui


class Relatorio030206Page(RotinaPage):
    """Rotina 03.02.06 - teste controlado de geracao PDF por intervalo."""

    FRAME_ROTINA = 1

    JS_ENVIAR_PDF_DIRETO = r"""
    try {
        if (document.all && document.all.opcao) {
            document.all.opcao.value = 4;
        }
        if (typeof EnviarFormulario === 'function') {
            EnviarFormulario();
        } else if (document.forms && document.forms.length > 0) {
            document.forms[0].submit();
        } else {
            return {ok: false, error: 'formulario indisponivel'};
        }
        try {
            if (typeof DisplayLoop === 'function') DisplayLoop();
        } catch (eLoop) {}
        return {ok: true};
    } catch (e) {
        return {ok: false, error: (e && e.message) ? e.message : String(e)};
    }
    """

    def _entrar_frame_formulario(self, timeout=15):
        self.switch_to_default_content()
        prazo = time.time() + timeout
        ultimo_erro = None

        while time.time() < prazo:
            try:
                if self.driver.execute_script("return !!document.getElementsByName('banco').length;"):
                    return

                frames = self.driver.find_elements(By.TAG_NAME, "frame")
                frames += self.driver.find_elements(By.TAG_NAME, "iframe")
                for indice in range(len(frames)):
                    self.switch_to_default_content()
                    frames_atualizados = self.driver.find_elements(By.TAG_NAME, "frame")
                    frames_atualizados += self.driver.find_elements(By.TAG_NAME, "iframe")
                    if indice >= len(frames_atualizados):
                        continue
                    self.driver.switch_to.frame(frames_atualizados[indice])
                    if self.driver.execute_script("return !!document.getElementsByName('banco').length;"):
                        return
            except Exception as exc:
                ultimo_erro = exc

            self.switch_to_default_content()
            time.sleep(0.5)

        raise TimeoutException(f"Campo banco nao encontrado nos frames da 030206: {ultimo_erro}")

    def testar_pdf_intervalo_direto(
        self,
        unidade=None,
        banco="237",
        armazem="01",
        emissao_inicial=None,
        emissao_final=None,
        por_vencimento=False,
        timeout_download=180,
        nome_arquivo="030206_teste_pdf_intervalo.pdf",
    ):
        if unidade is None or isinstance(unidade, list):
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                unidades_alvo=unidade if isinstance(unidade, list) else None,
                fn_execucao_unica=lambda cod, arq: self.testar_pdf_intervalo_direto(
                    unidade=cod,
                    banco=banco,
                    armazem=armazem,
                    emissao_inicial=emissao_inicial,
                    emissao_final=emissao_final,
                    por_vencimento=por_vencimento,
                    timeout_download=timeout_download,
                    nome_arquivo=arq,
                ),
            )

        if unidade:
            self.selecionar_unidade(unidade)

        self._entrar_frame_formulario(timeout=15)
        WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.NAME, "banco")))

        try:
            self.js_set_select_by_name("banco", banco)
            self.driver.execute_script("if (typeof VerificaBanco === 'function') VerificaBanco();")
            time.sleep(1)

            self.js_set_select_by_name("cdArmazem", armazem)
            self.js_set_input_by_name("emissaoInicial", emissao_inicial)
            self.js_set_input_by_name("emissaoFinal", emissao_final)
            self.js_set_checkbox_by_name("idDtVencto", bool(por_vencimento), force_click=True)

            resultado = self.driver.execute_script(self.JS_ENVIAR_PDF_DIRETO)
            if not resultado or not resultado.get("ok"):
                return False, f"ERRO_JS: {resultado}"

            time.sleep(1)
        except UnexpectedAlertPresentException:
            mensagens = self.lidar_com_alertas(tentativas=2, timeout=2, timeout_entre_alertas=1, max_alertas=10)
            detalhe = " | ".join(mensagens) if mensagens else "Alerta sem texto capturado"
            return False, f"ALERTA_BACKEND: {detalhe}"
        finally:
            try:
                self.switch_to_default_content()
            except UnexpectedAlertPresentException:
                mensagens = self.lidar_com_alertas(tentativas=2, timeout=2, timeout_entre_alertas=1, max_alertas=10)
                detalhe = " | ".join(mensagens) if mensagens else "Alerta sem texto capturado"
                return False, f"ALERTA_BACKEND: {detalhe}"

        diretorio_base = get_settings().download_dir
        subpasta = getattr(self, "subpasta_download", None)
        diretorio = diretorio_base / subpasta if subpasta else diretorio_base

        try:
            from core.services.report_download_service import capturar_url_temporaria

            resultado_http = capturar_url_temporaria(
                self.driver,
                nome_arquivo,
                diretorio_intermediario=diretorio,
                extensao_final=".pdf",
                timeout_segundos=15,
            )
        except Exception as exc:
            resultado_http = False, f"Captura HTTP indisponível: {exc}"

        if resultado_http[0]:
            self.logger.info("PDF 030206 capturado diretamente por HTTP: %s", resultado_http[1])
            return True, f"DOWNLOAD_OK: {diretorio / nome_arquivo}"

        self.logger.info(
            "PDF HTTP direto não localizado na 030206 (%s). Mantendo captura especial de logs.",
            resultado_http[1],
        )
        resultado_download = self._capturar_pdf_ignorando_logs(
            nome_arquivo=nome_arquivo,
            diretorio_destino=diretorio,
            timeout_download=timeout_download,
        )
        if resultado_download[0]:
            return True, f"DOWNLOAD_OK: {diretorio / nome_arquivo}"

        return False, f"SEM_DOWNLOAD: {resultado_download[1]}"

    def _capturar_pdf_ignorando_logs(self, nome_arquivo, diretorio_destino, timeout_download):
        pasta_downloads = Path.home() / "Downloads"
        diretorio_destino = Path(diretorio_destino)
        pasta_downloads.mkdir(parents=True, exist_ok=True)
        diretorio_destino.mkdir(parents=True, exist_ok=True)

        nome_limpo = re.sub(r'[\\/*?:"<>|]', "_", str(nome_arquivo))
        if not nome_limpo.lower().endswith(".pdf"):
            nome_limpo += ".pdf"
        caminho_final = diretorio_destino / nome_limpo

        arquivos_conhecidos = set(pasta_downloads.iterdir())
        prazo = time.time() + timeout_download
        logs_ignorados = 0
        alertas = []

        while time.time() < prazo:
            self._aceitar_alertas_pendentes(alertas)

            box_btn = validar_elemento("botaoDownload.png", timeout=15, confidence=0.8)
            if not box_btn:
                self._aceitar_alertas_pendentes(alertas)
                continue

            x, y = pyautogui.center(box_btn)
            pyautogui.moveTo(x, y, duration=0.3)
            time.sleep(0.2)
            pyautogui.click()

            arquivo = self._aguardar_arquivo_novo(pasta_downloads, arquivos_conhecidos, timeout=45)
            if arquivo is None:
                pyautogui.hotkey("alt", "s")
                arquivo = self._aguardar_arquivo_novo(pasta_downloads, arquivos_conhecidos, timeout=45)

            if arquivo is None:
                self._aceitar_alertas_pendentes(alertas)
                continue

            arquivos_conhecidos.add(arquivo)
            if self._eh_pdf_real(arquivo):
                if caminho_final.exists():
                    caminho_final.unlink()
                shutil.move(str(arquivo), str(caminho_final))
                self.logger.info(
                    "PDF real 030206 capturado: %s (logs ignorados: %s, alertas: %s)",
                    caminho_final,
                    logs_ignorados,
                    alertas,
                )
                return True, f"PDF capturado: {caminho_final}"

            logs_ignorados += 1
            self.logger.info("Download intermediario/log ignorado na 030206: %s", arquivo)
            try:
                arquivo.unlink()
            except Exception as exc:
                self.logger.warning("Nao foi possivel apagar download intermediario %s: %s", arquivo, exc)

            self._aguardar_e_fechar_popup_pre_download(alertas, timeout=60)
            self._aceitar_alertas_pendentes(alertas)

        return False, f"Timeout aguardando PDF real da 030206. Logs ignorados: {logs_ignorados}. Alertas: {alertas}"

    def _aguardar_arquivo_novo(self, pasta_downloads, arquivos_antes, timeout):
        prazo = time.time() + timeout
        ignoradas = {".tmp", ".crdownload", ".part", ".partial", ".ini"}

        while time.time() < prazo:
            for arquivo in set(pasta_downloads.iterdir()) - set(arquivos_antes):
                if not arquivo.is_file() or arquivo.suffix.lower() in ignoradas:
                    continue
                if self._arquivo_pronto(arquivo):
                    return arquivo
            time.sleep(0.5)
        return None

    @staticmethod
    def _arquivo_pronto(arquivo):
        try:
            if arquivo.stat().st_size <= 0:
                return False
            with arquivo.open("rb"):
                return True
        except PermissionError:
            return False

    @staticmethod
    def _eh_pdf_real(arquivo):
        try:
            with arquivo.open("rb") as fp:
                return fp.read(5) == b"%PDF-"
        except Exception:
            return False

    def _aceitar_alertas_pendentes(self, alertas):
        while True:
            try:
                alert = self.driver.switch_to.alert
                texto = str(alert.text)
                alertas.append(texto)
                self.logger.info("Popup/alerta 030206 aceito: %s", texto)
                alert.accept()
                time.sleep(0.5)
            except Exception:
                return

    def _aguardar_e_fechar_popup_pre_download(self, alertas, timeout=60):
        prazo = time.time() + timeout
        while time.time() < prazo:
            tamanho_antes = len(alertas)
            self._aceitar_alertas_pendentes(alertas)
            if len(alertas) > tamanho_antes:
                return True
            time.sleep(0.5)

        self.logger.warning("Popup pre-download da 030206 nao apareceu em %ss; seguindo para procurar o PDF.", timeout)
        return False
