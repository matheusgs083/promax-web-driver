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
