import re
from pathlib import Path

import pytest

from promax_http import html, ph
from promax_http.cliente import ClientePromax, Rotina
from promax_http.erros import ExportacaoNaoEntendida, RelatorioSemConteudo
from promax_http.receitas import pedido_csv_0105070402
from promax_http.transporte import Resposta

FIXTURES = Path(__file__).parent / "fixtures"
URL = "http://paubrasil.promaxcloud.com.br/pw/cgi-bin/PP00100.exe"
SUCESSO = (
    '{ "mensagemRetorno" : [ { "mensagem" :"CSV gerado com Sucesso!" } ], '
    '"downloadCSV" : [ { "dsCaminhoArquivoCSV" :"../tmp/rels/F7367_PH050094.csv" } ] }'
)


class PromaxPhFalso:
    """Responde como a tela PH050094 respondeu na captura 20261118_084728_captura_ph."""

    def __init__(self):
        self.posts = []
        self.json_gerar = SUCESSO
        self.arquivos = {"F7367_PH050094.csv": b"CLIENTE;NOME\n1;ABC\n"}
        self.baixados = []

    def post(self, url, campos):
        campos = list(campos.items()) if isinstance(campos, dict) else list(campos)
        self.posts.append(campos)
        if dict(campos).get("ajaxJson") == "N":
            texto = (FIXTURES / "tela_ph_0105070402_conteudo.html").read_text(encoding="utf-8")
            return Resposta(url, 200, "text/html", texto.encode("cp1252", "replace"))
        return Resposta(url, 200, "text/json", self.json_gerar.encode("cp1252"))

    def baixar(self, url, destino, *, ao_progredir=None):
        self.baixados.append(url)
        nome = url.rsplit("/", 1)[1]
        if nome not in self.arquivos:
            return 404, "text/html", 0
        parcial = destino.with_suffix(destino.suffix + ".parcial")
        parcial.parent.mkdir(parents=True, exist_ok=True)
        parcial.write_bytes(self.arquivos[nome])
        return 200, "text/plain", len(self.arquivos[nome])


@pytest.fixture
def promax():
    return PromaxPhFalso()


@pytest.fixture
def cliente(promax):
    return ClientePromax(URL, transporte=promax)


@pytest.fixture
def rotina():
    casca = (FIXTURES / "tela_ph_0105070402.html").read_text(encoding="utf-8")
    form = html.formulario(casca, "formPadrao")
    return Rotina(
        codigo="0105070402", menu_id="010507040200", programa="PH050094", sub_session_id="x",
        url_rotina=URL, url_frame9="", form=form, html_rotina=casca, html_topo="",
    )


def test_gerar_csv_envia_o_que_o_gerarcsv_da_tela_envia_e_baixa_o_caminho(cliente, promax, rotina, tmp_path):
    ph.carregar_tela(cliente, rotina, "btnGerarCSV")

    arquivo = ph.gerar_csv(cliente, rotina, pedido_csv_0105070402(), tmp_path / "dClientes.csv")

    enviado = promax.posts[-1]
    padrao = dict(enviado)
    assert (padrao["call"], padrao["opcao"], padrao["ppopcao"], padrao["ajaxJson"], padrao["callRetorno"]) == (
        "PH050094", "1", "0", "S", "PY050094",
    )
    assert ("flPreferencias", "1111111000") in enviado
    assert ("idGeo", "S") in enviado and ("cdCorporativoFim", "9.999.999.999.999") in enviado
    assert promax.baixados == ["http://paubrasil.promaxcloud.com.br/pw/tmp/rels/F7367_PH050094.csv"]
    assert arquivo.read_bytes() == b"CLIENTE;NOME\n1;ABC\n"


def test_carregar_tela_falha_quando_o_formulario_nao_vem(cliente, rotina):
    with pytest.raises(Exception, match="nao trouxe o formulario"):
        ph.carregar_tela(cliente, rotina, "idInexistente")


def test_mensagem_sem_dados_vira_sem_conteudo():
    with pytest.raises(RelatorioSemConteudo):
        ph.caminho_do_csv('{ "mensagemRetorno" : [ { "mensagem" :"Não há dados para listar" } ] }')


def test_erro_do_pp00100_vira_falha():
    with pytest.raises(ExportacaoNaoEntendida, match="ABERTURA"):
        ph.caminho_do_csv('{ "dsErroAbertura" : [ { "dsErro" :"Erro: 47 - ABERTURA" } ] }')


def test_preferencias_seguem_a_ordem_das_situacoes():
    pedido = pedido_csv_0105070402(situacoes=("ativos", "venda_temporaria"), as_=False, toda_geo=False)

    assert ("flPreferencias", "1000001000") in pedido.campos
    assert ("idAS", "N") in pedido.campos and ("idGeo", "S") not in pedido.campos


class _Tracker:
    def __init__(self):
        self.notas = []

    def anotar(self, rotina, unidade, status, detalhe, segundos):
        self.notas.append((rotina, unidade, status))


class _Logger:
    def info(self, *a, **k):
        pass

    error = debug = info


def _sessao_com(cliente, rotina):
    from promax_http.integracao import SessaoHttp

    cliente.abrir_rotina = lambda codigo: rotina
    cliente.fechar_rotina = lambda r: None
    sessao = SessaoHttp(settings=None, logger=_Logger(), pasta_rastro=Path("."))
    sessao.cliente = cliente
    return sessao


def _pedido():
    from promax_http.integracao import PedidoRelatorioPh

    return PedidoRelatorioPh(
        rotina="0105070402", tracker_name="Rotina 0105070402 Bot", subpasta="0105070402 bot",
        nome_arquivo="0105070402 bot - dClientes.csv", csv=pedido_csv_0105070402(), marca_tela="btnGerarCSV",
    )


def test_integracao_ph_grava_na_subpasta_e_anota_sucesso(cliente, rotina, tmp_path):
    from core.execution.execution_result import ExecutionStatus
    from promax_http.integracao import gerar_relatorio_ph_http

    tracker = _Tracker()
    resultado = gerar_relatorio_ph_http(
        _sessao_com(cliente, rotina), _pedido(), pasta_base=tmp_path, tracker=tracker, logger=_Logger()
    )

    assert resultado.status == ExecutionStatus.SUCCESS
    assert (tmp_path / "0105070402 bot" / "0105070402 bot - dClientes.csv").is_file()
    assert tracker.notas == [("Rotina 0105070402 Bot", "TODAS", "SUCESSO")]


def test_integracao_ph_erro_do_promax_vira_falha_tecnica(cliente, promax, rotina, tmp_path):
    from core.execution.execution_result import ExecutionStatus
    from promax_http.integracao import gerar_relatorio_ph_http

    promax.json_gerar = '{ "dsErroPP00100" : [ { "dsErro" :"Sessao expirada" } ] }'
    tracker = _Tracker()
    resultado = gerar_relatorio_ph_http(
        _sessao_com(cliente, rotina), _pedido(), pasta_base=tmp_path, tracker=tracker, logger=_Logger()
    )

    assert resultado.status == ExecutionStatus.TECHNICAL_FAILURE
    assert tracker.notas == [("Rotina 0105070402 Bot", "TODAS", "ERRO SISTEMA")]


def test_03114902_geo_usa_opcao_7_e_serializa_na_ordem_da_tela():
    from promax_http.receitas import pedido_csv_03114902

    pedido = pedido_csv_03114902(data_inicial="04/11/2026", data_final="18/11/2026", todas_operacoes=True, csv_geo=True)

    assert (pedido.opcao, pedido.call_retorno) == ("7", "PY050158")
    nomes = [n for n, _ in pedido.campos]
    assert nomes == [
        "opClassificacao", "checkRota", "checkAs", "checkTodasOper", "idRoteirizado", "mapaInicial", "mapaFinal",
        "dataInicial", "dataFinal", "roadInicial", "roadFinal", "cdTransportadoraInicial",
        "cdTransportadoraFinal", "opArmazem",
    ]
    assert ("opArmazem", "0") in pedido.campos and ("opClassificacao", "0") in pedido.campos


def test_03114902_liga_usa_opcao_6_e_codigo_do_armazem():
    from promax_http.receitas import pedido_csv_03114902

    pedido = pedido_csv_03114902(data_inicial="01/11/2026", data_final="17/11/2026", armazem="01 - ARMAZEM CENTRAL")

    assert pedido.opcao == "6" and ("opArmazem", "01") in pedido.campos


def test_03114902_recusa_periodo_que_atravessa_o_mes_como_a_tela():
    from promax_http.receitas import pedido_csv_03114902

    with pytest.raises(ValueError, match="mesmo mes"):
        pedido_csv_03114902(data_inicial="25/10/2026", data_final="08/11/2026")


def test_03114902_conteudo_capturado_tem_os_campos_da_receita():
    from promax_http.receitas import pedido_csv_03114902

    tela = (FIXTURES / "tela_ph_03114902_conteudo.html").read_text(encoding="utf-8")
    pedido = pedido_csv_03114902(data_inicial="01/11/2026", data_final="17/11/2026", csv_geo=True)

    for nome, _ in pedido.campos:
        assert f"name={nome}" in tela, nome
    assert 'onClick="PH050158.gerarCSVGeo();"' in tela


def _rotina_na_unidade(unidade):
    casca = (FIXTURES / "tela_ph_0105070402.html").read_text(encoding="utf-8").replace(
        '$("#unidadeMenu").val("2210003")', f'$("#unidadeMenu").val("{unidade}")'
    )
    return Rotina(
        codigo="0105070402", menu_id="010507040200", programa="PH050094", sub_session_id="x",
        url_rotina=URL, url_frame9="", form=html.formulario(casca, "formPadrao"), html_rotina=casca, html_topo="",
    )


def _casca_em(unidade, session_id="z0Kq7U19899585"):
    casca = (FIXTURES / "tela_ph_0105070402.html").read_text(encoding="utf-8")
    casca = casca.replace('$("#unidadeMenu").val("2210003")', f'$("#unidadeMenu").val("{unidade}")')
    return re.sub(r'(name="SessionID"\s+id="SessionID"\s+value=)\w+', rf"\g<1>{session_id}", casca)


def test_trocar_unidade_pede_a_tela_na_unidade_e_adota_o_sessionid_novo(cliente, promax, rotina):
    cliente.session_id = "z0Kq7U19899585"
    promax.post = lambda url, campos: (
        promax.posts.append(list(campos.items()) if isinstance(campos, dict) else list(campos))
        or Resposta(url, 200, "text/html", _casca_em("2210004", "a1b2c3d4e5f60718293a4b5c6d7e8").encode("cp1252", "replace"))
    )

    nova = ph.trocar_unidade(cliente, rotina, "2210004")

    enviado = dict(promax.posts[-1])
    assert (enviado["ppopcao"], enviado["call"], enviado["changeUNB"], enviado["unidade"]) == (
        "7", "010507040200", "A", "2210004",
    )
    assert re.fullmatch(r"[0-9a-f]{29}", enviado["SessionID"])
    assert ph.unidade_ativa(nova) == "2210004"
    # A unidade fica presa ao SessionID: os proximos pedidos tem que usar o novo.
    assert cliente.session_id == "a1b2c3d4e5f60718293a4b5c6d7e8"
    assert nova.form.campos["SessionID"] == "a1b2c3d4e5f60718293a4b5c6d7e8"


def test_trocar_unidade_falha_quando_a_tela_continua_na_unidade_antiga(cliente, promax, rotina):
    # Visto em 18/11: sem confirmar a unidade, o "Sume" saiu com os dados de Patos.
    promax.post = lambda url, campos: Resposta(url, 200, "text/html", _casca_em("2210003").encode("cp1252", "replace"))

    with pytest.raises(Exception, match="nao pegou"):
        ph.trocar_unidade(cliente, rotina, "2210004")


def test_trocar_unidade_nao_faz_nada_quando_ja_esta_na_unidade(cliente, promax, rotina):
    assert ph.trocar_unidade(cliente, rotina, "2210003") is rotina
    assert promax.posts == []
