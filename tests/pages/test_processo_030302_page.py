import pytest
from selenium.common.exceptions import UnexpectedAlertPresentException

from core.execution.execution_result import ExecutionResult, ExecutionStatus
from pages.processes.processo_030302_page import Processo030302Page


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
    assert Processo030302Page.normalizar_mapa(entrada) == esperado


@pytest.mark.parametrize("entrada", ["", None, "0", "abc"])
def test_normalizar_mapa_invalido(entrada):
    with pytest.raises(ValueError):
        Processo030302Page.normalizar_mapa(entrada)


def test_carregar_mapa_reentra_frame_quando_campo_mapa_some_do_contexto():
    page = Processo030302Page.__new__(Processo030302Page)
    page.logger = type(
        "LoggerFake",
        (),
        {
            "info": lambda *args, **kwargs: None,
            "debug": lambda *args, **kwargs: None,
            "warning": lambda *args, **kwargs: None,
            "exception": lambda *args, **kwargs: None,
        },
    )()
    chamadas = {"execute": 0, "reentrar": 0}

    class DriverFake:
        def execute_script(self, _script, _mapa):
            chamadas["execute"] += 1
            if chamadas["execute"] == 1:
                return {"ok": False, "error": "campo-mapa-nao-encontrado"}
            return {
                "ok": True,
                "trigger": "CarregaMapa",
                "mapaDigitado": "93741",
                "submitCount": 1,
                "pontoApoioDisabled": True,
                "pontoApoioValue": "0",
            }

    page.driver = DriverFake()
    page.entrar_frame_rotina_blindado = lambda *args, **kwargs: None
    page._esperar_campo_js = lambda *args, **kwargs: True

    def reentrar(*args, **kwargs):
        chamadas["reentrar"] += 1

    page._reentrar_frame = reentrar
    page._aguardar_e_clicar_sim_recuperar_mapa = lambda *args, **kwargs: None
    page._aguardar_estado_pos_mapa_js = lambda *args, **kwargs: {
        "submitCount": 1,
        "pontoApoioDisabled": True,
    }
    page._aguardar_carga_mapa = lambda *args, **kwargs: (True, [])
    page._aceitar_alerta = lambda *args, **kwargs: None
    page._aguardar_telinhas_pos_carga = lambda *args, **kwargs: {}
    page._estado_mapa_js = lambda *args, **kwargs: {"mapa": "93741", "produtos": []}
    page.switch_to_default_content = lambda *args, **kwargs: None

    resultado = page.carregar_mapa("93741")

    assert resultado.status == ExecutionStatus.SUCCESS
    assert chamadas["execute"] == 2
    assert chamadas["reentrar"] == 2
    assert resultado.metadata["trigger"] == "CarregaMapa"


def test_salvar_mapa_bloqueia_salvar_quando_redigitacao_nao_aplica():
    page = Processo030302Page.__new__(Processo030302Page)
    page.logger = type(
        "LoggerFake",
        (),
        {"info": lambda *args, **kwargs: None, "debug": lambda *args, **kwargs: None},
    )()

    chamadas = {"wait": 0, "salvar": 0}
    estado = {
        "statusMapa": "6",
        "produtos": [
            {
                "linha": "001",
                "codigo": "27983",
                "vazUn": "96",
                "vazUnDisabled": False,
            }
        ]
    }

    page.entrar_frame_rotina_blindado = lambda *args, **kwargs: None
    page._instalar_monitor_envio_js = lambda *args, **kwargs: None
    page._capturar_alertas = lambda *args, **kwargs: []
    page._estado_mapa_js = lambda *args, **kwargs: estado
    page._reativar_digitacao_valores_030302 = lambda *args, **kwargs: {
        "aplicados": [],
        "total": 0,
        "erro": "erro-js",
    }
    page.switch_to_default_content = lambda *args, **kwargs: None

    def wait_nao_deve_ser_chamado(*args, **kwargs):
        chamadas["wait"] += 1
        raise AssertionError("nao deve aguardar salvar quando redigitacao falha")

    def salvar_nao_deve_ser_chamado(*args, **kwargs):
        chamadas["salvar"] += 1
        raise AssertionError("nao deve clicar em salvar quando redigitacao falha")

    page.wait_for_js_condition = wait_nao_deve_ser_chamado
    page._clicar_salvar_js = salvar_nao_deve_ser_chamado

    resultado = page.salvar_mapa()

    assert resultado.status == ExecutionStatus.TECHNICAL_FAILURE
    assert "salvar bloqueado" in resultado.message
    assert resultado.metadata["digitacao"]["erro"] == "erro-js"
    assert chamadas == {"wait": 0, "salvar": 0}


def test_salvar_sem_codigos_exige_confirmacao_nao_existem_diferencas():
    page = Processo030302Page.__new__(Processo030302Page)
    page.logger = type(
        "LoggerFake",
        (),
        {"info": lambda *args, **kwargs: None, "debug": lambda *args, **kwargs: None},
    )()
    page.entrar_frame_rotina_blindado = lambda *args, **kwargs: None
    page._instalar_monitor_envio_js = lambda *args, **kwargs: None
    page._estado_mapa_js = lambda *args, **kwargs: {"mapa": "94041", "produtos": []}
    page._clicar_salvar_js = lambda *args, **kwargs: {"ok": True}
    page._aguardar_fechamento_final_isolado_030302 = lambda *args, **kwargs: {
        "confirmacoes": [
            {"classificacao_final": "liberacao_financeira", "resposta": "sim", "mensagem": "Liberar mapa?"}
        ]
    }
    page.switch_to_default_content = lambda *args, **kwargs: None

    resultado = page.salvar_mapa()

    assert resultado.status == ExecutionStatus.TECHNICAL_FAILURE
    assert resultado.metadata["integration_code"] == "CONFIRMACAO_030302_SEM_DIFERENCAS_AUSENTE"


def test_salvar_mapa_preenchido_usa_evento_js_no_botao_salvar():
    page = Processo030302Page.__new__(Processo030302Page)
    page.logger = type(
        "LoggerFake",
        (),
        {"info": lambda *args, **kwargs: None, "debug": lambda *args, **kwargs: None},
    )()

    estado = {
        "statusMapa": "6",
        "produtos": [
            {
                "linha": "001",
                "codigo": "27983",
                "vazUn": "96",
                "vazUnDisabled": False,
            }
        ]
    }
    chamadas = {}

    page.entrar_frame_rotina_blindado = lambda *args, **kwargs: None
    def instalar_monitor(*args, **kwargs):
        chamadas["interceptar_msgbx"] = kwargs.get("interceptar_msgbx")

    page._instalar_monitor_envio_js = instalar_monitor

    def capturar_alertas_nao_deve_ser_chamado(*args, **kwargs):
        raise AssertionError("salvar_mapa nao deve usar capturador generico de alertas")

    page._capturar_alertas = capturar_alertas_nao_deve_ser_chamado
    page._estado_mapa_js = lambda *args, **kwargs: estado
    page._reativar_digitacao_valores_030302 = lambda *args, **kwargs: {
        "aplicados": [{"nome": "textvazUn001", "valor": "96"}],
        "total": 1,
    }
    page.wait_for_js_condition = lambda *args, **kwargs: True
    page._seguir_fluxo_salvar_030302 = lambda *args, **kwargs: {
        "confirmacoes": [{"mensagem": "Nao existem diferencas"}],
        "etapas": {"diferencas": True, "financeiro": True, "resultado": True},
        "resultado": {
            "mensagemOk": True,
            "mensagemSemDiferencas": True,
            "listaDiferencasLength": 0,
        },
    }
    page._aguardar_envio_salvar_030302 = lambda *args, **kwargs: {
        "dados": {"submitCount": 1},
        "estado": {},
    }
    page._obter_confirmacoes_salvar_js = lambda *args, **kwargs: {"submitCount": 1}
    page._confirmacoes_tem_sem_diferencas = lambda confirmacoes: True
    page._extrair_alertas_capturados = lambda confirmacoes: []
    page.switch_to_default_content = lambda *args, **kwargs: None

    def clicar_salvar(trigger_suffix="", prefer_click=False, clique_simples=False):
        chamadas["trigger_suffix"] = trigger_suffix
        chamadas["prefer_click"] = prefer_click
        chamadas["clique_simples"] = clique_simples
        return {"ok": True, "trigger": "BotSalvar.click" + trigger_suffix}

    page._clicar_salvar_js = clicar_salvar

    resultado = page.salvar_mapa()

    assert resultado.status == ExecutionStatus.SUCCESS
    assert chamadas == {
        "interceptar_msgbx": False,
        "trigger_suffix": ".salvar-preenchido",
        "prefer_click": True,
        "clique_simples": False,
    }


@pytest.mark.parametrize(
    ("mensagem", "classificacao", "resposta"),
    [
        ("Existem diferencas deseja alterar?", "diferencas", "nao"),
        ("Libera mapa para o financeiro?", "liberacao_financeira", "sim"),
        ("Nao existem diferencas", "ok_sem_diferencas", "ok"),
        (
            "Impressao direcionada para impressora: LOGISTICA [RICOH]",
            "impressao_direcionada",
            "ok",
        ),
        (
            "N o h  guias B nus AS lan adas no mapa. Deseja continuar?",
            "bonus_as_sem_guias",
            "sim",
        ),
        (
            "Distancia percorrida e maior que KM medio + 50%, informado no modulo 01.04.17. Continuar?",
            "alerta_km_medio_continuar",
            "sim",
        ),
        (
            "Distancia percorrida e maior que o KM limite informado no modulo 01.04.17",
            "alerta_km_bloqueador",
            "pendente",
        ),
        (
            "Comodato nao foi fechado atraves da rotina 03.03.30",
            "comodato_030330_pendente",
            "ok",
        ),
    ],
)
def test_decide_msgbox_030302_por_texto(mensagem, classificacao, resposta):
    page = Processo030302Page.__new__(Processo030302Page)

    decisao = page._decidir_resposta_msgbox_030302(mensagem)

    assert decisao == {"classificacao": classificacao, "resposta": resposta}


def test_salvar_mapa_preenchido_financeiro_sem_ok_ou_lista_falha():
    page = Processo030302Page.__new__(Processo030302Page)
    page.logger = type(
        "LoggerFake",
        (),
        {
            "info": lambda *args, **kwargs: None,
            "debug": lambda *args, **kwargs: None,
            "warning": lambda *args, **kwargs: None,
            "exception": lambda *args, **kwargs: None,
        },
    )()

    estado = {
        "statusMapa": "6",
        "produtos": [
            {
                "linha": "001",
                "codigo": "27983",
                "vazUn": "96",
                "vazUnDisabled": False,
            }
        ],
        "divMensagemDisplay": "none",
        "listaDiferencasLength": 0,
    }
    confirmacoes = [
        {
            "tipo": "msgbxSimNao",
            "mensagem": "Libera mapa para o financeiro?",
            "resposta": "sim",
        }
    ]

    page.entrar_frame_rotina_blindado = lambda *args, **kwargs: None
    page._instalar_monitor_envio_js = lambda *args, **kwargs: None
    page._estado_mapa_js = lambda *args, **kwargs: estado
    page._reativar_digitacao_valores_030302 = lambda *args, **kwargs: {
        "aplicados": [{"nome": "textvazUn001", "valor": "96"}],
        "total": 1,
    }
    page.wait_for_js_condition = lambda *args, **kwargs: True
    page._clicar_salvar_js = lambda *args, **kwargs: {
        "ok": True,
        "trigger": "BotSalvar.click.salvar-preenchido",
        "formAfter": {
            "itensListaLength": 37,
            "numeroItems": "1",
            "opcao": "6",
            "produtos": [{"codigo": "27983", "vazUn": "96"}],
        },
    }
    page._seguir_fluxo_salvar_030302 = lambda *args, **kwargs: {
        "confirmacoes": confirmacoes,
        "etapas": {"diferencas": False, "financeiro": True, "resultado": False},
        "resultado": {},
    }
    page._aguardar_envio_salvar_030302 = lambda *args, **kwargs: {
        "dados": {"submitCount": 2},
        "estado": {
            "listaDiferencasLength": 0,
            "divDiferencasVisivel": False,
            "divMensagemDisplay": "none",
        },
    }
    page._obter_confirmacoes_salvar_js = lambda *args, **kwargs: {"submitCount": 2}
    page._extrair_alertas_capturados = lambda confirmacoes: list(confirmacoes or [])
    page._reentrar_frame = lambda *args, **kwargs: None
    page._aguardar_lista_diferencas = lambda *args, **kwargs: {
        "listaDiferencasLength": 0,
        "divDiferencasVisivel": False,
        "divMensagemDisplay": "none",
        "alertasRespondidos": [],
    }
    page.switch_to_default_content = lambda *args, **kwargs: None

    resultado = page.salvar_mapa()

    assert resultado.status == ExecutionStatus.TECHNICAL_FAILURE
    assert "sem alerta de confirmacao" in resultado.message
    assert "sem lista de diferencas" in resultado.message


def test_salvar_mapa_sem_valor_editavel_financeiro_sem_ok_ou_lista_falha():
    page = Processo030302Page.__new__(Processo030302Page)
    page.logger = type(
        "LoggerFake",
        (),
        {
            "info": lambda *args, **kwargs: None,
            "debug": lambda *args, **kwargs: None,
            "warning": lambda *args, **kwargs: None,
            "exception": lambda *args, **kwargs: None,
        },
    )()

    estado = {
        "produtos": [
            {
                "linha": "001",
                "codigo": "27983",
                "vazUn": "96",
                "vazUnDisabled": True,
            }
        ],
        "divMensagemDisplay": "none",
        "listaDiferencasLength": 0,
    }
    confirmacoes = [
        {
            "tipo": "msgbxSimNao",
            "mensagem": "Libera mapa para o financeiro?",
            "resposta": "sim",
        }
    ]
    chamadas = {"redigitar": 0, "opcao8": 0}

    page.entrar_frame_rotina_blindado = lambda *args, **kwargs: None
    page._instalar_monitor_envio_js = lambda *args, **kwargs: None
    page._estado_mapa_js = lambda *args, **kwargs: estado

    def redigitar_nao_deve_ser_chamado(*args, **kwargs):
        chamadas["redigitar"] += 1
        raise AssertionError("nao deve redigitar quando nao ha valor editavel")

    page._reativar_digitacao_valores_030302 = redigitar_nao_deve_ser_chamado
    page.wait_for_js_condition = lambda *args, **kwargs: True
    page._clicar_salvar_js = lambda *args, **kwargs: {
        "ok": True,
        "trigger": "BotSalvar.click.verificar-diferencas",
        "formAfter": {
            "itensListaLength": 37,
            "numeroItems": "1",
            "opcao": "6",
            "produtos": [{"codigo": "27983", "vazUn": "96"}],
        },
    }
    page._seguir_fluxo_salvar_030302 = lambda *args, **kwargs: {
        "confirmacoes": confirmacoes,
        "etapas": {"diferencas": False, "financeiro": True, "resultado": False},
        "resultado": {},
    }
    page._aguardar_envio_salvar_030302 = lambda *args, **kwargs: {
        "dados": {"submitCount": 2},
        "estado": {
            "listaDiferencasLength": 0,
            "divDiferencasVisivel": False,
            "divMensagemDisplay": "none",
        },
    }
    page._obter_confirmacoes_salvar_js = lambda *args, **kwargs: {"submitCount": 2}
    page._extrair_alertas_capturados = lambda confirmacoes: list(confirmacoes or [])
    page._reentrar_frame = lambda *args, **kwargs: None
    page._aguardar_lista_diferencas = lambda *args, **kwargs: {
        "listaDiferencasLength": 0,
        "divDiferencasVisivel": False,
        "divMensagemDisplay": "none",
        "alertasRespondidos": [],
    }
    page._enviar_opcao_030302_js = lambda *args, **kwargs: {
        "ok": True,
        "trigger": "EnviarFormulario.opcao-8.teste",
    } if not chamadas.__setitem__("opcao8", chamadas["opcao8"] + 1) else {}
    page.switch_to_default_content = lambda *args, **kwargs: None

    resultado = page.salvar_mapa()

    assert resultado.status == ExecutionStatus.TECHNICAL_FAILURE
    assert "sem alerta de confirmacao" in resultado.message
    assert "sem lista de diferencas" in resultado.message
    assert chamadas["redigitar"] == 0
    assert chamadas["opcao8"] == 0


def test_salvar_mapa_status_zero_com_valor_residual_usa_fluxo_inicial():
    page = Processo030302Page.__new__(Processo030302Page)
    page.logger = type(
        "LoggerFake",
        (),
        {
            "info": lambda *args, **kwargs: None,
            "debug": lambda *args, **kwargs: None,
            "warning": lambda *args, **kwargs: None,
            "exception": lambda *args, **kwargs: None,
        },
    )()

    estado = {
        "statusMapa": "0",
        "produtos": [
            {
                "linha": "001",
                "codigo": "27983",
                "vazUn": "",
                "vazUnDisabled": False,
            },
            {
                "linha": "003",
                "codigo": "899599",
                "vazUn": "4",
                "vazUnDisabled": False,
            },
        ],
        "divMensagemDisplay": "none",
        "listaDiferencasLength": 0,
    }
    chamadas = {"redigitar": 0, "opcao8": 0, "salvar": []}

    page.entrar_frame_rotina_blindado = lambda *args, **kwargs: None
    page._instalar_monitor_envio_js = lambda *args, **kwargs: None
    page._estado_mapa_js = lambda *args, **kwargs: estado

    def redigitar_nao_deve_ser_chamado(*args, **kwargs):
        chamadas["redigitar"] += 1
        raise AssertionError("statusMapa=0 nao deve usar fluxo preenchido")

    page._reativar_digitacao_valores_030302 = redigitar_nao_deve_ser_chamado
    page.wait_for_js_condition = lambda *args, **kwargs: True

    def clicar_salvar(*args, **kwargs):
        chamadas["salvar"].append((args, kwargs))
        trigger_suffix = args[0] if args else ""
        return {
            "ok": True,
            "trigger": "BotSalvar.click" + trigger_suffix,
            "formAfter": {
                "call": "PW02102C",
                "itensLista": "PAYLOAD-PARCIAL",
                "itensListaLength": 74,
                "numeroItems": "2",
                "opcao": "6",
                "produtos": [
                    {"codigo": "27983", "vazUn": "0"},
                    {"codigo": "899599", "vazUn": "4"},
                ],
            },
        }

    page._clicar_salvar_js = clicar_salvar
    page._seguir_fluxo_salvar_030302 = lambda *args, **kwargs: {
        "confirmacoes": [
            {
                "tipo": "msgbxSimNao",
                "mensagem": "Libera mapa para o financeiro?",
                "resposta": "sim",
            },
            {
                "tipo": "msgbxSimNao",
                "mensagem": "Existem diferencas. Quer acertar?",
                "resposta": "nao",
            },
        ],
        "etapas": {"diferencas": True, "financeiro": True, "resultado": False},
        "resultado": {},
    }
    page._aguardar_envio_salvar_030302 = lambda *args, **kwargs: {
        "dados": {"submitCount": 2},
        "estado": {
            "listaDiferencasLength": 0,
            "divDiferencasVisivel": False,
            "divMensagemDisplay": "none",
        },
    }
    page._obter_confirmacoes_salvar_js = lambda *args, **kwargs: {"submitCount": 2}
    page._extrair_alertas_capturados = lambda confirmacoes: list(confirmacoes or [])
    page._reentrar_frame = lambda *args, **kwargs: None
    page._aguardar_lista_diferencas = lambda *args, **kwargs: {
        "listaDiferencasLength": 0,
        "divDiferencasVisivel": False,
        "divMensagemDisplay": "none",
        "alertasRespondidos": [],
    }
    page._enviar_opcao_com_payload_salvo_030302 = lambda *args, **kwargs: (
        chamadas.__setitem__("opcao8", chamadas["opcao8"] + 1)
    )
    page._responder_pergunta_html_js = lambda *args, **kwargs: None
    page.switch_to_default_content = lambda *args, **kwargs: None

    resultado = page.salvar_mapa()

    assert resultado.status == ExecutionStatus.TECHNICAL_FAILURE
    assert "sem lista de diferencas" in resultado.message
    assert chamadas["redigitar"] == 0
    assert chamadas["opcao8"] == 0
    assert chamadas["salvar"][0][0] == (".verificar-diferencas",)
    assert chamadas["salvar"][0][1]["prefer_click"] is True


def test_salvar_mapa_zerado_habilita_botao_quando_promax_deixa_disabled():
    page = Processo030302Page.__new__(Processo030302Page)
    page.logger = type(
        "LoggerFake",
        (),
        {
            "info": lambda *args, **kwargs: None,
            "debug": lambda *args, **kwargs: None,
            "warning": lambda *args, **kwargs: None,
            "exception": lambda *args, **kwargs: None,
        },
    )()

    estado = {
        "produtos": [
            {
                "linha": "001",
                "codigo": "27983",
                "vazUn": "",
                "vazUnDisabled": False,
            }
        ],
        "botSalvarDisabled": True,
        "divMensagemDisplay": "none",
        "listaDiferencasLength": 0,
    }
    chamadas = {"habilitar": 0, "salvar": 0}

    page.entrar_frame_rotina_blindado = lambda *args, **kwargs: None
    page._instalar_monitor_envio_js = lambda *args, **kwargs: None
    estado_final_limpo = {
        "mapa": "93491",
        "mapaSalvo": "93491",
        "produtos": [],
        "divMensagemDisplay": "none",
        "divDiferencasDisplay": "none",
        "divDiferencasVisivel": False,
        "listaDiferencasLength": 0,
        "listaRows": 0,
        "opcao": "7",
        "botSalvarDisabled": True,
    }

    def estado_mapa(*args, **kwargs):
        if chamadas.get("aguardar_lista", 0) >= 2:
            return dict(estado_final_limpo)
        return dict(estado)

    page._estado_mapa_js = estado_mapa
    page._reativar_digitacao_valores_030302 = lambda *args, **kwargs: {
        "aplicados": [],
        "total": 0,
    }

    def habilitar(*args, **kwargs):
        chamadas["habilitar"] += 1
        estado["botSalvarDisabled"] = False
        return {
            "aplicados": [{"nome": "textvazUn001", "valorDepois": "0"}],
            "total": 1,
            "botSalvarDisabled": False,
        }

    page._habilitar_salvar_mapa_zerado_030302 = habilitar
    page.wait_for_js_condition = lambda *args, **kwargs: True

    def clicar_salvar(*args, **kwargs):
        chamadas["salvar"] += 1
        return {
            "ok": True,
            "trigger": "BotSalvar.click.verificar-diferencas",
            "formAfter": {
                "call": "PW02102C",
                "itensLista": "PAYLOAD-ZERADO",
                "itensListaLength": 37,
                "numeroItems": "1",
                "opcao": "6",
                "produtos": [{"codigo": "27983", "vazUn": "0"}],
            },
        }

    page._clicar_salvar_js = clicar_salvar
    page._seguir_fluxo_salvar_030302 = lambda *args, **kwargs: {
        "confirmacoes": [{"mensagem": "Nao existem diferencas", "resposta": "ok"}],
        "etapas": {"diferencas": False, "financeiro": False, "resultado": True},
        "resultado": {"mensagemSemDiferencas": True},
    }
    page._aguardar_envio_salvar_030302 = lambda *args, **kwargs: {
        "dados": {"submitCount": 1},
        "estado": {},
    }
    page._obter_confirmacoes_salvar_js = lambda *args, **kwargs: {"submitCount": 1}
    page._detectar_msgbox_script_pendente_030302 = lambda *args, **kwargs: {}
    page._extrair_alertas_capturados = lambda *args, **kwargs: []
    page.switch_to_default_content = lambda *args, **kwargs: None

    resultado = page.salvar_mapa()

    assert resultado.status == ExecutionStatus.SUCCESS
    assert "confirmado sem diferencas" in resultado.message
    assert chamadas == {"habilitar": 1, "salvar": 1}


def test_salvar_mapa_zerado_clica_para_gerar_lista_e_falha_se_lista_nao_aparecer():
    page = Processo030302Page.__new__(Processo030302Page)
    page.logger = type(
        "LoggerFake",
        (),
        {
            "info": lambda *args, **kwargs: None,
            "debug": lambda *args, **kwargs: None,
            "warning": lambda *args, **kwargs: None,
            "exception": lambda *args, **kwargs: None,
        },
    )()

    estado = {
        "produtos": [
            {
                "linha": "001",
                "codigo": "27983",
                "vazUn": "",
                "vazUnDisabled": False,
            }
        ],
        "divMensagemDisplay": "none",
        "listaDiferencasLength": 0,
    }
    chamadas = {"salvar": 0, "aguardar_lista": 0, "opcao8": 0}

    page.entrar_frame_rotina_blindado = lambda *args, **kwargs: None
    page._instalar_monitor_envio_js = lambda *args, **kwargs: None
    page._estado_mapa_js = lambda *args, **kwargs: estado
    page._reativar_digitacao_valores_030302 = lambda *args, **kwargs: {
        "aplicados": [],
        "total": 0,
    }
    page.wait_for_js_condition = lambda *args, **kwargs: True
    def clicar_salvar(*args, **kwargs):
        chamadas["salvar"] += 1
        return {
            "ok": True,
            "trigger": "BotSalvar.click.verificar-diferencas",
            "formAfter": {
                "call": "PW02102C",
                "itensLista": "PAYLOAD-ZERADO",
                "itensListaLength": 37,
                "numeroItems": "1",
                "opcao": "6",
                "produtos": [{"codigo": "27983", "vazUn": "0"}],
            },
        }

    page._clicar_salvar_js = clicar_salvar
    page._seguir_fluxo_salvar_030302 = lambda *args, **kwargs: {
        "confirmacoes": [
            {
                "tipo": "msgbxSimNao",
                "mensagem": "Existem diferencas. Quer acertar?",
                "resposta": "nao",
            },
            {
                "tipo": "msgbxSimNao",
                "mensagem": "Libera mapa para o financeiro?",
                "resposta": "sim",
            },
        ],
        "etapas": {"diferencas": True, "financeiro": True, "resultado": False},
        "resultado": {},
    }
    page._aguardar_envio_salvar_030302 = lambda *args, **kwargs: {
        "dados": {"submitCount": 2},
        "estado": {
            "listaDiferencasLength": 0,
            "divDiferencasVisivel": False,
            "divMensagemDisplay": "none",
        },
    }
    page._obter_confirmacoes_salvar_js = lambda *args, **kwargs: {"submitCount": 2}
    page._extrair_alertas_capturados = lambda confirmacoes: list(confirmacoes or [])
    page._reentrar_frame = lambda *args, **kwargs: None
    def aguardar_lista(*args, **kwargs):
        chamadas["aguardar_lista"] += 1
        return {
            "listaDiferencasLength": 0,
            "divDiferencasVisivel": False,
            "divMensagemDisplay": "none",
            "alertasRespondidos": [],
        }

    page._aguardar_lista_diferencas = aguardar_lista
    def enviar_payload(opcao, snapshot, trigger_suffix=""):
        chamadas["opcao8"] += 1
        raise AssertionError("mapa zerado nao deve forcar opcao=8 antes da lista real")

    page._enviar_opcao_com_payload_salvo_030302 = enviar_payload
    page._adicionar_confirmacao_030302 = lambda confirmacoes, confirmacao, origem="": False
    page._responder_pergunta_html_js = lambda *args, **kwargs: None
    page.switch_to_default_content = lambda *args, **kwargs: None

    resultado = page.salvar_mapa()

    assert resultado.status == ExecutionStatus.TECHNICAL_FAILURE
    assert "sem lista de diferencas" in resultado.message
    assert chamadas == {"salvar": 1, "aguardar_lista": 1, "opcao8": 0}
    assert resultado.metadata["resultado_js"]["retornoDiferencas"]["trigger"] == (
        "fluxo-zerado-sem-opcao8-forcado"
    )


def test_salvar_mapa_zerado_captura_lista_reabre_rotina_aplica_e_salva_final():
    page = Processo030302Page.__new__(Processo030302Page)
    page.logger = type(
        "LoggerFake",
        (),
        {
            "info": lambda *args, **kwargs: None,
            "debug": lambda *args, **kwargs: None,
            "warning": lambda *args, **kwargs: None,
            "exception": lambda *args, **kwargs: None,
        },
    )()

    estado = {
        "mapa": "93491",
        "mapaSalvo": "93491",
        "pontoApoio": "",
        "produtos": [
            {
                "linha": "001",
                "codigo": "27983",
                "vazUn": "",
                "vazUnDisabled": False,
            }
        ],
        "divMensagemDisplay": "none",
        "listaDiferencasLength": 0,
    }
    chamadas = {"salvar": 0, "recarregar": 0, "aplicar": 0, "fluxo": 0}
    cliques_salvar = []

    page.entrar_frame_rotina_blindado = lambda *args, **kwargs: None
    page._instalar_monitor_envio_js = lambda *args, **kwargs: None
    estado_final_limpo = {
        "mapa": "93491",
        "mapaSalvo": "93491",
        "produtos": [],
        "divMensagemDisplay": "none",
        "divDiferencasDisplay": "none",
        "divDiferencasVisivel": False,
        "listaDiferencasLength": 0,
        "listaRows": 0,
        "opcao": "7",
        "botSalvarDisabled": True,
    }

    def estado_mapa(*args, **kwargs):
        if chamadas.get("aguardar_lista", 0) >= 2:
            return dict(estado_final_limpo)
        return dict(estado)

    page._estado_mapa_js = estado_mapa
    page._reativar_digitacao_valores_030302 = lambda *args, **kwargs: {
        "aplicados": [],
        "total": 0,
    }
    page.wait_for_js_condition = lambda *args, **kwargs: True

    def clicar_salvar(trigger_suffix="", *args, **kwargs):
        chamadas["salvar"] += 1
        cliques_salvar.append((trigger_suffix, kwargs))
        produtos = [{"codigo": "27983", "vazUn": "0"}]
        if trigger_suffix == ".apos-aplicar-diferencas":
            produtos = [{"codigo": "27983", "vazUn": "96"}]
        return {
            "ok": True,
            "trigger": "BotSalvar.click" + trigger_suffix,
            "formAfter": {
                "itensListaLength": 37,
                "numeroItems": "1",
                "opcao": "6",
                "produtos": produtos,
            },
        }

    page._clicar_salvar_js = clicar_salvar
    def seguir_fluxo(*args, **kwargs):
        chamadas["fluxo"] += 1
        if chamadas["fluxo"] == 1:
            return {
                "confirmacoes": [
                    {
                        "tipo": "msgbxSimNao",
                        "mensagem": "Existem diferencas. Quer acertar?",
                        "resposta": "nao",
                    },
                    {
                        "tipo": "msgbxSimNao",
                        "mensagem": "Libera mapa para o financeiro?",
                        "resposta": "sim",
                    },
                ],
                "etapas": {"diferencas": True, "financeiro": True, "resultado": False},
                "resultado": {},
            }
        assert kwargs["parar_apos_financeiro"] is False
        assert kwargs["exigir_financeiro"] is False
        return {
            "confirmacoes": [
                {
                    "tipo": "msgbxSimNao",
                    "mensagem": "Libera mapa para o financeiro?",
                    "resposta": "sim",
                },
                {
                    "tipo": "alert",
                    "mensagem": "Nao existem diferencas",
                    "resposta": "ok",
                },
            ],
            "etapas": {"diferencas": False, "financeiro": True, "resultado": True},
            "resultado": {
                "mensagemOk": True,
                "mensagemSemDiferencas": True,
                "listaDiferencasLength": 0,
            },
        }

    page._seguir_fluxo_salvar_030302 = seguir_fluxo
    page._aguardar_envio_salvar_030302 = lambda *args, **kwargs: {
        "dados": {"submitCount": 2},
        "estado": {
            "listaDiferencasLength": 1,
            "divDiferencasVisivel": True,
            "divMensagemDisplay": "none",
        },
    }
    page._obter_confirmacoes_salvar_js = lambda *args, **kwargs: {"submitCount": 3}
    page._extrair_alertas_capturados = lambda *args, **kwargs: []
    page._reentrar_frame = lambda *args, **kwargs: None
    def aguardar_lista(*args, **kwargs):
        chamadas.setdefault("aguardar_lista", 0)
        chamadas["aguardar_lista"] += 1
        if chamadas["aguardar_lista"] >= 2:
            return {
                "listaDiferencasLength": 0,
                "divDiferencasVisivel": False,
                "divMensagemDisplay": "none",
                "alertasRespondidos": [],
            }
        return {
            "listaDiferencasLength": 1,
            "divDiferencasVisivel": True,
            "divMensagemDisplay": "none",
            "alertasRespondidos": [],
        }

    page._aguardar_lista_diferencas = aguardar_lista
    page._adicionar_confirmacao_030302 = lambda confirmacoes, confirmacao, origem="": False
    page._responder_pergunta_html_js = lambda *args, **kwargs: None
    page._capturar_diferencas_lista_js = lambda *args, **kwargs: {
        "encontrou": True,
        "total": 1,
        "itens": [{"codigo": "27983", "faltaUn": 96, "faltaAv": 0}],
    }

    def recarregar(mapa, ponto_apoio=None, timeout=45):
        chamadas["recarregar"] += 1
        assert mapa == "93491"
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message="Mapa recarregado",
        )

    page._recarregar_mapa_para_acerto = recarregar

    def aplicar(itens):
        chamadas["aplicar"] += 1
        assert itens == [{"codigo": "27983", "faltaUn": 96, "faltaAv": 0}]
        return {
            "encontrou": True,
            "aplicados": [
                {
                    "codigo": "27983",
                    "linha": "001",
                    "destino": "vazio",
                    "campoUn": "textvazUn001",
                    "faltaUn": 96,
                }
            ],
        }

    page._aplicar_diferencas_capturadas_js = aplicar

    page.switch_to_default_content = lambda *args, **kwargs: None

    resultado = page.salvar_mapa()

    assert resultado.status == ExecutionStatus.SUCCESS
    assert "diferencas capturadas" in resultado.message
    assert chamadas == {
        "salvar": 2,
        "recarregar": 1,
        "aplicar": 1,
        "fluxo": 2,
        "aguardar_lista": 1,
    }
    assert cliques_salvar[1][0] == ".apos-aplicar-diferencas"
    assert cliques_salvar[1][1]["prefer_click"] is True
    assert cliques_salvar[1][1]["clique_simples"] is False
    assert resultado.metadata["diferencas_corrigidas"]["aplicados"][0]["campoUn"] == "textvazUn001"


def test_salvar_mapa_preenchido_usa_mesmo_envio_do_zerado():
    page = Processo030302Page.__new__(Processo030302Page)
    page.logger = type(
        "LoggerFake",
        (),
        {
            "info": lambda *args, **kwargs: None,
            "debug": lambda *args, **kwargs: None,
            "warning": lambda *args, **kwargs: None,
            "exception": lambda *args, **kwargs: None,
        },
    )()

    estado_antes = {
        "statusMapa": "6",
        "produtos": [
            {
                "linha": "001",
                "codigo": "27983",
                "vazUn": "96",
                "vazUnDisabled": False,
            }
        ],
        "divMensagemDisplay": "none",
        "listaDiferencasLength": 0,
        "listaRows": 4,
        "opcao": "2",
    }
    estado_depois = {
        "produtos": [],
        "divMensagemDisplay": "none",
        "listaDiferencasLength": 0,
        "listaRows": 0,
        "opcao": "7",
    }
    chamadas = {"estado": 0}

    def estado_mapa(*args, **kwargs):
        chamadas["estado"] += 1
        return dict(estado_antes if chamadas["estado"] <= 2 else estado_depois)

    page.entrar_frame_rotina_blindado = lambda *args, **kwargs: None
    page._instalar_monitor_envio_js = lambda *args, **kwargs: None
    page._estado_mapa_js = estado_mapa
    page._reativar_digitacao_valores_030302 = lambda *args, **kwargs: {
        "aplicados": [{"nome": "textvazUn001", "valor": "96"}],
        "total": 1,
    }
    page.wait_for_js_condition = lambda *args, **kwargs: True
    chamadas_click = []

    def clicar_salvar(*args, **kwargs):
        trigger_suffix = args[0] if args else ""
        chamadas_click.append((args, kwargs))
        return {
            "ok": True,
            "trigger": "BotSalvar.click" + trigger_suffix,
            "formAfter": {
                "itensListaLength": 37,
                "numeroItems": "1",
                "opcao": "6",
                "produtos": [{"codigo": "27983", "vazUn": "96"}],
            },
        }

    page._clicar_salvar_js = clicar_salvar
    page._seguir_fluxo_salvar_030302 = lambda *args, **kwargs: {
        "confirmacoes": [],
        "etapas": {"diferencas": False, "financeiro": False, "resultado": False},
        "resultado": {},
    }
    page._aguardar_envio_salvar_030302 = lambda *args, **kwargs: {
        "dados": {"submitCount": 2},
        "estado": {
            "listaDiferencasLength": 0,
            "divDiferencasVisivel": False,
            "divMensagemDisplay": "none",
        },
    }
    page._liberar_financeiro_pos_salvar_js = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("nao deve liberar financeiro por fallback direto")
    )
    page._reentrar_frame = lambda *args, **kwargs: None
    page._aguardar_lista_diferencas = lambda *args, **kwargs: {
        "listaDiferencasLength": 0,
        "mensagemSemDiferencas": True,
    }
    page._obter_confirmacoes_salvar_js = lambda *args, **kwargs: {"submitCount": 2}
    page._extrair_alertas_capturados = lambda *args, **kwargs: []
    page.switch_to_default_content = lambda *args, **kwargs: None

    resultado = page.salvar_mapa()

    assert resultado.status == ExecutionStatus.SUCCESS
    assert resultado.metadata["trigger"] == "BotSalvar.click.salvar-preenchido"
    assert chamadas_click[0][0] == (".salvar-preenchido",)
    assert chamadas_click[0][1]["prefer_click"] is True
    assert chamadas_click[0][1]["clique_simples"] is False


def test_salvar_mapa_preenchido_reenvia_opcao8_com_payload_salvo():
    page = Processo030302Page.__new__(Processo030302Page)
    page.logger = type(
        "LoggerFake",
        (),
        {
            "info": lambda *args, **kwargs: None,
            "debug": lambda *args, **kwargs: None,
            "warning": lambda *args, **kwargs: None,
            "exception": lambda *args, **kwargs: None,
        },
    )()

    estado_antes = {
        "statusMapa": "6",
        "produtos": [
            {
                "linha": "001",
                "codigo": "27983",
                "vazUn": "96",
                "vazUnDisabled": False,
            }
        ],
        "divMensagemDisplay": "none",
        "listaDiferencasLength": 0,
        "listaRows": 4,
        "opcao": "2",
    }
    chamadas = {"aguardar_lista": 0, "payload": []}

    page.entrar_frame_rotina_blindado = lambda *args, **kwargs: None
    page._instalar_monitor_envio_js = lambda *args, **kwargs: None
    page._estado_mapa_js = lambda *args, **kwargs: dict(estado_antes)
    page._reativar_digitacao_valores_030302 = lambda *args, **kwargs: {
        "aplicados": [{"nome": "textvazUn001", "valor": "96"}],
        "total": 1,
    }
    page.wait_for_js_condition = lambda *args, **kwargs: True
    page._clicar_salvar_js = lambda *args, **kwargs: {
        "ok": True,
        "trigger": "BotSalvar.click.salvar-preenchido",
        "formAfter": {
            "call": "PW02102C",
            "itensLista": "PAYLOAD-COM-VALOR",
            "itensListaLength": 17,
            "numeroItems": "1",
            "mapa": "93491",
            "opcao": "6",
            "idAchouGuiaMapa": "N",
            "idAchouGuiasSalvas": " ",
            "idMostraMsgAfericao": "N",
            "produtos": [{"codigo": "27983", "vazUn": "96"}],
        },
    }
    page._seguir_fluxo_salvar_030302 = lambda *args, **kwargs: {
        "confirmacoes": [],
        "etapas": {"diferencas": False, "financeiro": False, "resultado": False},
        "resultado": {},
    }
    page._aguardar_envio_salvar_030302 = lambda *args, **kwargs: {
        "dados": {
            "submitCount": 2,
            "ultimoSalvar": {
                "opcao": "7",
                "itensListaLength": 0,
                "produtos": [],
            },
        },
        "estado": {
            "listaDiferencasLength": 0,
            "divDiferencasVisivel": False,
            "divMensagemDisplay": "none",
        },
    }

    def aguardar_lista(*args, **kwargs):
        chamadas["aguardar_lista"] += 1
        if chamadas["aguardar_lista"] == 1:
            return {
                "listaDiferencasLength": 0,
                "mensagemSemDiferencas": False,
                "alertasRespondidos": [],
            }
        return {
            "listaDiferencasLength": 0,
            "mensagemSemDiferencas": True,
            "alertasRespondidos": [
                {
                    "tipo": "alert",
                    "mensagem": "Nao existem diferencas",
                    "resposta": "ok",
                }
            ],
        }

    def enviar_payload(opcao, snapshot, trigger_suffix=""):
        chamadas["payload"].append((opcao, snapshot, trigger_suffix))
        return {
            "ok": True,
            "trigger": "EnviarFormulario.payload-salvo-opcao-8",
            "formAfter": {
                "opcao": "8",
                "itensLista": snapshot["itensLista"],
                "itensListaLength": len(snapshot["itensLista"]),
            },
        }

    page._aguardar_lista_diferencas = aguardar_lista
    page._enviar_opcao_com_payload_salvo_030302 = enviar_payload
    page._obter_confirmacoes_salvar_js = lambda *args, **kwargs: {"submitCount": 3}
    page._extrair_alertas_capturados = lambda *args, **kwargs: []
    page.switch_to_default_content = lambda *args, **kwargs: None

    resultado = page.salvar_mapa()

    assert resultado.status == ExecutionStatus.SUCCESS
    assert chamadas["aguardar_lista"] == 2
    assert chamadas["payload"][0][0] == "8"
    assert chamadas["payload"][0][1]["call"] == "PW02102C"
    assert chamadas["payload"][0][1]["itensLista"] == "PAYLOAD-COM-VALOR"
    assert chamadas["payload"][0][2] == ".confirmacao-financeira-preenchido"
    assert (
        resultado.metadata["resultado_payload_preenchido"]["trigger"]
        == "EnviarFormulario.payload-salvo-opcao-8"
    )


def test_fluxo_salvar_030302_exige_financeiro_antes_do_resultado():
    page = Processo030302Page.__new__(Processo030302Page)
    page.logger = type(
        "LoggerFake",
        (),
        {"info": lambda *args, **kwargs: None, "debug": lambda *args, **kwargs: None},
    )()

    respostas = iter(
        [
            {"tipo": "alert", "mensagem": "Existem diferencas deseja alterar?", "resposta": "nao"},
            {"tipo": "alert", "mensagem": "Nao existem diferencas", "resposta": "ok"},
            {"tipo": "alert", "mensagem": "Liberar mapa para o financeiro?", "resposta": "sim"},
        ]
    )

    page._responder_alerta_nativo = lambda *args, **kwargs: next(respostas, None)
    page._responder_pergunta_html_js = lambda *args, **kwargs: None
    page._estado_telinhas_js = lambda *args, **kwargs: {}
    page._aguardar_lista_diferencas = lambda *args, **kwargs: {}

    resultado = page._seguir_fluxo_salvar_030302(timeout=1, exigir_financeiro=True)

    assert resultado["etapas"] == {
        "diferencas": True,
        "financeiro": True,
        "resultado": True,
    }
    assert [item["resposta"] for item in resultado["confirmacoes"]] == ["nao", "ok", "sim"]
    assert resultado["resultado"]["mensagemSemDiferencas"] is True


def test_fluxo_salvar_030302_financeiro_opcional_aceita_ok_sem_financeiro():
    page = Processo030302Page.__new__(Processo030302Page)
    page.logger = type(
        "LoggerFake",
        (),
        {"info": lambda *args, **kwargs: None, "debug": lambda *args, **kwargs: None},
    )()

    respostas = iter(
        [
            {"tipo": "alert", "mensagem": "Nao existem diferencas", "resposta": "ok"},
        ]
    )

    page._responder_alerta_nativo = lambda *args, **kwargs: next(respostas, None)
    page._responder_pergunta_html_js = lambda *args, **kwargs: None
    page._estado_telinhas_js = lambda *args, **kwargs: {}
    page._aguardar_lista_diferencas = lambda *args, **kwargs: {}

    resultado = page._seguir_fluxo_salvar_030302(
        timeout=1,
        exigir_financeiro=False,
        parar_apos_financeiro=False,
    )

    assert resultado["etapas"] == {
        "diferencas": False,
        "financeiro": False,
        "resultado": True,
    }
    assert [item["resposta"] for item in resultado["confirmacoes"]] == ["ok"]
    assert resultado["resultado"]["mensagemSemDiferencas"] is True


def test_fluxo_salvar_030302_financeiro_opcional_responde_financeiro_e_depois_ok():
    page = Processo030302Page.__new__(Processo030302Page)
    page.logger = type(
        "LoggerFake",
        (),
        {"info": lambda *args, **kwargs: None, "debug": lambda *args, **kwargs: None},
    )()

    respostas = iter(
        [
            {"tipo": "alert", "mensagem": "Libera mapa para o financeiro?", "resposta": "sim"},
            {"tipo": "alert", "mensagem": "Nao existem diferencas", "resposta": "ok"},
        ]
    )

    page._responder_alerta_nativo = lambda *args, **kwargs: next(respostas, None)
    page._responder_pergunta_html_js = lambda *args, **kwargs: None
    page._estado_telinhas_js = lambda *args, **kwargs: {}
    page._aguardar_lista_diferencas = lambda *args, **kwargs: {}

    resultado = page._seguir_fluxo_salvar_030302(
        timeout=1,
        exigir_financeiro=False,
        parar_apos_financeiro=False,
    )

    assert resultado["etapas"] == {
        "diferencas": False,
        "financeiro": True,
        "resultado": True,
    }
    assert [item["resposta"] for item in resultado["confirmacoes"]] == ["sim", "ok"]
    assert resultado["resultado"]["mensagemSemDiferencas"] is True


def test_alerta_script_msgbox_nao_e_fechado_automaticamente():
    page = Processo030302Page.__new__(Processo030302Page)

    class AlertFake:
        text = "function() { document.parentWindow.parent.rotina.document.all('BotSalvar').disabled = false; }"

        def __init__(self):
            self.accepted = False
            self.dismissed = False

        def accept(self):
            self.accepted = True

        def dismiss(self):
            self.dismissed = True

    class SwitchFake:
        def __init__(self, alert):
            self.alert = alert

    class DriverFake:
        def __init__(self, alert):
            self.switch_to = SwitchFake(alert)

    alerta = AlertFake()
    page.driver = DriverFake(alerta)
    page._garantir_janela_030302 = lambda *args, **kwargs: True

    resposta = page._responder_alerta_nativo(acertar_diferencas=True)

    assert resposta["tipo"] == "alert-script-aberto"
    assert resposta["resposta"] == "pendente"
    assert resposta["bloqueia_fluxo"] is True
    assert alerta.accepted is False
    assert alerta.dismissed is False


def test_alerta_nativo_desconhecido_nao_e_fechado_automaticamente():
    page = Processo030302Page.__new__(Processo030302Page)

    class AlertFake:
        text = "Mensagem inesperada da 030302"

        def __init__(self):
            self.accepted = False
            self.dismissed = False

        def accept(self):
            self.accepted = True

        def dismiss(self):
            self.dismissed = True

    class SwitchFake:
        def __init__(self, alert):
            self.alert = alert

    class DriverFake:
        def __init__(self, alert):
            self.switch_to = SwitchFake(alert)

    alerta = AlertFake()
    page.driver = DriverFake(alerta)
    page._garantir_janela_030302 = lambda *args, **kwargs: True

    resposta = page._responder_alerta_nativo(acertar_diferencas=True)

    assert resposta["tipo"] == "alert-nao-tratado"
    assert resposta["resposta"] == "pendente"
    assert resposta["bloqueia_fluxo"] is True
    assert alerta.accepted is False
    assert alerta.dismissed is False


def test_alerta_km_aberto_fecha_e_sinaliza_reabertura_com_fallback():
    page = Processo030302Page.__new__(Processo030302Page)
    page._km_inicial_030302 = "94855"
    page._km_prev_030302 = "120"
    page.logger = type(
        "LoggerFake",
        (),
        {
            "info": lambda *args, **kwargs: None,
            "debug": lambda *args, **kwargs: None,
            "warning": lambda *args, **kwargs: None,
        },
    )()
    class AlertFake:
        text = "KM fora do previsto. Deseja continuar?"

        def __init__(self):
            self.accepted = False
            self.dismissed = False

        def accept(self):
            self.accepted = True

        def dismiss(self):
            self.dismissed = True

    class SwitchFake:
        def __init__(self, alert):
            self.alert = alert

    class DriverFake:
        def __init__(self, alert):
            self.switch_to = SwitchFake(alert)

    alerta = AlertFake()
    page.driver = DriverFake(alerta)
    page.wait_for_no_alert = lambda *args, **kwargs: None
    page._registrar_alerta_030302 = lambda *args, **kwargs: None

    resultado = page._tratar_alerta_km_aberto_para_fallback(
        alerta.text,
        {"classificacao": "alerta_km", "resposta": "sim"},
    )

    assert alerta.dismissed is True
    assert alerta.accepted is False
    assert resultado["ok"] is True
    assert resultado["reabrir_030302_com_km"] is True
    assert resultado["km_atual"] == "94975"
    assert page._reabrir_030302_com_km["km_atual"] == "94975"


def test_aguardar_estado_pos_mapa_captura_alerta_km_para_reabertura(monkeypatch):
    page = Processo030302Page.__new__(Processo030302Page)
    page._km_inicial_030302 = "94855"
    page._km_prev_030302 = "120"
    page._reabrir_030302_com_km = None
    page.logger = type(
        "LoggerFake",
        (),
        {
            "info": lambda *args, **kwargs: None,
            "debug": lambda *args, **kwargs: None,
            "warning": lambda *args, **kwargs: None,
        },
    )()

    class AlertFake:
        text = "KM fora do previsto. Deseja continuar?"

        def __init__(self):
            self.dismissed = False

        def dismiss(self):
            self.dismissed = True

    class SwitchFake:
        def __init__(self, alert):
            self.alert = alert

    class DriverFake:
        def __init__(self, alert):
            self.switch_to = SwitchFake(alert)

        def execute_script(self, *_args, **_kwargs):
            raise UnexpectedAlertPresentException("alerta km")

    alerta = AlertFake()
    page.driver = DriverFake(alerta)
    page._garantir_janela_030302 = lambda *args, **kwargs: True
    page.wait_for_no_alert = lambda *args, **kwargs: None
    page._registrar_alerta_030302 = lambda *args, **kwargs: None
    monkeypatch.setattr(
        "pages.processes.processo_030302_page.WebDriverWait",
        lambda *_args, **_kwargs: type("WaitFake", (), {"until": lambda _self, condition: condition(page.driver)})(),
    )

    estado = page._aguardar_estado_pos_mapa_js(timeout=1)

    assert estado["reabrir_030302_com_km"] is True
    assert estado["alertaKm"]["km_atual"] == "94975"
    assert alerta.dismissed is True


def test_alerta_km_medio_durante_carga_clica_sim_sem_fallback():
    page = Processo030302Page.__new__(Processo030302Page)
    page._reabrir_030302_com_km = None
    page.logger = type(
        "LoggerFake",
        (),
        {
            "info": lambda *args, **kwargs: None,
            "debug": lambda *args, **kwargs: None,
            "warning": lambda *args, **kwargs: None,
        },
    )()

    class AlertFake:
        text = "Distancia percorrida e maior que KM medio + 50%, informado no modulo 01.04.17. Continuar?"

        def __init__(self):
            self.accepted = False
            self.dismissed = False

        def accept(self):
            self.accepted = True

        def dismiss(self):
            self.dismissed = True

    class SwitchFake:
        def __init__(self, alert):
            self.alert = alert

    class DriverFake:
        def __init__(self, alert):
            self.switch_to = SwitchFake(alert)

    alerta = AlertFake()
    page.driver = DriverFake(alerta)
    page._garantir_janela_030302 = lambda *args, **kwargs: True
    page._registrar_alerta_030302 = lambda *args, **kwargs: None

    resultado = page._tratar_alerta_carregamento_mapa_030302("93854", origem="teste")

    assert resultado == {
        "acao": "continuar",
        "mensagem": alerta.text,
    }
    assert alerta.accepted is True
    assert alerta.dismissed is False
    assert page._reabrir_030302_com_km is None
