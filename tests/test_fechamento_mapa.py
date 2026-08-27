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

    class Fake030303Page:
        def __init__(self, _driver, _handle_menu):
            pass

        def carregar_mapa(self, _mapa):
            return ExecutionResult(
                ExecutionStatus.SUCCESS,
                "030303 carregada",
                metadata={"mapa": "93741", "dados_030303": {"motorista": {"nome": "MATHEUS"}}},
            )

        def salvar_mapa(self):
            return ExecutionResult(
                ExecutionStatus.SUCCESS,
                "030303 salva",
                metadata={"dados_030303": {"motorista": {"nome": "MATHEUS"}}},
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
    monkeypatch.setattr(fechamento_mapa, "Processo030303Page", Fake030303Page)
    monkeypatch.setattr(fechamento_mapa, "Processo030302Page", Fake030302Page)
    monkeypatch.setattr(fechamento_mapa, "Processo03030702Page", Fake03030702Page)

    result = fechamento_mapa.fechar_mapa_sessao_unica(
        "93741",
        unidade="PATOS",
        salvar=True,
    )

    assert result.status == ExecutionStatus.SUCCESS
    assert result.metadata["resultado_030303"]["dados_030303"]["motorista"]["nome"] == "MATHEUS"
    dados = result.metadata["dados_fechamento_03030702"]
    assert dados["rotina"] == "03030702"
    assert dados["etapa"] == "apos_salvar_financeiro"
    assert dados["saida"]["itens"][0]["descricao"] == "TRANSFERENCIA"
    assert result.metadata["resultado_financeiro"].metadata["dados_fechamento_03030702"] == dados


def test_fechamento_mapa_modo_financeiro_executa_030303_antes_da_03030702(monkeypatch):
    chamadas = []

    def fake_030303(**kwargs):
        chamadas.append(("030303", kwargs))
        return ExecutionResult(
            ExecutionStatus.SUCCESS,
            "030303 salva",
            metadata={"dados_030303": {"motorista": {"nome": "MATHEUS"}, "placa": "ABC1D23"}},
        )

    def fake_03030702(**kwargs):
        chamadas.append(("03030702", kwargs))
        return ExecutionResult(
            ExecutionStatus.SUCCESS,
            "03030702 salva",
            metadata={"dados_fechamento_03030702": {"mapa": "93741"}},
        )

    monkeypatch.setattr(fechamento_mapa, "main_030303", fake_030303)
    monkeypatch.setattr(fechamento_mapa, "main_03030702", fake_03030702)

    result = fechamento_mapa.main(
        mapa="93741",
        unidade="2210003",
        modo="financeiro",
        salvar=True,
    )

    assert [item[0] for item in chamadas] == ["030303", "03030702"]
    assert chamadas[0][1]["mapa"] == "93741"
    assert chamadas[1][1]["mapa"] == "93741"
    assert result.status == ExecutionStatus.SUCCESS
    assert result.metadata["resultado_030303"]["dados_030303"]["motorista"]["nome"] == "MATHEUS"
    assert result.metadata["integration_code"] == "MAPA_LIBERADO_FINANCEIRO"


def test_fechamento_mapa_reabre_030302_com_km_fallback(monkeypatch):
    rotinas_acessadas = []
    km_recebidos_030302 = []
    fechamentos_030302 = []

    class FakeSwitchTo:
        def window(self, _handle):
            return None

    class FakeDriver:
        switch_to = FakeSwitchTo()

    class FakeMenuPage:
        def acessar_rotina(self, rotina):
            rotinas_acessadas.append(rotina)
            return SimpleNamespace(driver=FakeDriver(), handle_menu=f"janela-{rotina}")

    class Fake030303Page:
        def __init__(self, _driver, _handle_menu):
            pass

        def carregar_mapa(self, _mapa):
            return ExecutionResult(
                ExecutionStatus.SUCCESS,
                "030303 carregada",
                metadata={"mapa": "93792", "dados_030303": {"motorista": {"nome": "MATHEUS"}}},
            )

        def salvar_mapa(self):
            return ExecutionResult(
                ExecutionStatus.SUCCESS,
                "030303 salva",
                metadata={"dados_030303": {"motorista": {"nome": "MATHEUS"}}},
            )

    class Fake030302Page:
        chamadas = 0

        def __init__(self, _driver, _handle_menu):
            pass

        def carregar_mapa(self, _mapa, ponto_apoio=None, km_atual=None, km_inicial=None, km_prev=None):
            Fake030302Page.chamadas += 1
            km_recebidos_030302.append(km_atual)
            if Fake030302Page.chamadas == 1:
                return ExecutionResult(
                    ExecutionStatus.ABORTED,
                    "Reabrir rotina com KM 94975.",
                    retry=True,
                    metadata={
                        "reabrir_030302_com_km_fallback": True,
                        "km_atual_fallback": "94975",
                        "km_inicial": "94855",
                        "km_prev": "120",
                    },
                )
            assert km_atual == "94975"
            return ExecutionResult(ExecutionStatus.SUCCESS, "030302 carregada")

        def fechar_e_voltar(self):
            fechamentos_030302.append(True)
            return FakeMenuPage()

        def tem_codigos_fisicos(self):
            return True

        def salvar_mapa(self):
            return ExecutionResult(ExecutionStatus.SUCCESS, "030302 salva")

    class Fake03030702Page:
        def __init__(self, _driver, _handle_menu):
            pass

        def carregar_mapa(self, _mapa, ponto_apoio=None):
            return ExecutionResult(ExecutionStatus.SUCCESS, "03030702 carregada")

        def salvar_mapa(self):
            return ExecutionResult(ExecutionStatus.SUCCESS, "03030702 salva")

        def extrair_pagina_json(self, timeout_segundos=8):
            return {"rotina": "03030702", "mapa": "93792"}

    monkeypatch.setattr(fechamento_mapa, "iniciar_sessao_padrao", lambda *_args: (FakeDriver(), FakeMenuPage()))
    monkeypatch.setattr(fechamento_mapa, "encerrar_driver", lambda _driver: None)
    monkeypatch.setattr(fechamento_mapa.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(fechamento_mapa, "Processo030303Page", Fake030303Page)
    monkeypatch.setattr(fechamento_mapa, "Processo030302Page", Fake030302Page)
    monkeypatch.setattr(fechamento_mapa, "Processo03030702Page", Fake03030702Page)

    result = fechamento_mapa.fechar_mapa_sessao_unica(
        "93792",
        unidade="PATOS",
        km_inicial="94855",
        km_prev="120",
        salvar=True,
        manter_aberto_ao_falhar=False,
    )

    assert result.status == ExecutionStatus.SUCCESS
    assert rotinas_acessadas == ["030303", "030302", "030302", "03030702"]
    assert km_recebidos_030302 == [None, "94975"]
    assert fechamentos_030302 == [True]
    assert result.metadata["resultado_fisico"].metadata["reabriu_030302_por_km"] is True
    assert result.metadata["resultado_fisico"].metadata["km_atual_reabertura"] == "94975"


def test_fechamento_mapa_executa_030330_quando_030302_pede_comodato(monkeypatch):
    rotinas_acessadas = []
    fechamentos_030302 = []
    fechamentos_030330 = []
    cancelamentos_030330 = []

    class FakeSwitchTo:
        def window(self, _handle):
            return None

    class FakeDriver:
        switch_to = FakeSwitchTo()

    class FakeMenuPage:
        def acessar_rotina(self, rotina):
            rotinas_acessadas.append(rotina)
            return SimpleNamespace(driver=FakeDriver(), handle_menu=f"janela-{rotina}")

    class Fake030303Page:
        def __init__(self, _driver, _handle_menu):
            pass

        def carregar_mapa(self, _mapa):
            return ExecutionResult(
                ExecutionStatus.SUCCESS,
                "030303 carregada",
                metadata={"mapa": "93854", "dados_030303": {"motorista": {"nome": "MATHEUS"}}},
            )

        def salvar_mapa(self):
            return ExecutionResult(
                ExecutionStatus.SUCCESS,
                "030303 salva",
                metadata={"dados_030303": {"motorista": {"nome": "MATHEUS"}}},
            )

    class Fake030302Page:
        chamadas = 0

        def __init__(self, _driver, _handle_menu):
            pass

        def carregar_mapa(self, _mapa, ponto_apoio=None):
            Fake030302Page.chamadas += 1
            if Fake030302Page.chamadas == 1:
                return ExecutionResult(
                    ExecutionStatus.BUSINESS_FAILURE,
                    "Mapa 93854 recusado pelo sistema: Comodato nao foi fechado atraves da rotina 03.03.30",
                    retry=False,
                    metadata={"alertas": ["Comodato nao foi fechado atraves da rotina 03.03.30"]},
                )
            return ExecutionResult(ExecutionStatus.SUCCESS, "030302 carregada")

        def fechar_e_voltar(self):
            fechamentos_030302.append(True)
            return FakeMenuPage()

        def tem_codigos_fisicos(self):
            return True

        def salvar_mapa(self):
            return ExecutionResult(ExecutionStatus.SUCCESS, "030302 salva")

    class Fake030330Page:
        def __init__(self, _driver, _handle_menu):
            pass

        def carregar_mapa(self, _mapa, dt_emissao=None, tp_mapa="COMODATO"):
            assert tp_mapa == "COMODATO"
            return ExecutionResult(
                ExecutionStatus.SUCCESS,
                "030330 carregada",
                metadata={"mapa": "93854", "dados_030330": {"nrLinhas": "1"}},
            )

        def salvar_mapa(self):
            return ExecutionResult(
                ExecutionStatus.SUCCESS,
                "030330 salva",
                metadata={"dados_030330": {"nrLinhas": "0"}},
            )

        def fechar_e_voltar(self):
            fechamentos_030330.append(True)
            return FakeMenuPage()

        def cancelar(self):
            cancelamentos_030330.append(True)

    class Fake03030702Page:
        def __init__(self, _driver, _handle_menu):
            pass

        def carregar_mapa(self, _mapa, ponto_apoio=None):
            return ExecutionResult(ExecutionStatus.SUCCESS, "03030702 carregada")

        def salvar_mapa(self):
            return ExecutionResult(ExecutionStatus.SUCCESS, "03030702 salva")

        def extrair_pagina_json(self, timeout_segundos=8):
            return {"rotina": "03030702", "mapa": "93854"}

    monkeypatch.setattr(fechamento_mapa, "iniciar_sessao_padrao", lambda *_args: (FakeDriver(), FakeMenuPage()))
    monkeypatch.setattr(fechamento_mapa, "encerrar_driver", lambda _driver: None)
    monkeypatch.setattr(fechamento_mapa.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(fechamento_mapa, "Processo030303Page", Fake030303Page)
    monkeypatch.setattr(fechamento_mapa, "Processo030302Page", Fake030302Page)
    monkeypatch.setattr(fechamento_mapa, "Processo030330Page", Fake030330Page)
    monkeypatch.setattr(fechamento_mapa, "Processo03030702Page", Fake03030702Page)

    result = fechamento_mapa.fechar_mapa_sessao_unica(
        "93854",
        unidade="PATOS",
        salvar=True,
        manter_aberto_ao_falhar=False,
    )

    assert result.status == ExecutionStatus.SUCCESS
    assert rotinas_acessadas == ["030303", "030302", "030330", "030302", "03030702"]
    assert fechamentos_030302 == [True]
    assert cancelamentos_030330 == [True]
    assert fechamentos_030330 == [True]
    assert result.metadata["resultado_030330"]["status"] == "SUCESSO"


def test_fechamento_mapa_preserva_dados_validos_da_carga_030303(monkeypatch):
    class FakeSwitchTo:
        def window(self, _handle):
            return None

    class FakeDriver:
        switch_to = FakeSwitchTo()

    class FakeMenuPage:
        def acessar_rotina(self, rotina):
            return SimpleNamespace(driver=FakeDriver(), handle_menu=f"janela-{rotina}")

    class Fake030303Page:
        def __init__(self, _driver, _handle_menu):
            pass

        @staticmethod
        def _dados_equipe_validos(dados):
            motorista = (((dados or {}).get("motorista") or {}).get("nome") or "").strip()
            return motorista not in {"", "--Selecionar--"}

        def carregar_mapa(self, _mapa):
            return ExecutionResult(
                ExecutionStatus.SUCCESS,
                "030303 carregada",
                metadata={
                    "mapa": "93792",
                    "dados_030303": {
                        "motorista": {"nome": "LEONARDO VIEIRA DA SILVA", "origem_nome": "Motorista"},
                        "campos": [{"label": "Ajudante 1", "value": {"texto": "07480 - CARLOS ALBERTO NASCIMENTO DE A"}}],
                    },
                },
            )

        def salvar_mapa(self):
            return ExecutionResult(
                ExecutionStatus.SUCCESS,
                "030303 salva",
                metadata={
                    "dados_030303": {
                        "motorista": {"nome": "--Selecionar--", "origem_nome": "ajudante1"},
                        "campos": [],
                    }
                },
            )

    monkeypatch.setattr(fechamento_mapa, "Processo030303Page", Fake030303Page)

    resultado, _janela = fechamento_mapa._executar_030303_sessao_unica(FakeMenuPage(), "93792", salvar=True)

    assert resultado.metadata["dados_030303"]["motorista"]["nome"] == "LEONARDO VIEIRA DA SILVA"


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

    class Fake030303Page:
        def __init__(self, _driver, _handle_menu):
            pass

        def carregar_mapa(self, _mapa):
            return ExecutionResult(
                ExecutionStatus.SUCCESS,
                "030303 carregada",
                metadata={"mapa": "93741", "dados_030303": {"motorista": {"nome": "MATHEUS"}}},
            )

        def salvar_mapa(self):
            return ExecutionResult(
                ExecutionStatus.SUCCESS,
                "030303 salva",
                metadata={"dados_030303": {"motorista": {"nome": "MATHEUS"}}},
            )

    class Fake03030702Page:
        def __init__(self, _driver, _handle_menu):
            raise AssertionError("03030702 nao deve abrir quando a 030302 falha")

    monkeypatch.setattr(fechamento_mapa, "iniciar_sessao_padrao", lambda *_args: (FakeDriver(), FakeMenuPage()))
    monkeypatch.setattr(fechamento_mapa, "encerrar_driver", lambda _driver: None)
    monkeypatch.setattr(fechamento_mapa.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(fechamento_mapa, "Processo030303Page", Fake030303Page)
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
    assert rotinas_acessadas == ["030303", "030302"]
