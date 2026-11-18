from promax_http.cliente import Rotina
from promax_http.html import Formulario, Opcao


def test_resumo_lista_campos_opcoes_e_botoes():
    from promax_http.capturar_telas import resumo_campos

    form = Formulario("form1", "", "POST", {"quebra1": "00", "dataInicial": ""}, {"quebra1": [Opcao("00", "--", True), Opcao("14", "Operacao")]}, {"BotVisualizar": {"onclick": "return Visualizar()"}})
    rotina = Rotina("030237", "030237000000", "PW02099R", "s", "u", "u9", form, "", "", [Opcao("2210003", "PATOS")])

    texto = resumo_campos(rotina)

    assert "Programa: PW02099R" in texto
    assert "'14': Operacao" in texto and "'00': -- *" in texto
    assert "BotVisualizar  onclick='return Visualizar()'" in texto
