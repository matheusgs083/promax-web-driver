import time

from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pages.common.rotina_page import RotinaPage


class Relatorio030312Page(RotinaPage):
    """
    Rotina 03.03.12 - mapas por data de emissao.

    HTML base: PW02126C.
    Campos principais:
    - dataEmissao
    - idAmbev
    - idMetalfrio
    - BotIrPara / BotGeraCsv / BotGeraCsvGeo
    """

    FRAME_ROTINA = 1

    def gerar_relatorio(
        self,
        unidade=None,
        data_emissao=None,
        ambev=True,
        metalfrio=True,
        acao="BotGeraCsv",
        timeout_download=360,
        nome_arquivo="030312.csv",
    ):
        if unidade is None or isinstance(unidade, list):
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                unidades_alvo=unidade if isinstance(unidade, list) else None,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    unidade=cod,
                    data_emissao=data_emissao,
                    ambev=ambev,
                    metalfrio=metalfrio,
                    acao=acao,
                    timeout_download=timeout_download,
                    nome_arquivo=arq,
                ),
            )

        if not ambev and not metalfrio:
            raise ValueError("A rotina 030312 exige pelo menos um tipo de mapa: Ambev ou Metalfrio.")

        self.selecionar_unidade(unidade)
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=15)

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.NAME, "dataEmissao"))
            )
        except TimeoutException:
            self.logger.warning("Formulario 030312 demorou a renderizar.")

        try:
            if data_emissao is not None:
                self.js_set_input_by_name("dataEmissao", str(data_emissao))

            self.js_set_checkbox_by_name("idAmbev", bool(ambev), force_click=True)
            self._assert_checkbox("idAmbev", bool(ambev))

            self.js_set_checkbox_by_name("idMetalfrio", bool(metalfrio), force_click=True)
            self._assert_checkbox("idMetalfrio", bool(metalfrio))

            acao = (acao or "BotGeraCsv").strip()
            if acao not in {"BotIrPara", "BotGeraCsv", "BotGeraCsvGeo"}:
                raise ValueError(f"Acao invalida para 030312: {acao}")

            botao = self.find_element((By.NAME, acao))
            self.js_click_ie(botao)
            time.sleep(2)

        except UnexpectedAlertPresentException:
            self.logger.warning("Alerta durante preenchimento da rotina 030312.")
            self.lidar_com_alertas()
            raise
        finally:
            self.switch_to_default_content()

        if acao == "BotIrPara":
            return True

        return self._capturar_download_csv_direto(
            timeout_download=timeout_download,
            nome_arquivo=nome_arquivo,
        )

    def _capturar_download_csv_direto(self, timeout_download, nome_arquivo):
        if not getattr(self, "_download_service_disponivel", True):
            return False, "Servico de download indisponivel"

        try:
            from core.services.report_download_service import capturar_download_relatorio
            from core.config.settings import get_settings
        except ImportError as exc:
            self.logger.warning("Servico de download nao carregado: %s", exc)
            return False, "Servico de download nao carregado"

        diretorio_base = get_settings().download_dir
        subpasta = getattr(self, "subpasta_download", None)
        diretorio = diretorio_base / subpasta if subpasta else diretorio_base

        self.logger.info("Aguardando download CSV direto da rotina 030312.")
        return capturar_download_relatorio(
            diretorio_destino=str(diretorio),
            nome_arquivo_final=nome_arquivo,
        )
