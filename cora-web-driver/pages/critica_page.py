from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class CoraCriticaPage:
    """Fluxo da consulta Critica no portal Cora."""

    def __init__(self, driver: Any, download_dir: Path) -> None:
        self.driver = driver
        self.download_dir = Path(download_dir)

    def _click_exact(self, text: str, timeout_seconds: float = 30.0) -> None:
        deep_clicked = self.driver.execute_script(
            """
            const wanted = arguments[0];
            const roots = [document];
            const seen = new Set();
            const matches = [];
            while (roots.length) {
              const root = roots.shift();
              if (!root || seen.has(root)) continue;
              seen.add(root);
              for (const el of root.querySelectorAll ? root.querySelectorAll('*') : []) {
                const text = (el.innerText || el.textContent || '').trim();
                if (text === wanted && el.offsetParent !== null) {
                  const target = el.closest('button,a,[role="button"]') || el;
                  target.click();
                  return true;
                }
                if (el.shadowRoot) roots.push(el.shadowRoot);
              }
            }
            return false;
            """,
            text,
        )
        if deep_clicked:
            return

        def visible_target(driver: Any) -> Any:
            for element in driver.find_elements(By.XPATH, f"//*[normalize-space()={_xpath_literal(text)}]"):
                if not element.is_displayed():
                    continue
                try:
                    return element.find_element(
                        By.XPATH,
                        "ancestor-or-self::*[self::button or self::a or @role='button'][1]",
                    )
                except Exception:
                    return element
            return False

        target = WebDriverWait(self.driver, timeout_seconds).until(visible_target)
        self.driver.execute_script("arguments[0].click();", target)

    def _click_contains(self, text: str, timeout_seconds: float = 30.0) -> None:
        clicked = self.driver.execute_script(
            """
            const wanted = arguments[0].toLocaleLowerCase();
            const roots = [document];
            const seen = new Set();
            while (roots.length) {
              const root = roots.shift();
              if (!root || seen.has(root)) continue;
              seen.add(root);
              for (const el of root.querySelectorAll ? root.querySelectorAll('*') : []) {
                const value = (el.innerText || el.textContent || '').trim().toLocaleLowerCase();
                const target = value.includes(wanted)
                  ? (el.matches?.('button,a,[role="button"]')
                      ? el
                      : el.closest?.('button,a,[role="button"]'))
                  : null;
                if (target && target.offsetParent !== null) {
                  target.click();
                  return true;
                }
                if (value.includes(wanted) && el.offsetParent !== null) matches.push(el);
                if (el.shadowRoot) roots.push(el.shadowRoot);
              }
            }
            matches.sort((a, b) => (a.innerText || a.textContent || '').length -
              (b.innerText || b.textContent || '').length);
            if (matches.length) {
              const el = matches[0];
              el.click();
              return true;
            }
            return false;
            """,
            text,
        )
        if clicked:
            return
        target = WebDriverWait(self.driver, timeout_seconds).until(
            lambda driver: next(
                (
                    element
                    for element in driver.find_elements(
                        By.XPATH,
                        f"//button[contains(normalize-space(), {_xpath_literal(text)})]"
                        f" | //a[contains(normalize-space(), {_xpath_literal(text)})]"
                        f" | //*[@role='button' and contains(normalize-space(), {_xpath_literal(text)})]",
                    )
                    if element.is_displayed()
                ),
                False,
            )
        )
        self.driver.execute_script("arguments[0].click();", target)

    def _switch_to_app_frame(self, timeout_seconds: float = 60.0) -> None:
        """Entra no iframe que contém as telas de consulta do Cora."""
        self.driver.switch_to.default_content()
        WebDriverWait(self.driver, timeout_seconds).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, "root-app_iframe"))
        )

    def _switch_to_shell(self) -> None:
        """Volta ao shell principal, onde fica o gerenciador de relatórios."""
        self.driver.switch_to.default_content()

    def open_consulta_pedidos(self) -> None:
        # A navegação direta deixa o fluxo determinístico e reproduz o caminho
        # Pedido > Consulta de Pedidos sem depender do estado de abertura do
        # menu lateral.
        self._switch_to_shell()
        base_url = self.driver.current_url.split("/", 3)[:3]
        self.driver.get("/".join(base_url) + "/pedidos/consulta-pedidos")
        WebDriverWait(self.driver, 60.0).until(lambda driver: "consulta-pedidos" in driver.current_url)
        self._switch_to_app_frame()
        WebDriverWait(self.driver, 60.0).until(
            lambda driver: any(
                (element.is_displayed() and element.text.strip() == "Critica")
                for element in driver.find_elements(By.XPATH, "//*[normalize-space()='Critica']")
            )
        )

    def open_critica(self) -> None:
        # A consulta salva é uma linha clicável, mas o Cora nem sempre coloca
        # o listener no próprio texto. Tentamos o texto, os ancestrais
        # interativos e, por fim, o teclado; depois confirmamos a tela de
        # configuração pelo botão "Gerar relatório".
        self._click_exact("Critica")
        if self._wait_for_text("Gerar relatório", 8.0):
            return

        candidates = self.driver.find_elements(
            By.XPATH, "//*[normalize-space()='Critica']"
        )
        for candidate in candidates:
            if not candidate.is_displayed():
                continue
            try:
                candidate.click()
            except Exception:
                pass
            if self._wait_for_text("Gerar relatório", 4.0):
                return
            self.driver.execute_script(
                """
                const el = arguments[0];
                let node = el;
                for (let i = 0; i < 5 && node; i++, node = node.parentElement) {
                  for (const type of ['pointerdown', 'mousedown', 'mouseup', 'click']) {
                    node.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
                  }
                  if (node.getAttribute && (node.getAttribute('role') === 'button' ||
                      node.hasAttribute('tabindex') || node.onclick)) break;
                }
                """,
                candidate,
            )
            if self._wait_for_text("Gerar relatório", 4.0):
                return
        raise RuntimeError("Não foi possível abrir a consulta Critica no Cora.")

    def set_delivery_date(self, delivery_date: date) -> None:
        """Set both delivery-date fields in the saved Cora query."""
        formatted = delivery_date.strftime("%d/%m/%Y")
        fields = [
            element
            for element in self.driver.find_elements(By.CSS_SELECTOR, "input")
            if _is_delivery_date_input(element)
        ]
        if len(fields) < 2:
            raise RuntimeError("Campos de data de entrega não encontrados na consulta Critica do Cora.")
        for field in fields[:2]:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", field)
            field.click()
            field.send_keys(Keys.CONTROL, "a")
            field.send_keys(formatted)
            field.send_keys("\ue007")
        # React masks the input and may not emit a change event for keyboard
        # replacement in every portal version. Dispatch both events after the
        # visible values have been entered.
        self.driver.execute_script(
            """
            for (const field of arguments[0]) {
              field.dispatchEvent(new Event('input', {bubbles: true}));
              field.dispatchEvent(new Event('change', {bubbles: true}));
              field.blur();
            }
            """,
            fields[:2],
        )

    def _wait_for_text(self, text: str, timeout_seconds: float) -> bool:
        def present(driver: Any) -> bool:
            return any(
                element.is_displayed() and element.text.strip() == text
                for element in driver.find_elements(
                    By.XPATH, f"//*[normalize-space()={_xpath_literal(text)}]"
                )
            )

        try:
            WebDriverWait(self.driver, timeout_seconds).until(present)
            return True
        except Exception:
            return False

    def generate_report(self) -> None:
        def target(driver: Any) -> Any:
            for element in driver.find_elements(
                By.XPATH,
                "//button[@role='button' and normalize-space()='Gerar relatório']"
                " | //button[@role='button'][.//*[normalize-space()='Gerar relatório']]",
            ):
                if element.is_displayed() and element.is_enabled():
                    return element
            return False

        try:
            button = WebDriverWait(self.driver, 60.0).until(target)
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", button
            )
            button.click()
        except Exception:
            # Compatibilidade com uma versão que renderiza o botão fora do
            # DOM nativo ou dentro de outro Web Component.
            self._click_exact("Gerar relatório", timeout_seconds=60.0)

    def open_report_manager(self) -> None:
        self._switch_to_shell()
        # O botão superior usa apenas a classe ``tooltip``; o rótulo fica em
        # um span interno, sem aria-label. Priorize esse elemento conhecido.
        for button in self.driver.find_elements(By.CSS_SELECTOR, "button.tooltip"):
            if "Gerenciador" in (button.text or "") and button.is_displayed():
                self.driver.execute_script("arguments[0].click();", button)
                break
        else:
            deep_clicked = self.driver.execute_script(
                """
                const roots = [document];
                const seen = new Set();
                while (roots.length) {
                  const root = roots.shift();
                  if (!root || seen.has(root)) continue;
                  seen.add(root);
                  for (const el of root.querySelectorAll ? root.querySelectorAll('*') : []) {
                    const label = `${el.getAttribute?.('aria-label') || ''} ${el.getAttribute?.('title') || ''}`;
                    if (label.includes('Gerenciador de relatórios') && el.offsetParent !== null) {
                      el.click(); return true;
                    }
                    if (el.shadowRoot) roots.push(el.shadowRoot);
                  }
                }
                return false;
                """,
            )
            if not deep_clicked:
                self._click_exact("Gerenciador de relatórios", timeout_seconds=30.0)
        try:
            WebDriverWait(self.driver, 10.0).until(
                lambda driver: any(
                    item.is_displayed()
                    and "closed" not in (item.get_attribute("class") or "")
                    for item in driver.find_elements(
                        By.CSS_SELECTOR, "[role='dialog'][aria-label*='Gerenciador']"
                    )
                )
            )
        except Exception:
            # Algumas versões do portal não definem role/aria no drawer; o
            # conteúdo ainda pode ser localizado pelos botões de download.
            pass

    def download_latest_report(self, timeout_seconds: float = 180.0) -> list[Path]:
        self._switch_to_shell()
        self.download_dir.mkdir(parents=True, exist_ok=True)
        before = {path.resolve() for path in self.download_dir.iterdir() if path.is_file()}
        deadline = time.monotonic() + timeout_seconds
        selectors = (
            "//button[.//label[normalize-space()='Baixar arquivo']]",
            "//*[@aria-label='Baixar']",
            "//*[contains(@aria-label, 'Baix')]",
            "//*[@title='Baixar']",
            "//a[@download]",
        )
        clicked = False
        # A geração é assíncrona: o drawer pode abrir vazio e só depois
        # inserir o item concluído. Portanto, procuramos o botão durante todo
        # o timeout, em vez de testar uma única vez.
        while time.monotonic() < deadline and not clicked:
            # O drawer é recriado pelo React. Busque o botão no DOM atual a
            # cada ciclo, sem reutilizar uma referência de uma div anterior.
            try:
                clicked = bool(
                    self.driver.execute_script(
                        """
                        const buttons = Array.from(document.querySelectorAll(
                          'button.sc-fpSqyW.cKRLCz'
                        )).filter(button => button.offsetParent !== null);
                        if (buttons.length) {
                          buttons[0].click();
                          return true;
                        }
                        return false;
                        """
                    )
                )
            except Exception:
                clicked = False
            if clicked:
                break
            for selector in selectors:
                visible = []
                for item in self.driver.find_elements(By.XPATH, selector):
                    try:
                        if item.is_displayed():
                            visible.append(item)
                    except Exception:
                        # O drawer atualiza a lista de relatórios de forma
                        # reativa; ignore o elemento que foi substituído e
                        # refaça a busca no próximo ciclo.
                        continue
                for item in visible:
                    try:
                        row = item.find_element(
                            By.XPATH,
                            "ancestor::*[contains(normalize-space(.), '0 Bytes')][1]",
                        )
                    except Exception:
                        pass
                    self.driver.execute_script("arguments[0].click();", item)
                    clicked = True
                    break
                if clicked:
                    break
            if clicked:
                break
            try:
                deep_result = self.driver.execute_script(
                        """
                        const roots = [document];
                        const seen = new Set();
                        const matches = [];
                        let sawZero = false;
                        while (roots.length) {
                          const root = roots.shift();
                          if (!root || seen.has(root)) continue;
                          seen.add(root);
                          for (const el of root.querySelectorAll ? root.querySelectorAll('*') : []) {
                            const text = (el.innerText || el.textContent || '').trim();
                            const label = `${el.getAttribute?.('aria-label') || ''} ${el.getAttribute?.('title') || ''}`;
                            if ((text.includes('Baixar arquivo') || label.includes('Baix') || el.hasAttribute?.('download')) && el.offsetParent !== null) {
                              const target = el.closest?.('button,a,[role="button"]') || el;
                              matches.push(target);
                            }
                            if (el.shadowRoot) roots.push(el.shadowRoot);
                          }
                        }
                        const target = matches[matches.length - 1];
                        if (target) { target.click(); return {clicked: true, sawZero}; }
                        return {clicked: false, sawZero};
                        """,
                    )
                clicked = bool(deep_result and deep_result.get("clicked"))
            except Exception:
                clicked = False
            if not clicked:
                time.sleep(0.75)
        if not clicked:
            raise RuntimeError("Botão de download não encontrado no gerenciador de relatórios.")
        while time.monotonic() < deadline:
            current = {
                path.resolve()
                for path in self.download_dir.iterdir()
                if path.is_file()
                and not path.name.endswith((".crdownload", ".tmp"))
                and path.stat().st_size > 0
            }
            created = sorted(current - before, key=lambda path: path.stat().st_mtime)
            if created:
                return created
            time.sleep(0.5)
        raise TimeoutError("O download do relatório Cora não terminou no tempo limite.")


def _xpath_literal(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ", \"'\", ".join(f"'{part}'" for part in parts) + ")"


def _is_delivery_date_input(element: Any) -> bool:
    try:
        if not element.is_displayed() or not element.is_enabled():
            return False
        label = " ".join(
            str(element.get_attribute(name) or "")
            for name in ("aria-label", "placeholder", "name", "id")
        ).casefold()
        value = str(element.get_attribute("value") or "")
        return "data de entrega" in label or bool(value and _looks_like_br_date(value))
    except Exception:
        return False


def _looks_like_br_date(value: str) -> bool:
    try:
        date.fromisoformat("-".join(reversed(value.split("/"))))
        return len(value) == 10 and value[2] == "/" and value[5] == "/"
    except (TypeError, ValueError):
        return False


def next_delivery_date(today: date, holidays: set[date] | frozenset[date] = frozenset()) -> date:
    """Return the next operational delivery date for the Cora query.

    Friday normally advances to Monday. If Saturday is the operational day
    immediately before a Sunday/Monday holiday, Friday pulls Saturday instead.
    Sundays and configured holidays are always skipped.
    """
    tomorrow = today + timedelta(days=1)
    if today.weekday() == 4:  # Friday
        saturday = tomorrow
        sunday = saturday + timedelta(days=1)
        monday = saturday + timedelta(days=2)
        if saturday not in holidays and (sunday in holidays or monday in holidays):
            candidate = saturday
        else:
            candidate = monday
    else:
        candidate = tomorrow
    while candidate.weekday() == 6 or candidate in holidays:
        candidate += timedelta(days=1)
    return candidate
