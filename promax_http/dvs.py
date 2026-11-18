"""Arquivos que o Promax grava no DVS do servidor (03.08.05, 17.06).

Essas rotinas nao exportam pela tela: o Visualizar grava o arquivo na pasta DVS
e o robo do Edge o busca em tres lugares, nesta ordem (teste de 18/11: os quatro
arquivos vieram pela pasta de rede):

1. pasta de rede  \\\\<servidor>\\integ\\dvs\\<arquivo>
2. HTTP           /arquivos/browse/dvs/<arquivo>
3. HTTP           /arquivos/dvs/<arquivo>
"""
from __future__ import annotations

import re
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit

from promax_http.erros import PromaxHttpErro
from promax_http.transporte import Transporte

# Folga entre o relogio do servidor de arquivos e o desta maquina.
FOLGA_RELOGIO = 5


class BuscaDvs:
    """Procura um arquivo do DVS nos tres lugares que o robo do Edge usa."""

    def __init__(self, transporte: Transporte, url_promax: str, logger) -> None:
        partes = urlsplit(url_promax)
        self.http = transporte
        self.logger = logger
        self.pasta_rede = PureWindowsPath(rf"\\{partes.hostname}\integ\dvs")
        self.bases_http = [f"{partes.scheme}://{partes.netloc}/", f"{partes.scheme}://{partes.hostname}:8080/"]

    def por_nome(self, nome: str, desde: float | None = None) -> tuple[str, bytes] | None:
        """``desde``: na rede so vale arquivo gravado depois do Visualizar (o nome da
        03.08.05 so tem o dia; sem isso um arquivo de outro mes seria pego)."""
        rede = Path(str(self.pasta_rede / nome))
        try:
            if rede.is_file() and (desde is None or rede.stat().st_mtime >= desde - FOLGA_RELOGIO):
                return f"rede:{rede}", rede.read_bytes()
        except OSError as exc:
            self.logger.info("Pasta de rede indisponivel (%s): %s", rede, exc)
        for base in self.bases_http:
            for caminho in ("arquivos/browse/dvs/", "arquivos/dvs/"):
                url = base + caminho + nome
                resposta = self._get(url)
                if resposta and resposta.status == 200 and parece_arquivo(resposta.corpo):
                    return f"http:{url}", resposta.corpo
        return None

    def por_prefixo(self, prefixo: str, desde: float) -> tuple[str, bytes] | None:
        """17.06: o nome muda (id_<puxada><filial>...inf ou NOCRIPTO...csv); vale o prefixo."""
        pasta = Path(str(self.pasta_rede))
        try:
            candidatos = [
                p for p in pasta.iterdir()
                if p.is_file() and prefixo in p.name and p.suffix.lower() in {".inf", ".csv"}
                and p.stat().st_mtime >= desde - FOLGA_RELOGIO
            ]
            if candidatos:
                mais_novo = max(candidatos, key=lambda p: p.stat().st_mtime)
                return f"rede:{mais_novo}", mais_novo.read_bytes()
        except OSError as exc:
            self.logger.info("Pasta de rede indisponivel (%s): %s", pasta, exc)
        for nome in self.nomes_na_listagem(prefixo):
            achado = self.por_nome(nome)
            if achado:
                return achado
        return None

    def nomes_na_listagem(self, trecho: str) -> list[str]:
        nomes: list[str] = []
        for base in self.bases_http:
            resposta = self._get(base + "arquivos/browse/dvs/")
            if resposta and resposta.status == 200:
                for nome in re.findall(r'href=["\']?([^"\'> ]+)', resposta.texto, re.IGNORECASE):
                    nome = nome.rstrip("/").rsplit("/", 1)[-1]
                    if trecho in nome and nome not in nomes:
                        nomes.append(nome)
        return nomes

    def _get(self, url: str):
        try:
            return self.http.get(url)
        except PromaxHttpErro as exc:
            self.logger.info("GET %s falhou: %s", url, exc)
            return None


def parece_arquivo(corpo: bytes) -> bool:
    inicio = (corpo or b"")[:300].lower()
    return bool(corpo) and b"<html" not in inicio and b"<!doctype" not in inicio


def parece_arquivo(corpo: bytes) -> bool:
    inicio = (corpo or b"")[:300].lower()
    return bool(corpo) and b"<html" not in inicio and b"<!doctype" not in inicio
