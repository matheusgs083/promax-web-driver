from pathlib import Path

from core.execution.execution_result import ExecutionStatus
from promax_http.cliente import Rotina
from promax_http.erros import PromaxHttpErro, RelatorioSemConteudo
from promax_http.html import Formulario, Opcao
from promax_http.integracao import PedidoRelatorio, gerar_relatorio_http, rotinas_em_http


class TrackerFalso:
    def __init__(self):
        self.registros = []

    def anotar(self, rotina, unidade, status, detalhe, duracao=0):
        self.registros.append((rotina, unidade, status))


class ClienteFalso:
    def __init__(self, resultados):
        self.resultados = resultados
        self.fechou = False
        self.campos_enviados = []

    def abrir_rotina(self, codigo):
        opcoes = [Opcao(valor=c, texto=c) for c in self.resultados]
        return Rotina(codigo, "m", "PW", "sub", "u", "u9", Formulario("form1", "", "POST"), "", "", opcoes)

    def trocar_unidade(self, rotina, codigo):
        return rotina

    def exportar_csv(self, rotina, campos, destino):
        self.campos_enviados.append(campos)
        resultado = self.resultados[destino.stem.rsplit("_", 1)[1]]
        if isinstance(resultado, Exception):
            raise resultado
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(resultado)
        return destino

    def fechar_rotina(self, rotina):
        self.fechou = True


class SessaoFalsa:
    def __init__(self, cliente):
        self.cliente = cliente


class Logger:
    def info(self, *a):
        pass

    error = debug = warning = info


PEDIDO = PedidoRelatorio("030237", "Rotina 030237 Estoque", "030237 Estoque", "03,02,37_nomeUnidade030237estoque", {"a": "1"})


def test_grava_com_o_mesmo_nome_da_versao_edge_e_anota_o_tracker(tmp_path):
    cliente = ClienteFalso({"2210003": b"A;B\n", "2210004": RelatorioSemConteudo("Nao ha notas")})
    tracker = TrackerFalso()

    resultado = gerar_relatorio_http(
        SessaoFalsa(cliente), PEDIDO, unidades_alvo=None, pasta_base=tmp_path, tracker=tracker, logger=Logger()
    )

    assert (tmp_path / "030237 Estoque" / "03,02,37_nomeUnidade030237estoque_2210003.csv").read_bytes() == b"A;B\n"
    assert tracker.registros == [
        ("Rotina 030237 Estoque", "2210003", "SUCESSO"),
        ("Rotina 030237 Estoque", "2210004", "SEM CONTEUDO"),
    ]
    assert resultado.status is ExecutionStatus.SUCCESS
    assert cliente.fechou


def test_falha_de_uma_unidade_vira_sucesso_parcial_com_repescagem(tmp_path):
    cliente = ClienteFalso({"2210003": b"A;B\n", "2210004": PromaxHttpErro("caiu")})
    tracker = TrackerFalso()

    resultado = gerar_relatorio_http(
        SessaoFalsa(cliente), PEDIDO, unidades_alvo=None, pasta_base=tmp_path, tracker=tracker, logger=Logger()
    )

    assert resultado.status is ExecutionStatus.PARTIAL_SUCCESS and resultado.should_retry
    assert tracker.registros[1][2] == "ERRO SISTEMA"


def test_repescagem_roda_so_as_unidades_pedidas(tmp_path):
    cliente = ClienteFalso({"2210003": b"A;B\n", "2210004": b"C;D\n"})

    gerar_relatorio_http(
        SessaoFalsa(cliente), PEDIDO, unidades_alvo=["2210004"], pasta_base=tmp_path, tracker=TrackerFalso(), logger=Logger()
    )

    assert [p.name for p in (tmp_path / "030237 Estoque").iterdir()] == ["03,02,37_nomeUnidade030237estoque_2210004.csv"]


def test_so_vao_para_http_as_rotinas_com_receita_de_grupos_habilitados(monkeypatch):
    monkeypatch.setenv("PROMAX_HTTP_GRUPOS", "estoque, giro")

    assert rotinas_em_http("estoque", ["030237_ESTOQUE", "020502"], {"030237_ESTOQUE"}) == {"030237_ESTOQUE"}
    assert rotinas_em_http("inadimplencia", ["0513"], {"0513"}) == set()
