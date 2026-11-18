"""Gera identificadores de sessao no mesmo formato do JavaScript do Promax.

O Promax nao cria o SessionID no servidor: a tela de login roda
``MontaSessionID()`` no navegador e envia o valor no formulario. O mesmo vale
para o ``SubSessionID`` de cada janela de rotina.
"""
from __future__ import annotations

import random

_CONSOANTES = "b c d f g h j k l m n p q r s t v y x z w".split()
_NUMEROS = "1 2 3 4 5 6 7 8 9 0".split()
_VOGAIS = "a e i o u A E I O U C K I J K L".split()


def gerar_session_id(rnd: random.Random | None = None) -> str:
    rnd = rnd or random.SystemRandom()
    r1, r2 = rnd.random(), rnd.random()
    prefixo = (
        _CONSOANTES[int(r1 * len(_CONSOANTES))]
        + _NUMEROS[int(r1 * len(_NUMEROS))]
        + _VOGAIS[int(r1 * len(_VOGAIS))]
        + _CONSOANTES[int(r2 * len(_CONSOANTES))]
        + _NUMEROS[int(r2 * len(_NUMEROS))]
        + _VOGAIS[int(r2 * len(_VOGAIS))]
    )
    sufixo = int(67891346 * (rnd.random() + 0.2))
    return f"{prefixo}{sufixo}"


def gerar_id_troca_unidade(rnd: random.Random | None = None) -> str:
    """Valor que ``TrocaEmpresa()`` coloca no SessionID ao trocar de unidade."""
    rnd = rnd or random.SystemRandom()
    saida = []
    for caractere in "xxxxxxxxxxxxxxxyxxxxxxxxxxxxx":
        r = int(rnd.random() * 16)
        saida.append(format(r if caractere == "x" else (r & 0x3) | 0x8, "x"))
    return "".join(saida)
