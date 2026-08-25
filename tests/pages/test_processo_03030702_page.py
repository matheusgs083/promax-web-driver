import pytest

from pages.processes.processo_03030702_page import Processo03030702Page
from core.execution.execution_result import ExecutionStatus


def _fake_page_03030702():
    page = Processo03030702Page.__new__(Processo03030702Page)
    page.logger = type(
        "LoggerFake",
        (),
        {
            "debug": lambda *args, **kwargs: None,
            "info": lambda *args, **kwargs: None,
            "warning": lambda *args, **kwargs: None,
            "error": lambda *args, **kwargs: None,
        },
    )()
    page._entrar_iframe_retorno_nativo = lambda: False
    return page


def test_extrair_pagina_json_retorna_dom_vivo_estruturado():
    page = Processo03030702Page.__new__(Processo03030702Page)
    page.logger = type(
        "LoggerFake",
        (),
        {"debug": lambda *args, **kwargs: None, "info": lambda *args, **kwargs: None},
    )()

    class DriverFake:
        current_url = "http://paubrasil.promaxcloud.com.br/pw/cgi-bin/PP00100.exe"
        title = "Promax"

    page.driver = DriverFake()
    page._garantir_frame_rotina = lambda *args, **kwargs: None
    page._extrair_dom_estruturado_03030702 = lambda incluir_html=False: {
        "ok": True,
        "totalFrames": 2,
        "frames": [
            {
                "caminho": "window",
                "campos": [
                    {"name": "numeroMapa", "value": "93615", "tag": "input"},
                    {"name": "pontoApoio", "value": "0", "tag": "input"},
                ],
                "tabelas": [],
            },
            {
                "caminho": "window.frames[1]",
                "campos": [
                    {"name": "textcod001", "value": "2", "tag": "input"},
                    {"name": "textvalor001", "value": "12.043,36", "tag": "input"},
                ],
                "tabelas": [
                    {
                        "id": "lista",
                        "rows": [
                            {"index": 0, "cells": ["Codigo", "Descricao", "Valor"]},
                            {"index": 1, "cells": ["2", "BLOQUETO BANCARIO", "12.043,36"]},
                        ],
                    }
                ],
            },
        ],
    }
    page.obter_itens_saida = lambda timeout_segundos=20: [
        {
            "descricao": "BLOQUETO BANCARIO",
            "qtNfs": "12",
            "valor": "12.043,36",
        }
    ]
    page.obter_contas_retorno = lambda: [
        {
            "seq": "001",
            "codigo": "2",
            "descricao": "BLOQUETO BANCARIO",
            "valor": "12.043,36",
            "linhaVazia": False,
        }
    ]
    page.obter_resumo_diferencas = lambda: {
        "produtos": "0,00",
        "vasilhames": "0,00",
        "contas": "0,00",
        "total": "0,00",
    }

    payload = page.extrair_pagina_json()

    assert payload["rotina"] == "03030702"
    assert payload["url"].startswith("http://paubrasil.promaxcloud.com.br")
    assert payload["mapa"] == "93615"
    assert payload["pontoApoio"] == "0"
    assert payload["camposChave"]["numeroMapa"]["value"] == "93615"
    assert payload["saida"]["totalItens"] == 1
    assert payload["saida"]["itens"][0]["valor"] == "12.043,36"
    assert payload["retorno"]["totalLinhas"] == 1
    assert payload["retorno"]["linhas"][0]["codigo"] == "2"
    assert payload["resumo"]["total"] == "0,00"
    assert payload["dom"]["totalFrames"] == 2


def test_extrair_pagina_json_usa_campo_mapa_quando_numero_mapa_nao_existe():
    page = _fake_page_03030702()

    class DriverFake:
        current_url = "http://paubrasil.promaxcloud.com.br/pw/cgi-bin/PP00100.exe"
        title = "Promax"

    page.driver = DriverFake()
    page._garantir_frame_rotina = lambda *args, **kwargs: None
    page._extrair_dom_estruturado_03030702 = lambda incluir_html=False: {
        "ok": True,
        "totalFrames": 1,
        "frames": [
            {
                "caminho": "window",
                "campos": [{"name": "mapa", "value": "93709", "tag": "input"}],
                "tabelas": [],
            }
        ],
    }
    page.obter_itens_saida = lambda timeout_segundos=20: []
    page.obter_contas_retorno = lambda: []
    page.obter_resumo_diferencas = lambda: {}

    payload = page.extrair_pagina_json()

    assert payload["mapa"] == "93709"


def test_salvar_mapa_trata_prestacao_de_contas_como_sucesso():
    page = _fake_page_03030702()

    class DriverFake:
        def execute_script(self, _script):
            return True

    page.driver = DriverFake()
    page._garantir_frame_rotina = lambda *args, **kwargs: None
    page._instalar_interceptador_alertas_salvar = lambda *args, **kwargs: None
    page.obter_resumo_diferencas = lambda: {
        "produtos": "0,00",
        "vasilhames": "0,00",
        "contas": "0,00",
        "total": "0,00",
    }
    page._lidar_com_alerta_ie = lambda: "Relatorio de Prestacao de Contas sera executado"

    result = page.salvar_mapa()

    assert result.status == ExecutionStatus.SUCCESS
    assert result.metadata["integration_code"] == "MAPA_LIBERADO_FINANCEIRO"


def test_salvar_mapa_trata_prestacao_de_contas_com_acento_como_sucesso():
    page = _fake_page_03030702()

    class DriverFake:
        def execute_script(self, _script):
            return True

    page.driver = DriverFake()
    page._garantir_frame_rotina = lambda *args, **kwargs: None
    page._instalar_interceptador_alertas_salvar = lambda *args, **kwargs: None
    page.obter_resumo_diferencas = lambda: {
        "produtos": "0,00",
        "vasilhames": "0,00",
        "contas": "0,00",
        "total": "0,00",
    }
    page._lidar_com_alerta_ie = lambda: "Relatório de Prestação de Contas será executado"

    result = page.salvar_mapa()

    assert result.status == ExecutionStatus.SUCCESS


def test_salvar_mapa_bloqueia_quando_diferenca_continua_apos_reequilibrio():
    page = _fake_page_03030702()
    chamadas_salvar = []
    resumos = iter(
        [
            {"produtos": "0,00", "vasilhames": "0,00", "contas": "10,00", "total": "10,00"},
            {"produtos": "0,00", "vasilhames": "0,00", "contas": "5,00", "total": "5,00"},
        ]
    )

    class DriverFake:
        def execute_script(self, _script):
            chamadas_salvar.append(True)
            return True

    page.driver = DriverFake()
    page._garantir_frame_rotina = lambda *args, **kwargs: None
    page._instalar_interceptador_alertas_salvar = lambda *args, **kwargs: None
    page.obter_resumo_diferencas = lambda: next(resumos)
    page.equilibrar_contas_saida = lambda: None
    page._lidar_com_alerta_ie = lambda: "Relatorio de Prestacao de Contas sera executado"

    result = page.salvar_mapa()

    assert result.status == ExecutionStatus.BUSINESS_FAILURE
    assert result.metadata["integration_code"] == "DIFERENCA_PRESTACAO_CONTAS"
    assert chamadas_salvar == []


@pytest.mark.parametrize(
    ("valor", "tem_valor"),
    [
        ("", False),
        ("-", False),
        ("0", False),
        ("0,00", False),
        ("0.00", False),
        ("R$ 0,00", False),
        ("10,00", True),
        ("10.00", True),
        ("1.234,56-", True),
    ],
)
def test_diferenca_tem_valor_normaliza_formatos_do_promax(valor, tem_valor):
    assert Processo03030702Page._diferenca_tem_valor(valor) is tem_valor


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("CRÉDITO EM CONTA", "CREDITO EM CONTA"),
        ("BONIFICAÇÃO / VERBA", "BONIFICACAO / VERBA"),
        ("À VISTA", "A VISTA"),
        ("CRÃ‰DITO EM CONTA", "CREDITO EM CONTA"),
    ],
)
def test_normalizar_descricao_conta_remove_acentos_e_repara_mojibake(valor, esperado):
    assert Processo03030702Page._normalizar_descricao_conta(valor) == esperado


def test_salvar_mapa_nao_reequilibra_quando_diferenca_zero_em_formato_alternativo():
    page = _fake_page_03030702()
    chamadas_equilibrio = []

    class DriverFake:
        def execute_script(self, _script):
            return True

    page.driver = DriverFake()
    page._garantir_frame_rotina = lambda *args, **kwargs: None
    page._instalar_interceptador_alertas_salvar = lambda *args, **kwargs: None
    page.obter_resumo_diferencas = lambda: {
        "produtos": "0",
        "vasilhames": "0.00",
        "contas": "R$ 0,00",
        "total": "-",
    }
    page.equilibrar_contas_saida = lambda: chamadas_equilibrio.append(True)
    page._lidar_com_alerta_ie = lambda: "Relatorio de Prestacao de Contas sera executado"

    result = page.salvar_mapa()

    assert result.status == ExecutionStatus.SUCCESS
    assert chamadas_equilibrio == []


def test_equilibrar_contas_saida_ignora_simples_remessa():
    page = _fake_page_03030702()

    lancamentos = []
    page.obter_itens_saida = lambda timeout_segundos=20: [
        {
            "descricao": "SIMPLES REMESSA",
            "qtNfs": "1",
            "valor": "100,00",
        }
    ]
    page.obter_contas_retorno = lambda: []
    page.lancar_conta_retorno = lambda codigo_conta, valor, num_vale=0: lancamentos.append(
        (codigo_conta, valor)
    ) or True

    page.equilibrar_contas_saida()

    assert lancamentos == []


def test_equilibrar_contas_saida_nao_duplica_conta_existente_no_retorno():
    page = _fake_page_03030702()
    lancamentos = []
    page.obter_itens_saida = lambda timeout_segundos=20: [
        {
            "descricao": "BLOQUETO BANCARIO",
            "qtNfs": "7",
            "valor": "7.656,63",
        }
    ]
    page.obter_contas_retorno = lambda: [
        {
            "seq": "001",
            "codigo": "2",
            "descricao": "BLOQUETO",
            "valor": "7.656,63",
            "linhaVazia": False,
        }
    ]
    page.lancar_conta_retorno = lambda codigo_conta, valor, num_vale=0: lancamentos.append(
        (codigo_conta, valor)
    ) or True

    page.equilibrar_contas_saida()

    assert lancamentos == []


def test_equilibrar_contas_saida_bloqueia_conta_existente_com_valor_diferente():
    page = _fake_page_03030702()
    page.obter_itens_saida = lambda timeout_segundos=20: [
        {
            "descricao": "BLOQUETO BANCARIO",
            "qtNfs": "7",
            "valor": "7.656,63",
        }
    ]
    page.obter_contas_retorno = lambda: [
        {
            "seq": "001",
            "codigo": "2",
            "descricao": "BLOQUETO",
            "valor": "1.000,00",
            "linhaVazia": False,
        }
    ]
    page.lancar_conta_retorno = lambda codigo_conta, valor, num_vale=0: True

    with pytest.raises(RuntimeError, match="valor diferente"):
        page.equilibrar_contas_saida()


def test_equilibrar_contas_saida_lanca_conta_ausente_e_valida_postback():
    page = _fake_page_03030702()
    lancamentos = []
    retornos = [
        [],
        [
            {
                "seq": "001",
                "codigo": "27",
                "descricao": "DINHEIRO",
                "valor": "161,70",
                "linhaVazia": False,
            }
        ],
        [
            {
                "seq": "001",
                "codigo": "27",
                "descricao": "DINHEIRO",
                "valor": "161,70",
                "linhaVazia": False,
            }
        ],
    ]
    page.obter_itens_saida = lambda timeout_segundos=20: [
        {
            "descricao": "A VISTA",
            "qtNfs": "1",
            "valor": "161,70",
        }
    ]
    page.obter_contas_retorno = lambda: retornos.pop(0)
    page.lancar_conta_retorno = lambda codigo_conta, valor, num_vale=0: lancamentos.append(
        (codigo_conta, valor)
    ) or True

    page.equilibrar_contas_saida()

    assert lancamentos == [("27", "161,70")]


def test_equilibrar_contas_saida_mapeia_categorias_com_acentos_reais():
    page = _fake_page_03030702()
    lancamentos = []
    retornos = [
        [],
        [
            {
                "seq": "001",
                "codigo": "18",
                "descricao": "CREDITO EM CONTA",
                "valor": "17.127,80",
                "linhaVazia": False,
            }
        ],
        [
            {
                "seq": "001",
                "codigo": "18",
                "descricao": "CREDITO EM CONTA",
                "valor": "17.127,80",
                "linhaVazia": False,
            }
        ],
    ]
    page.obter_itens_saida = lambda timeout_segundos=20: [
        {
            "descricao": "CRÉDITO EM CONTA",
            "qtNfs": "17",
            "valor": "17.127,80",
        }
    ]
    page.obter_contas_retorno = lambda: retornos.pop(0)
    page.lancar_conta_retorno = lambda codigo_conta, valor, num_vale=0: lancamentos.append(
        (codigo_conta, valor)
    ) or True

    page.equilibrar_contas_saida()

    assert lancamentos == [("18", "17.127,80")]


def test_equilibrar_contas_saida_ignora_valor_zero_na_validacao_final():
    page = _fake_page_03030702()
    page.obter_itens_saida = lambda timeout_segundos=20: [
        {
            "descricao": "BLOQUETO BANCARIO",
            "qtNfs": "0",
            "valor": "0,00",
        }
    ]
    page.obter_contas_retorno = lambda: []
    page.lancar_conta_retorno = lambda codigo_conta, valor, num_vale=0: True

    page.equilibrar_contas_saida()


def test_equilibrar_contas_saida_adiciona_linha_vazia_apos_equilibrio():
    page = _fake_page_03030702()
    chamadas_linha_vazia = []
    page.obter_itens_saida = lambda timeout_segundos=20: [
        {
            "descricao": "BLOQUETO BANCARIO",
            "qtNfs": "7",
            "valor": "7.656,63",
        }
    ]
    page.obter_contas_retorno = lambda: [
        {
            "seq": "001",
            "codigo": "2",
            "descricao": "BLOQUETO",
            "valor": "7.656,63",
            "linhaVazia": False,
        }
    ]
    page._adicionar_linha_vazia_retorno = lambda: chamadas_linha_vazia.append(True) or True

    page.equilibrar_contas_saida()

    assert chamadas_linha_vazia == [True]


def test_equilibrar_contas_saida_bloqueia_vasilhame_ausente_do_retorno():
    page = _fake_page_03030702()
    page.obter_itens_saida = lambda timeout_segundos=20: [
        {
            "descricao": "Vasilhame",
            "qtNfs": "0",
            "valor": "22.680,00",
        }
    ]
    page.obter_contas_retorno = lambda: []
    page.lancar_conta_retorno = lambda codigo_conta, valor, num_vale=0: True

    with pytest.raises(RuntimeError, match="Vasilhame"):
        page.equilibrar_contas_saida()


def test_equilibrar_contas_saida_bloqueia_categoria_sem_mapeamento():
    page = _fake_page_03030702()
    page.obter_itens_saida = lambda timeout_segundos=20: [
        {
            "descricao": "CONTA NOVA SEM CODIGO",
            "qtNfs": "1",
            "valor": "10,00",
        }
    ]
    page.obter_contas_retorno = lambda: []
    page.lancar_conta_retorno = lambda codigo_conta, valor, num_vale=0: True

    with pytest.raises(RuntimeError, match="sem codigo mapeado"):
        page.equilibrar_contas_saida()
