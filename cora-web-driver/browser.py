from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
import tempfile
from typing import Any

from config import CoraSettings
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class CoraBrowser(AbstractContextManager["CoraBrowser"]):
    """Sessão Selenium própria do Cora.

    A sessão fica separada do driver IE Mode do Promax. O login não é
    automatizado nesta camada: cada fluxo deve declarar explicitamente como a
    autenticação do Cora será fornecida e validada.
    """

    def __init__(self, settings: CoraSettings | None = None, *, driver_factory: Any = None) -> None:
        self.settings = settings or CoraSettings.from_env()
        self._driver_factory = driver_factory
        self.driver: Any = None
        self._profile_dir: tempfile.TemporaryDirectory[str] | None = None

    def start(self) -> "CoraBrowser":
        if self.driver is not None:
            return self
        if self._driver_factory is None:
            from selenium import webdriver

            options = webdriver.EdgeOptions()
            # O portal apresenta falhas quando reaproveita cookies/cache. Cada
            # job recebe um perfil descartável e uma sessão anônima nova.
            self._profile_dir = tempfile.TemporaryDirectory(prefix="cora-web-driver-")
            options.add_argument(f"--user-data-dir={self._profile_dir.name}")
            options.add_argument("--incognito")
            if self.settings.headless:
                options.add_argument("--headless=new")
            options.add_argument("--disable-notifications")
            self.settings.download_dir.mkdir(parents=True, exist_ok=True)
            options.add_experimental_option(
                "prefs",
                {
                    "download.default_directory": str(self.settings.download_dir.resolve()),
                    "download.prompt_for_download": False,
                    "download.directory_upgrade": True,
                    "safebrowsing.enabled": True,
                },
            )
            self.driver = webdriver.Edge(options=options)
        else:
            self.driver = self._driver_factory(self.settings)
        self.driver.set_page_load_timeout(self.settings.timeout_seconds)
        self.driver.delete_all_cookies()
        self.driver.get(self.settings.url)
        return self

    def close(self) -> None:
        if self.driver is not None:
            self.driver.quit()
            self.driver = None
        if self._profile_dir is not None:
            self._profile_dir.cleanup()
            self._profile_dir = None

    def login(self) -> None:
        """Executa o login federado após entrar como Revenda."""
        if not self.settings.username or not self.settings.password:
            raise RuntimeError("CORA_USER/CORA_PASS não configurados no .env do worker.")
        if self.driver is None:
            raise RuntimeError("A sessão Cora ainda não foi iniciada.")
        wait = WebDriverWait(self.driver, self.settings.timeout_seconds)
        wait.until(
            lambda driver: any(
                host in driver.current_url
                for host in ("login.microsoftonline.com", "auth.ambevdevs.com.br")
            )
        )
        if "auth.ambevdevs.com.br" in self.driver.current_url:
            email_id, password_id, submit_id = "username", "password", "kc-login"
        else:
            # Compatibilidade com o fluxo federado Microsoft usado por outras
            # opções do portal; a opção Revenda normalmente usa Keycloak.
            email_id, password_id, submit_id = "i0116", "i0118", "idSIButton9"
        email = wait.until(EC.presence_of_element_located((By.ID, email_id)))
        email.clear()
        email.send_keys(self.settings.username)
        password = wait.until(EC.presence_of_element_located((By.ID, password_id)))
        password.clear()
        password.send_keys(self.settings.password)
        wait.until(EC.element_to_be_clickable((By.ID, submit_id))).click()
        # Se a federação exigir MFA, CAPTCHA ou aprovação adicional, não
        # marcamos o job como concluído: o operador precisa concluir a etapa.
        wait.until(
            lambda driver: all(
                host not in driver.current_url
                for host in ("login.microsoftonline.com", "auth.ambevdevs.com.br")
            )
        )

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
