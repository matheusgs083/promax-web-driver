from promax_http.receitas import campos_030237


def test_030237_estoque_preenche_faixas_e_itens_como_a_tela():
    campos = campos_030237(quebra1="14", quebra2="16", itens="s", data_inicial="01/10/2026", data_final="17/11/2026")

    assert campos["quebra1"] == "14" and campos["quebra2"] == "16" and campos["quebra3"] == "00"
    assert (campos["quebra1Inicial"], campos["quebra1Final"]) == ("0", "99999999")
    assert (campos["quebra2Inicial"], campos["quebra2Final"]) == ("0", "99999999")
    assert (campos["quebra3Inicial"], campos["quebra3Final"]) == ("", "")
    assert campos["itens"] == "S"
    assert (campos["embalagemInicial"], campos["embalagemFinal"]) == ("0", "99999")
    assert (campos["mercadoriaInicial"], campos["mercadoriaFinal"]) == ("0", "9999999")


def test_030237_quebras_especiais_usam_as_faixas_da_tela():
    campos = campos_030237(quebra1="08", quebra2="28", data_inicial="01/11/2026", data_final="16/11/2026")

    assert (campos["quebra1Inicial"], campos["quebra1Final"]) == ("AA00000000", "ZZ99999999")
    assert (campos["quebra1Ini8"], campos["quebra1Fim8"]) == ("AA00000000", "ZZ99999999")
    assert (campos["quebra2Inicial"], campos["quebra2Final"]) == ("0", "Z")


def test_030237_quebra_geral_zera_as_outras():
    campos = campos_030237(quebra1="01", quebra2="14", data_inicial="01/11/2026", data_final="16/11/2026")

    assert (campos["quebra2"], campos["quebra2Inicial"]) == ("00", "")


def test_030237_envia_faixa_de_valor_como_o_navegador():
    campos = campos_030237(quebra1="14", data_inicial="01/11/2026", data_final="16/11/2026")

    assert (campos["valorInicial"], campos["valorFinal"]) == ("0,00", "999999999,99")


def test_020502_estoque_desmarca_vasilhames_e_mantem_faixa_de_item():
    from promax_http.receitas import campos_020502

    campos = campos_020502(opcao_rel="1", listar_produtos=True, listar_vasilhames_garrafeiras=False, tipo_data="E")

    assert campos["idListarProdutos"] == "S"
    assert campos["idListarVasGarraf"] is None
    assert (campos["cdMercadoriaInicial"], campos["cdMercadoriaFinal"]) == ("0", "9999999")
    assert "periodoInicial" not in campos


def test_030237_entrada_usa_faixas_da_tarefa_e_nota_de_compra():
    campos = campos_030237(
        quebra1="14", quebra2="12", quebra3="39", notas="NE", itens="s",
        faixas={1: ("251", "314"), 2: ("1", "2")}, lista_nota_compra=True,
        data_inicial="28/08/2026", data_final="17/11/2026",
    )

    assert (campos["quebra1Inicial"], campos["quebra1Final"]) == ("251", "314")
    assert (campos["quebra2Inicial"], campos["quebra2Final"]) == ("1", "2")
    assert (campos["quebra3Inicial"], campos["quebra3Final"]) == ("0", "99999999")
    assert campos["notas"] == "NE" and campos["listaNotaCompra"] == "S"


def test_030237_nota_de_compra_so_vale_para_entrada():
    campos = campos_030237(quebra1="14", notas="NS", lista_nota_compra=True, data_inicial="1", data_final="2")

    assert campos["listaNotaCompra"] is None


def test_020220_auditool_marca_so_as_mercadorias_pedidas():
    from promax_http.receitas import campos_020220

    campos = campos_020220(mercadorias={"garrafeira", "vasilhame", "sopi_visa"}, selecao="P", exibe_inf_documentos=True)

    assert campos["todos"] is None
    assert (campos["garrafeira"], campos["vasilhame"], campos["idSopiVisa"]) == ("X", "X", "X")
    assert campos["idOutrosMat"] is None and campos["idPitStop"] is None
    assert (campos["selecao"], campos["dataInicial"], campos["dataFinal"]) == ("P", "00/00/0000", "99/99/9999")
    assert campos["idExibeInfDocumentos"] == "S"
    assert campos["opcaoRel"] == "01"


def test_020220_sem_mercadoria_ou_com_todas_vira_todos():
    from promax_http.receitas import MERCADORIAS_020220, campos_020220

    assert campos_020220()["todos"] == "X"
    tudo = campos_020220(mercadorias=set(MERCADORIAS_020220))
    assert tudo["todos"] == "X" and tudo["garrafeira"] is None


def test_0512_comercial_com_hectolitro():
    from promax_http.receitas import campos_0512

    assert campos_0512(opcao_rel="11", ano="2026", converte_hecto=True) == {
        "opcaoRel": "11", "ano": "2026", "idConverteHecto": "S"
    }


def test_150501_mensal_competencia_monta_listas_como_salvaitem():
    from promax_http.receitas import campos_150501

    campos = campos_150501(visao="02", periodo="M", mes_ano="11/2026", totaliza_periodo=True)

    assert (campos["visao"], campos["idPeriodo"], campos["dtMesAno"]) == ("02", "M", "11/2026")
    assert (campos["dtInicial"], campos["dtFinal"]) == ("", "")
    assert campos["listaNbz"] == "99" and campos["listaDepto"] == "9999"
    assert campos["listaPacote"] == "9999" and campos["listaVbz"] == "9999"
    assert campos["listaConta"] == "9999999999"
    assert campos["idTotalizaPeriodo"] == "S"


def test_140501_numerica_sem_previsoes():
    from promax_http.receitas import campos_140501

    campos = campos_140501(opcao_rel="01")

    assert campos["opcaoRel"] == "01"
    assert all(campos[n] is None for n in ("quebraPag", "idListaPrevTodas", "idListaPrevPendAprov"))


def test_140501_recusa_classificacao_inexistente():
    import pytest
    from promax_http.receitas import campos_140501

    with pytest.raises(ValueError):
        campos_140501(opcao_rel="07")


def test_140506_data_contabil_com_periodo():
    from promax_http.receitas import campos_140506

    campos = campos_140506(opcao_rel="01", tipo_data="c", data_inicial="01/11/2026", data_final="16/11/2026")

    assert (campos["preferencias1"], campos["iniDat"], campos["fimDat"]) == ("C", "01/11/2026", "16/11/2026")


def test_120606_so_altera_os_titulos_informados():
    from promax_http.receitas import campos_120606

    campos = campos_120606(opcao_rel="01", tipo_data="C", data_inicial="01/11/2026", data_final="16/11/2026", titulos={"normais": True})

    assert (campos["tpData"], campos["idTitulosNormais"]) == ("C", "S")
    assert "idTitulosRefugo" not in campos


def test_140506_e_120606_tiram_o_relatorio_da_fila_de_impressao():
    from promax_http.receitas import campos_120606, campos_140506

    args = dict(opcao_rel="01", tipo_data="C", data_inicial="01/11/2026", data_final="16/11/2026")

    assert campos_140506(**args)["filaimpressao"] == "0"
    assert campos_120606(**args)["filaimpressao"] == "0"


def test_0513_financeiro_tira_hectolitro_e_usa_todas_as_situacoes():
    from promax_http.receitas import campos_0513

    campos = campos_0513(opcao_rel="12", volume_fin="F", tp_equipe="A", mes_ano_inicial="11/2026", mes_ano_final="11/2026", quantos_clientes="99999")

    assert (campos["OpcaoRel"], campos["Todos"], campos["volumeFin"]) == ("12", "G", "F")
    assert campos["hectolitro"] is None and campos["Ativo"] is None


def test_0513_recusa_classificacao_inexistente():
    import pytest
    from promax_http.receitas import campos_0513

    with pytest.raises(ValueError):
        campos_0513(opcao_rel="0", volume_fin="F", tp_equipe="A", mes_ano_inicial="11/2026", mes_ano_final="11/2026", quantos_clientes="1")


def test_120601_pendentes_royalties_so_nas_classificacoes_01_e_02():
    from promax_http.receitas import campos_120601

    args = dict(vencimento_inicial="01/10/2026", vencimento_final="17/11/2026")

    assert campos_120601(opcao_rel="01", **args)["idPendRoyalties"] == "S"
    assert campos_120601(opcao_rel="05", **args)["idPendRoyalties"] is None
