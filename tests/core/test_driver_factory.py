from __future__ import annotations

from dataclasses import dataclass

from core.browser.driver_factory import DriverFactory


@dataclass
class FakeSettings:
    edge_path: str = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    driver_path: str | None = r"C:\drivers\IEDriverServer.exe"
    require_window_focus: bool = False


def _image_name(command: list[str]) -> str:
    idx = command.index("/IM")
    return command[idx + 1]


def test_get_driver_configures_edge_ie_mode(monkeypatch, ie_mode_options):
    captured: dict[str, object] = {}

    def fake_cleanup():
        captured["cleanup"] = True

    def fake_ie(service, options):
        captured["service"] = service
        captured["options"] = options
        return "fake-driver"

    class FakeService:
        def __init__(self, executable_path):
            self.executable_path = executable_path

    monkeypatch.setattr("core.browser.driver_factory.get_settings", lambda: FakeSettings())
    monkeypatch.setattr("core.browser.driver_factory.os.path.exists", lambda path: path == FakeSettings().driver_path)
    monkeypatch.setattr("core.browser.driver_factory.DriverFactory._limpar_processos_zumbis", fake_cleanup)
    monkeypatch.setattr("core.browser.driver_factory.IEService", FakeService)
    monkeypatch.setattr("core.browser.driver_factory.webdriver.Ie", fake_ie)

    driver = DriverFactory.get_driver()

    assert driver == "fake-driver"
    assert captured["cleanup"] is True
    options = captured["options"]
    capabilities = options.to_capabilities()
    ie_capabilities = capabilities["se:ieOptions"]
    assert options.attach_to_edge_chrome is False
    assert options.require_window_focus is FakeSettings().require_window_focus
    assert options.page_load_strategy == ie_mode_options.page_load_strategy
    assert ie_capabilities["ie.edgechromium"] is True
    assert ie_capabilities["ie.edgepath"] == FakeSettings().edge_path


def test_get_driver_permite_desligar_window_focus(monkeypatch):
    captured: dict[str, object] = {}

    @dataclass
    class FocusOffSettings(FakeSettings):
        require_window_focus: bool = False

    def fake_ie(service, options):
        captured["options"] = options
        return "fake-driver"

    class FakeService:
        def __init__(self, executable_path):
            self.executable_path = executable_path

    monkeypatch.setattr("core.browser.driver_factory.get_settings", lambda: FocusOffSettings())
    monkeypatch.setattr(
        "core.browser.driver_factory.os.path.exists",
        lambda path: path == FocusOffSettings().driver_path,
    )
    monkeypatch.setattr("core.browser.driver_factory.DriverFactory._limpar_processos_zumbis", lambda: None)
    monkeypatch.setattr("core.browser.driver_factory.IEService", FakeService)
    monkeypatch.setattr("core.browser.driver_factory.webdriver.Ie", fake_ie)

    driver = DriverFactory.get_driver()

    assert driver == "fake-driver"
    assert captured["options"].require_window_focus is False


def test_get_driver_reintenta_subida_do_iedriver(monkeypatch):
    chamadas_ie = {"count": 0}

    class FakeService:
        def __init__(self, executable_path):
            self.executable_path = executable_path

    def fake_ie(service, options):
        chamadas_ie["count"] += 1
        if chamadas_ie["count"] == 1:
            raise TimeoutError("startup timeout")
        return {"service": service, "options": options}

    monkeypatch.setattr("core.browser.driver_factory.get_settings", lambda: FakeSettings())
    monkeypatch.setattr("core.browser.driver_factory.os.path.exists", lambda path: path == FakeSettings().driver_path)
    monkeypatch.setattr("core.browser.driver_factory.DriverFactory._limpar_processos_zumbis", lambda: None)
    monkeypatch.setattr("core.browser.driver_factory.IEService", FakeService)
    monkeypatch.setattr("core.browser.driver_factory.webdriver.Ie", fake_ie)
    monkeypatch.setattr("core.browser.driver_factory.time.sleep", lambda *_args, **_kwargs: None)

    driver = DriverFactory.get_driver()

    assert chamadas_ie["count"] == 2
    assert driver["service"].executable_path == FakeSettings().driver_path


def test_cleanup_uses_safe_mode_by_default(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return None

    monkeypatch.delenv("PROMAX_DRIVER_CLEANUP_MODE", raising=False)
    monkeypatch.setattr("core.browser.driver_factory.subprocess.run", fake_run)

    DriverFactory._limpar_processos_zumbis()

    assert len(calls) == 1
    assert _image_name(calls[0][0]) == "IEDriverServer.exe"


def test_cleanup_can_switch_to_aggressive_mode(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return None

    monkeypatch.setenv("PROMAX_DRIVER_CLEANUP_MODE", "aggressive")
    monkeypatch.setattr("core.browser.driver_factory.subprocess.run", fake_run)

    DriverFactory._limpar_processos_zumbis()

    assert [_image_name(call) for call in calls] == ["IEDriverServer.exe", "iexplore.exe", "msedge.exe"]


