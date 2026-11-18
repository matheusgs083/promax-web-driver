"""Envio das requisicoes ao Promax e gravacao do rastro para diagnostico."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from threading import Lock
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from promax_http.erros import PromaxInacessivel
from http.cookiejar import CookieJar

ENCODING = "cp1252"
USER_AGENT = "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 10.0; Win64; x64; Trident/7.0)"
_CAMPOS_SECRETOS = re.compile(r"senha|pass", re.IGNORECASE)


@dataclass
class Resposta:
    url: str
    status: int
    content_type: str
    corpo: bytes

    @property
    def texto(self) -> str:
        return self.corpo.decode(ENCODING, errors="replace")


class Transporte:
    def __init__(self, *, timeout: float = 600, pasta_rastro: Path | None = None) -> None:
        self.timeout = timeout
        self.pasta_rastro = pasta_rastro
        self._sequencia = 0
        self._trava_rastro = Lock()
        self._ultima_url = ""
        self._opener = build_opener(HTTPCookieProcessor(CookieJar()))
        if pasta_rastro:
            pasta_rastro.mkdir(parents=True, exist_ok=True)

    def baixar(self, url: str, destino: Path, *, ao_progredir=None, intervalo_log: float = 5.0) -> tuple[int, str, int]:
        """Baixa um arquivo em partes direto para <destino>.parcial.

        Relatorios grandes (dezenas de MB) nao passam pela memoria inteira e o
        progresso aparece no log. Devolve (status HTTP, content-type, bytes).
        """
        headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        if self._ultima_url:
            headers["Referer"] = self._ultima_url
        parcial = destino.with_suffix(destino.suffix + ".parcial")
        parcial.parent.mkdir(parents=True, exist_ok=True)
        inicio = ultimo_log = time.time()
        total = 0
        try:
            with self._opener.open(Request(url, headers=headers), timeout=self.timeout) as r:
                status, content_type = r.status, str(r.headers.get("Content-Type", ""))
                with parcial.open("wb") as arquivo:
                    while True:
                        bloco = r.read(1024 * 1024)
                        if not bloco:
                            break
                        arquivo.write(bloco)
                        total += len(bloco)
                        if ao_progredir and time.time() - ultimo_log >= intervalo_log:
                            ao_progredir(total, time.time() - inicio)
                            ultimo_log = time.time()
        except HTTPError as exc:
            parcial.unlink(missing_ok=True)
            status, content_type, total = exc.code, "", 0
        except (URLError, TimeoutError, ConnectionError) as exc:
            parcial.unlink(missing_ok=True)
            raise PromaxInacessivel(f"Download interrompido em {url.split('?')[0]}: {exc}") from exc
        self._ultima_url = url
        self._registrar_download(url, status, content_type, total, time.time() - inicio)
        return status, content_type, total

    def _proxima_sequencia(self) -> int:
        # Varias unidades podem baixar ao mesmo tempo; a numeracao do rastro nao pode repetir.
        with self._trava_rastro:
            self._sequencia += 1
            return self._sequencia

    def _registrar_download(self, url, status, content_type, total, duracao) -> None:
        if not self.pasta_rastro:
            return
        (self.pasta_rastro / f"{self._proxima_sequencia():03d}_DOWNLOAD.json").write_text(
            json.dumps(
                {"metodo": "GET", "url": url, "status": status, "content_type": content_type,
                 "bytes": total, "segundos": round(duracao, 2)},
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )

    def get(self, url: str) -> Resposta:
        return self._enviar("GET", url, None)

    def post(self, url: str, campos: dict[str, str] | list[tuple[str, str]]) -> Resposta:
        return self._enviar("POST", url, campos)

    def _enviar(self, metodo: str, url: str, campos) -> Resposta:
        pares = list(campos.items()) if isinstance(campos, dict) else list(campos or [])
        dados = urlencode(pares, encoding=ENCODING).encode("ascii") if metodo == "POST" else None
        headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        if self._ultima_url:
            headers["Referer"] = self._ultima_url
        if dados is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        inicio = time.time()
        try:
            with self._opener.open(Request(url, data=dados, headers=headers, method=metodo), timeout=self.timeout) as r:
                resposta = Resposta(
                    url=r.geturl(),
                    status=r.status,
                    content_type=str(r.headers.get("Content-Type", "")),
                    corpo=r.read(),
                )
        except HTTPError as exc:
            # 3xx/4xx/5xx do Promax tambem sao respostas: o chamador decide o que fazer.
            resposta = Resposta(
                url=exc.geturl() or url,
                status=exc.code,
                content_type=str(exc.headers.get("Content-Type", "")) if exc.headers else "",
                corpo=exc.read() or b"",
            )
        except (URLError, TimeoutError, ConnectionError) as exc:
            raise PromaxInacessivel(f"Sem resposta do Promax em {url.split('?')[0]}: {exc}") from exc
        self._ultima_url = url
        self._gravar_rastro(metodo, url, pares, resposta, time.time() - inicio)
        return resposta

    def _gravar_rastro(self, metodo, url, pares, resposta: Resposta, duracao: float) -> None:
        if not self.pasta_rastro:
            return
        base = self.pasta_rastro / f"{self._proxima_sequencia():03d}_{metodo}"
        mascarados = [(k, "***" if _CAMPOS_SECRETOS.search(k) else v) for k, v in pares]
        base.with_suffix(".json").write_text(
            json.dumps(
                {
                    "metodo": metodo,
                    "url": url,
                    "campos": mascarados,
                    "status": resposta.status,
                    "content_type": resposta.content_type,
                    "bytes": len(resposta.corpo),
                    "segundos": round(duracao, 2),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        extensao = ".html" if "html" in resposta.content_type.lower() or not resposta.content_type else ".bin"
        # Arquivos de relatorio podem ter varios MB; no rastro basta o comeco.
        corpo = resposta.texto if extensao == ".html" else resposta.corpo[:65536].decode(ENCODING, "replace")
        # A tela de login devolve um token de senha num campo oculto; nao gravamos.
        corpo = re.sub(r'(name=["\']?Senha["\']?\s+value=["\']?)[^"\'\s>]*', r"\1***", corpo, flags=re.IGNORECASE)
        base.with_suffix(extensao).write_text(corpo, encoding="utf-8")
