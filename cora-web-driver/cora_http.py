"""Critica do Cora por HTTP, sem navegador.

Caminho (igual ao que a tela faz):
1. Login no Keycloak da Ambev (realm Third): abre a pagina de login, envia
   usuario e senha no formulario e troca o "code" devolvido por um token.
2. Le a consulta salva "Critica" na API de pedidos e monta o pedido do CSV
   com a data de entrega desejada.
3. Pede o CSV (generate-csv), acompanha o gerenciador de downloads ate o
   arquivo ficar pronto e baixa pelo link temporario do Azure.

Grade de estoque (Pedidos > Grade de Estoque > exportar CSV): mesmo login e
mesmo gerenciador; o pedido do CSV e feito por filial na API allocation-stock.
"""
from __future__ import annotations

import html
import json
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener

AUTH_BASE = "https://auth.ambevdevs.com.br/realms/Third/protocol/openid-connect"
CLIENT_ID = "ambev-hercules-autorizacao"
REDIRECT_URI = "https://cora-revenda.ambev.com.br/"
TENANT = "ambev-hercules-autorizacao-tenant-bra-3pd"
API_PEDIDOS = "https://apim.ambevdevs.com.br/pedidos/orders/v1"
API_DOWNLOADS = "https://apim.ambevdevs.com.br/foundation-cora/download-center/v1"
API_ESTOQUE = "https://apim.ambevdevs.com.br/pedidos/allocation-stock/v1/api"
FILTRO_DATA_ENTREGA = "52bedfa2-a540-473e-bec6-68b1fa004239"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0"
)

# Status do gerenciador de downloads (enum do proprio portal).
PRONTO = 2
STATUS_FALHA = {3: "removido", 4: "erro", 5: "cancelado"}

_FORM_LOGIN = re.compile(r'<form[^>]*action="([^"]*login-actions/authenticate[^"]*)"', re.IGNORECASE)
_ERRO_LOGIN = re.compile(
    r'(?:id="input-error[^"]*"|class="[^"]*(?:kc-feedback-text|alert-error|pf-c-alert__title)[^"]*")[^>]*>\s*([^<]+)',
    re.IGNORECASE,
)


class CoraErro(RuntimeError):
    pass


class CoraBloqueado(CoraErro):
    """A protecao anti-robo (Imperva) recusou o pedido."""


@dataclass
class Resposta:
    status: int
    corpo: bytes
    cabecalhos: dict[str, str] = field(default_factory=dict)

    @property
    def texto(self) -> str:
        return self.corpo.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.texto) if self.corpo else None


class _SemRedirecionar(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401 - devolve o 302 para quem chamou
        return None


class Transporte:
    """Envia pedidos com cookies e sem seguir redirecionamentos."""

    def __init__(self, timeout: float = 120) -> None:
        self.timeout = timeout
        self._abrir = build_opener(HTTPCookieProcessor(CookieJar()), _SemRedirecionar()).open

    def enviar(self, metodo: str, url: str, *, cabecalhos: dict[str, str] | None = None, corpo: bytes | None = None) -> Resposta:
        pedido = Request(url, data=corpo, method=metodo, headers={"User-Agent": USER_AGENT, **(cabecalhos or {})})
        try:
            with self._abrir(pedido, timeout=self.timeout) as r:
                return Resposta(r.status, r.read(), dict(r.headers.items()))
        except HTTPError as erro:
            return Resposta(erro.code, erro.read() or b"", dict(erro.headers.items()) if erro.headers else {})
        except URLError as erro:
            raise CoraErro(f"Sem conexao com {urlsplit(url).netloc}: {erro.reason}") from erro


def _parece_bloqueio(resposta: Resposta) -> bool:
    texto = resposta.texto[:3000].lower()
    return "incapsula" in texto or "_incapsula_resource" in texto or "request unsuccessful" in texto


class ClienteCora:
    def __init__(self, transporte: Transporte | None = None, *, log: Callable[[str], None] = print,
                 dormir: Callable[[float], None] = time.sleep, agora: Callable[[], datetime] | None = None) -> None:
        self.http = transporte or Transporte()
        self.log = log
        self.dormir = dormir
        self.agora = agora or (lambda: datetime.now(timezone.utc))
        self.token = ""

    # ---- login -------------------------------------------------------------
    def login(self, usuario: str, senha: str) -> None:
        if not usuario or not senha:
            raise CoraErro("CORA_USER/CORA_PASS nao configurados no .env do worker.")
        self.log("Abrindo o login da Ambev (Keycloak) ...")
        consulta = urlencode({
            "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI, "state": str(uuid.uuid4()),
            "response_mode": "fragment", "response_type": "code", "scope": "openid", "nonce": str(uuid.uuid4()),
        })
        pagina = self.http.enviar("GET", f"{AUTH_BASE}/auth?{consulta}")
        acao = _FORM_LOGIN.search(pagina.texto)
        if not acao:
            if _parece_bloqueio(pagina) or pagina.status in (403, 429):
                raise CoraBloqueado(f"A protecao anti-robo do login recusou o acesso (HTTP {pagina.status}).")
            raise CoraErro(f"Pagina de login inesperada (HTTP {pagina.status}).")

        self.log("Enviando usuario e senha ...")
        envio = self.http.enviar(
            "POST", html.unescape(acao.group(1)),
            cabecalhos={"Content-Type": "application/x-www-form-urlencoded"},
            corpo=urlencode({"username": usuario, "password": senha, "credentialId": ""}).encode(),
        )
        codigo = _codigo_do_redirecionamento(envio.cabecalhos.get("Location", ""))
        if not codigo:
            if _parece_bloqueio(envio) or envio.status in (403, 429):
                raise CoraBloqueado(f"A protecao anti-robo recusou o envio do login (HTTP {envio.status}).")
            erro = _ERRO_LOGIN.search(envio.texto)
            motivo = html.unescape(erro.group(1)).strip() if erro else f"HTTP {envio.status}"
            raise CoraErro(f"Login do Cora recusado: {motivo}")

        token = self.http.enviar(
            "POST", f"{AUTH_BASE}/token",
            cabecalhos={"Content-Type": "application/x-www-form-urlencoded"},
            corpo=urlencode({"grant_type": "authorization_code", "client_id": CLIENT_ID,
                             "code": codigo, "redirect_uri": REDIRECT_URI}).encode(),
        )
        dados = token.json() if token.status == 200 else None
        if not dados or not dados.get("access_token"):
            raise CoraErro(f"Keycloak nao entregou o token (HTTP {token.status}).")
        self.token = dados["access_token"]
        self.log("Login no Cora ok.")

    # ---- API ---------------------------------------------------------------
    def api(self, metodo: str, url: str, corpo: Any = None) -> Resposta:
        if not self.token:
            raise CoraErro("Faca login antes de chamar a API do Cora.")
        cabecalhos = {
            "Authorization": f"Bearer {self.token}", "x-tenant": TENANT,
            "Accept-Language": "pt-BR", "UTC-Offset": "-180", "Accept": "application/json",
        }
        dados = None
        if corpo is not None:
            cabecalhos["Content-Type"] = "application/json;charset=UTF-8"
            dados = json.dumps(corpo).encode()
        resposta = self.http.enviar(metodo, url, cabecalhos=cabecalhos, corpo=dados)
        if resposta.status >= 400:
            raise CoraErro(f"API do Cora respondeu HTTP {resposta.status} em {urlsplit(url).path}: {resposta.texto[:200]}")
        return resposta

    def consulta_salva(self, nome: str) -> dict:
        lista = self.api("GET", f"{API_PEDIDOS}/templates").json() or {}
        for modelo in (lista.get("userTemplate") or []) + (lista.get("defaultTemplate") or []):
            if str(modelo.get("name", "")).strip().lower() == nome.strip().lower():
                return self.api("GET", f"{API_PEDIDOS}/templates/{modelo['id']}").json()
        nomes = [m.get("name") for m in lista.get("userTemplate") or []]
        raise CoraErro(f"Consulta salva '{nome}' nao existe no Cora. Consultas do usuario: {nomes}")

    def baixar_critica(self, data_entrega: date, pasta: Path, *, nome_consulta: str = "Critica",
                       espera: float = 600, intervalo: float = 5) -> Path:
        modelo = self.consulta_salva(nome_consulta)
        corpo = pedido_csv(modelo, data_entrega)
        inicio = self.agora()
        self.log(f"Pedindo o CSV da consulta {nome_consulta} para entrega em {data_entrega:%d/%m/%Y} ...")
        self.api("POST", f"{API_PEDIDOS}/search/generate-csv", corpo)
        return self._baixar_do_gerenciador(f"consulta-pedidos_{data_entrega:%d%m%Y}_", inicio, pasta, espera, intervalo)

    # ---- grade de estoque (Pedidos > Grade de Estoque > exportar) -----------
    def filiais_estoque(self) -> list[dict]:
        """Filiais da grade de estoque: [{'code': 747530, 'name': ..., 'company': {'code': 2221}}, ...]."""
        return (self.api("GET", f"{API_ESTOQUE}/branches").json() or {}).get("branches") or []

    def baixar_grade_estoque(self, data_grade: date, pasta: Path, *, filiais: list[str] | None = None,
                             espera: float = 600, intervalo: float = 5) -> list[Path]:
        """Exporta a grade de estoque de cada filial (todas, se nao informar) e baixa os CSVs."""
        disponiveis = self.filiais_estoque()
        if filiais:
            pedidas = {str(f).strip() for f in filiais}
            escolhidas = [f for f in disponiveis if str(f.get("code")) in pedidas]
            faltando = pedidas - {str(f.get("code")) for f in escolhidas}
            if faltando:
                raise CoraErro(f"Filial(is) {sorted(faltando)} nao aparecem na grade de estoque. "
                               f"Disponiveis: {[f.get('code') for f in disponiveis]}")
        else:
            escolhidas = disponiveis
        if not escolhidas:
            raise CoraErro("Nenhuma filial disponivel na grade de estoque deste usuario.")
        arquivos = []
        for filial in escolhidas:
            empresa, codigo = filial["company"]["code"], filial["code"]
            corpo = {
                "movementDate": data_grade.isoformat(),
                "company": {"branch": {"code": codigo}, "code": empresa},
                "grid": 0,
                "productCodes": [],
                "reserve": "TODAS",
            }
            inicio = self.agora()
            self.log(f"Pedindo a grade de estoque de {filial.get('name', codigo)} ({data_grade:%d/%m/%Y}) ...")
            self.api("POST", f"{API_ESTOQUE}/reports/stock-products:csv", corpo)
            prefixo = f"STOCK_PRODUCT-{data_grade:%Y%m%d}-{empresa}{codigo}-"
            nome = f"ESTOQUE_{nome_revenda(filial)}_{data_grade:%Y%m%d}"
            arquivos.append(self._baixar_do_gerenciador(prefixo, inicio, pasta, espera, intervalo, nome=nome))
        return arquivos

    # ---- gerenciador de downloads ------------------------------------------
    def _baixar_do_gerenciador(self, prefixo: str, inicio: datetime, pasta: Path, espera: float, intervalo: float,
                               *, nome: str | None = None) -> Path:
        """Espera o arquivo pedido ficar pronto no gerenciador e baixa ("Baixar arquivo").

        `nome` troca o nome que o Cora deu ao arquivo (sem a extensao)."""
        arquivo = self._esperar_arquivo(prefixo, inicio, espera, intervalo)
        link = self.api("POST", f"{API_DOWNLOADS}/files/{arquivo['id']}:generatedownloadlink").json()["link"]
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / f"{nome or arquivo['name']}.csv"
        conteudo = self.http.enviar("GET", link)
        if conteudo.status != 200:
            raise CoraErro(f"Download do CSV falhou (HTTP {conteudo.status}).")
        parcial = destino.with_suffix(".csv.parcial")
        parcial.write_bytes(conteudo.corpo)
        parcial.replace(destino)
        self.log(f"CSV salvo: {destino.name} ({len(conteudo.corpo) / 1_048_576:.1f} MB)")
        return destino

    def _esperar_arquivo(self, prefixo: str, inicio: datetime, espera: float, intervalo: float) -> dict:
        desde = inicio - timedelta(seconds=30)  # folga para diferenca de relogio
        limite = time.monotonic() + espera
        while True:
            arquivos = (self.api("GET", f"{API_DOWNLOADS}/files?_page=0&_size=20").json() or {}).get("data") or []
            novos = [a for a in arquivos if str(a.get("name", "")).startswith(prefixo) and _instante(a.get("createAt")) >= desde]
            if novos:
                arquivo = max(novos, key=lambda a: _instante(a.get("createAt")))
                status = arquivo.get("status")
                if status == PRONTO:
                    return arquivo
                if status in STATUS_FALHA:
                    raise CoraErro(f"O Cora marcou o arquivo como {STATUS_FALHA[status]}: {arquivo.get('name')}")
                self.log(f"... Cora gerando o CSV ({arquivo.get('percentile') or 0}%)")
            if time.monotonic() >= limite:
                raise CoraErro(f"O arquivo {prefixo}* nao ficou pronto em {int(espera)}s.")
            self.dormir(intervalo)


def pedido_csv(modelo: dict, data_entrega: date) -> dict:
    """Monta o corpo do generate-csv como a tela faz a partir da consulta salva."""
    conteudo = modelo.get("content") or {}
    colunas = sorted(conteudo.get("columns") or [], key=lambda c: c.get("order", 0))
    dia = data_entrega.isoformat()
    filtros = []
    for filtro in conteudo.get("filters") or []:
        valores = filtro.get("values", filtro.get("value"))
        if filtro.get("id") == FILTRO_DATA_ENTREGA:
            valores = [dia, dia]
        filtros.append({"id": filtro["id"], "value": valores})
    if not any(f["id"] == FILTRO_DATA_ENTREGA for f in filtros):
        filtros.insert(0, {"id": FILTRO_DATA_ENTREGA, "value": [dia, dia]})
    return {
        "columns": [{"id": c["id"], "order": i, "value": None} for i, c in enumerate(colunas)],
        "filters": filtros,
    }


_PALAVRAS_GENERICAS = {"PAU", "BRASIL", "FILIAL", "MATRIZ", "BEBIDAS", "DISTRIBUIDORA", "LTDA", "ME", "EPP", "SA", "DE", "DA", "DO"}


def nome_revenda(filial: dict) -> str:
    """Nome curto da revenda para o arquivo: 'Pau Brasil Filial Sume' -> 'SUME'; sem nome, o codigo."""
    texto = unicodedata.normalize("NFKD", str(filial.get("name") or "")).encode("ascii", "ignore").decode()
    palavras = re.findall(r"[A-Z0-9]+", texto.upper())
    proprias = [p for p in palavras if p not in _PALAVRAS_GENERICAS]
    return "_".join(proprias or palavras) or str(filial.get("code"))


def _codigo_do_redirecionamento(local: str) -> str:
    partes = urlsplit(local)
    for trecho in (partes.fragment, partes.query):
        codigo = parse_qs(trecho).get("code")
        if codigo:
            return codigo[0]
    return ""


def _instante(texto: Any) -> datetime:
    try:
        valor = str(texto).replace("Z", "+00:00")
        # O portal manda microssegundos com 6 digitos ou mais; o Python aceita ate 6.
        valor = re.sub(r"(\.\d{6})\d+", r"\1", valor)
        instante = datetime.fromisoformat(valor)
        return instante if instante.tzinfo else instante.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)
