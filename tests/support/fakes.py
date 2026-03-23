from __future__ import annotations

from dataclasses import dataclass, field

from selenium.common.exceptions import NoAlertPresentException


@dataclass
class FakeElement:
    value: str = ""
    attributes: dict[str, str] = field(default_factory=dict)

    def clear(self) -> None:
        self.value = ""

    def send_keys(self, text: str) -> None:
        self.value += text

    def click(self) -> None:
        return None

    def get_attribute(self, name: str) -> str:
        if name == "value":
            return self.value
        return self.attributes.get(name, "")


class FakeAlert:
    def __init__(self, driver: "FakeDriver", text: str) -> None:
        self._driver = driver
        self.text = text

    def accept(self) -> None:
        self._driver.accepted_alerts.append(self.text)
        self._driver.alert_texts.pop(0)


class FakeSwitchTo:
    def __init__(self, driver: "FakeDriver") -> None:
        self._driver = driver
        self.default_content_calls = 0
        self.window_calls: list[str] = []

    @property
    def alert(self) -> FakeAlert:
        if not self._driver.alert_texts:
            raise NoAlertPresentException()
        return FakeAlert(self._driver, self._driver.alert_texts[0])

    def default_content(self) -> None:
        self.default_content_calls += 1

    def window(self, handle: str) -> None:
        self.window_calls.append(handle)
        self._driver.current_window_handle = handle


class FakeDriver:
    def __init__(self) -> None:
        self.current_window_handle = "menu"
        self._window_handles = ["menu"]
        self.switch_to = FakeSwitchTo(self)
        self.accepted_alerts: list[str] = []
        self.alert_texts: list[str] = []
        self.script_calls: list[str] = []
        self.script_results: dict[str, object] = {}

    @property
    def window_handles(self) -> list[str]:
        # Selenium expõe uma coleção nova a cada leitura; retornar cópia
        # evita aliasing acidental nos testes.
        return list(self._window_handles)

    @window_handles.setter
    def window_handles(self, value: list[str]) -> None:
        self._window_handles = list(value)

    def open_window(self, handle: str) -> None:
        self._window_handles = [*self._window_handles, handle]

    def execute_script(self, script: str, *args):
        self.script_calls.append(script)
        if script in self.script_results:
            result = self.script_results[script]
            return result(*args) if callable(result) else result
        return {"ok": True}

    def find_element(self, *_args, **_kwargs):
        return FakeElement()


