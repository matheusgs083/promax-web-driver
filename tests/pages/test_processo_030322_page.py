import pytest

from pages.processes.processo_030322_page import Processo030322Page


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("93792", "93792"),
        (93792, "93792"),
        ("93792.0", "93792"),
        ("93.792", "93792"),
        (" 000123 ", "000123"),
    ],
)
def test_normalizar_mapa_valido(entrada, esperado):
    assert Processo030322Page.normalizar_mapa(entrada) == esperado


@pytest.mark.parametrize("entrada", ["", None, "abc"])
def test_normalizar_mapa_obrigatorio_invalido(entrada):
    with pytest.raises(ValueError):
        Processo030322Page.normalizar_mapa(entrada)


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("04092026", "04/09/2026"),
        ("2026-09-04", "04/09/2026"),
        ("04/09/2026", "04/09/2026"),
        ("00/00/0000", "00/00/0000"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalizar_data(entrada, esperado):
    assert Processo030322Page.normalizar_data(entrada) == esperado


@pytest.mark.parametrize("entrada", ["2026/09/04", "32092026", "texto"])
def test_normalizar_data_invalida(entrada):
    with pytest.raises(ValueError):
        Processo030322Page.normalizar_data(entrada)


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("abertos", "A"),
        ("fechados", "F"),
        ("liberados", "L"),
        ("todos", "T"),
        ("A", "A"),
        ("f", "F"),
    ],
)
def test_normalizar_status_mapas(entrada, esperado):
    assert Processo030322Page.normalizar_status_mapas(entrada) == esperado


def test_normalizar_status_mapas_invalido():
    with pytest.raises(ValueError):
        Processo030322Page.normalizar_status_mapas("inexistente")


def test_parse_relatorio_030322_com_notas_devolucao_e_vasilhame():
    texto = """
PW02136R-t-Promax Web          (052 )  Prestacao de Contas       LIBERADA        Mapa:  94.041 de 03/09/2026    04/09/2026       Pag.    1
Distribuidora de Bebidas Pau Brasil LTDA  Liberada em: 03/09/2026                Rev.:       1                       09:47
Veiculo ..:   6 OFE2918 PB   Transp. .: 01 TRANSPORTADORA PAU BR  Motorista ....:  6096 JOSIVALDO GOMES DE OL  Ajudante 1 .: 07444
Entrega ..: ROTA             Frota ...: PADRONIZADA               Carga Original: ROTEIRIZADA                  Ajudante 2 .: 07316
Caixa ....:  53 ANDRE VINICIUS BARROS MACA                        Carga Atual ..: ROTEIRIZADA                  Conferente .: 07207
UNB/Codigo Razao Social                      Nota  Sit    Op Condicao Pagto         Valor da Nota         Devolucao    Valor Liquido
     17695 FLAVIO PIRES                 204.742 003        1 CREDITO EM CONTAS             215,60                             215,60
     12572 BOLIBAR RESTAURATE PETISCAR  204.745 003 DEV    1 BOLETO 6 DIAS 2,5%          1.198,05          1.198,05
                  Totais ..........:            2                                          1.413,65          1.198,05           215,60
VASILHAME
 Codigo Un   Denominacao                             Preco   ------- Saida -------    ------ Retorno ------    ------ Diferenca -----
   27983 un   GFA VIDRO 635ML,AMBAR,TIPO A,RET         1,20    120/00        144,00     120/00        144,00        /00
                                              Totais ..........:            144,00                   144,00   Falta:             0,00-
RESUMO FINANCEIRO
         CREDITO EM CONTA                    215,60               18     CREDITO CONTA                       215,60
"""
    payload = Processo030322Page._parse_relatorio_texto(texto)

    assert payload["cabecalho"]["mapa"] == "94041"
    assert payload["cabecalho"]["revenda"] == "1"
    assert payload["cabecalho"]["motorista"] == "6096 JOSIVALDO GOMES DE OL"
    assert payload["resumo"]["notas"] == 2
    assert payload["resumo"]["devolucoes"] == 1
    assert payload["notas"][0]["nota"] == "204742"
    assert payload["notas"][1]["situacao"] == "DEV"
    assert payload["vasilhames"][0]["codigo"] == "27983"
