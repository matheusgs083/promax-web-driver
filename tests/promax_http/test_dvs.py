import pytest

from promax_http.receitas import campos_030805, campos_1706, nome_dvs_030805
from promax_http.dvs import BuscaDvs
from promax_http.transporte import Resposta


class Logger:
    def info(self, *a):
        pass


class HttpFalso:
    def __init__(self, arquivos):
        self.arquivos = arquivos
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        if url in self.arquivos:
            return Resposta(url, 200, "text/plain", self.arquivos[url])
        if url.endswith("arquivos/browse/dvs/"):
            return Resposta(url, 200, "text/html", b'<a href="2artd17_0003.txt">x</a><a href="id_000074753000031111111111.inf">y</a>')
        return Resposta(url, 404, "text/html", b"<html>404</html>")


URL = "http://paubrasil.promaxcloud.com.br/pw/cgi-bin/PP00100.exe"


def test_nome_dvs_da_030805_usa_dia_e_filial():
    assert nome_dvs_030805(data="17/11/2026", unidade="2210004") == "2artd17_0004.txt"


def test_030805_manda_a_mesma_data_e_atualiza_arquivos():
    campos = campos_030805(data="17/11/2026")

    assert (campos["dataInicial"], campos["dataFinal"], campos["transp"], campos["atualizarArquivos"]) == (
        "17/11/2026", "17/11/2026", "1", "S",
    )


def test_1706_exige_mesmo_mes_como_a_tela():
    with pytest.raises(ValueError, match="mes/ano"):
        campos_1706(unidade="2210003", data_inicial="25/10/2026", data_final="02/11/2026")


def test_1706_nao_envia_grupo_desabilitado():
    campos = campos_1706(unidade="2210004", data_inicial="01/11/2026", data_final="17/11/2026")

    assert campos["opcaoGrupo"] is None and campos["idDesempenho"] == "S" and campos["opcaoUnidades"] == "2210004"


def test_busca_por_nome_tenta_os_caminhos_http_do_edge():
    alvo = "http://paubrasil.promaxcloud.com.br/arquivos/dvs/2artd17_0003.txt"
    http = HttpFalso({alvo: b"0001;CONFERENCIA\n"})

    origem, conteudo = BuscaDvs(http, URL, Logger()).por_nome("2artd17_0003.txt")

    assert origem == f"http:{alvo}" and conteudo.startswith(b"0001")
    assert http.urls[0].endswith("arquivos/browse/dvs/2artd17_0003.txt")


def test_busca_por_prefixo_usa_a_listagem_http_quando_nao_ha_rede():
    alvo = "http://paubrasil.promaxcloud.com.br/arquivos/browse/dvs/id_000074753000031111111111.inf"
    http = HttpFalso({alvo: b"INDICADORES"})

    origem, _ = BuscaDvs(http, URL, Logger()).por_prefixo("0000747530", desde=0)

    assert origem == f"http:{alvo}"
