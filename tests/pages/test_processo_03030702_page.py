from pages.processes.processo_03030702_page import Processo03030702Page
from core.execution.execution_result import ExecutionStatus


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


def test_salvar_mapa_trata_prestacao_de_contas_como_sucesso():
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


def test_equilibrar_contas_saida_ignora_simples_remessa():
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
    page._entrar_iframe_retorno_nativo = lambda: False

    page.equilibrar_contas_saida()

    assert lancamentos == []
