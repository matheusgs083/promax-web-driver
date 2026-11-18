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
    # A 17.06 não mantém um nome estável para todas as revendas.  Patos
    # normalmente gera o INF conhecido acima, enquanto Sumé pode publicar o
    # CSV com o prefixo NOCRIPTO e um sufixo de data/hora.  O prefixo é a
    # parte estável e permite usar a mesma captura direta no DVS da 03.08.05.
    DVS_PREFIX_BY_UNIT = {
        "2210003": "0000747530",
        "2210004": "0000747548",
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

        # A filial selecionada no formulário não troca a unidade da sessão
        # Promax. Sem esta etapa a segunda execução continuava na unidade
        # que abriu a rotina (Patos), embora o formulário exibisse Sumé.
        # A 03.08.05 já usa a mesma troca de contexto antes de gerar.
        self.selecionar_unidade(codigo)
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=15)
        inicio_geracao = time.time()
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
        return self._capturar_arquivo_gerado(
            nome_dvs=nome_dvs,
            prefixo_dvs=self.DVS_PREFIX_BY_UNIT[codigo],
            nome_final=destino,
            timeout_arquivo=timeout_arquivo,
            inicio_geracao=inicio_geracao,
        )

    def _capturar_arquivo_gerado(
        self,
        *,
        nome_dvs: str,
        prefixo_dvs: str,
        nome_final: str,
        timeout_arquivo: int,
        inicio_geracao: float,
    ):
        """Captura o arquivo recém-gerado no DVS, como a 03.08.05.

        A busca por prefixo evita que a rotina fique presa a um nome de INF
        obsoleto quando o Promax exporta a versão ``id_NOCRIPTO``.
        """
        destino = self._diretorio_arquivo_1706(nome_final)
        prazo = time.time() + timeout_arquivo
        while time.time() < prazo:
            origem = self._arquivo_dvs_recente(prefixo_dvs, inicio_geracao)
            if origem is not None:
                try:
                    destino.write_bytes(origem.read_bytes())
                except OSError as exc:
                    self.logger.debug("Falha ao copiar 17.06 do DVS %s: %s", origem, exc)
                else:
                    self.logger.info("Arquivo 17.06 capturado da rede Promax: %s -> %s", origem, destino)
                    return True, f"Arquivo 17.06 capturado na rede Promax: {destino}"
            time.sleep(3)

        # Mantém os fallbacks HTTP/navegador da 03.08.05 para instalações em
        # que o compartilhamento DVS não esteja acessível ao worker.
        return self._capturar_arquivo_dvs(nome_dvs, nome_final, timeout_arquivo=15)

    def _diretorio_arquivo_1706(self, nome_final: str):
        destino_dir = self._diretorio_destino_1706()
        destino_dir.mkdir(parents=True, exist_ok=True)
        destino = destino_dir / nome_final
        return destino if destino.suffix else destino.with_suffix(".inf")

    def _diretorio_destino_1706(self):
        from core.config.settings import get_settings

        subpasta = getattr(self, "subpasta_download", None)
        return get_settings().download_dir / subpasta if subpasta else get_settings().download_dir

    def _arquivo_dvs_recente(self, prefixo_dvs: str, inicio_geracao: float):
        try:
            candidatos = [
                path for path in (self.NETWORK_BASE_PATH / self.NETWORK_DVS_PATH).iterdir()
                if path.is_file()
                and prefixo_dvs in path.name
                and path.suffix.lower() in {".inf", ".csv"}
                and path.stat().st_mtime >= inicio_geracao - 5
            ]
        except OSError as exc:
            self.logger.debug("Não foi possível listar o DVS da 17.06: %s", exc)
            return None
        return max(candidatos, key=lambda path: path.stat().st_mtime, default=None)
