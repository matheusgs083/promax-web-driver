import pytest

from core.execution.execution_result import ExecutionStatus
from pages.processes.processo_030303_page import Processo030303Page


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("123456", "123456"),
        (123456, "123456"),
        ("123456.0", "123456"),
        ("123.456", "123456"),
    ],
)
def test_normalizar_mapa_valido(entrada, esperado):
    assert Processo030303Page.normalizar_mapa(entrada) == esperado


@pytest.mark.parametrize("entrada", ["", None, "0", "abc"])
def test_normalizar_mapa_invalido(entrada):
    with pytest.raises(ValueError):
        Processo030303Page.normalizar_mapa(entrada)


def test_carregar_mapa_sucesso():
    page = Processo030303Page.__new__(Processo030303Page)
    page.logger = type(
        "LoggerFake",
        (),
        {
            "info": lambda *args, **kwargs: None,
            "debug": lambda *args, **kwargs: None,
            "error": lambda *args, **kwargs: None,
        },
    )()

    page.entrar_frame_rotina_blindado = lambda *args, **kwargs: None
    page.preencher_campo_com_gatilho = lambda campo, val, trig: (True, "OK")
    page.lidar_com_alertas = lambda *args, **kwargs: []

    resultado = page.carregar_mapa("93703")

    assert resultado.status == ExecutionStatus.SUCCESS
    assert "93703" in resultado.message
    assert resultado.metadata["mapa"] == "93703"


def test_carregar_mapa_alerta_erro():
    page = Processo030303Page.__new__(Processo030303Page)
    page.logger = type(
        "LoggerFake",
        (),
        {
            "info": lambda *args, **kwargs: None,
            "debug": lambda *args, **kwargs: None,
            "error": lambda *args, **kwargs: None,
        },
    )()

    page.entrar_frame_rotina_blindado = lambda *args, **kwargs: None
    page.preencher_campo_com_gatilho = lambda campo, val, trig: (True, "OK")
    page.lidar_com_alertas = lambda *args, **kwargs: ["Mapa invalido ou nao encontrado"]

    resultado = page.carregar_mapa("93703")

    assert resultado.status == ExecutionStatus.BUSINESS_FAILURE
    assert "Mapa invalido ou nao encontrado" in resultado.message


def test_salvar_mapa_sucesso():
    page = Processo030303Page.__new__(Processo030303Page)
    page.logger = type(
        "LoggerFake",
        (),
        {
            "info": lambda *args, **kwargs: None,
            "debug": lambda *args, **kwargs: None,
            "error": lambda *args, **kwargs: None,
        },
    )()

    page.entrar_frame_rotina_blindado = lambda *args, **kwargs: None
    page.executar_gatilho_e_aguardar = lambda gatilho: (True, "Dados gravados com sucesso")
    page.lidar_com_alertas = lambda *args, **kwargs: []

    resultado = page.salvar_mapa()

    assert resultado.status == ExecutionStatus.SUCCESS
    assert "salvo com sucesso" in resultado.message


def test_salvar_mapa_falha():
    page = Processo030303Page.__new__(Processo030303Page)
    page.logger = type(
        "LoggerFake",
        (),
        {
            "info": lambda *args, **kwargs: None,
            "debug": lambda *args, **kwargs: None,
            "error": lambda *args, **kwargs: None,
        },
    )()

    page.entrar_frame_rotina_blindado = lambda *args, **kwargs: None
    page.executar_gatilho_e_aguardar = lambda gatilho: (False, "Timeout aguardando confirmacao")
    page.lidar_com_alertas = lambda *args, **kwargs: []

    resultado = page.salvar_mapa()

    assert resultado.status == ExecutionStatus.TECHNICAL_FAILURE
    assert "Falha ao salvar" in resultado.message


def test_enriquecer_motorista_usa_cs_motorista_quando_nao_generico():
    dados = {
        "campos": [
            {"name": "csMotorista", "value": "07777 - JOAO DA SILVA"},
            {"name": "ajudante1", "value": {"texto": "07442 - GABRIEL MORAIS BEZERRA", "valor": "07442"}},
        ],
        "motorista": {},
    }

    enriquecido = Processo030303Page._enriquecer_motorista(dados)

    assert enriquecido["motorista"]["nome"] == "JOAO DA SILVA"
    assert enriquecido["motorista"]["origem_nome"] == "csMotorista"


def test_enriquecer_motorista_generico_pau_brasil_usa_ajudante1():
    dados = {
        "campos": [
            {"name": "csMotorista", "value": "00001 - (*) PAU BRASIL"},
            {"name": "ajudante1", "value": {"texto": "07442 - GABRIEL MORAIS BEZERRA", "valor": "07442"}},
        ],
        "motorista": {"csMotorista": "00001 - (*) PAU BRASIL"},
    }

    enriquecido = Processo030303Page._enriquecer_motorista(dados)

    assert enriquecido["motorista"]["nome"] == "GABRIEL MORAIS BEZERRA"
    assert enriquecido["motorista"]["origem_nome"] == "ajudante1"
    assert enriquecido["motorista"]["valor_original"] == "07442 - GABRIEL MORAIS BEZERRA"
