from promax_http import html
from promax_http.explorar_030104 import podar_ramos, valores_da_resposta
from promax_http.pedido_030104 import _TRAVA_COND, formatar_ttv, item_lista

D = "document.parentWindow.parent.rotina.document.all ( '{}' )"


def test_if_com_literais_fica_so_com_o_ramo_executado():
    js = (
        "if( '0' == 0) { " + D.format("nrMapa") + ".value = '096710'; }\n"
        "else { " + D.format("nrMapa") + ".value = ''; }"
    )
    assert valores_da_resposta(js)["nrMapa"] == "096710"


def test_condicao_em_varias_linhas_descarta_pergunta_que_nunca_aparece():
    js = """if( ('N' == 'S' || 'N' == 's')

        && ("" == "S" || "0" == "0" )

        &&  "001" == 1){
            R.msgbxSimNao( 'Digitacao Pedido' , 'Voce deseja MESMO utilizar a tabela de TTV Cheio' );
        }"""
    assert "msgbxSimNao" not in podar_ramos(js)


def test_condicao_com_campo_da_tela_usa_o_valor_atual():
    js = "if ( " + D.format("cdOperacao") + ".value == 33 ){ alert(\"Mapa de transferencia\"); }"
    assert html.alertas(podar_ramos(js, {"cdOperacao": "1"})) == []
    assert html.alertas(podar_ramos(js, {"cdOperacao": "33"})) == ["Mapa de transferencia"]


def test_condicao_desconhecida_mantem_os_dois_ramos():
    js = "if( x > 1 ){ alert('a'); } else { alert('b'); }"
    assert podar_ramos(js) == js


def test_lista_de_condicoes_carregada_pelo_promax():
    js = 'CCmbcdCondicaoPagto("408","408 - BOLETO 8 DIAS 2,5%");CCmbcdCondicaoPagto("002","002 - DINHEIRO")'
    assert [(o.valor, o.texto) for o in html.opcoes_carregadas(js)["cdCondicaoPagto"]] == [
        ("408", "408 - BOLETO 8 DIAS 2,5%"), ("002", "002 - DINHEIRO"),
    ]


def test_trava_da_condicao():
    assert _TRAVA_COND.findall(D.format("cdCondicaoPagto") + ".disabled = true;") == ["true"]


def test_item_no_formato_da_tela():
    item = item_lista({"cdProduto": "2349", "qtPedida": "2", "vlTtv": formatar_ttv("44"), "sgUnidade": "cx"})
    assert len(item) == 139
    assert item.startswith("000234900002000000044,00000000000000000")
    assert item[79:84] == "Ncx  "  # 7+5+12+15+20+1+10+2+7 = 79


def test_lista_de_condicoes_gravada_e_preservada(tmp_path):
    from promax_http.pedido_030104 import gravar_catalogo
    import json

    dados = {"unidade": "2210003", "lido_em": "x", "condicoes": [{"codigo": "408", "descricao": "BOLETO"}]}
    arquivo = gravar_catalogo(dados, tmp_path)
    assert arquivo.name == "030104_condicoes_2210003.json"
    assert json.loads(arquivo.read_text(encoding="utf-8"))["condicoes"][0]["codigo"] == "408"
    # leitura vazia nao apaga a ultima lista boa
    assert gravar_catalogo({"unidade": "2210003", "condicoes": []}, tmp_path) is None
    assert "408" in arquivo.read_text(encoding="utf-8")


class _Resposta:
    def __init__(self, texto):
        self.texto, self.status = texto, 200


class _ClienteFalso:
    def __init__(self, respostas):
        self.respostas, self.enviados = list(respostas), []

    def _enviar_frame9(self, rotina, campos):
        self.enviados.append(dict(campos))
        return _Resposta(self.respostas.pop(0))


class _Rotina:
    class form:
        campos = {"cdDestinatario": "", "idSetorDifere": ""}


def _digitacao(respostas):
    import logging
    from promax_http.pedido_030104 import Digitacao
    falso = _ClienteFalso(respostas)
    return Digitacao(falso, _Rotina(), logging.getLogger("teste")), falso


def test_cliente_de_outro_setor_responde_sim_e_reenvia():
    from pathlib import Path
    pergunta = (Path(__file__).parent / "fixtures" / "030104_cliente_outro_setor.html").read_text(encoding="utf-8")
    ok = "<script>" + D.format("cdCondicaoPagto") + ".value = '408';</script>"
    d, falso = _digitacao([pergunta, ok])
    d.informar_cliente("16883")
    assert [e["opcao"] for e in falso.enviados] == ["5", "5"]
    assert falso.enviados[0]["idSetorDifere"] == "" and falso.enviados[1]["idSetorDifere"] == "S"
    assert falso.enviados[1]["cdDestinatario"] == "16883"
    assert d.form["cdCondicaoPagto"] == "408"


def test_cliente_com_outra_pergunta_continua_parando():
    import pytest
    from promax_http.pedido_030104 import Parada
    outra = "<script>x.msgbxSimNao( 'PW02043C' , 'Cliente bloqueado, Confirma ?', function(){}, function(){});</script>"
    d, _ = _digitacao([outra])
    with pytest.raises(Parada, match="bloqueado"):
        d.informar_cliente("16883")
