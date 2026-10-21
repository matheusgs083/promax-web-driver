import pytest

from core.execution.execution_result import ExecutionStatus
from pages.processes.processo_020105_page import Processo020105Page


def test_normalizar_lancamento_valido():
    armazem, deposito, data, itens = Processo020105Page.normalizar_lancamento(
        armazem="1", deposito="02", data_movimento="08/10/2026",
        itens=[{"codigo": "123", "caixa": "4", "unidade": 2}],
    )

    assert (armazem, deposito, data) == ("1", "02", "08/10/2026")
    assert itens[0].codigo == "123"
    assert itens[0].caixa == 4
    assert itens[0].unidade == 2


def test_normalizar_item_aceita_sku_da_tela():
    item = Processo020105Page.normalizar_item({"codigo": "22177", "sku": "222"})

    assert item.caixa == 222


@pytest.mark.parametrize(
    "dados",
    [
        {"armazem": "", "deposito": "02", "data_movimento": "08/10/2026", "itens": [{"codigo": "1", "caixa": 1}]},
        {"armazem": "1", "deposito": "02", "data_movimento": "2026-10-08", "itens": [{"codigo": "1", "caixa": 1}]},
        {"armazem": "1", "deposito": "02", "data_movimento": "08/10/2026", "itens": [{"codigo": "1", "caixa": 0}]},
    ],
)
def test_normalizar_lancamento_invalido(dados):
    with pytest.raises(ValueError):
        Processo020105Page.normalizar_lancamento(**dados)


def test_lancar_grade_para_no_primeiro_erro():
    page = Processo020105Page.__new__(Processo020105Page)
    page.carregar_grade = lambda **_kwargs: type("Resultado", (), {"ok": True})()
    page.adicionar_item = lambda _item: type("Resultado", (), {"ok": False, "message": "item invalido"})()

    resultado = page.lancar_grade(
        armazem="1", deposito="2", data_movimento="08/10/2026", itens=[{"codigo": "1", "caixa": 1}],
    )

    assert resultado.message == "item invalido"


def test_adicionar_item_retorna_falha_de_negocio():
    page = Processo020105Page.__new__(Processo020105Page)
    page.driver = type("DriverFake", (), {"execute_script": lambda *_args, **_kwargs: None})()
    page.entrar_frame_rotina_blindado = lambda *_args, **_kwargs: None
    page.preencher_campo_com_gatilho = lambda *_args, **_kwargs: (False, "Item nao encontrado")

    resultado = page.adicionar_item({"codigo": "999", "caixa": 1})

    assert resultado.status == ExecutionStatus.BUSINESS_FAILURE
    assert "999" in resultado.message
