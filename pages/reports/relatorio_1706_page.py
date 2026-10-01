from __future__ import annotations

import time
from datetime import datetime

from selenium.common.exceptions import UnexpectedAlertPresentException
from selenium.webdriver.common.by import By

from pages.reports.relatorio_030805_page import Relatorio030805Page


class Relatorio1706Page(Relatorio030805Page):
    """17.06 (PW02468R): gera o INF de indicadores no DVS do Promax."""

    FRAME_ROTINA = 1
    DVS_INF_BY_UNIT = {
        # Puxada da revenda + sufixo da filial + marcador fixo do Promax.
        "2210003": ("PATOS", "id_000074753000031111111111.inf"),
        "2210004": ("SUME", "id_000074754800041111111111.inf"),
    }

    def gerar_relatorio(
        self,
        *,
        unidade: str,
        data_inicial: str,
        data_final: str,
        timeout_arquivo: int = 120,
        nome_arquivo: str | None = None,
    ):
        codigo = str(unidade or "").strip()
        if codigo not in self.DVS_INF_BY_UNIT:
            raise ValueError(f"17.06 não possui nome DVS mapeado para a unidade {codigo!r}.")
        inicio = datetime.strptime(str(data_inicial), "%d/%m/%Y").date()
        fim = datetime.strptime(str(data_final), "%d/%m/%Y").date()
        if (inicio.year, inicio.month) != (fim.year, fim.month):
            raise ValueError("17.06 exige data inicial e final no mesmo mês.")

        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=15)
        try:
            self.js_set_select_by_name("opcaoUnidades", codigo)
            self.js_set_select_by_name("opcaoGrupo", "4")
            for field, value in (
                ("cdDesempenhoInicial", "000"), ("cdDesempenhoFinal", "999"),
                ("cdGerenteVendasInicial", "0000"), ("cdGerenteVendasFinal", "9999"),
                ("cdSupervisorInicial", "00000"), ("cdSupervisorFinal", "99999"),
                ("cdVendedorInicial", "00000"), ("cdVendedorFinal", "99999"),
                ("cdSegmentoInicial", "00"), ("cdSegmentoFinal", "99"),
                ("dtMovimentoInicial", str(data_inicial)), ("dtMovimentoFinal", str(data_final)),
            ):
                self.js_set_input_by_name(field, value)
            self.js_set_checkbox_by_name("idInfoFiliais", False, force_click=True)
            self.js_set_checkbox_by_name("idDesempenho", True, force_click=True)
            self.js_click_ie(self.find_element((By.NAME, "BotVisualizar")))
            time.sleep(2)
        except UnexpectedAlertPresentException:
            mensagens = self.lidar_com_alertas(tentativas=1, timeout=1, max_alertas=3)
            detalhe = "; ".join(str(item).strip() for item in mensagens if str(item).strip())
            return False, f"17.06 rejeitada pelo Promax: {detalhe or 'alerta sem texto'}"
        finally:
            self.switch_to_default_content()

        revenda, nome_dvs = self.DVS_INF_BY_UNIT[codigo]
        destino = nome_arquivo or f"17.06_{revenda}_{inicio.strftime('%Y_%m')}.inf"
        return self._capturar_arquivo_dvs(nome_dvs, destino, timeout_arquivo)
