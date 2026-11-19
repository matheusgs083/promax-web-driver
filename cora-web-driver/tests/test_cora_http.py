from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

import cora_http as c
from cora_http import ClienteCora, CoraBloqueado, CoraErro, Resposta, pedido_csv

FORM = (
    '<html><form id="kc-form-login" onsubmit="x" action="https://auth.ambevdevs.com.br/realms/Third/'
    'login-actions/authenticate?session_code=S&amp;execution=E&amp;client_id=ambev-hercules-autorizacao&amp;tab_id=T" method="post">'
    '<input name="username"><input name="password"></form></html>'
)
MODELO = {
    "id": "crit",
    "content": {
        "columns": [{"id": "b", "order": 11}, {"id": "a", "order": 5}, {"id": "c", "order": 12}],
        "filters": [
            {"id": c.FILTRO_DATA_ENTREGA, "values": ["Thu Oct 22 2026 14:51:05 GMT-0300"] * 2},
            {"id": "unid", "values": ["u1", "u2"]},
            {"id": "buffer", "values": ["0"]},
        ],
    },
}


class Falso:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.pedidos = []

    def enviar(self, metodo, url, *, cabecalhos=None, corpo=None):
        self.pedidos.append((metodo, url, cabecalhos or {}, corpo))
        status, conteudo, extra = self.respostas.pop(0)
        dados = conteudo if isinstance(conteudo, bytes) else (json.dumps(conteudo).encode() if not isinstance(conteudo, str) else conteudo.encode())
        return Resposta(status, dados, extra or {})


def _login_ok():
    return [
        (200, FORM, None),
        (302, "", {"Location": "https://cora-revenda.ambev.com.br/#state=s&session_state=x&code=CODIGO"}),
        (200, {"access_token": "TOK"}, None),
    ]


def test_login_envia_formulario_e_troca_codigo_por_token():
    falso = Falso(_login_ok())
    cliente = ClienteCora(falso, log=lambda m: None)
    cliente.login("u@x", "segredo")
    _, url_form, _, corpo_form = falso.pedidos[1]
    assert "session_code=S&execution=E" in url_form  # &amp; desfeito
    assert b"username=u%40x" in corpo_form and b"password=segredo" in corpo_form
    _, url_token, _, corpo_token = falso.pedidos[2]
    assert url_token.endswith("/token") and b"code=CODIGO" in corpo_token
    assert cliente.token == "TOK"


def test_login_recusado_mostra_motivo_sem_vazar_senha():
    falso = Falso([(200, FORM, None), (200, '<span id="input-error" class="x">Usuário ou senha inválidos.</span>', None)])
    with pytest.raises(CoraErro, match="Usuário ou senha inválidos") as erro:
        ClienteCora(falso, log=lambda m: None).login("u", "segredo")
    assert "segredo" not in str(erro.value)


def test_bloqueio_da_imperva_vira_erro_proprio():
    falso = Falso([(403, "<html>Request unsuccessful. Incapsula incident ID</html>", None)])
    with pytest.raises(CoraBloqueado):
        ClienteCora(falso, log=lambda m: None).login("u", "s")


def test_pedido_csv_reordena_colunas_e_troca_a_data():
    corpo = pedido_csv(MODELO, date(2026, 11, 19))
    assert corpo["columns"] == [{"id": "a", "order": 0, "value": None}, {"id": "b", "order": 1, "value": None}, {"id": "c", "order": 2, "value": None}]
    assert corpo["filters"] == [
        {"id": c.FILTRO_DATA_ENTREGA, "value": ["2026-11-19", "2026-11-19"]},
        {"id": "unid", "value": ["u1", "u2"]},
        {"id": "buffer", "value": ["0"]},
    ]


def _arquivo(status, criado="2026-11-18T17:40:23.230181Z", nome="consulta-pedidos_19112026_18112026-174023175"):
    return {"id": "arq1", "name": nome, "status": status, "createAt": criado, "percentile": 50}


def test_baixar_critica_espera_ficar_pronto_e_baixa(tmp_path):
    falso = Falso(_login_ok() + [
        (200, {"userTemplate": [{"id": "crit", "name": "Critica"}], "defaultTemplate": []}, None),
        (200, MODELO, None),
        (200, "", None),  # generate-csv
        (200, {"data": [_arquivo(1), _arquivo(2, criado="2026-11-17T10:00:00Z")]}, None),  # antigo pronto nao conta
        (200, {"data": [_arquivo(2)]}, None),
        (200, {"link": "https://blob/x.csv?sig=1"}, None),
        (200, b"a;b\n1;2\n", None),
    ])
    cliente = ClienteCora(falso, log=lambda m: None, dormir=lambda s: None,
                          agora=lambda: datetime(2026, 11, 18, 17, 40, 20, tzinfo=timezone.utc))
    cliente.login("u", "s")
    destino = cliente.baixar_critica(date(2026, 11, 19), tmp_path)
    assert destino.read_bytes() == b"a;b\n1;2\n"
    assert destino.name == "consulta-pedidos_19112026_18112026-174023175.csv"
    metodo, url, cab, corpo = falso.pedidos[5]
    assert url.endswith("/search/generate-csv") and cab["x-tenant"] == c.TENANT and cab["Authorization"] == "Bearer TOK"
    assert json.loads(corpo)["filters"][0]["value"] == ["2026-11-19", "2026-11-19"]
    assert falso.pedidos[-1][2].get("Authorization") is None  # link do Azure vai sem token


def test_arquivo_com_erro_no_cora_falha(tmp_path):
    falso = Falso(_login_ok() + [
        (200, {"userTemplate": [{"id": "crit", "name": "Critica"}]}, None),
        (200, MODELO, None),
        (200, "", None),
        (200, {"data": [_arquivo(4)]}, None),
    ])
    cliente = ClienteCora(falso, log=lambda m: None, dormir=lambda s: None,
                          agora=lambda: datetime(2026, 11, 18, 17, 40, 20, tzinfo=timezone.utc))
    cliente.login("u", "s")
    with pytest.raises(CoraErro, match="erro"):
        cliente.baixar_critica(date(2026, 11, 19), tmp_path)


def test_consulta_inexistente_lista_as_do_usuario():
    falso = Falso(_login_ok() + [(200, {"userTemplate": [{"id": "1", "name": "BUFFER"}]}, None)])
    cliente = ClienteCora(falso, log=lambda m: None)
    cliente.login("u", "s")
    with pytest.raises(CoraErro, match="BUFFER"):
        cliente.consulta_salva("Critica")


FILIAIS = {"branches": [
    {"code": 747530, "name": "Pau Brasil Filial Patos", "company": {"code": 2221}},
    {"code": 747548, "name": "Pau Brasil Filial Sume", "company": {"code": 2221}},
]}


def _estoque(status, filial="747530", criado="2026-11-19T11:10:38.876396Z"):
    return {"id": f"arq{filial}", "name": f"STOCK_PRODUCT-20261119-2221{filial}-20261119-081038828",
            "status": status, "createAt": criado}


def test_grade_de_estoque_pede_por_filial_e_baixa(tmp_path):
    falso = Falso(_login_ok() + [
        (200, FILIAIS, None),
        (202, "", None),  # stock-products:csv
        (200, {"data": [_estoque(1)]}, None),
        (200, {"data": [_estoque(2)]}, None),
        (200, {"link": "https://blob/estoque.csv?sig=1"}, None),
        (200, b"codigo;produto\n347;SUKITA\n", None),
    ])
    cliente = ClienteCora(falso, log=lambda m: None, dormir=lambda s: None,
                          agora=lambda: datetime(2026, 11, 19, 11, 10, 30, tzinfo=timezone.utc))
    cliente.login("u", "s")
    arquivos = cliente.baixar_grade_estoque(date(2026, 11, 19), tmp_path, filiais=["747530"])
    assert [a.name for a in arquivos] == ["ESTOQUE_PATOS_20261119.csv"]
    assert arquivos[0].read_bytes().startswith(b"codigo;produto")
    metodo, url, _, corpo = falso.pedidos[4]
    assert metodo == "POST" and url.endswith("/reports/stock-products:csv")
    assert json.loads(corpo) == {"movementDate": "2026-11-19", "company": {"branch": {"code": 747530}, "code": 2221},
                                 "grid": 0, "productCodes": [], "reserve": "TODAS"}


def test_grade_de_estoque_filial_inexistente_lista_as_disponiveis(tmp_path):
    falso = Falso(_login_ok() + [(200, FILIAIS, None)])
    cliente = ClienteCora(falso, log=lambda m: None)
    cliente.login("u", "s")
    with pytest.raises(CoraErro, match="747548"):
        cliente.baixar_grade_estoque(date(2026, 11, 19), tmp_path, filiais=["999"])


@pytest.mark.parametrize("nome, esperado", [
    ("Pau Brasil Filial Patos", "PATOS"),
    ("PAU BRASIL FILIAL SUMÉ", "SUME"),
    ("Sousa", "SOUSA"),
    ("Sao Joao do Rio do Peixe", "SAO_JOAO_RIO_PEIXE"),
    ("", "747530"),
])
def test_nome_revenda_no_arquivo(nome, esperado):
    from cora_http import nome_revenda
    assert nome_revenda({"code": 747530, "name": nome}) == esperado


def test_grade_de_estoque_ignora_filial_que_o_login_nao_ve(tmp_path):
    falso = Falso(_login_ok() + [
        (200, FILIAIS, None),
        (202, "", None),
        (200, {"data": [_estoque(2)]}, None),
        (200, {"link": "https://blob/estoque.csv?sig=1"}, None),
        (200, b"codigo;produto\n347;SUKITA\n", None),
    ])
    mensagens = []
    cliente = ClienteCora(falso, log=mensagens.append, dormir=lambda s: None,
                          agora=lambda: datetime(2026, 11, 19, 11, 10, 30, tzinfo=timezone.utc))
    cliente.login("u", "s")
    unidades = cliente.baixar_grade_estoque_detalhada(date(2026, 11, 19), tmp_path, filiais=["747530", "820288"])
    assert [u["code"] for u in unidades] == ["747530"]
    assert any("820288" in m and "ignoradas" in m for m in mensagens)
