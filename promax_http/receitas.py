"""Campos de cada rotina, com os preenchimentos automaticos que o JavaScript da tela faria.

No navegador, escolher uma opcao dispara JavaScript que preenche outros campos
(por exemplo, as faixas de cada quebra). Pelo HTTP isso nao acontece, entao cada
receita repete esses efeitos. A referencia e sempre o JavaScript da propria tela,
guardado no rastro em logs/promax_http/.
"""
from __future__ import annotations

# 03.02.37 (PW02099R) -- funcoes Carrega(num) e Habilita(num) da tela.
_FAIXA_QUEBRA_030237 = {
    "08": ("AA00000000", "ZZ99999999"),  # Municipio
    "28": ("0", "Z"),  # Classe Road
}
_FAIXA_PADRAO_030237 = ("0", "99999999")


def campos_030237(
    *,
    data_inicial: str,
    data_final: str,
    quebra1: str,
    quebra2: str = "00",
    quebra3: str = "00",
    itens: str | None = None,
    notas: str | None = None,
    extras: dict[str, str] | None = None,
) -> dict[str, str]:
    quebras = [_codigo_quebra(q) for q in (quebra1, quebra2, quebra3)]
    campos: dict[str, str] = {"dataInicial": data_inicial, "dataFinal": data_final}

    if quebras[0] == "01":
        # Quebra "Geral": a tela zera as demais quebras e limpa as faixas.
        quebras = ["01", "00", "00"]
    for numero, quebra in enumerate(quebras, start=1):
        campos[f"quebra{numero}"] = quebra
        if quebra in {"00", "01"}:
            inicial, final = "", ""
        else:
            inicial, final = _FAIXA_QUEBRA_030237.get(quebra, _FAIXA_PADRAO_030237)
        campos[f"quebra{numero}Inicial"] = inicial
        campos[f"quebra{numero}Final"] = final
        # ValidaParRel copia as faixas de Municipio/Classe Road para estes campos.
        if quebra in {"08", "28"}:
            campos[f"quebra{numero}Ini8"] = inicial
            campos[f"quebra{numero}Fim8"] = final

    if "29" in quebras:
        itens = "S"  # Carrega() forca itens=Sim quando ha quebra por Codigo Fiscal.
    if itens:
        campos["itens"] = itens.strip().upper()
        if campos["itens"] == "N":
            campos.update(embalagemInicial="", embalagemFinal="", mercadoriaInicial="", mercadoriaFinal="")
        else:
            # HabilitaEmbalagem(): itens Sim/Caneta liberam e preenchem estas faixas.
            campos.update(
                embalagemInicial="0", embalagemFinal="99999", mercadoriaInicial="0", mercadoriaFinal="9999999"
            )
    if notas:
        campos["notas"] = notas.strip().upper()
    # A tela carrega 0,00 a 999.999.999,99 e ValidaParRel tira os pontos antes de enviar.
    campos.update(valorInicial="0,00", valorFinal="999999999,99")
    campos.update(extras or {})
    return campos


def _codigo_quebra(valor: str) -> str:
    texto = str(valor or "0").strip()
    return texto.zfill(2) if texto.isdigit() else texto


# 02.05.02 (PW03064R) -- funcao Habilita() e script de carga da tela.
_FAIXA_MERCADORIA_020502 = {"2": ("0", "999"), "3": ("0", "999")}


def campos_020502(
    *,
    opcao_rel: str = "1",
    listar_produtos: bool = True,
    listar_vasilhames_garrafeiras: bool = True,
    tipo_data: str = "E",
    periodo_inicial: str | None = None,
    periodo_final: str | None = None,
) -> dict[str, str | None]:
    """Campos da 02.05.02. Sem periodo, vale o da tela (data de hoje no servidor).

    Valor None remove o campo do envio (checkbox desmarcado).
    """
    opcao = str(opcao_rel).strip()
    inicial, final = _FAIXA_MERCADORIA_020502.get(opcao, ("0", "9999999"))
    campos: dict[str, str | None] = {
        "opcaoRel": opcao,
        "cdMercadoriaInicial": inicial,
        "cdMercadoriaFinal": final,
        "idListarProdutos": "S" if listar_produtos else None,
        "idListarVasGarraf": "S" if listar_vasilhames_garrafeiras else None,
        "tpData": str(tipo_data).strip().upper(),
    }
    if periodo_inicial:
        campos["periodoInicial"] = periodo_inicial
    if periodo_final:
        campos["periodoFinal"] = periodo_final
    return campos
