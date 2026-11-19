"""Digita UM pedido na 03.01.04 por HTTP (teste controlado).

Repete o caminho do navegador:
    opcao 2  Mapa (0 = o Promax gera o mapa; a janela MPD so preenche campos)
    opcao 11 Vendedor   opcao 4 Operacao   opcao 5 Cliente   opcao 8 Itens
    opcao 7  Adicionar item (ClickCarregar -> SalvarItem)
    opcao 6  Salvar Lista (com "Enviar ao Roteirizador?" = Sim)

Para antes do opcao 6 se aparecer alerta, pergunta do Promax ou campo
obrigatorio vazio. Sem --salvar nunca envia o opcao 6.

    python -m promax_http.pedido_030104 --mapa 0 --vendedor 992 --operacao 1 --cliente 16883 --produto 988 --qtd 2 --salvar
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from core.config.project_paths import DATA_DIR, LOGS_DIR
from core.config.settings import get_settings
from core.observability.logger import get_logger
from promax_http import html
from promax_http.cliente import ClientePromax
from promax_http.explorar_030104 import podar_ramos, valores_da_resposta
from promax_http.transporte import Transporte

_RADIO_MARCADO = re.compile(r"""document\.all(?:\.(\w+)|\s*\(\s*['"](\w+)['"]\s*\))\s*\[(\d)\]\.checked\s*=\s*true""")
_NOVA_OPCAO = re.compile(r"(\w+)\.(?:add|options\[[^\]]*\]\s*=)\s*\(?\s*new\s+Option\s*\(\s*['\"]([^'\"]*)['\"]\s*,\s*['\"]([^'\"]*)['\"]")
_SETOR_DIFERENTE = re.compile(r"Cliente pertence ao Setor\s+(\d+)")
_PERGUNTA = re.compile(r"msgbxSimNao\s*\(\s*['\"][^'\"]*['\"]\s*,\s*['\"]([^'\"]+)|confirm\s*\(\s*['\"]([^'\"]+)")
_RADIOS = {"idGeraCarregamento": ["S", "N"]}
_TRAVA_COND = re.compile(r"""cdCondicaoPagto['"]?\s*\)?\s*\.disabled\s*=\s*(true|false)""")


class Parada(Exception):
    pass


def _js_pad(texto: str, tamanho: int, char: str = "0", esquerda: bool = True) -> str:
    falta = max(0, tamanho - len(texto))
    return char * falta + texto if esquerda else texto + char * falta


def _js_int(valor: str) -> int | None:
    m = re.match(r"\s*([+-]?\d+)", valor or "")
    return int(m.group(1)) if m else None


def item_lista(item: dict[str, str]) -> str:
    """Um item no formato de ContinuaSalvarCont2 (139 posicoes)."""
    ttv = _js_pad(item.get("vlTtv", ""), 15)
    inteiro = _js_int(ttv[0:12].replace(".", "", 2)) or 0
    ttv = _js_pad(str(inteiro), 9) + "," + ttv[13:15]
    motivo = _js_int(item.get("cdMotivoTroca", "")) or 0
    invertido = _js_int(item.get("cdProdutoInvertido", ""))
    opcao_sub = _js_int(item.get("cdOpcaoSub", "")) or 0
    qt_sub = _js_int(item.get("qtSubstituicao", "")) or 0
    return (
        _js_pad(item["cdProduto"], 7)
        + _js_pad(item["qtPedida"], 5)
        + ttv
        + _js_pad(item.get("nrPedidoEdi", ""), 15)
        + _js_pad(item.get("nrSerie", ""), 20, " ", esquerda=False)
        + _js_pad(item.get("idNumeroSerie", ""), 1, " ", esquerda=False)
        + _js_pad(item.get("dtFabr", ""), 10, " ", esquerda=False)
        + _js_pad(str(motivo), 2)
        + _js_pad(str(invertido if invertido is not None else 0), 7)
        + item.get("idUnidade", "N")
        + _js_pad(item.get("sgUnidade", ""), 4, " ", esquerda=False)
        + _js_pad(str(opcao_sub), 3)
        + _js_pad(str(qt_sub), 9)
        + _js_pad(item.get("vlAliquota", ""), 6, " ", esquerda=False)
        + _js_pad(item.get("vlFCI", ""), 36, " ", esquerda=False)
        + _js_pad(item.get("vlOrigemMerc", ""), 1, " ", esquerda=False)
    )


def formatar_ttv(valor: str) -> str:
    """Como FormataCampo(..., '999.999.999,99', 'valor') da tela: 51,84 -> 51,84; 1234,5 -> 1.234,50."""
    valor = (valor or "").strip()
    if not valor:
        return ""
    centavos = round(float(valor.replace(".", "").replace(",", ".")) * 100)
    inteiro, cent = divmod(centavos, 100)
    return f"{inteiro:,}".replace(",", ".") + f",{cent:02d}"


def catalogo(rotina) -> dict:
    """Condicoes de pagamento que o Promax oferece nesta unidade, lidas ao abrir a tela."""
    condicoes = html.opcoes_carregadas(rotina.carga_frame9).get("cdCondicaoPagto", [])
    return {
        "unidade": rotina.unidade_ativa,
        "lido_em": datetime.now().isoformat(timespec="seconds"),
        "condicoes": [
            {"codigo": o.valor, "descricao": o.texto.split(" - ", 1)[-1]} for o in condicoes if o.valor
        ],
    }


def gravar_catalogo(dados: dict, pasta: Path | None = None) -> Path | None:
    """Guarda a lista atualizada para o sistema ler: data/catalogos/030104_condicoes_<unidade>.json.

    So sobrescreve quando a lista veio preenchida, para uma leitura com falha nao
    apagar a ultima lista boa. Grava num temporario e troca, para nunca ficar pela metade.
    """
    if not dados.get("condicoes"):
        return None
    pasta = pasta or Path(DATA_DIR) / "catalogos"
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"030104_condicoes_{dados.get('unidade') or 'sem_unidade'}.json"
    temporario = destino.with_suffix(".json.parcial")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    temporario.replace(destino)
    return destino


class Digitacao:
    def __init__(self, cliente: ClientePromax, rotina, logger) -> None:
        self.cliente, self.rotina, self.log = cliente, rotina, logger
        self.form = rotina.form.campos
        self.opcoes_novas: dict[str, list[tuple[str, str]]] = {}
        self.condicao_travada = False

    def enviar(self, opcao: str, nome: str, campos: dict[str, str] | None = None, *, parar_em_alerta: bool = True) -> str:
        self.form.update(campos or {})
        resposta = self.cliente._enviar_frame9(self.rotina, {k: v for k, v in self.form.items() if v is not None} | {"opcao": opcao})
        # So vale o que o navegador executaria com os valores atuais da tela.
        texto = podar_ramos(resposta.texto, self.form)
        novos = valores_da_resposta(texto)
        self.form.update(novos)
        for nome_a, nome_b, indice in _RADIO_MARCADO.findall(texto):
            nome_radio = nome_a or nome_b
            if nome_radio in _RADIOS:
                self.form[nome_radio] = _RADIOS[nome_radio][int(indice)]
        travas = _TRAVA_COND.findall(texto)
        if travas:
            self.condicao_travada = travas[-1] == "true"
        for campo, texto_op, valor in _NOVA_OPCAO.findall(texto):
            self.opcoes_novas.setdefault(campo, []).append((valor, texto_op))
        alertas = html.alertas(texto)
        perguntas = [a or b for a, b in _PERGUNTA.findall(texto)]
        self.log.info("opcao %-2s %-16s HTTP %s  campos=%d  alertas=%s  perguntas=%s",
                      opcao, nome, resposta.status, len(novos), alertas, perguntas)
        if parar_em_alerta and (alertas or perguntas):
            raise Parada(f"{nome}: Promax respondeu {alertas or perguntas}")
        return texto

    def informar_cliente(self, cliente: str) -> str:
        """opcao 5. Cliente de outro setor: responde Sim como o operador (idSetorDifere=S e reenvia)."""
        self.form.update({"cdDestinatario": cliente, "idSetorDifere": ""})
        tela = dict(self.form)
        texto = self.enviar("5", "Cliente", parar_em_alerta=False)
        alertas = html.alertas(texto)
        perguntas = [a or b for a, b in _PERGUNTA.findall(texto)]
        setor = [p for p in perguntas if _SETOR_DIFERENTE.search(p)]
        if setor and len(setor) == len(perguntas) and not alertas:
            self.log.info("Cliente %s pertence ao setor %s; confirmando (Sim).",
                          cliente, _SETOR_DIFERENTE.search(setor[0]).group(1))
            # A resposta traz o "Nao" (limpa cliente e condicao); o navegador so roda o "Sim".
            self.form.clear()
            self.form.update(tela | {"idSetorDifere": "S"})
            return self.enviar("5", "Cliente")
        if alertas or perguntas:
            raise Parada(f"Cliente: Promax respondeu {alertas or perguntas}")
        return texto


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for nome in ("mapa", "vendedor", "operacao", "cliente", "produto", "qtd"):
        p.add_argument(f"--{nome}")
    p.add_argument("--cond-pagto", help="Condicao de pagamento; vazio = a padrao do cliente")
    p.add_argument("--catalogo", action="store_true", help="So le o catalogo de condicoes (nao digita nada)")
    p.add_argument("--ttv", default="", help="Preco (TTV) do item, ex.: 51,84; vazio = o Promax decide")
    p.add_argument("--unidade", default="2210003")
    p.add_argument("--tipo-mapa", help="So se o Promax nao preencher (0=Automatico, 1=Rota, ...)")
    p.add_argument("--gera-carregamento", choices=["S", "N"])
    p.add_argument("--salvar", action="store_true", help="Envia o opcao 6 (grava o pedido)")
    args = p.parse_args(argv)
    faltando = [n for n in ("mapa", "vendedor", "operacao", "cliente", "produto", "qtd") if not getattr(args, n)]
    if faltando and not args.catalogo:
        p.error("faltam: " + ", ".join("--" + n for n in faltando))

    logger = get_logger("PROMAX_HTTP_PEDIDO")
    settings = get_settings()
    rastro = Path(LOGS_DIR) / "promax_http" / f"{datetime.now():%Y%m%d_%H%M%S}_pedido_030104"
    cliente = ClientePromax(settings.promax_url, transporte=Transporte(pasta_rastro=rastro), logger=logger)
    rotina = None
    resultado = "NAO SALVO"
    saida: dict = {"event": "pedido_030104_result", "status": "nao_salvo"}
    try:
        cliente.login(settings.promax_user, settings.promax_pass, unidade=args.unidade)
        rotina = cliente.abrir_rotina("030104")
        saida["catalogo"] = catalogo(rotina)
        logger.info("Condicoes de pagamento disponiveis na unidade: %d", len(saida["catalogo"]["condicoes"]))
        if args.catalogo:
            saida["status"] = "catalogo"
            raise Parada("So catalogo: nada digitado.")
        d = Digitacao(cliente, rotina, logger)

        d.enviar("2", "Mapa", {"nrMapa": args.mapa})
        if int(args.mapa or 0) == 0:
            if args.tipo_mapa is not None:
                d.form["cdTipoMapa"] = args.tipo_mapa
            if args.gera_carregamento:
                d.form["idGeraCarregamento"] = args.gera_carregamento
            logger.info("MPD: tipo de mapa=%r, gera carregamento=%r, motivo=%r",
                        d.form.get("cdTipoMapa"), d.form.get("idGeraCarregamento"), d.form.get("cdMotivoNaoCarga"))
            if not d.form.get("cdTipoMapa"):
                raise Parada("MPD: o Promax nao preencheu o Tipo de Mapa. Rode de novo com --tipo-mapa (ex.: 0 = Automatico).")
            # O proprio Promax devolve "Gerar Carregamento = Nao" com o motivo em branco para mapa 0;
            # usamos o que ele definiu (a janela MPD do navegador so mostra esses campos).
            logger.info("Mapa gerado pelo Promax: %s", d.form.get("nrMapa"))

        d.enviar("11", "Vendedor", {"cdVendedor": args.vendedor})
        d.enviar("4", "Operacao", {"cdOperacao": args.operacao})
        d.informar_cliente(args.cliente)
        if not d.form.get("cdCondicaoPagto"):
            opcoes = [v for v, _ in d.opcoes_novas.get("cdCondicaoPagto", []) if v]
            if len(opcoes) == 1:
                d.form["cdCondicaoPagto"] = opcoes[0]
            else:
                raise Parada(f"Condicao de pagamento nao veio definida. Opcoes do Promax: {d.opcoes_novas.get('cdCondicaoPagto')}")
        saida["condicao_padrao_cliente"] = d.form.get("cdCondicaoPagto")
        saida["condicao_travada"] = d.condicao_travada
        if args.cond_pagto:
            codigos = {c["codigo"] for c in saida["catalogo"]["condicoes"]}
            pedida = args.cond_pagto.zfill(3)
            if pedida not in codigos:
                raise Parada(f"Condicao {pedida} nao esta liberada no Promax desta unidade.")
            if d.condicao_travada and pedida != d.form.get("cdCondicaoPagto"):
                raise Parada(f"Condicao travada pelo Promax para este cliente/operacao (padrao {d.form.get('cdCondicaoPagto')}).")
            d.form["cdCondicaoPagto"] = pedida
        saida["condicao_usada"] = d.form.get("cdCondicaoPagto")
        logger.info("Cabecalho: cond.pagto=%r tabela=%r transp=%r tpMovimento=%r",
                    d.form.get("cdCondicaoPagto"), d.form.get("codTabelaPrecos"), d.form.get("codTransportadora"), d.form.get("tpMovimento"))
        d.enviar("8", "Itens")

        # Enter na quantidade -> ClickCarregar -> AbreFCI (sem FCI) -> SalvarItem
        ttv = formatar_ttv(args.ttv)
        d.form.update({"codProduto": args.produto, "qtPedida": args.qtd, "valorTTV": ttv, "idUnidade": "N", "vlAliquota": "", "vlFCI": "",
                       "itensLista": "", "carregando": "1"})
        resposta_item = d.enviar("7", "Adicionar item")  # texto ja podado
        if "AdicionaLista" not in resposta_item:
            raise Parada("O Promax nao confirmou o item (sem AdicionaLista na resposta). Veja o rastro.")
        item = {
            "cdProduto": args.produto, "qtPedida": args.qtd, "vlTtv": d.form.get("valorTTV") or ttv,
            "sgUnidade": d.form.get("siglaUnidade", ""), "idUnidade": "N", "cdOpcaoSub": "0",
        }
        logger.info("Item aceito: %s %s, unidade %r, TTV %r", d.form.get("nomeProduto", ""), args.qtd, item["sgUnidade"], item["vlTtv"])
        if not args.salvar:
            raise Parada("Sem --salvar: parei antes de gravar.")

        d.form.update({"itensLista": item_lista(item), "idEnviaRoad": "S", "carregando": "0"})
        texto = d.enviar("6", "Salvar", parar_em_alerta=False)
        # Depois de salvar, o Promax recarrega a tela inteira (com todas as funcoes dela);
        # o que interessa e a mensagem "Pedido NNNNNN gerado".
        gerado = re.search(r"Pedido\s+(\d+)\s+gerado", texto)
        saida["mapa"] = d.form.get("nrMapa")
        if gerado:
            resultado = f"PEDIDO {gerado.group(1)} GERADO no mapa {d.form.get('nrMapa')}"
            saida.update(status="salvo", pedido=gerado.group(1))
        else:
            resultado = f"SALVAR SEM CONFIRMACAO. Alertas: {html.alertas(texto)[:3]}. Veja o rastro."
        logger.info(resultado)
    except Parada as parada:
        resultado = f"PAROU: {parada}"
        if saida["status"] != "catalogo":
            saida.update(status="parou", motivo=str(parada))
        logger.warning(resultado)
    finally:
        try:
            if rotina is not None:
                cliente.fechar_rotina(rotina)
            cliente.logoff()
        except Exception:  # noqa: BLE001
            pass
        if saida.get("catalogo"):
            try:
                arquivo = gravar_catalogo(saida["catalogo"])
                if arquivo:
                    logger.info("Lista de condicoes atualizada em %s", arquivo)
            except OSError as erro:
                logger.warning("Nao consegui gravar a lista de condicoes: %s", erro)
        rastro.mkdir(parents=True, exist_ok=True)
        (rastro / "resultado.txt").write_text(resultado + "\n", encoding="utf-8")
        (rastro / "resultado.json").write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(saida, ensure_ascii=False), flush=True)
        logger.info("Rastro em %s", rastro)
    return 0


if __name__ == "__main__":
    sys.exit(main())
