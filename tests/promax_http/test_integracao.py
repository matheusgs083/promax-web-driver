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


class ClientePdfFalso(ClienteFalso):
    def gerar_pdf_frame9(self, rotina, campos, *, opcao, destino):
        self.opcao_pdf = opcao
        resultado = self.resultados[self.unidade]
        if isinstance(resultado, Exception):
            raise resultado
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(resultado)
        return destino


def test_pdf_http_gera_um_pdf_por_unidade_com_o_nome_do_loop_unidades(tmp_path):
    from core.execution.execution_result import ExecutionStatus
    from promax_http.erros import PromaxHttpErro
    from promax_http.integracao import PedidoRelatorioPdf, gerar_pdf_http

    cliente = ClientePdfFalso({"2210003": b"%PDF-1", "2210004": PromaxHttpErro("caiu")})
    tracker = TrackerFalso()
    pedido = PedidoRelatorioPdf("030206", "Rotina 030206 Bot", "030206 bot", "03,02,06.pdf", {"banco": "237"}, "4")

    resultado = gerar_pdf_http(
        SessaoFalsa(cliente), pedido, unidades_alvo=None, pasta_base=tmp_path, tracker=tracker, logger=Logger()
    )

    assert (tmp_path / "030206 bot" / "03,02,06_2210003.pdf").read_bytes() == b"%PDF-1"
    assert cliente.opcao_pdf == "4" and cliente.fechou
    assert tracker.por_unidade() == {"2210003": "SUCESSO", "2210004": "ERRO SISTEMA"}
    assert resultado.status == ExecutionStatus.PARTIAL_SUCCESS


def test_nome_por_unidade_grava_o_nome_exato_da_liga(tmp_path):
    from promax_http.integracao import PedidoRelatorio, gerar_relatorio_http

    cliente = ClienteFalso({"2210003": b"A;B\n", "2210004": b"C;D\n"})
    nomes = {"2210003": "PATOS", "2210004": "SUME"}
    pedido = PedidoRelatorio(
        "030224", "Rotina 030224 Resumo Liga Entrega", "03.02.24/Resumo", "ignorado", {"a": "1"},
        nome_por_unidade=lambda codigo: f"03.02.24_{nomes[codigo]}_OUT.csv",
    )

    gerar_relatorio_http(
        SessaoFalsa(cliente), pedido, unidades_alvo=None, pasta_base=tmp_path, tracker=TrackerFalso(), logger=Logger()
    )

    pasta = tmp_path / "03.02.24" / "Resumo"
    assert sorted(p.name for p in pasta.iterdir()) == ["03.02.24_PATOS_OUT.csv", "03.02.24_SUME_OUT.csv"]
    assert (pasta / "03.02.24_SUME_OUT.csv").read_bytes() == b"C;D\n"


class ClienteDvsFalso(ClienteFalso):
    def visualizar(self, rotina, campos):
        self.ordem.append(("visualizar", self.unidade, campos["unidade"]))
        resultado = self.resultados[self.unidade]
        if isinstance(resultado, Exception):
            raise resultado


class SessaoDvsFalsa(SessaoFalsa):
    settings = type("S", (), {"promax_url": "http://paubrasil.promaxcloud.com.br/pw/cgi-bin/PP00100.exe"})()


def _pedido_dvs(achados):
    from promax_http.integracao import PedidoArquivoDvs

    return PedidoArquivoDvs(
        rotina="030805",
        tracker_name="Rotina 030805 Liga Entrega",
        subpasta="03.08.05",
        campos_da_unidade=lambda u: {"unidade": u},
        nome_final_da_unidade=lambda u: {"2210003": "PATOS_17_11.csv", "2210004": "SUME_17_11.csv"}[u],
        localizar=lambda busca, u, instante: achados.get(u),
        unidade_permitida=lambda u: u != "3610006",
    )


def test_dvs_salva_o_arquivo_de_cada_unidade_com_o_nome_da_liga(tmp_path):
    from core.execution.execution_result import ExecutionStatus
    from promax_http.erros import RelatorioSemConteudo
    from promax_http.integracao import gerar_arquivo_dvs_http

    cliente = ClienteDvsFalso({"2210003": None, "2210004": RelatorioSemConteudo("Nao ha movimento"), "3610006": None})
    tracker = TrackerFalso()
    achados = {"2210003": ("rede:x", b"Data;Transp\n")}

    resultado = gerar_arquivo_dvs_http(
        SessaoDvsFalsa(cliente), _pedido_dvs(achados), unidades_alvo=None,
        pasta_base=tmp_path, tracker=tracker, logger=Logger(), espera=0,
    )

    assert (tmp_path / "03.08.05" / "PATOS_17_11.csv").read_bytes() == b"Data;Transp\n"
    assert tracker.por_unidade() == {"2210003": "SUCESSO", "2210004": "SEM CONTEUDO"}
    assert ("visualizar", "3610006", "3610006") not in cliente.ordem  # unidade bloqueada
    assert resultado.status == ExecutionStatus.SUCCESS


def test_dvs_sem_arquivo_vira_falha_tecnica(tmp_path):
    from core.execution.execution_result import ExecutionStatus
    from promax_http.integracao import gerar_arquivo_dvs_http

    cliente = ClienteDvsFalso({"2210003": None})
    tracker = TrackerFalso()

    resultado = gerar_arquivo_dvs_http(
        SessaoDvsFalsa(cliente), _pedido_dvs({}), unidades_alvo=None,
        pasta_base=tmp_path, tracker=tracker, logger=Logger(), espera=0,
    )

    assert tracker.por_unidade() == {"2210003": "ERRO SISTEMA"}
    assert resultado.status == ExecutionStatus.TECHNICAL_FAILURE
