import os

from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.config.settings import get_settings
from pages.common.base_page import BasePage
from pages.common.menu_page import MenuPage


class LoginPage(BasePage):
    LOCATOR_USUARIO = (By.XPATH, "//*[@name='Usuario']")
    LOCATOR_SENHA = (By.XPATH, "//*[@name='Senha']")
    LOCATOR_BTN_CONFIRMA = (By.XPATH, "//*[@name='cmdConfirma']")
    LOCATOR_UNIDADE = (By.XPATH, "//*[@name='unidade']")

    JS_SET_VALUE_IE = """
    var el = arguments[0];
    var val = arguments[1];
    try {
        try { el.scrollIntoView(true); } catch(e) {}
        try { el.focus(); } catch(e) {}
        el.value = val;
        if (document.createEvent) {
            var ev1 = document.createEvent('HTMLEvents'); ev1.initEvent('input', true, true); el.dispatchEvent(ev1);
            var ev2 = document.createEvent('HTMLEvents'); ev2.initEvent('change', true, true); el.dispatchEvent(ev2);
            var ev3 = document.createEvent('HTMLEvents'); ev3.initEvent('blur', true, true); el.dispatchEvent(ev3);
        } else if (el.fireEvent) {
            try { el.fireEvent('oninput'); } catch(e) {}
            try { el.fireEvent('onchange'); } catch(e) {}
            try { el.fireEvent('onblur'); } catch(e) {}
        }
        return { ok: true, value: el.value };
    } catch (e) {
        return { ok: false, error: (e && e.message) ? e.message : String(e) };
    }
    """

    JS_CLICK_IE = """
    var el = arguments[0];
    try {
        try { el.scrollIntoView(true); } catch(e) {}
        try { el.focus(); } catch(e) {}
        if (el.click) { el.click(); } else if (el.fireEvent) { el.fireEvent('onclick'); }
        return { ok: true };
    } catch (e) {
        return { ok: false, error: (e && e.message) ? e.message : String(e) };
    }
    """

    def __init__(self, driver):
        super().__init__(driver)
        self.settings = get_settings()
        self.url_promax = self.settings.promax_url
        self._carregar_mapa_unidades()

    def _carregar_mapa_unidades(self):
        self.mapa_unidades = {}
        excluir = {"PROMAX_URL", "DRIVER_PATH", "DOWNLOAD_DIR", "PROMAX_USER", "PROMAX_PASS"}
        for k, v in os.environ.items():
            if k in excluir or not v:
                continue
            v_norm = v.strip()
            if v_norm.isdigit() and 6 <= len(v_norm) <= 10:
                self.mapa_unidades[k.strip().upper()] = v_norm

    def fazer_login(self, usuario, senha, nome_unidade=None):
        self.logger.info(f"--- LOGIN PROMAX (Unidade: {nome_unidade}) ---")
        if not self.url_promax:
            raise ValueError("PROMAX_URL não definida na configuração")
        self.driver.get(self.url_promax)

        if len(self.driver.window_handles) > 1:
            self.logger.warning(f"Janelas detectadas: {len(self.driver.window_handles)}. Focando na última.")
            self.driver.switch_to.window(self.driver.window_handles[-1])

        self.logger.info("Aguardando carregamento inicial...")

        frames = self.driver.find_elements(By.TAG_NAME, "frame") + self.driver.find_elements(By.TAG_NAME, "iframe")
        frame_index = None

        try:
            if frames:
                frame_index = 0
                self.wait.until(EC.frame_to_be_available_and_switch_to_it(frame_index))
                self.logger.info(f"Entrou no frame index={frame_index}")
            else:
                self.logger.info("Nenhum frame detectado. Tentando login na raiz.")
        except Exception as e:
            self.logger.warning(f"Falha ao entrar no frame, tentando seguir na raiz: {e}")

        try:
            campo_usuario, campo_senha, botao_confirma, frame_index = self._localizar_campos_login_js(
                timeout=20,
                frame_index_inicial=frame_index,
            )

            self.driver.execute_script(self.JS_SET_VALUE_IE, campo_usuario, usuario)
            self.driver.execute_script(self.JS_SET_VALUE_IE, campo_senha, senha)
            self.driver.execute_script(self.JS_CLICK_IE, botao_confirma)

            self.logger.info("Credenciais enviadas.")
        except Exception as e:
            self.logger.error("Erro ao localizar/interagir com campos de login.")
            raise e

        codigo_unidade = self.mapa_unidades.get(nome_unidade.upper()) if nome_unidade else None

        if codigo_unidade:
            self.logger.info(f"Selecionando unidade: {nome_unidade} ({codigo_unidade})")

            if frame_index is not None:
                try:
                    self.switch_to_default_content()
                except UnexpectedAlertPresentException:
                    self.logger.warning("Alerta bloqueando a saída do frame. Tentando aceitar...")
                    try:
                        self.driver.switch_to.alert.accept()
                        self.switch_to_default_content()
                        self.wait_for_no_alert(timeout=2)
                    except Exception as alert_error:
                        self.logger.warning(f"Não foi possível limpar o alerta ao sair do frame: {alert_error}")
                except Exception as e:
                    self.logger.error(f"Erro inesperado ao tentar sair do frame: {e}")

                try:
                    self.wait.until(EC.frame_to_be_available_and_switch_to_it(frame_index))
                except Exception as e:
                    self.logger.warning(f"Não foi possível retornar ao frame de login: {e}")

            try:
                frame_index = self._selecionar_unidade_login_js(
                    codigo_unidade,
                    frame_index_inicial=frame_index,
                    timeout=15,
                )
                unidade_confirmada = False
                try:
                    self._confirmar_selecao_unidade(codigo_unidade, frame_index=frame_index, timeout=2)
                    unidade_confirmada = True
                    self.logger.info("Unidade selecionada via JS.")
                except Exception as e:
                    self.logger.info(f"Confirmação da unidade não estabilizou antes do clique final: {e}")

                try:
                    if frame_index is not None:
                        self.switch_to_default_content()
                        self.wait.until(EC.frame_to_be_available_and_switch_to_it(frame_index))

                    self._clicar_confirmar_login_js()
                    if unidade_confirmada:
                        self.logger.info("Segunda confirmação clicada via JS com unidade previamente confirmada.")
                    else:
                        self.logger.info("Segunda confirmação clicada via JS mesmo sem estabilização explícita da unidade.")
                except Exception as e:
                    self.logger.warning(f"Não foi possível acionar a segunda confirmação do login: {e}")
            except Exception as e:
                self.logger.warning(f"Erro no fluxo de unidade: {e}")

        self.logger.info("Aguardando alertas de sistema (Dia 15, Estoque, etc)...")
        self.lidar_com_alertas(tentativas=2, timeout=4, timeout_entre_alertas=1, max_alertas=10)

        try:
            self.switch_to_default_content()
        except UnexpectedAlertPresentException:
            self.logger.warning("Novo alerta detectado após a rotina principal de tratamento. Tentando drenar novamente...")
            self.lidar_com_alertas(tentativas=2, timeout=1, timeout_entre_alertas=1, max_alertas=5)
            self.switch_to_default_content()

        self._aguardar_menu_disponivel(timeout=10)

        try:
            self.switch_to_default_content()
        except UnexpectedAlertPresentException:
            self.logger.warning("Alerta detectado ao sair do frame final. Aceitando...")
            try:
                self.driver.switch_to.alert.accept()
                self.switch_to_default_content()
                self.wait_for_no_alert(timeout=2)
            except Exception as e:
                self.logger.warning(f"Não foi possível limpar o alerta final do login: {e}")

        self._limpar_janelas_extras()
        self.logger.info("Login concluido sem validacao visual obrigatoria.")
        return MenuPage(self.driver)

    def _localizar_campos_login_js(self, timeout=20, frame_index_inicial=None):
        primeiro_aviso = {"emitido": False}

        def _procurar(driver):
            for contexto in self._contextos_login(frame_index_inicial):
                try:
                    driver.switch_to.default_content()
                    if contexto is not None:
                        WebDriverWait(driver, 2, poll_frequency=0.2).until(
                            EC.frame_to_be_available_and_switch_to_it(contexto)
                        )

                    campo_usuario = self._elemento_por_name_ou_id_js("Usuario")
                    campo_senha = self._elemento_por_name_ou_id_js("Senha")
                    botao_confirma = self._elemento_por_name_ou_id_js("cmdConfirma")
                    if campo_usuario and campo_senha and botao_confirma:
                        self.logger.info(
                            "Campos de login localizados via JS no contexto: %s",
                            "raiz" if contexto is None else f"frame index={contexto}",
                        )
                        return campo_usuario, campo_senha, botao_confirma, contexto
                except Exception:
                    continue

            if not primeiro_aviso["emitido"]:
                self.logger.warning(
                    "Campos de login nao encontrados no primeiro contexto. Varrendo raiz e frames via JS."
                )
                primeiro_aviso["emitido"] = True
            return False

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.5).until(_procurar)
        except TimeoutException as exc:
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass
            raise TimeoutException(
                "Campos de login Usuario/Senha/cmdConfirma nao foram encontrados via JS"
            ) from exc

    def _contextos_login(self, frame_index_inicial=None):
        contextos = []
        if frame_index_inicial is not None:
            contextos.append(frame_index_inicial)
        contextos.append(None)

        try:
            self.driver.switch_to.default_content()
            frames = self.driver.find_elements(By.TAG_NAME, "frame") + self.driver.find_elements(By.TAG_NAME, "iframe")
            contextos.extend(range(len(frames)))
        except Exception:
            pass

        unicos = []
        for contexto in contextos:
            if contexto not in unicos:
                unicos.append(contexto)
        return unicos

    def _elemento_por_name_ou_id_js(self, nome):
        return self.driver.execute_script(
            """
            var nome = arguments[0];
            var lower = String(nome).toLowerCase();
            return document.getElementsByName(nome)[0]
                || document.getElementById(nome)
                || document.getElementsByName(lower)[0]
                || document.getElementById(lower)
                || null;
            """,
            nome,
        )

    def _elemento_por_locator_js(self, locator):
        by, value = locator
        return self.driver.execute_script(
            """
            var by = arguments[0];
            var value = arguments[1];
            try {
                if (by === 'name') {
                    return document.getElementsByName(value)[0] || null;
                }
                if (by === 'id') {
                    return document.getElementById(value) || null;
                }
                if (by === 'xpath') {
                    return document.evaluate(
                        value,
                        document,
                        null,
                        XPathResult.FIRST_ORDERED_NODE_TYPE,
                        null
                    ).singleNodeValue || null;
                }
                return null;
            } catch (e) {
                return null;
            }
            """,
            by,
            value,
        )

    def _clicar_confirmar_login_js(self):
        resultado = self.driver.execute_script(
            """
            var btn = document.getElementsByName('cmdConfirma')[0]
                || document.getElementById('cmdConfirma')
                || document.getElementsByName('CmdConfirma')[0]
                || null;
            if (!btn) return {ok:false, error:'cmdConfirma-not-found'};
            try {
                try { btn.focus(); } catch(e) {}
                if (btn.click) btn.click();
                else if (btn.fireEvent) btn.fireEvent('onclick');
                return {ok:true};
            } catch(e) {
                return {ok:false, error:String(e)};
            }
            """
        )
        if not resultado or not resultado.get("ok"):
            raise RuntimeError(f"Falha ao clicar confirmacao do login via JS: {resultado}")
        return True

    def _selecionar_unidade_login_js(self, codigo_unidade, frame_index_inicial=None, timeout=15):
        ultimo_resultado = {"ok": False, "error": "nao-executado"}

        def _procurar_e_selecionar(driver):
            nonlocal ultimo_resultado
            for contexto in self._contextos_login(frame_index_inicial):
                try:
                    driver.switch_to.default_content()
                    if contexto is not None:
                        WebDriverWait(driver, 2, poll_frequency=0.2).until(
                            EC.frame_to_be_available_and_switch_to_it(contexto)
                        )

                    resultado = self._selecionar_unidade_no_contexto_js(codigo_unidade)
                    ultimo_resultado = resultado or {"ok": False, "error": "sem-retorno-js"}
                    if resultado and resultado.get("ok"):
                        self.logger.info(
                            "Unidade selecionada via JS no login: %s (contexto: %s)",
                            codigo_unidade,
                            "raiz" if contexto is None else f"frame index={contexto}",
                        )
                        return "__ROOT__" if contexto is None else f"__FRAME__:{contexto}"
                except Exception as exc:
                    ultimo_resultado = {"ok": False, "error": str(exc).split("\n")[0]}
                    continue
            return False

        try:
            contexto = WebDriverWait(self.driver, timeout, poll_frequency=0.5).until(
                _procurar_e_selecionar
            )
            if contexto == "__ROOT__":
                return None
            if isinstance(contexto, str) and contexto.startswith("__FRAME__:"):
                return int(contexto.split(":", 1)[1])
            return contexto
        except TimeoutException as exc:
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass
            raise RuntimeError(
                f"Falha ao selecionar unidade do login via JS: {ultimo_resultado}"
            ) from exc

    def _selecionar_unidade_no_contexto_js(self, codigo_unidade):
        return self.driver.execute_script(
            """
            var codigo = String(arguments[0]);
            var sel = document.getElementsByName('unidade')[0]
                || document.getElementById('unidade')
                || null;
            if (!sel || !sel.options) return {ok:false, error:'unidade-select-not-found'};

            var encontrou = false;
            for (var i = 0; i < sel.options.length; i++) {
                if (String(sel.options[i].value).replace(/^\\s+|\\s+$/g, '') === codigo) {
                    sel.selectedIndex = i;
                    encontrou = true;
                    break;
                }
            }
            if (!encontrou) return {ok:false, error:'unidade-not-found', value:codigo};

            try { sel.focus(); } catch(e) {}
            if (document.createEvent) {
                var ev = document.createEvent('HTMLEvents');
                ev.initEvent('change', true, true);
                sel.dispatchEvent(ev);
            } else if (sel.fireEvent) {
                sel.fireEvent('onchange');
            }
            return {ok:true, value:sel.value};
            """,
            codigo_unidade,
        )

    def _confirmar_selecao_unidade(self, codigo_unidade, frame_index=None, timeout=6):
        codigo_unidade = str(codigo_unidade).strip()

        def _unidade_confirmada(driver):
            try:
                if self._menu_ja_disponivel(driver):
                    return True

                if frame_index is not None:
                    driver.switch_to.default_content()
                    WebDriverWait(driver, 1, poll_frequency=0.2).until(
                        EC.frame_to_be_available_and_switch_to_it(frame_index)
                    )

                try:
                    combo = self._elemento_por_locator_js(self.LOCATOR_UNIDADE)
                    if not combo:
                        return self._menu_ja_disponivel(driver)
                except Exception:
                    return self._menu_ja_disponivel(driver)

                valor_atual = str(combo.get_attribute("value") or "").strip()
                return valor_atual == codigo_unidade
            except Exception:
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass
                return False

        try:
            WebDriverWait(self.driver, timeout, poll_frequency=0.2).until(_unidade_confirmada)
        except TimeoutException as exc:
            raise TimeoutException(f"Timeout aguardando confirmação da unidade '{codigo_unidade}'") from exc
        finally:
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass

    def _menu_ja_disponivel(self, driver):
        try:
            driver.switch_to.default_content()
            WebDriverWait(driver, 1, poll_frequency=0.2).until(
                EC.frame_to_be_available_and_switch_to_it("top")
            )
            WebDriverWait(driver, 1, poll_frequency=0.2).until(
                EC.frame_to_be_available_and_switch_to_it(0)
            )
            if not self._elemento_por_locator_js((By.ID, "atalho")):
                return False
            driver.switch_to.default_content()
            return True
        except Exception:
            try:
                driver.switch_to.default_content()
            except Exception:
                pass
            return False

    def _aguardar_menu_disponivel(self, timeout=10):
        try:
            WebDriverWait(self.driver, timeout, poll_frequency=0.3).until(self._menu_ja_disponivel)
        except TimeoutException as exc:
            raise RuntimeError("Menu principal não ficou disponível após o login") from exc

    def _limpar_janelas_extras(self):
        try:
            if not self.driver.window_handles:
                return

            atual = self.driver.current_window_handle
            for h in self.driver.window_handles:
                if h != atual:
                    self.driver.switch_to.window(h)
                    self.driver.close()
            self.driver.switch_to.window(atual)
        except Exception as e:
            self.logger.warning(f"Falha ao limpar janelas extras após o login: {e}")

