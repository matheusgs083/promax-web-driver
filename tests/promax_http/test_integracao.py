import threading

from core.execution.execution_result import ExecutionStatus
from promax_http.cliente import ExportacaoPreparada, Rotina
from promax_http.erros import PromaxHttpErro, RelatorioSemConteudo
from promax_http.html import Formulario, Opcao
from promax_http.integracao import PedidoRelatorio, gerar_relatorio_http, rotinas_em_http


class TrackerFalso:
    def __init__(self):
        self.registros = []

    def anotar(self, rotina, unidade, status, detalhe, duracao=0):
        self.registros.append((rotina, unidade, status))

    def por_unidade(self):
        return {unidade: status for _, unidade, status in self.registros}


class ClienteFalso:
    """Janela unica: troca unidade e prepara; a conclusao (download) pode rodar em paralelo."""

    def __init__(self, resultados, *, falha_ao_visualizar=()):
        self.resultados = resultados
        self.falha_ao_visualizar = set(falha_ao_visualizar)
        self.unidade = None
        self.fechou = False
        self.ordem = []

    def abrir_rotina(self, codigo):
        opcoes = [Opcao(valor=c, texto=c) for c in self.resultados]
        return Rotina(codigo, "m", "PW", "sub", "u", "u9", Formulario("form1", "", "POST"), "", "", opcoes)

    def trocar_unidade(self, rotina, codigo):
        self.unidade = codigo
        return rotina

    def preparar_exportacao(self, rotina, campos, **opcoes):
        self.opcoes = opcoes
        self.ordem.append(("visualizar", self.unidade))
        resultado = self.resultados[self.unidade]
        if self.unidade in self.falha_ao_visualizar:
            raise resultado
        return ExportacaoPreparada(url=self.unidade, campos=dict(campos))

    def concluir_exportacao(self, exportacao, destino):
        resultado = self.resultados[exportacao.url]
        if callable(resultado):
            resultado = resultado()
        if isinstance(resultado, Exception):
            raise resultado
        self.ordem.append(("baixou", exportacao.url))
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


def gerar(cliente, tmp_path, tracker=None, unidades=None):
    return gerar_relatorio_http(
        SessaoFalsa(cliente), PEDIDO, unidades_alvo=unidades, pasta_base=tmp_path, tracker=tracker or TrackerFalso(), logger=Logger()
    )


def test_grava_com_o_mesmo_nome_da_versao_edge_e_anota_o_tracker(tmp_path):
    cliente = ClienteFalso(
        {"2210003": b"A;B\n", "2210004": RelatorioSemConteudo("Nao ha notas")}, falha_ao_visualizar={"2210004"}
    )
    tracker = TrackerFalso()

    resultado = gerar(cliente, tmp_path, tracker)

    assert (tmp_path / "030237 Estoque" / "03,02,37_nomeUnidade030237estoque_2210003.csv").read_bytes() == b"A;B\n"
    assert tracker.por_unidade() == {"2210003": "SUCESSO", "2210004": "SEM CONTEUDO"}
    assert resultado.status is ExecutionStatus.SUCCESS
    assert cliente.fechou


def test_janela_segue_para_a_proxima_unidade_enquanto_o_download_roda(tmp_path):
    liberar = threading.Event()

    def download_lento():
        assert liberar.wait(5), "a janela nao seguiu para a proxima unidade"
        return b"A;B\n"

    cliente = ClienteFalso({"2210003": download_lento, "2210004": b"C;D\n"})
    original = cliente.preparar_exportacao

    def preparar(rotina, campos, **opcoes):
        if cliente.unidade == "2210004":
            liberar.set()  # so libera o 1o download depois que a 2a unidade foi visualizada
        return original(rotina, campos, **opcoes)

    cliente.preparar_exportacao = preparar

    resultado = gerar(cliente, tmp_path)

    assert resultado.status is ExecutionStatus.SUCCESS
    assert cliente.ordem.index(("visualizar", "2210004")) < cliente.ordem.index(("baixou", "2210003"))


def test_sucesso_so_e_anotado_depois_do_download(tmp_path):
    cliente = ClienteFalso({"2210003": b"A;B\n", "2210004": PromaxHttpErro("HTTP 300")})
    tracker = TrackerFalso()

    resultado = gerar(cliente, tmp_path, tracker)

    assert tracker.por_unidade() == {"2210003": "SUCESSO", "2210004": "ERRO SISTEMA"}
    assert resultado.status is ExecutionStatus.PARTIAL_SUCCESS and resultado.should_retry


def test_postbacks_e_opcao_do_visualizar_do_pedido_chegam_ao_cliente(tmp_path):
    from dataclasses import replace

    cliente = ClienteFalso({"2210003": b"A;B\n"})
    pedido = replace(PEDIDO, passos_previos=("2", "5"), opcao_visualizar="1")

    gerar_relatorio_http(SessaoFalsa(cliente), pedido, unidades_alvo=None, pasta_base=tmp_path, tracker=TrackerFalso(), logger=Logger())

    assert cliente.opcoes == {"passos_previos": ("2", "5"), "opcao_visualizar": "1"}


def test_repescagem_roda_so_as_unidades_pedidas(tmp_path):
    cliente = ClienteFalso({"2210003": b"A;B\n", "2210004": b"C;D\n"})

    gerar(cliente, tmp_path, unidades=["2210004"])

    assert [p.name for p in (tmp_path / "030237 Estoque").iterdir()] == ["03,02,37_nomeUnidade030237estoque_2210004.csv"]


def test_so_vao_para_http_as_rotinas_com_receita_de_grupos_habilitados(monkeypatch):
    monkeypatch.setenv("PROMAX_HTTP_GRUPOS", "estoque, giro")

    assert rotinas_em_http("estoque", ["030237_ESTOQUE", "020502"], {"030237_ESTOQUE"}) == {"030237_ESTOQUE"}
    assert rotinas_em_http("inadimplencia", ["0513"], {"0513"}) == set()
