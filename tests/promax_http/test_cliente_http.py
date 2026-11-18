import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from promax_http.cliente import ClientePromax
from promax_http.erros import LoginRecusado, RelatorioSemConteudo, SemPermissao
from promax_http.ids import gerar_id_troca_unidade, gerar_session_id
from promax_http.transporte import Resposta, Transporte

FIXTURES = Path(__file__).parent / "fixtures"
URL = "http://paubrasil.promaxcloud.com.br/pw/cgi-bin/PP00100.exe?ppopcao=1"


def fixture(nome):
    return (FIXTURES / nome).read_text(encoding="utf-8")


class PromaxFalso:
    """Responde como o Promax respondeu na captura 030302_ie_20260814_085553."""

    def __init__(self):
        self.chamadas = []
        self.resposta_frame9 = "<html></html>"
        self.arquivos = {}
        self.login_recusado = False
        self.unidade_ativa = "2210003"
        self.pagina_rotina = "rotina.html"
        self.tela_resultado = ""
        self.frameset = "frameset.html"

    def get(self, url):
        return self._responder("GET", url, {})

    def baixar(self, url, destino, *, ao_progredir=None):
        self.chamadas.append(("GET", url, {}))
        nome = url.rsplit("/", 1)[1]
        if nome not in self.arquivos:
            return 300, "text/html", 0
        parcial = destino.with_suffix(destino.suffix + ".parcial")
        parcial.parent.mkdir(parents=True, exist_ok=True)
        parcial.write_bytes(self.arquivos[nome])
        if ao_progredir:
            ao_progredir(len(self.arquivos[nome]), 1.0)
        return 200, "text/plain", len(self.arquivos[nome])

    def post(self, url, campos):
        return self._responder("POST", url, dict(campos))

    def _responder(self, metodo, url, campos):
        self.chamadas.append((metodo, url, campos))
        query = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        ppopcao = campos.get("ppopcao") or query.get("ppopcao")
        html = "<html></html>"
        tipo = "text/html"
        if "/tmp/rels/" in url:
            nome = url.rsplit("/", 1)[1]
            if nome not in self.arquivos:
                return Resposta(url, 300, "text/html", b"<html>Multiple Choices</html>")
            return Resposta(url, 200, "text/plain", self.arquivos[nome])
        if metodo == "POST" and campos.get("ppopcao") == "1" and "Usuario" in campos:
            html = "<script>alert('Senha inválida');</script>" if self.login_recusado else fixture("login_unidade.html")
        elif metodo == "POST" and campos.get("ppopcao") == "2":
            assert campos["Senha"] == "TOKEN_FICTICIO"
            html = fixture("menu.html").replace("s7Cl4E65714027", campos["SessionID"])
        elif ppopcao == "6":
            tipo = "text/json"
            html = fixture("atalho.json") if campos.get("MenuID") == "03030718000" else '{ "nivel" : [] }'
        elif ppopcao == "7":
            if campos.get("changeUNB") == "A":
                self.unidade_ativa = campos["unidade"]
            html = fixture(self.frameset)
        elif ppopcao == "8":
            html = fixture("topo.html").replace(
                'document.all.unidade.value = "2210003"', f'document.all.unidade.value = "{self.unidade_ativa}"'
            )
        elif query.get("frame") == "0" and metodo == "POST" and campos.get("opcao") == "1":
            html = self.tela_resultado
        elif query.get("frame") == "0" and metodo == "POST" and campos.get("opcao") == "88":
            html = self.resposta_frame9
        elif query.get("frame") == "0":
            html = fixture(self.pagina_rotina)
        elif metodo == "POST" and campos.get("frame") == "9":
            html = self.resposta_frame9
        return Resposta(url, 200, tipo, html.encode("cp1252"))


@pytest.fixture
def promax():
    return PromaxFalso()


@pytest.fixture
def cliente(promax):
    return ClientePromax(URL, transporte=promax)


def test_session_id_tem_o_formato_do_javascript_do_promax():
    for _ in range(50):
        assert re.fullmatch(r"[a-z][0-9][A-Za-z][a-z][0-9][A-Za-z]\d{7,9}", gerar_session_id())
    assert re.fullmatch(r"[0-9a-f]{29}", gerar_id_troca_unidade())


def test_login_reenvia_o_token_da_segunda_tela_e_abre_o_menu(cliente, promax):
    unidade = cliente.login("F7367", "segredo", unidade="SUME")

    assert unidade == "2210004"
    segundo_post = [c for m, u, c in promax.chamadas if c.get("ppopcao") == "2"][0]
    assert segundo_post["unidade"] == "2210004"
    assert segundo_post["SessionID"] == cliente.session_id


def test_login_recusado_traz_o_alerta(cliente, promax):
    promax.login_recusado = True
    with pytest.raises(LoginRecusado, match="Senha"):
        cliente.login("F7367", "errada")


def test_abrir_rotina_descobre_menu_id_programa_e_unidades(cliente):
    cliente.login("F7367", "segredo")
    rotina = cliente.abrir_rotina("03030718")

    assert rotina.menu_id == "03030718000"
    assert rotina.programa == "PW02481C"
    assert rotina.unidade_ativa == "2210003"
    assert [o.valor for o in rotina.unidades][:2] == ["2210003", "2210004"]
    assert "call=PW02481C&frame=9" in rotina.url_frame9
    assert "nrMapa" in rotina.form.campos


def test_exportar_csv_segue_o_link_tmp_rels(cliente, promax, tmp_path):
    promax.resposta_frame9 = "<script>window.open('../tmp/rels/F7367_120616.csv');</script>"
    promax.arquivos["F7367_120616.csv"] = "COD;NOME\n1;ABC\n".encode("cp1252")
    cliente.login("F7367", "segredo")
    rotina = cliente.abrir_rotina("03030718")

    arquivo = cliente.exportar_csv(rotina, {"nrMapa": "1"}, tmp_path / "saida.csv")

    assert arquivo.read_text(encoding="cp1252") == "COD;NOME\n1;ABC\n"
    envio = [c for m, u, c in promax.chamadas if c.get("frame") == "9"][0]
    assert (envio["opcao"], envio["opcaorelat"], envio["nrMapa"]) == ("88", "3", "1")
    assert envio["SubSessionID"] == rotina.sub_session_id
    assert not list(tmp_path.glob("*.parcial"))


def test_alerta_de_relatorio_vazio_vira_sem_conteudo(cliente, promax, tmp_path):
    promax.resposta_frame9 = "<script>alert( 'Nenhuma informação encontrada' );</script>"
    cliente.login("F7367", "segredo")
    rotina = cliente.abrir_rotina("03030718")

    with pytest.raises(RelatorioSemConteudo):
        cliente.exportar_csv(rotina, {}, tmp_path / "saida.csv")


def test_alerta_de_permissao_vira_sem_permissao(cliente, promax, tmp_path):
    promax.resposta_frame9 = "<script>alert( 'Usuário sem permissão' );</script>"
    cliente.login("F7367", "segredo")
    rotina = cliente.abrir_rotina("03030718")

    with pytest.raises(SemPermissao):
        cliente.exportar_csv(rotina, {}, tmp_path / "saida.csv")


def test_rastro_nunca_grava_a_senha(tmp_path):
    from promax_http import transporte as modulo

    class RespostaHttp:
        status = 200
        headers = {"Content-Type": "text/html"}

        def __init__(self, url):
            self.url = url

        def geturl(self):
            return self.url

        def read(self):
            return b'<INPUT type=hidden name=Senha         value="1386174620881872">'

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    t = modulo.Transporte(pasta_rastro=tmp_path)
    t._opener = type("O", (), {"open": lambda self, req, timeout: RespostaHttp(req.full_url)})()
    t.post(URL, {"Usuario": "F7367", "Senha": "minha-senha"})

    gravado = "".join(p.read_text(encoding="utf-8") for p in tmp_path.iterdir())
    assert "minha-senha" not in gravado
    assert "1386174620881872" not in gravado


def test_trocar_unidade_reenvia_o_formframes_e_confere_a_unidade_ativa(cliente, promax):
    cliente.login("F7367", "segredo")
    rotina = cliente.abrir_rotina("03030718")

    nova = cliente.trocar_unidade(rotina, "3610006")

    troca = [c for m, u, c in promax.chamadas if c.get("changeUNB") == "A"][0]
    assert (troca["unidade"], troca["SubSessionID"], troca["call"]) == ("3610006", rotina.sub_session_id, "03030718000")
    assert nova.unidade_ativa == "3610006"


def test_exportar_030237_segue_visualizar_e_depois_gera_excel(cliente, promax, tmp_path):
    promax.pagina_rotina = "rotina_030237.html"
    promax.tela_resultado = (
        "<form name=form1 method=post><input type=hidden name=SessionID value=abc>"
        "<input type=hidden name=opcao value=1><input type=hidden name=relatorio value=XYZ>"
        "<input type=button name=GerExecl value='Gera CSV'></form>"
    )
    promax.resposta_frame9 = "<script>window.open('../tmp/rels/F7367_030237.csv');</script>"
    promax.arquivos["F7367_030237.csv"] = b"A;B\n1;2\n"
    cliente.login("F7367", "segredo")
    rotina = cliente.abrir_rotina("03030718")

    arquivo = cliente.exportar_csv(rotina, {"quebra1": "14", "dataInicial": "01/11/2026"}, tmp_path / "s.csv")

    assert arquivo.read_bytes() == b"A;B\n1;2\n"
    visualizar, exportar = [c for m, u, c in promax.chamadas if "frame=0" in u and m == "POST"]
    assert (visualizar["opcao"], visualizar["quebra1"], visualizar["call"]) == ("1", "14", "PW02099R")
    assert (exportar["opcao"], exportar["opcaorelat"], exportar["relatorio"]) == ("88", "3", "XYZ")


def test_link_csv_inf_e_o_proprio_csv(cliente, promax, tmp_path):
    promax.resposta_frame9 = '<script>window.open( "../tmp/rels/03.02.37_PW02099R_F7367_1.csv.inf", "relatorio" );</script>'
    promax.arquivos["03.02.37_PW02099R_F7367_1.csv.inf"] = b"A;B\n"
    cliente.login("F7367", "segredo")
    rotina = cliente.abrir_rotina("03030718")

    assert cliente.exportar_csv(rotina, {}, tmp_path / "s.csv").read_bytes() == b"A;B\n"
    baixados = [u for m, u, c in promax.chamadas if "/tmp/rels/" in u]
    assert baixados == ["http://paubrasil.promaxcloud.com.br/pw/tmp/rels/03.02.37_PW02099R_F7367_1.csv.inf"]


def test_nao_ha_notas_para_listar_vira_sem_conteudo(cliente, promax, tmp_path):
    promax.resposta_frame9 = "<script>alert( 'N\u00e3o h\u00e1 notas para listar' );</script>"
    cliente.login("F7367", "segredo")
    rotina = cliente.abrir_rotina("03030718")

    with pytest.raises(RelatorioSemConteudo):
        cliente.exportar_csv(rotina, {}, tmp_path / "s.csv")


def test_tela_ph_sem_frameset_e_aberta_para_captura(cliente, promax):
    promax.frameset = "tela_ph_0105070402.html"
    cliente.login("F7367", "segredo")

    rotina = cliente.abrir_rotina("03030718")

    assert rotina.programa == "PH050094"
    assert "formPadrao" in rotina.html_rotina


def test_020502_envia_valores_de_carga_da_tela_e_respeita_checkbox_desmarcado(cliente, promax, tmp_path):
    from promax_http.receitas import campos_020502

    promax.pagina_rotina = "rotina_020502.html"
    promax.tela_resultado = "<form name=form1 method=post><input type=hidden name=GeraExcel value=1></form>"
    promax.resposta_frame9 = "<script>window.open('../tmp/rels/F7367_020502.csv.inf');</script>"
    promax.arquivos["F7367_020502.csv.inf"] = b"A;B\n"
    cliente.login("F7367", "segredo")
    rotina = cliente.abrir_rotina("03030718")

    cliente.exportar_csv(rotina, campos_020502(listar_vasilhames_garrafeiras=False), tmp_path / "s.csv")

    visualizar = [c for m, u, c in promax.chamadas if "frame=0" in u and m == "POST"][0]
    assert visualizar["opcao"] == "1"
    assert visualizar["periodoInicial"] == "17/11/2026"
    assert (visualizar["cdArmazemInicial"], visualizar["cdArmazemFinal"]) == ("0", "99")
    assert visualizar["idListarProdutos"] == "S"
    assert "idListarVasGarraf" not in visualizar


def test_download_grande_vai_em_partes_para_o_disco_com_progresso(tmp_path):
    from promax_http import transporte as modulo

    conteudo = b"A;B\n" + b"1;2\n" * 700_000  # ~2,8 MB

    class RespostaHttp:
        status = 200
        headers = {"Content-Type": "text/plain"}

        def __init__(self):
            self.lido = 0

        def read(self, n):
            bloco = conteudo[self.lido:self.lido + n]
            self.lido += len(bloco)
            return bloco

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    t = modulo.Transporte()
    t._opener = type("O", (), {"open": lambda self, req, timeout: RespostaHttp()})()
    progresso = []

    status, _, total = t.baixar(URL, tmp_path / "r.csv", ao_progredir=lambda b, s: progresso.append(b), intervalo_log=0)

    assert (status, total) == (200, len(conteudo))
    assert (tmp_path / "r.csv.parcial").read_bytes() == conteudo
    assert progresso and progresso[-1] == len(conteudo)


def test_020220_envia_faixas_de_carga_e_mercadorias_da_receita(cliente, promax, tmp_path):
    from promax_http.receitas import campos_020220

    promax.pagina_rotina = "rotina_020220.html"
    promax.tela_resultado = "<form name=form1 method=post><input type=hidden name=GeraExcel value=1></form>"
    promax.resposta_frame9 = "<script>window.open('../tmp/rels/F7367_020220.csv.inf');</script>"
    promax.arquivos["F7367_020220.csv.inf"] = b"A;B\n"
    cliente.login("F7367", "segredo")
    rotina = cliente.abrir_rotina("03030718")

    cliente.exportar_csv(rotina, campos_020220(mercadorias={"garrafeira", "sopi_visa"}), tmp_path / "s.csv")

    visualizar = [c for m, u, c in promax.chamadas if "frame=0" in u and m == "POST"][0]
    assert visualizar["call"] == "PW03004R" and visualizar["opcao"] == "1"
    assert (visualizar["rotaInicial"], visualizar["rotaFinal"]) == ("1", "7")
    assert (visualizar["clienteInicial"], visualizar["clienteFinal"]) == ("0", "99999")
    assert (visualizar["garrafeira"], visualizar["idSopiVisa"]) == ("X", "X")
    assert "todos" not in visualizar and "vasilhame" not in visualizar
    assert (visualizar["idNpHistorico"], visualizar["omitirMapa"]) == ("S", "S")


def test_150501_faz_os_postbacks_da_tela_antes_do_visualizar(cliente, promax, tmp_path):
    from promax_http.receitas import PASSOS_150501, campos_150501

    promax.pagina_rotina = "rotina_150501.html"
    promax.tela_resultado = "<form name=form1 method=post><input type=hidden name=GeraExcel value=1></form>"
    promax.resposta_frame9 = "<script>window.open('../tmp/rels/F7367_150501.csv.inf');</script>"
    promax.arquivos["F7367_150501.csv.inf"] = b"A;B\n"
    cliente.login("F7367", "segredo")
    rotina = cliente.abrir_rotina("03030718")

    cliente.exportar_csv(
        rotina, campos_150501(visao="02", periodo="M", mes_ano="11/2026"), tmp_path / "s.csv",
        passos_previos=PASSOS_150501, opcao_visualizar="1",
    )

    postbacks = [c["opcao"] for m, u, c in promax.chamadas if m == "POST" and c.get("frame") == "9"]
    assert postbacks == ["2", "3", "4", "5"]
    visualizar = [c for m, u, c in promax.chamadas if "frame=0" in u and m == "POST"][0]
    assert (visualizar["opcao"], visualizar["call"], visualizar["listaConta"]) == ("1", "PW06011R", "9999999999")


def _visualizar_com(cliente, promax, tmp_path, pagina, campos):
    promax.pagina_rotina = pagina
    promax.tela_resultado = "<form name=form1 method=post><input type=hidden name=GeraExcel value=1></form>"
    promax.resposta_frame9 = "<script>window.open('../tmp/rels/X.csv.inf');</script>"
    promax.arquivos["X.csv.inf"] = b"A;B\n"
    cliente.login("F7367", "segredo")
    cliente.exportar_csv(cliente.abrir_rotina("03030718"), campos, tmp_path / "s.csv")
    return [c for m, u, c in promax.chamadas if "frame=0" in u and m == "POST"][0]


def test_120606_envia_titulos_marcados_pela_tela_e_periodo_da_tarefa(cliente, promax, tmp_path):
    from promax_http.receitas import campos_120606

    enviado = _visualizar_com(
        cliente, promax, tmp_path, "rotina_120606.html",
        campos_120606(opcao_rel="01", tipo_data="C", data_inicial="01/11/2026", data_final="16/11/2026", titulos={"normais": True}),
    )

    assert (enviado["call"], enviado["tpData"], enviado["iniDat"]) == ("PW04109R", "C", "01/11/2026")
    for nome in ("idTitulosNormais", "idTitulosCobrancaCa", "idTitulosValeFisico", "idTitulosRefugo", "idTitulosQuebras"):
        assert enviado[nome] == "S", nome
    assert "idTitulosAluguel" not in enviado
    assert (enviado["iniCli"], enviado["fimCli"]) == ("0", "999999")


def test_140501_envia_faixas_da_tela(cliente, promax, tmp_path):
    from promax_http.receitas import campos_140501

    enviado = _visualizar_com(cliente, promax, tmp_path, "rotina_140501.html", campos_140501())

    assert (enviado["call"], enviado["opcaoRel"]) == ("PW04210R", "01")
    assert (enviado["iniValor"], enviado["fimValor"], enviado["fimCGC"]) == ("0,00", "99999999,99", "ZZZZZZZZZZZZ99")
    assert not any(n.startswith("idListaPrev") for n in enviado)


def test_140506_envia_tipo_de_data_e_periodo(cliente, promax, tmp_path):
    from promax_http.receitas import campos_140506

    enviado = _visualizar_com(
        cliente, promax, tmp_path, "rotina_140506.html",
        campos_140506(opcao_rel="01", tipo_data="C", data_inicial="01/11/2026", data_final="16/11/2026"),
    )

    assert (enviado["call"], enviado["preferencias1"], enviado["fimDat"]) == ("PW04235R", "C", "16/11/2026")
    assert (enviado["iniEmi"], enviado["fimEmi"]) == ("00/00/0000", "99/99/9999")
