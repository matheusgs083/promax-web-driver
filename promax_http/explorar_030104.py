"""Explora a 03.01.04 (Digitacao de Pedidos) passo a passo, SEM gravar pedido.

Repete o que a tela faz ao digitar o cabecalho e um item, guardando cada
resposta do Promax no rastro (logs/promax_http/<data>_explorar_030104):

    opcao 2  CarregaMapa       (nrMapa)
    opcao 11 CarregaVendedor   (cdVendedor)
    opcao 4  CarregaOperacao   (cdOperacao)
    opcao 5  CarregaCliente    (cdDestinatario)
    opcao 8  DigitaItens       (libera a digitacao dos itens)
    opcao 12 ValidaMercadoria  (codProduto)
    opcao 13 ValidaQuantidade  (qtPedida)

Nunca envia opcao 7 (adicionar item) nem opcao 6 (salvar o pedido).

    python -m promax_http.explorar_030104                 # 1o pedido da planilha de pedidos
    python -m promax_http.explorar_030104 --mapa 123 --vendedor 45 --operacao 1 --cliente 9999 --produto 1234 --qtd 5
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

from core.config.project_paths import LOGS_DIR
from core.config.settings import get_settings
from core.observability.logger import get_logger
from promax_http import html
from promax_http.cliente import ClientePromax
from promax_http.transporte import Transporte

PROIBIDAS = {"6", "7"}  # salvar pedido / adicionar item: nunca nesta exploracao

# parent.rotina.document.all.X.value = ...  ou  document.all('X').value = ...
_ATRIBUICAO = re.compile(
    r"""document\.all(?:\.(\w+)|\s*\(\s*['"](\w+)['"]\s*\))\s*\.value\s*=\s*([^;\n]+);"""
)
_LITERAL = re.compile(r"""\s*(?:'[^']*'|"[^"]*"|-?\d+(?:[.,]\d+)?)\s*""")


_IF = re.compile(r"\bif\s*\(")
_COND_LITERAL = re.compile(r"""^(?:\s|'[^']*'|"[^"]*"|-?\d+(?:\.\d+)?|==|!=|&&|\|\||[()])*$""")
_TERMO = re.compile(r"""('[^']*'|"[^"]*"|-?\d+(?:\.\d+)?)\s*(==|!=)\s*('[^']*'|"[^"]*"|-?\d+(?:\.\d+)?)""")


def _js_igual(a: str, b: str) -> bool:
    """== do JavaScript entre literais: se um lado e numero, compara como numero."""
    texto_a, texto_b = a[0] in "'\"", b[0] in "'\""
    va, vb = (a[1:-1] if texto_a else a), (b[1:-1] if texto_b else b)
    if texto_a and texto_b:
        return va == vb
    try:
        return float(va or 0) == float(vb or 0)
    except ValueError:
        return False


def _avaliar(condicao: str) -> bool | None:
    if not _COND_LITERAL.match(condicao):
        return None
    expr = _TERMO.sub(lambda m: str(_js_igual(m.group(1), m.group(3)) == (m.group(2) == "==")), condicao)
    expr = " ".join(expr.replace("&&", " and ").replace("||", " or ").split())
    if re.search(r"""['"\d]""", expr):
        return None
    try:
        return bool(eval(expr, {"__builtins__": {}}, {}))  # so True/False/and/or/()
    except Exception:  # noqa: BLE001
        return None


def _fecha(texto: str, inicio: int, abre: str, fecha: str) -> int:
    nivel = 0
    for i in range(inicio, len(texto)):
        if texto[i] == abre:
            nivel += 1
        elif texto[i] == fecha:
            nivel -= 1
            if nivel == 0:
                return i
    return -1


_CAMPO_NA_CONDICAO = re.compile(
    r"""(?:document\.parentWindow\.parent\.rotina\s*\.)?document\.all(?:\.(\w+)|\s*\(\s*['"](\w+)['"]\s*\))\s*\.value"""
)


def _trocar_campos(condicao: str, campos: dict[str, str] | None) -> str:
    if not campos:
        return condicao

    def troca(m: re.Match) -> str:
        nome = m.group(1) or m.group(2)
        if nome not in campos or campos[nome] is None:
            return m.group(0)
        return "'" + str(campos[nome]).replace("'", "") + "'"

    return _CAMPO_NA_CONDICAO.sub(troca, condicao)


def podar_ramos(texto: str, campos: dict[str, str] | None = None) -> str:
    """Tira do script os ramos de if/else que o navegador nao executaria: condicoes
    com literais (if( '0' == 0 )) ou com campos da tela cujo valor conhecemos."""
    pos = 0
    while True:
        m = _IF.search(texto, pos)
        if not m:
            return texto
        fim_cond = _fecha(texto, m.end() - 1, "(", ")")
        abre = texto.find("{", fim_cond)
        if fim_cond < 0 or abre < 0 or texto[fim_cond + 1:abre].strip():
            pos = m.end()
            continue
        fim_then = _fecha(texto, abre, "{", "}")
        resultado = _avaliar(_trocar_campos(texto[m.end():fim_cond], campos))
        if fim_then < 0 or resultado is None:
            pos = m.end()
            continue
        then = texto[abre + 1:fim_then]
        depois = fim_then + 1
        senao = ""
        m_else = re.match(r"\s*(?://[^\n]*\s*)*else\s*\{", texto[depois:])
        if m_else:
            abre_else = depois + m_else.end() - 1
            fim_else = _fecha(texto, abre_else, "{", "}")
            if fim_else > 0:
                senao = texto[abre_else + 1:fim_else]
                depois = fim_else + 1
        texto = texto[:m.start()] + (then if resultado else senao) + texto[depois:]
        pos = m.start()


def valores_da_resposta(texto: str, campos: dict[str, str] | None = None) -> dict[str, str]:
    texto = podar_ramos(texto or "", campos)
    valores: dict[str, str] = {}
    for nome_a, nome_b, expressao in _ATRIBUICAO.findall(texto or ""):
        partes = expressao.split("+")
        if all(_LITERAL.fullmatch(p) for p in partes):
            valores[nome_a or nome_b] = "".join(p.strip().strip("'\"") for p in partes)
    return valores


def primeiro_pedido_da_planilha(caminho: str) -> dict:
    from pages.processes.processo_030104_page import Processo030104Page

    pedidos = Processo030104Page(None, None).ler_planilha_pedidos(caminho)
    if not pedidos:
        raise SystemExit(f"Nenhum pedido lido da planilha {caminho}")
    return pedidos[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for nome in ("mapa", "vendedor", "operacao", "cliente", "produto", "qtd"):
        parser.add_argument(f"--{nome}")
    parser.add_argument("--unidade", default="2210003", help="Unidade (padrao: Patos)")
    args = parser.parse_args(argv)

    logger = get_logger("PROMAX_HTTP_030104")
    settings = get_settings()
    if not all([args.mapa, args.vendedor, args.operacao, args.cliente, args.produto, args.qtd]):
        pedido = primeiro_pedido_da_planilha(str(settings.pedidos_planilha_path))
        item = pedido["itens"][0]
        args.mapa = args.mapa or pedido["mapa"]
        args.vendedor = args.vendedor or pedido["vendedor"]
        args.operacao = args.operacao or pedido["operacao"]
        args.cliente = args.cliente or pedido["cliente"]
        args.produto = args.produto or item["codigo"]
        args.qtd = args.qtd or item["qtd"]
    logger.info(
        "Explorando 030104 (sem gravar): mapa %s, vendedor %s, operacao %s, cliente %s, produto %s, qtd %s",
        args.mapa, args.vendedor, args.operacao, args.cliente, args.produto, args.qtd,
    )

    rastro = Path(LOGS_DIR) / "promax_http" / f"{datetime.now():%Y%m%d_%H%M%S}_explorar_030104"
    cliente = ClientePromax(settings.promax_url, transporte=Transporte(pasta_rastro=rastro), logger=logger)
    passos = [
        ("2", "CarregaMapa", {"nrMapa": args.mapa}),
        ("11", "CarregaVendedor", {"cdVendedor": args.vendedor}),
        ("4", "CarregaOperacao", {"cdOperacao": args.operacao}),
        ("5", "CarregaCliente", {"cdDestinatario": args.cliente}),
        ("8", "DigitaItens", {}),
        ("12", "ValidaMercadoria", {"codProduto": args.produto}),
        ("13", "ValidaQuantidade", {"qtPedida": args.qtd}),
    ]
    resumo: list[str] = []
    rotina = None
    try:
        cliente.login(settings.promax_user, settings.promax_pass, unidade=args.unidade)
        rotina = cliente.abrir_rotina("030104")
        form = rotina.form.campos
        for opcao, nome, campos in passos:
            assert opcao not in PROIBIDAS
            form.update(campos)
            resposta = cliente._enviar_frame9(rotina, {k: v for k, v in form.items() if v is not None} | {"opcao": opcao})
            novos = valores_da_resposta(resposta.texto)
            form.update({k: v for k, v in novos.items() if k in form})
            alertas = html.alertas(resposta.texto)
            linha = f"opcao {opcao:>2} {nome:<17} HTTP {resposta.status}  {len(resposta.texto):>6} bytes  campos={len(novos)}  alertas={alertas}"
            logger.info(linha)
            resumo.append(linha)
        logger.info("Fim da exploracao. Nada foi salvo (opcao 7 e 6 nao foram enviadas).")
    finally:
        try:
            if rotina is not None:
                cliente.fechar_rotina(rotina)
            cliente.logoff()
        except Exception:  # noqa: BLE001 - o logoff e cortesia
            pass
        rastro.mkdir(parents=True, exist_ok=True)
        (rastro / "resumo.txt").write_text("\n".join(resumo) + "\n", encoding="utf-8")
        logger.info("Rastro em %s", rastro)
    return 0


if __name__ == "__main__":
    sys.exit(main())
