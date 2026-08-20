from types import SimpleNamespace

from core.execution.execution_result import ExecutionResult, ExecutionStatus
from entrypoints.processes import fechamento_mapa


def test_fechamento_mapa_inclui_dados_estruturados_da_03030702(monkeypatch):
    class FakeSwitchTo:
        def window(self, _handle):
            return None

    class FakeDriver:
        switch_to = FakeSwitchTo()

    class FakeMenuPage:
        def acessar_rotina(self, rotina):
            return SimpleNamespace(driver=FakeDriver(), handle_menu=f"janela-{rotina}")

    class Fake030302Page:
        def __init__(self, _driver, _handle_menu):
            pass

        def carregar_mapa(self, _mapa, ponto_apoio=None):
            return ExecutionResult(ExecutionStatus.SUCCESS, "030302 carregada")

        def tem_codigos_fisicos(self):
            return True

        def salvar_mapa(self):
            return ExecutionResult(
                ExecutionStatus.SUCCESS,
                "030302 salva",
                metadata={"fluxo": "final-nao-existem-diferencas"},
            )

    class Fake03030702Page:
        def __init__(self, _driver, _handle_menu):
            pass

        def carregar_mapa(self, _mapa, ponto_apoio=None):
            return ExecutionResult(ExecutionStatus.SUCCESS, "03030702 carregada")

        def salvar_mapa(self):
            return ExecutionResult(
                ExecutionStatus.SUCCESS,
                "03030702 salva",
                metadata={"alerta": "Relatorio de Prestacao de Contas sera executado"},
            )

        def extrair_pagina_json(self, timeout_segundos=8):
            return {
                "rotina": "03030702",
                "mapa": "93741",
                "saida": {
                    "itens": [{"descricao": "TRANSFERENCIA", "valor": "75.683,91"}],
                    "totalItens": 1,
                },
                "retorno": {
                    "linhas": [{"codigo": "59", "valor": "75.683,91"}],
                    "totalLinhas": 1,
                },
                "resumo": {"total": "0,00"},
            }

    monkeypatch.setattr(fechamento_mapa, "iniciar_sessao_padrao", lambda *_args: (FakeDriver(), FakeMenuPage()))
    monkeypatch.setattr(fechamento_mapa, "encerrar_driver", lambda _driver: None)
    monkeypatch.setattr(fechamento_mapa.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(fechamento_mapa, "Processo030302Page", Fake030302Page)
    monkeypatch.setattr(fechamento_mapa, "Processo03030702Page", Fake03030702Page)

    result = fechamento_mapa.fechar_mapa_sessao_unica(
        "93741",
        unidade="PATOS",
        salvar=True,
    )

    assert result.status == ExecutionStatus.SUCCESS
    dados = result.metadata["dados_fechamento_03030702"]
    assert dados["rotina"] == "03030702"
    assert dados["etapa"] == "apos_salvar_financeiro"
    assert dados["saida"]["itens"][0]["descricao"] == "TRANSFERENCIA"
    assert result.metadata["resultado_financeiro"].metadata["dados_fechamento_03030702"] == dados


def test_fechamento_mapa_para_quando_030302_falha(monkeypatch):
    rotinas_acessadas = []

    class FakeSwitchTo:
        def window(self, _handle):
            return None

    class FakeDriver:
        switch_to = FakeSwitchTo()

    class FakeMenuPage:
        def acessar_rotina(self, rotina):
            rotinas_acessadas.append(rotina)
            return SimpleNamespace(driver=FakeDriver(), handle_menu=f"janela-{rotina}")

    class Fake030302Page:
        def __init__(self, _driver, _handle_menu):
            pass

        def carregar_mapa(self, _mapa, ponto_apoio=None):
            return ExecutionResult(ExecutionStatus.SUCCESS, "030302 carregada")

        def tem_codigos_fisicos(self):
            return True

        def salvar_mapa(self):
            return ExecutionResult(
                ExecutionStatus.TECHNICAL_FAILURE,
                "campo-mapa-nao-encontrado",
                retry=False,
            )

    class Fake03030702Page:
        def __init__(self, _driver, _handle_menu):
            raise AssertionError("03030702 nao deve abrir quando a 030302 falha")

    monkeypatch.setattr(fechamento_mapa, "iniciar_sessao_padrao", lambda *_args: (FakeDriver(), FakeMenuPage()))
    monkeypatch.setattr(fechamento_mapa, "encerrar_driver", lambda _driver: None)
    monkeypatch.setattr(fechamento_mapa.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(fechamento_mapa, "Processo030302Page", Fake030302Page)
    monkeypatch.setattr(fechamento_mapa, "Processo03030702Page", Fake03030702Page)

    result = fechamento_mapa.fechar_mapa_sessao_unica(
        "93741",
        unidade="PATOS",
        salvar=True,
        manter_aberto_ao_falhar=False,
    )

    assert result.status == ExecutionStatus.TECHNICAL_FAILURE
    assert result.message == "Falha no Fechamento Fisico (030302): campo-mapa-nao-encontrado"
    assert result.metadata["passo_falha"] == "030302"
    assert result.metadata["resultado_financeiro"] is None
    assert result.metadata["dados_fechamento_03030702"] is None
    assert rotinas_acessadas == ["030302"]
