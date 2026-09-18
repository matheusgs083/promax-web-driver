from selenium.common.exceptions import NoAlertPresentException, UnexpectedAlertPresentException

from core.execution.execution_result import ExecutionStatus
from pages.processes.processo_030330_page import Processo030330Page


class _LoggerFake:
    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None


def test_salvar_mapa_trata_alerta_material_controlado_e_repete_salvamento(monkeypatch):
    estado = {"alerta_aberto": False, "alerta_aceito": False, "salvamentos": 0, "modal": 0}

    class AlertaFake:
        text = "Nota(s) com material controlado. Falta informar Etiqueta/Nº de Série"

        def accept(self):
            estado["alerta_aberto"] = False
            estado["alerta_aceito"] = True

    class SwitchToFake:
        @property
        def alert(self):
            if estado["alerta_aberto"]:
                return AlertaFake()
            raise NoAlertPresentException()

    class DriverFake:
        switch_to = SwitchToFake()

        def execute_script(self, _script, *_args):
            estado["salvamentos"] += 1
            if estado["salvamentos"] == 1:
                estado["alerta_aberto"] = True
                raise UnexpectedAlertPresentException(
                    "material controlado",
                    alert_text=AlertaFake.text,
                )
            return {"ok": True, "trigger": "Salvar()"}

    page = Processo030330Page.__new__(Processo030330Page)
    page.driver = DriverFake()
    page.logger = _LoggerFake()
    page._garantir_frame_rotina = lambda: None
    page.wait_for_no_alert = lambda timeout=2: True
    page.lidar_com_alertas = lambda **kwargs: []
    page.obter_resumo_mapa = lambda: {
        "nrLinhas": "1",
        "notas": [{"notaSerie": "123"}],
    }

    def tratar_modal(dt_fechamento=None):
        if estado["alerta_aceito"] and estado["modal"] == 0:
            estado["modal"] += 1
            return True
        return False

    page.tratar_div_numero_serie = tratar_modal
    monkeypatch.setattr("pages.processes.processo_030330_page.time.sleep", lambda *_args: None)

    resultado = page.salvar_mapa()

    assert resultado.status == ExecutionStatus.SUCCESS
    assert estado["alerta_aceito"] is True
    assert estado["modal"] == 1
    assert estado["salvamentos"] == 2
    assert resultado.metadata["alertas"] == [AlertaFake.text]
    assert resultado.metadata["resultado_salvar"]["trigger"] == "Salvar()"


def test_salvar_mapa_preserva_alerta_desconhecido_sem_aceitar(monkeypatch):
    estado = {"alerta_aberto": False, "alerta_aceito": False}

    class AlertaFake:
        text = "Mapa bloqueado para fechamento"

        def accept(self):
            estado["alerta_aberto"] = False
            estado["alerta_aceito"] = True

    class SwitchToFake:
        @property
        def alert(self):
            if estado["alerta_aberto"]:
                return AlertaFake()
            raise NoAlertPresentException()

    class DriverFake:
        switch_to = SwitchToFake()

        def execute_script(self, _script, *_args):
            estado["alerta_aberto"] = True
            raise UnexpectedAlertPresentException("bloqueado", alert_text=AlertaFake.text)

    page = Processo030330Page.__new__(Processo030330Page)
    page.driver = DriverFake()
    page.logger = _LoggerFake()
    page._garantir_frame_rotina = lambda: None
    page.obter_resumo_mapa = lambda: {
        "nrLinhas": "1",
        "notas": [{"notaSerie": "123"}],
    }
    page.tratar_div_numero_serie = lambda dt_fechamento=None: False
    monkeypatch.setattr("pages.processes.processo_030330_page.time.sleep", lambda *_args: None)

    resultado = page.salvar_mapa()

    assert resultado.status == ExecutionStatus.BUSINESS_FAILURE
    assert resultado.message == "Alerta ao salvar mapa na 030330: Mapa bloqueado para fechamento"
    assert resultado.metadata["integration_code"] == "ALERTA_030330_NAO_TRATADO"
    assert estado["alerta_aceito"] is False
