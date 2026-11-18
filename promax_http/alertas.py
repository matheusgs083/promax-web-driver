"""Classificacao dos textos de alert() devolvidos pelo Promax."""
from __future__ import annotations

import unicodedata

SEM_CONTEUDO = (
    "nenhuma informacao",
    "sem conteudo",
    "sem dados",
    "nao existem dados",
    "nao ha informacoes",
    "nao ha dados",
    "nao ha pedidos para listar",
    "relatorio vazio",
    "nenhum movimento",
    "nao houve movimento",
    "nao ha notas",
    "para listar",
    "nenhum registro",
    "nao existem titulos",
    "nao ha movimento",
)
FALHA_GERACAO = ("erro ao gerar arquivo",)
SEM_PERMISSAO = ("sem permissao", "nao autoriz", "acesso negado", "sem acesso")
LOGIN_RECUSADO = ("usuario invalido", "senha invalida", "senha incorreta", "usuario bloqueado", "senha expirada")


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def contem(textos: list[str], indicadores: tuple[str, ...]) -> str | None:
    for texto in textos:
        normalizado = normalizar(texto)
        if any(indicador in normalizado for indicador in indicadores):
            return texto
    return None
