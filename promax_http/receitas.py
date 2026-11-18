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
    faixas: dict[int, tuple[str, str]] | None = None,
    lista_nota_compra: bool | None = None,
    extras: dict[str, str] | None = None,
) -> dict[str, str | None]:
    quebras = [_codigo_quebra(q) for q in (quebra1, quebra2, quebra3)]
    campos: dict[str, str | None] = {"dataInicial": data_inicial, "dataFinal": data_final}

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
    # Faixas informadas pela tarefa substituem as da tela (o robo do Edge digita depois de escolher a quebra).
    for numero, (inicial, final) in (faixas or {}).items():
        campos[f"quebra{numero}Inicial"] = str(inicial)
        campos[f"quebra{numero}Final"] = str(final)
    if notas:
        campos["notas"] = notas.strip().upper()
    if lista_nota_compra is not None:
        # TrataCampoCompra(): so existe com notas de Entrada (NE).
        campos["listaNotaCompra"] = "S" if lista_nota_compra and campos.get("notas") == "NE" else None
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


# 02.02.20 (PW03004R) -- TipoMarca(), AlteraData() e script de carga da tela.
MERCADORIAS_020220 = {
    "vasilhame": "vasilhame",
    "garrafeira": "garrafeira",
    "sopi_visa": "idSopiVisa",
    "outros_mat": "idOutrosMat",
    "barril_cilindro": "idBarrilCilindro",
    "chopp_post": "idChoppPost",
    "outros_ref": "idOutrosRef",
    "pit_stop": "idPitStop",
}


def campos_020220(
    *,
    opcao_rel: str = "01",
    mercadorias: set[str] | None = None,
    selecao: str = "T",
    situacao: str | None = None,
    exibe_inf_documentos: bool | None = None,
    cd_visao: str | None = None,
) -> dict[str, str | None]:
    """Campos da 02.02.20. ``mercadorias=None`` marca "Todos".

    As faixas (area, setor, rota, cliente, material, segmento, campo) e o
    periodo 00/00/0000 a 99/99/9999 vem do script de carga da tela.
    """
    escolhidas = set(mercadorias or ())
    desconhecidas = escolhidas - set(MERCADORIAS_020220)
    if desconhecidas:
        raise ValueError(f"Mercadorias desconhecidas na 02.02.20: {sorted(desconhecidas)}")
    # TipoMarca(): marcar todas as especificas equivale a "Todos".
    todos = not escolhidas or escolhidas == set(MERCADORIAS_020220)
    campos: dict[str, str | None] = {"opcaoRel": str(opcao_rel).zfill(2), "todos": "X" if todos else None}
    for chave, campo in MERCADORIAS_020220.items():
        campos[campo] = "X" if (not todos and chave in escolhidas) else None

    selecao = str(selecao).strip().upper()
    campos["selecao"] = selecao
    if selecao in {"T", "P"}:
        # AlteraData(): Todos/Pendentes usam o periodo aberto.
        campos.update(dataInicial="00/00/0000", dataFinal="99/99/9999")
    elif selecao == "V":
        campos.update(dataInicial="", dataFinal="")
    if situacao:
        campos["situacao"] = str(situacao).strip().upper()
    if exibe_inf_documentos is not None:
        campos["idExibeInfDocumentos"] = "S" if exibe_inf_documentos else None
    if cd_visao is not None:
        campos["cdVisao"] = str(cd_visao)
    return campos


# 05.12 (PW02008R) -- o script de carga preenche ano, meses e todas as faixas;
# Habilita() com opcao diferente de 01 so libera os campos, sem mudar valores.
def campos_0512(*, opcao_rel: str, ano: str, converte_hecto: bool | None = None) -> dict[str, str | None]:
    campos: dict[str, str | None] = {"opcaoRel": str(opcao_rel).zfill(2), "ano": str(ano)}
    if converte_hecto is not None:
        campos["idConverteHecto"] = "S" if converte_hecto else None
    return campos


# 15.05.01 (PW06011R) -- listas NBZ/Depto/Pacote/VBZ/Conta (SalvaItem), periodo
# (CarregaPeriodo/VerificaPeriodo) e a sequencia de postbacks do botao Visualizar.
PASSOS_150501 = ("2", "3", "4", "5")  # AdicionaNbz, AdicionaPacote, AdicionaVbz, ValidaSelecoes
_TAMANHO_LISTA_150501 = {"Nbz": 2, "Depto": 4, "Pacote": 4, "Vbz": 4, "Conta": 10}


def campos_150501(
    *,
    visao: str,
    periodo: str,
    mes_ano: str | None = None,
    data_inicial: str | None = None,
    data_final: str | None = None,
    ano: str | None = None,
    totaliza_periodo: bool | None = None,
    nbz: tuple[str, ...] = ("99",),
    depto: tuple[str, ...] = ("9999",),
    pacote: tuple[str, ...] = ("9999",),
    vbz: tuple[str, ...] = ("9999",),
    conta: tuple[str, ...] = ("9999999999",),
) -> dict[str, str | None]:
    periodo = str(periodo).strip().upper()
    campos: dict[str, str | None] = {"visao": str(visao).zfill(2), "idPeriodo": periodo}
    # VerificaPeriodo(): Diario abre 00/00/0000 a 99/99/9999; Mensal/Anual limpam as datas.
    if periodo == "D":
        campos.update(dtInicial=data_inicial or "00/00/0000", dtFinal=data_final or "99/99/9999")
    else:
        campos.update(dtInicial="", dtFinal="")
    if periodo == "M":
        campos["dtMesAno"] = mes_ano
    if periodo == "A":
        campos["dtAno"] = ano
    for nome, itens in (("Nbz", nbz), ("Depto", depto), ("Pacote", pacote), ("Vbz", vbz), ("Conta", conta)):
        tamanho = _TAMANHO_LISTA_150501[nome]
        campos[f"lista{nome}"] = "".join(str(item).zfill(tamanho) for item in itens)
    if totaliza_periodo is not None:
        campos["idTotalizaPeriodo"] = "S" if totaliza_periodo else None
    return campos


# 14.05.01 (PW04210R) -- o script de carga preenche todas as faixas; o robo so
# escolhe a classificacao e deixa as preferencias de previsao desmarcadas.
_CLASSIFICACOES_140501 = {"01", "02", "03", "04", "05", "06", "08", "09", "11", "12", "16"}


def campos_140501(*, opcao_rel: str = "01") -> dict[str, str | None]:
    opcao = str(opcao_rel).zfill(2)
    if opcao not in _CLASSIFICACOES_140501:
        raise ValueError(f"Classificacao invalida para a 14.05.01: {opcao_rel}")
    return {
        "opcaoRel": opcao,
        "quebraPag": None,
        "idListaPrevTodas": None,
        "idListaPrevPendAprov": None,
        "idListaPrevAprovadas": None,
        "idListaPrevRejeitadas": None,
    }


# 14.05.06 (PW04235R) e 12.06.06 (PW04109R) -- mesmo desenho de tela: o tipo de
# data (Contabil/Movimento) libera iniDat/fimDat (CarregaCampo); demais faixas
# vem do script de carga.
def _campos_titulos_por_data(campo_tipo: str, opcao_rel, tipo_data, data_inicial, data_final):
    tipo = str(tipo_data).strip().upper()
    if tipo not in {"C", "M"}:
        raise ValueError(f"Tipo de data invalido: {tipo_data} (use C=Contabil ou M=Movimento)")
    return {
        "opcaoRel": str(opcao_rel).zfill(2),
        campo_tipo: tipo,
        "iniDat": data_inicial,
        "fimDat": data_final,
        # ValidaParRel() zera a fila antes do submit; com 1 o relatorio vai para a fila de impressao.
        "filaimpressao": "0",
    }


def campos_140506(*, opcao_rel: str, tipo_data: str, data_inicial: str, data_final: str) -> dict[str, str | None]:
    campos = _campos_titulos_por_data("preferencias1", opcao_rel, tipo_data, data_inicial, data_final)
    # HabilitaQuebraPg(): quebra de pagina so existe na classificacao Portador (03).
    campos["quebraPagina"] = None
    return campos


TITULOS_120606 = {
    "normais": "idTitulosNormais",
    "aluguel": "idTitulosAluguel",
    "cobranca_ca": "idTitulosCobrancaCa",
    "vale_fisico": "idTitulosValeFisico",
    "refugo": "idTitulosRefugo",
    "quebras": "idTitulosQuebras",
}


def campos_120606(
    *,
    opcao_rel: str,
    tipo_data: str,
    data_inicial: str,
    data_final: str,
    titulos: dict[str, bool] | None = None,
) -> dict[str, str | None]:
    """``titulos`` so muda os tipos informados; os outros ficam como a tela carrega
    (Normais, Cobranca CA, Vale Fisico, Refugo e Quebras marcados)."""
    campos = _campos_titulos_por_data("tpData", opcao_rel, tipo_data, data_inicial, data_final)
    for chave, marcado in (titulos or {}).items():
        if chave not in TITULOS_120606:
            raise ValueError(f"Tipo de titulo desconhecido na 12.06.06: {chave}")
        campos[TITULOS_120606[chave]] = "S" if marcado else None
    return campos


# 05.13 (PW02009R) -- Analise de Vendas. Replica Habilita() da classificacao,
# DesabilitaCampos() de "Todos" e HabilitaHectolitro() do radio volumeFin.
_CLASSIFICACOES_0513 = {str(n) for n in range(1, 15)}


def campos_0513(
    *,
    opcao_rel: str,
    volume_fin: str,
    tp_equipe: str,
    mes_ano_inicial: str,
    mes_ano_final: str,
    quantos_clientes: str,
) -> dict[str, str | None]:
    opcao = str(int(opcao_rel))
    if opcao not in _CLASSIFICACOES_0513:
        raise ValueError(f"Classificacao invalida para a 05.13: {opcao_rel}")
    if volume_fin not in {"V", "F"} or tp_equipe not in {"A", "E"}:
        raise ValueError("volume_fin deve ser V/F e tp_equipe A/E")
    campos: dict[str, str | None] = {
        "OpcaoRel": opcao,
        # Habilita(): faixas voltam a 0..9999 e o tipo de perfil sai desmarcado.
        "codigoInicial1": "0",
        "codigoFinal1": "9999",
        "codigoInicial2": "0",
        "codigoFinal2": "9999",
        "selecionarTipoPerfil": None,
        "tipoPerfil": None,  # desabilitado por HabilitaEscolheTipoPerfil(); o navegador nao envia
        # Situacao "Todos" desmarca e desabilita as situacoes individuais.
        "Todos": "G",
        **{n: None for n in ("Ativo", "Bloqueado", "Inativo", "Temporario", "Duplicado", "Excluido")},
        "volumeFin": volume_fin,
        "tpEquipe": tp_equipe,
        "mesAnoInicial": mes_ano_inicial,
        "mesAnoFinal": mes_ano_final,
        "quantosClientes": str(quantos_clientes),
        "percentualVenda": "0,00",
        "tpConsolidacao": None,
    }
    # HabilitaHectolitro(): hectolitro so existe em Volume.
    campos["hectolitro"] = "S" if volume_fin == "V" else None
    return campos


# 12.06.16 (PW04119R) -- a tela nao preenche faixas; o robo Edge tambem as deixa vazias.
def campos_120616(*, opcao_rel: str, mes_ano: str) -> dict[str, str | None]:
    opcao = str(int(opcao_rel))
    if opcao not in {"1", "2", "3", "4", "5"}:
        raise ValueError(f"Classificacao invalida para a 12.06.16: {opcao_rel}")
    return {"opcaoRel": opcao, "mesAno": mes_ano, "filaimpressao": "0"}


# 12.06.01 (PW04105R) -- Titulos em aberto. Habilita() marca "Pendentes Royalties"
# nas classificacoes 01/02; as demais faixas vem do script de carga.
def campos_120601(
    *,
    opcao_rel: str,
    vencimento_inicial: str,
    vencimento_final: str,
    especie_inicial: int | str | None = None,
    especie_final: int | str | None = None,
    notas_tit_nao_atualizados: bool = True,
) -> dict[str, str | None]:
    opcao = str(opcao_rel).zfill(2)
    campos: dict[str, str | None] = {
        "opcaoRel": opcao,
        "idPendRoyalties": "S" if opcao in {"01", "02"} else None,
        "idNotasTitNaoAtu": "S" if notas_tit_nao_atualizados else None,
        "iniVencimento": vencimento_inicial,
        "fimVencimento": vencimento_final,
        # Combos de dia de visita ficam desabilitados sem "diasVisita"; o navegador nao envia.
        "diaVisitaInicial": None,
        "diaVisitaFinal": None,
    }
    if especie_inicial is not None:
        campos["iniEspecie"] = str(especie_inicial)
    if especie_final is not None:
        campos["fimEspecie"] = str(especie_final)
    return campos
