from __future__ import annotations

import re
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.config.settings import get_settings
from pages.common.rotina_page import RotinaPage


class Relatorio030805Page(RotinaPage):
    """
    Rotina 03.08.05 (PW02201R) - gera arquivo DVS no servidor.

    A rotina nao dispara download no navegador. Depois de gerar, o arquivo fica
    disponivel no Promax abaixo da base de rede \\paubrasil.promaxcloud.com.br\\integ,
    com o padrao 2artdDD_XXXX.txt, onde DD e o dia e XXXX e o sufixo da filial.
    """

    FRAME_ROTINA = 1
    NETWORK_BASE_PATH = Path(r"\\paubrasil.promaxcloud.com.br\integ")
    NETWORK_DVS_PATH = Path("dvs")
    FILES_BASE_PATH = "/arquivos/"
    DVS_BROWSE_PATH = "browse/dvs/"
    DVS_DIRECT_PATH = "dvs/"

    def gerar_relatorio(
        self,
        unidade=None,
        opcao_rel="1",
        data_inicial=None,
        data_final=None,
        transportadora="1",
        timeout_arquivo=90,
        nome_arquivo=None,
    ):
        if unidade is None or isinstance(unidade, list):
            return self.loop_unidades(
                nome_arquivo=nome_arquivo or "2artdDD_nomeUnidade030805.txt",
                unidades_alvo=unidade if isinstance(unidade, list) else None,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    unidade=cod,
                    opcao_rel=opcao_rel,
                    data_inicial=data_inicial,
                    data_final=data_final,
                    transportadora=transportadora,
                    timeout_arquivo=timeout_arquivo,
                    nome_arquivo=arq,
                ),
            )

        if not data_inicial or not data_final:
            raise ValueError("030805 exige data_inicial e data_final.")

        self.selecionar_unidade(unidade)
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=15)

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.NAME, "opcaoRel"))
            )
        except TimeoutException:
            self.logger.warning("Formulario 030805 demorou a renderizar.")

        alerta_visualizar = None
        try:
            self.js_set_select_by_name("opcaoRel", str(opcao_rel))
            self.js_set_input_by_name("dataInicial", str(data_inicial))
            self.js_set_input_by_name("dataFinal", str(data_final))
            self.js_set_input_by_name("transp", str(transportadora))

            botao = self.find_element((By.NAME, "BotVisualizar"))
            self.js_click_ie(botao)
            time.sleep(2)
        except UnexpectedAlertPresentException:
            alerta_visualizar = self._drenar_alerta_visualizar()
        finally:
            try:
                self.switch_to_default_content()
            except UnexpectedAlertPresentException:
                alerta_visualizar = self._drenar_alerta_visualizar()
                self.switch_to_default_content()

        if alerta_visualizar:
            return False, f"030805 rejeitada pelo Promax: {alerta_visualizar}"

        data_ref = _parse_data_br(data_inicial)
        filial = _sufixo_filial(unidade)
        nome_servidor = f"2artd{data_ref.day:02d}_{filial}.txt"
        nome_final = nome_arquivo or nome_servidor
        return self._capturar_arquivo_dvs(nome_servidor, nome_final, timeout_arquivo)

    def _drenar_alerta_visualizar(self) -> str | None:
        alertas = self.lidar_com_alertas(tentativas=1, timeout=1, max_alertas=3)
        mensagens = [str(item).strip() for item in alertas if str(item).strip()]
        mensagem = "; ".join(mensagens)
        if not mensagem:
            self.logger.info("Alerta sem texto apos Visualizar da 030805 ignorado; seguindo para capturar arquivo DVS.")
            return None
        self.logger.warning("Alerta durante Visualizar da rotina 030805: %s", mensagem)
        return mensagem

    def _capturar_arquivo_dvs(self, nome_servidor: str, nome_final: str, timeout_arquivo: int):
        destino = _diretorio_destino(getattr(self, "subpasta_download", None))
        destino.mkdir(parents=True, exist_ok=True)
        caminho_final = destino / nome_final
        if not caminho_final.suffix:
            caminho_final = caminho_final.with_suffix(".txt")

        sessao = requests.Session()
        for cookie in self._cookies_driver():
            nome = cookie.get("name")
            valor = cookie.get("value")
            dominio = cookie.get("domain")
            if not nome or valor is None:
                continue
            if dominio:
                sessao.cookies.set(nome, valor, domain=dominio)
            else:
                sessao.cookies.set(nome, valor)

        base_url = _base_url(self.driver.current_url)
        arquivos_url = urljoin(base_url, self.FILES_BASE_PATH)
        browse_url = urljoin(arquivos_url, self.DVS_BROWSE_PATH)
        direct_dvs_url = urljoin(arquivos_url, self.DVS_DIRECT_PATH)
        file_urls = _dedupe_urls(
            urljoin(browse_url, nome_servidor),
            urljoin(direct_dvs_url, nome_servidor),
        )
        browse_urls = _dedupe_urls(browse_url, direct_dvs_url, arquivos_url)
        prazo = time.time() + timeout_arquivo
        ultimo_erro = "arquivo ainda nao encontrado"

        while time.time() < prazo:
            if self._capturar_arquivo_dvs_rede(nome_servidor, caminho_final):
                return True, f"Arquivo 030805 capturado na rede Promax: {caminho_final}"

            for url in file_urls:
                try:
                    resp = sessao.get(url, timeout=15, allow_redirects=True)
                except Exception as exc:  # pragma: no cover - depende de rede Promax
                    ultimo_erro = str(exc)
                    continue

                if resp.status_code == 200 and _parece_txt_dvs(resp.content):
                    caminho_final.write_bytes(resp.content)
                    return True, f"Arquivo 030805 capturado: {caminho_final}"
                ultimo_erro = f"HTTP {resp.status_code} em {url}"

            for url in browse_urls:
                try:
                    resp = sessao.get(url, timeout=15, allow_redirects=True)
                except Exception as exc:  # pragma: no cover - depende de rede Promax
                    ultimo_erro = str(exc)
                    continue

                if resp.status_code == 200 and nome_servidor.lower() in resp.text.lower():
                    href = _extrair_href(resp.text, nome_servidor) or nome_servidor
                    try:
                        arq = sessao.get(urljoin(url, href), timeout=15, allow_redirects=True)
                        if arq.status_code == 200 and _parece_txt_dvs(arq.content):
                            caminho_final.write_bytes(arq.content)
                            return True, f"Arquivo 030805 capturado: {caminho_final}"
                    except Exception as exc:  # pragma: no cover
                        ultimo_erro = str(exc)

                ultimo_erro = f"HTTP {resp.status_code} em {url}"

            for file_url in file_urls:
                try:
                    if self._capturar_arquivo_dvs_pelo_navegador(file_url, caminho_final):
                        return True, f"Arquivo 030805 capturado pelo navegador: {caminho_final}"
                except Exception as exc:  # pragma: no cover - depende do navegador Promax
                    ultimo_erro = f"fallback navegador: {exc}"
            time.sleep(3)

        return False, f"Arquivo {nome_servidor} nao encontrado a partir de {arquivos_url}: {ultimo_erro}"

    def _capturar_arquivo_dvs_rede(self, nome_servidor: str, caminho_final: Path) -> bool:
        origem = self.NETWORK_BASE_PATH / self.NETWORK_DVS_PATH / nome_servidor
        try:
            if not origem.exists() or not origem.is_file():
                return False
            content = origem.read_bytes()
        except OSError as exc:
            self.logger.debug("Nao foi possivel ler arquivo 030805 na rede Promax %s: %s", origem, exc)
            return False

        if not _parece_txt_dvs(content):
            self.logger.debug("Arquivo 030805 encontrado na rede, mas conteudo nao parece TXT DVS: %s", origem)
            return False

        caminho_final.write_bytes(content)
        self.logger.info("Arquivo 030805 capturado da rede Promax: %s -> %s", origem, caminho_final)
        return True

    def _cookies_driver(self):
        try:
            cookies = self.driver.get_cookies()
        except Exception as exc:  # pragma: no cover - depende do driver IE
            self.logger.warning("Nao foi possivel ler cookies do navegador Promax: %s", exc)
            return []

        cookies_normalizados = []
        for cookie in cookies or []:
            if isinstance(cookie, dict):
                cookies_normalizados.append(cookie)
                continue
            if isinstance(cookie, str) and "=" in cookie:
                nome, valor = cookie.split("=", 1)
                nome = nome.strip()
                if nome:
                    cookies_normalizados.append({"name": nome, "value": valor.strip()})
                continue
            self.logger.debug("Cookie Promax ignorado por formato inesperado: %r", cookie)
        return cookies_normalizados

    def _capturar_arquivo_dvs_pelo_navegador(self, file_url: str, caminho_final: Path) -> bool:
        handle_original = self.driver.current_window_handle
        handles_antes = set(self.driver.window_handles)
        self.driver.execute_script("window.open(arguments[0], '_blank');", file_url)
        WebDriverWait(self.driver, 10).until(lambda drv: len(set(drv.window_handles) - handles_antes) >= 1)
        novo_handle = next(iter(set(self.driver.window_handles) - handles_antes))
        try:
            self.driver.switch_to.window(novo_handle)
            WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            body_text = self.driver.find_element(By.TAG_NAME, "body").text or ""
            page_source = self.driver.page_source or ""
            if not body_text.strip():
                return False
            lower_source = page_source[:500].lower()
            lower_text = body_text[:500].lower()
            if "<html" in lower_source and any(token in lower_text for token in ("404", "not found", "não encontrado", "nao encontrado", "sessão", "sessao")):
                return False
            data = body_text.encode("cp1252", errors="replace")
            if not _parece_txt_dvs(data):
                return False
            caminho_final.write_bytes(data)
            return True
        finally:
            try:
                self.driver.close()
            finally:
                self.driver.switch_to.window(handle_original)
                self.switch_to_default_content()


def _parse_data_br(value: str) -> date:
    return datetime.strptime(str(value), "%d/%m/%Y").date()


def _sufixo_filial(unidade) -> str:
    digitos = re.sub(r"\D", "", str(unidade or ""))
    return (digitos[-4:] if digitos else "0000").zfill(4)


def _base_url(current_url: str) -> str:
    parsed = urlparse(current_url)
    if not parsed.scheme or not parsed.netloc:
        return "http://paubrasil.promaxcloud.com.br:8080/"
    return f"{parsed.scheme}://{parsed.netloc}/"


def _diretorio_destino(subpasta: str | None) -> Path:
    base = get_settings().download_dir
    return base / subpasta if subpasta else base


def _dedupe_urls(*urls: str) -> list[str]:
    vistos = set()
    unicos = []
    for url in urls:
        if url and url not in vistos:
            vistos.add(url)
            unicos.append(url)
    return unicos


def _parece_txt_dvs(content: bytes) -> bool:
    if not content:
        return False
    sample = content[:300].lower()
    return b"<html" not in sample and b"<!doctype" not in sample


def _extrair_href(html: str, nome_arquivo: str) -> str | None:
    pattern = re.compile(r"href=[\"']([^\"']*" + re.escape(nome_arquivo) + r")[\"']", re.I)
    match = pattern.search(html)
    return match.group(1) if match else None
