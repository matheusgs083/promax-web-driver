"""Limpa uma gravacao de rede (.har) do Cora antes de compartilhar.

Remove senha, tokens, cookies e cabecalhos de autenticacao, e corta respostas
grandes. Mantem os enderecos, metodos, nomes de campos e o formato das
respostas, que e o que precisamos para montar a versao HTTP.

Uso: python limpar_har.py entrada.har saida_limpa.har
"""
from __future__ import annotations

import json
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

OCULTO = "***"
LIMITE_RESPOSTA = 4000

CABECALHOS_SENSIVEIS = {"authorization", "cookie", "set-cookie", "x-xsrf-token", "x-csrf-token", "proxy-authorization"}
CAMPOS_SENSIVEIS = re.compile(
    r"pass|senha|secret|token|code|session_state|state|nonce|assertion|credential|cookie|auth|jwt|bearer|otp",
    re.IGNORECASE,
)
JWT = re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]*")


def limpar_url(url: str) -> str:
    partes = urlsplit(url)
    query = [(k, OCULTO if CAMPOS_SENSIVEIS.search(k) else v) for k, v in parse_qsl(partes.query, keep_blank_values=True)]
    fragmento = OCULTO if partes.fragment else ""
    return urlunsplit((partes.scheme, partes.netloc, partes.path, urlencode(query), fragmento))


def limpar_valor(valor):
    if isinstance(valor, dict):
        return {k: (OCULTO if CAMPOS_SENSIVEIS.search(str(k)) else limpar_valor(v)) for k, v in valor.items()}
    if isinstance(valor, list):
        return [limpar_valor(v) for v in valor]
    if isinstance(valor, str):
        return JWT.sub(OCULTO, valor)
    return valor


def limpar_texto(texto: str, tipo: str) -> str:
    if not texto:
        return texto
    if "json" in (tipo or "") or texto.lstrip()[:1] in "{[":
        try:
            return json.dumps(limpar_valor(json.loads(texto)), ensure_ascii=False)[:LIMITE_RESPOSTA]
        except ValueError:
            pass
    if "x-www-form-urlencoded" in (tipo or ""):
        pares = [(k, OCULTO if CAMPOS_SENSIVEIS.search(k) else v) for k, v in parse_qsl(texto, keep_blank_values=True)]
        return urlencode(pares)
    texto = JWT.sub(OCULTO, texto)
    texto = re.sub(r'(name="?[^"\s>]*(?:pass|senha|token|code)[^"\s>]*"?[^>]*value=")[^"]*', r"\1" + OCULTO, texto, flags=re.I)
    return texto[:LIMITE_RESPOSTA]


def limpar_cabecalhos(cabecalhos: list[dict]) -> list[dict]:
    limpos = []
    for c in cabecalhos or []:
        nome = str(c.get("name", ""))
        valor = OCULTO if nome.lower() in CABECALHOS_SENSIVEIS or CAMPOS_SENSIVEIS.search(nome) else c.get("value", "")
        if nome.lower() == "location":
            valor = limpar_url(str(c.get("value", "")))
        limpos.append({"name": nome, "value": valor})
    return limpos


def limpar_entrada(e: dict) -> dict:
    req, resp = e.get("request", {}), e.get("response", {})
    post = req.get("postData") or {}
    conteudo = resp.get("content") or {}
    return {
        "startedDateTime": e.get("startedDateTime"),
        "request": {
            "method": req.get("method"),
            "url": limpar_url(req.get("url", "")),
            "headers": limpar_cabecalhos(req.get("headers")),
            "postData": {
                "mimeType": post.get("mimeType"),
                "text": limpar_texto(post.get("text", ""), post.get("mimeType", "")),
            } if post else None,
        },
        "response": {
            "status": resp.get("status"),
            "headers": limpar_cabecalhos(resp.get("headers")),
            "content": {
                "mimeType": conteudo.get("mimeType"),
                "size": conteudo.get("size"),
                "text": limpar_texto(conteudo.get("text", ""), conteudo.get("mimeType", ""))
                if conteudo.get("encoding") != "base64" else "(binario omitido)",
            },
        },
    }


IGNORAR = re.compile(r"\.(png|jpe?g|gif|svg|ico|woff2?|ttf|css|map)(\?|$)", re.I)


def main(entrada: str, saida: str) -> None:
    with open(entrada, encoding="utf-8-sig") as f:
        har = json.load(f)
    entradas = [
        limpar_entrada(e)
        for e in har.get("log", {}).get("entries", [])
        if not IGNORAR.search(e.get("request", {}).get("url", ""))
    ]
    with open(saida, "w", encoding="utf-8") as f:
        json.dump({"log": {"entries": entradas}}, f, ensure_ascii=False, indent=1)
    print(f"{len(entradas)} chamadas gravadas em {saida} (senha, tokens e cookies removidos).")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Uso: python limpar_har.py entrada.har saida_limpa.har")
    main(sys.argv[1], sys.argv[2])
