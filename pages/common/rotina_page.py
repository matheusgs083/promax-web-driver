import time
import os
import datetime as dt  # <-- CORRIGIDO: Usando apelido dt para evitar conflitos
import csv
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoAlertPresentException, UnexpectedAlertPresentException
from pages.common.base_page import BasePage
from core.execution.execution_result import ExecutionResult, ExecutionStatus, normalize_execution_result
from core.config.settings import get_settings

try:
    from core.services.report_download_service import capturar_download_relatorio as salvar_arquivo_visual
    from core.observability.relatorio_execucao import tracker
    validar_elemento = True
except ImportError:
    salvar_arquivo_visual = None
    validar_elemento = None
    # Fallback seguro caso o tracker não exista ainda
    class MockTracker:
        def anotar(self, *args, **kwargs): pass
    tracker = MockTracker()

class RotinaPage(BasePage):
    """
    Classe base para todas as janelas de rotina.
    """

    # --- LOCATORS ---
    FRAME_TOP_ROTINA = "top_rotina"
    LOCATOR_UNIDADE = (By.NAME, "unidade")
    FRAME_ROTINA = 1
    BTN_GERA_EXCEL_1 = (By.NAME, "GerExecl")
    BTN_GERA_EXCEL_2 = (By.NAME, "GeraExcel")
    ALERTA_ERRO_UNIDADE_KEYWORDS = (
        "erro",
        "falha",
        "inválid",
        "invalida",
        "invalido",
        "não encontrada",
        "nao encontrada",
        "não existe",
        "nao existe",
        "não pertence",
        "nao pertence",
        "não autoriz",
        "nao autoriz",
        "acesso negado",
        "sem acesso",
        "bloquead",
        "não cadastr",
        "nao cadastr",
        "inconsisten",
    )

    def __init__(self, driver, handle_menu_original):
        super().__init__(driver)
        self.handle_menu = handle_menu_original
        self.subpasta_download = None
        
        try:
            self.driver.switch_to.window(self.driver.current_window_handle)
            self.driver.maximize_window()
        except Exception as e:
            self.logger.debug(f"Não foi possível maximizar/focar a janela da rotina: {e}")
        
        try:
            atual = self.obter_unidade_atual()
            self.logger.info(f"Janela aberta. Unidade ativa: {atual}")
        except Exception as e:
            self.logger.debug(f"Não foi possível ler a unidade ativa ao abrir a rotina: {e}")

    def _entrar_frame_topo(self):
        self.switch_to_default_content()
        try:
            self.wait.until(EC.frame_to_be_available_and_switch_to_it(self.FRAME_TOP_ROTINA))
        except Exception as e:
            self.logger.debug(f"Falha ao entrar no frame '{self.FRAME_TOP_ROTINA}', usando fallback frame[0]: {e}")
            self.driver.switch_to.default_content()
            self.driver.switch_to.frame(0)

    def obter_unidade_atual(self):
        self._entrar_frame_topo()
        js = "var els=document.getElementsByName('unidade'); if(els && els.length>0) return els[0].value; return null;"
        return self.driver.execute_script(js)

    def listar_unidades(self):
        self._entrar_frame_topo()
        try:
            el_select = self.wait.until(EC.presence_of_element_located(self.LOCATOR_UNIDADE))
            js_listar = """
            var sel = arguments[0];
            var lista = [];
            if (!sel || !sel.options) return [];
            for (var i = 0; i < sel.options.length; i++) {
                var opt = sel.options[i];
                var val = opt.value;
                if (val) {
                    var valClean = val.replace(/^\\s+|\\s+$/g, '');
                    if (valClean !== "") {
                        lista.push({'texto': opt.text, 'valor': val});
                    }
                }
            }
            return lista;
            """
            return self.driver.execute_script(js_listar, el_select)
        except Exception as e:
            self.logger.error(f"Erro ao listar unidades: {e}")
            return []

    def _extrair_falha_troca_unidade(self, mensagens_alerta):
        for mensagem in mensagens_alerta or []:
            texto = str(mensagem).strip()
            texto_normalizado = texto.lower()
            if any(keyword in texto_normalizado for keyword in self.ALERTA_ERRO_UNIDADE_KEYWORDS):
                return texto
        return None

    def selecionar_unidade(self, valor_unidade):
        """
        Seleciona unidade, drena alertas residuais e confirma a troca pelo estado real da tela.
        """
        valor_unidade = str(valor_unidade).strip()
        unidade_atual = None

        try:
            unidade_atual = self.obter_unidade_atual()
            if unidade_atual and str(unidade_atual).strip() == valor_unidade:
                self.logger.info(f"Unidade {valor_unidade} ja selecionada.")
                return
        except UnexpectedAlertPresentException:
            try:
                self.driver.switch_to.alert.accept()
                self.wait_for_no_alert(timeout=2)
            except Exception as e:
                self.logger.warning(f"Falha ao limpar alerta durante leitura da unidade atual: {e}")

        self._entrar_frame_topo()
        self.logger.info(f"--- Trocando Unidade para: {valor_unidade} ---")
        if not self.selecionar_combo_js(self.LOCATOR_UNIDADE, valor_unidade):
            raise RuntimeError(f"Unidade '{valor_unidade}' nao encontrada no combo da rotina.")

        self.logger.info("Monitorando alertas pos-troca...")
        alertas = self.lidar_com_alertas(tentativas=2, timeout=3, timeout_entre_alertas=1, max_alertas=10)
        falha_alerta = self._extrair_falha_troca_unidade(alertas)
        if falha_alerta:
            raise RuntimeError(
                f"Falha detectada na troca de unidade para '{valor_unidade}': {falha_alerta}"
            )

        self._confirmar_unidade_ativa(valor_unidade, timeout=10)

    def fechar_e_voltar(self):
        try:
            self.driver.close()
        except Exception as e:
            self.logger.warning(f"Falha ao fechar a janela da rotina antes de voltar ao menu: {e}")
        self.driver.switch_to.window(self.handle_menu)
        self.switch_to_default_content()
        from pages.common.menu_page import MenuPage
        return MenuPage(self.driver)

    def _confirmar_unidade_ativa(self, valor_unidade, timeout=5):
        valor_unidade = str(valor_unidade).strip()
        prazo = time.time() + timeout
        ultimo_valor_lido = None
        ultimo_alerta_erro = None

        while time.time() < prazo:
            try:
                atual = self.obter_unidade_atual()
                ultimo_valor_lido = str(atual).strip() if atual is not None else None
                if ultimo_valor_lido == valor_unidade:
                    self.logger.info(f"Unidade confirmada com sucesso: {valor_unidade}")
                    return
            except UnexpectedAlertPresentException:
                self.logger.warning("Alerta tardio detectado durante confirmacao da unidade. Drenando...")
                alertas = self.lidar_com_alertas(
                    tentativas=1,
                    timeout=1,
                    timeout_entre_alertas=1,
                    max_alertas=5,
                )
                ultimo_alerta_erro = self._extrair_falha_troca_unidade(alertas) or ultimo_alerta_erro
                if ultimo_alerta_erro:
                    raise RuntimeError(
                        f"Falha detectada na confirmacao da unidade '{valor_unidade}': {ultimo_alerta_erro}"
                    )
            except NoAlertPresentException:
                pass
            except Exception as e:
                self.logger.debug(f"Aguardando estabilizacao da unidade {valor_unidade}: {e}")
            finally:
                try:
                    self.switch_to_default_content()
                except Exception:
                    pass

            time.sleep(0.3)

        if ultimo_alerta_erro:
            detalhe = f"Ultimo alerta de erro detectado: '{ultimo_alerta_erro}'"
        elif ultimo_valor_lido is not None:
            detalhe = f"Ultimo valor lido: '{ultimo_valor_lido}'"
        else:
            detalhe = "Nenhum valor de unidade foi lido apos a troca"
        raise TimeoutException(f"Timeout aguardando confirmacao da unidade '{valor_unidade}'. {detalhe}")

    def entrar_frame_rotina_blindado(self, frame_index: int = 1, timeout: int = 15):
        """
        Abstrai o padrão repetido de entrada no frame da rotina:
        - switch_to_default_content
        - wait frame
        - trata alertas residuais
        - fallback switch_to.frame
        """
        self.switch_to_default_content()
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.frame_to_be_available_and_switch_to_it(frame_index)
            )
        except UnexpectedAlertPresentException:
            self.lidar_com_alertas()
            self.switch_to_default_content()
            self.driver.switch_to.frame(frame_index)
        except TimeoutException:
            self.driver.switch_to.frame(frame_index)

    def aguardar_formulario_rotina(self, nome_campo: str, timeout: int = 15, frame_index: int | None = None):
        frame = self.FRAME_ROTINA if frame_index is None else frame_index
        self.entrar_frame_rotina_blindado(frame, timeout=timeout)
        self.wait_until(EC.presence_of_element_located((By.NAME, nome_campo)), timeout=timeout)
        return True

    def aguardar_loader_oculto(self, timeout: int = 5):
        try:
            self.wait_for_js_condition(
                "var el = document.getElementById('imgWait'); return !el || el.style.display === 'none';",
                timeout=timeout,
                description="loader principal oculto",
            )
            return True
        except TimeoutException:
            return False

    def loop_unidades(
        self,
        nome_arquivo: str,
        fn_execucao_unica,
        unidades_alvo: list = None,
        sleep_entre: float = 2.0,
        tentativas_alertas: int = 5,
        timeout_alertas: int = 20,
    ):
        self.logger.info("--- LOOP AUTOMÁTICO DE UNIDADES ---")
        todas_unidades = self.listar_unidades()
        if not todas_unidades:
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message="Nenhuma unidade foi encontrada na tela para processamento",
            )

        # --- LÓGICA DE FILTRAGEM (Aceita a Lista de Números) ---
        if unidades_alvo:
            alvos_limpos = [str(u).strip() for u in unidades_alvo]
            
            # Filtra a lista mantendo apenas os códigos (números) que você pediu
            unidades = [u for u in todas_unidades if str(u.get("valor", "")).strip() in alvos_limpos]
            
            if not unidades:
                self.logger.warning(f"Nenhuma unidade alvo {alvos_limpos} foi encontrada na tela.")
                return ExecutionResult(
                    status=ExecutionStatus.BUSINESS_FAILURE,
                    message=f"Nenhuma unidade alvo {alvos_limpos} foi encontrada na tela",
                )
                
            self.logger.info(f"Filtro ativo! Rodando apenas para {len(unidades)} unidade(s).")
        else:
            unidades = todas_unidades

        # Extrai o nome da rotina dinamicamente (ex: Relatorio0513Page -> Rotina 0513)
        rotina_nome = self.__class__.__name__.replace("Page", "").replace("Relatorio", "Rotina ")
        resultados = []
        falhas_negocio = 0
        falhas_tecnicas = 0

        for i, item in enumerate(unidades):
            cod = str(item.get("valor", "")).strip()
            texto = item.get("texto", cod)
            self.logger.info(f"===> [{i+1}/{len(unidades)}] Unidade: {texto} ({cod})")

            base, ext = os.path.splitext(nome_arquivo)
            ext = ext or ".csv"
            nome_por_unidade = f"{base}_{cod}{ext}"

            # MARCA O TEMPO INICIAL DA UNIDADE
            inicio_unidade = time.time()

            try:
                # Recebe o retorno da sua função de geração de relatório
                resultado = fn_execucao_unica(cod, nome_por_unidade)
                
                # CALCULA A DURAÇÃO
                duracao_unidade = time.time() - inicio_unidade
                
                # Desempacota o resultado para o relatório consolidado
                resultado_normalizado = normalize_execution_result(
                    resultado,
                    success_message="Unidade processada com sucesso",
                    failure_message="Falha na execução (retornou False)",
                )
                ok = resultado_normalizado.ok
                motivo = resultado_normalizado.message

                # Loga no arquivo CSV Tracker (agora passando a duracao)
                if ok:
                    tracker.anotar(rotina_nome, cod, "SUCESSO", motivo, duracao_unidade)
                else:
                    tracker.anotar(rotina_nome, cod, "FALHA DOWNLOAD", motivo, duracao_unidade)
                    falhas_negocio += 1

                resultados.append(ok)
                time.sleep(sleep_entre)
                
            except Exception as e:
                # Calcula a duração mesmo se der erro rápido
                duracao_unidade = time.time() - inicio_unidade
                
                # Captura erros bloqueantes como "Nenhuma informação encontrada"
                msg_erro = str(e).split('\n')[0]
                self.logger.error(f"Erro na unidade {cod}: {msg_erro}")
                
                # Loga o erro no arquivo CSV Tracker
                tracker.anotar(rotina_nome, cod, "ERRO SISTEMA", msg_erro, duracao_unidade)
                
                self.lidar_com_alertas(tentativas=tentativas_alertas, timeout=timeout_alertas)
                resultados.append(False)
                falhas_tecnicas += 1

        total_unidades = len(unidades)
        sucessos = sum(1 for item in resultados if item)

        if sucessos == total_unidades:
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Todas as {total_unidades} unidade(s) foram processadas com sucesso",
            )

        if sucessos > 0:
            return ExecutionResult(
                status=ExecutionStatus.PARTIAL_SUCCESS,
                message=(
                    f"Execução parcial: {sucessos}/{total_unidades} unidade(s) com sucesso, "
                    f"{falhas_negocio} falha(s) de negócio e {falhas_tecnicas} falha(s) técnica(s)"
                ),
            )

        status = ExecutionStatus.TECHNICAL_FAILURE if falhas_tecnicas else ExecutionStatus.BUSINESS_FAILURE
        return ExecutionResult(
            status=status,
            message=(
                f"Nenhuma unidade processada com sucesso. "
                f"{falhas_negocio} falha(s) de negócio e {falhas_tecnicas} falha(s) técnica(s)"
            ),
        )

    # ======================
    # JS HELPERS (sem duplicar por Page)
    # ======================

    JS_SET_VALUE_IE = """var el = arguments[0]; var val = arguments[1]; try { try { el.scrollIntoView(true); } catch(e) {} try { el.focus(); } catch(e) {} el.value = val; if (document.createEvent) { var ev1 = document.createEvent('HTMLEvents'); ev1.initEvent('input', true, true); el.dispatchEvent(ev1); var ev2 = document.createEvent('HTMLEvents'); ev2.initEvent('change', true, true); el.dispatchEvent(ev2); var ev3 = document.createEvent('HTMLEvents'); ev3.initEvent('blur', true, true); el.dispatchEvent(ev3); } else if (el.fireEvent) { try { el.fireEvent('oninput'); } catch(e) {} try { el.fireEvent('onchange'); } catch(e) {} try { el.fireEvent('onblur'); } catch(e) {} } return { ok: true, value: el.value }; } catch (e) { return { ok: false, error: (e && e.message) ? e.message : String(e) }; }"""
    JS_CLICK_IE = """var el = arguments[0]; try { try { el.scrollIntoView(true); } catch(e) {} try { el.focus(); } catch(e) {} if (el.click) { el.click(); } else if (el.fireEvent) { el.fireEvent('onclick'); } return { ok: true }; } catch (e) { return { ok: false, error: (e && e.message) ? e.message : String(e) }; }"""
    JS_RADIO_BY_NAME = """var name = arguments[0]; var val = arguments[1]; try { var els = document.getElementsByName(name); if (!els || !els.length) return { ok:false, error:"no-elements" }; for (var i=0; i<els.length; i++) { var el = els[i]; if ((el.value || "") == val) { try { el.scrollIntoView(true); } catch(e) {} try { el.focus(); } catch(e) {} el.checked = true; if (el.click) { el.click(); } else if (el.fireEvent) { el.fireEvent('onclick'); } if (document.createEvent) { var ev = document.createEvent('HTMLEvents'); ev.initEvent('change', true, true); el.dispatchEvent(ev); } else if (el.fireEvent) { try { el.fireEvent('onchange'); } catch(e) {} } return { ok:true, chosen: val }; } } return { ok:false, error:"value-not-found", wanted: val }; } catch(e) { return { ok:false, error:(e && e.message) ? e.message : String(e) }; }"""
    JS_SELECT_BY_NAME = """var name = arguments[0]; var val = arguments[1]; try { var els = document.getElementsByName(name); if (!els || !els.length) return { ok:false, error:"no-select" }; var el = els[0]; try { el.scrollIntoView(true); } catch(e) {} try { el.focus(); } catch(e) {} el.value = val; if (document.createEvent) { var ev = document.createEvent('HTMLEvents'); ev.initEvent('change', true, true); el.dispatchEvent(ev); } else if (el.fireEvent) { try { el.fireEvent('onchange'); } catch(e) {} } return { ok:true, value: el.value }; } catch(e) { return { ok:false, error:(e && e.message) ? e.message : String(e) }; }"""

        
    JS_CHECKED_BY_NAME_VALUE = """
    var name = arguments[0], value = arguments[1], desired = arguments[2], forceClick = arguments[3];
    try {
        var els = document.getElementsByName(name);
        if (!els || !els.length) return { ok:false, error:"no-elements" };
        var target = null;
        for (var i=0; i<els.length; i++) {
            if ((els[i].value || "") == value) { target = els[i]; break; }
        }
        if (!target) return { ok:false, error:"value-not-found", wanted:value };
        try { target.scrollIntoView(true); target.focus(); } catch(e) {}
        if (forceClick && target.checked !== desired) {
            if (target.click) target.click(); else if (target.fireEvent) target.fireEvent('onclick');
        }
        target.checked = desired;
        if (document.createEvent) {
            var ev = document.createEvent('HTMLEvents'); ev.initEvent('change', true, true);
            target.dispatchEvent(ev);
        }
        return { ok:true, checked: target.checked };
    } catch(e) { return { ok:false, error: String(e) }; }
    """


    JS_CHECKBOX_BY_NAME = """
    var name = arguments[0];
    var desired = arguments[1]; // true/false
    var forceClick = arguments[2]; // true/false
    try {
        var els = document.getElementsByName(name);
        if (!els || !els.length) return { ok:false, error:"no-elements" };
        var el = els[0];
        try { el.scrollIntoView(true); } catch(e) {}
        try { el.focus(); } catch(e) {}

        if (forceClick) {
            if (el.checked !== desired) {
                if (el.click) { el.click(); }
                else if (el.fireEvent) { el.fireEvent('onclick'); }
            }
        }
        el.checked = desired;

        if (document.createEvent) {
            var ev = document.createEvent('HTMLEvents');
            ev.initEvent('change', true, true);
            el.dispatchEvent(ev);
        } else if (el.fireEvent) {
            try { el.fireEvent('onchange'); } catch(e) {}
        }
        return { ok:true, checked: el.checked };
    } catch(e) {
        return { ok:false, error:(e && e.message) ? e.message : String(e) };
    }
    """

    def js_click_ie(self, element):
        res = self.driver.execute_script(self.JS_CLICK_IE, element)
        if not res or not res.get("ok"):
            raise RuntimeError(f"Falha click IE: {res}")
        return True

    def js_set_input_by_name(self, name: str, value):
        if value is None:
            return
        el = self.find_element((By.NAME, name))
        res = self.driver.execute_script(self.JS_SET_VALUE_IE, el, str(value))
        if not res or not res.get("ok"):
            raise RuntimeError(f"Falha set input {name}={value}: {res}")

    def js_set_select_by_name(self, name: str, value):
        if value is None:
            return
        res = self.driver.execute_script(self.JS_SELECT_BY_NAME, name, str(value))
        if not res or not res.get("ok"):
            raise RuntimeError(f"Falha select {name}={value}: {res}")

    def js_set_radio_by_name(self, name: str, value):
        if value is None:
            return
        res = self.driver.execute_script(self.JS_RADIO_BY_NAME, name, str(value))
        if not res or not res.get("ok"):
            raise RuntimeError(f"Falha radio {name}={value}: {res}")

    def js_set_checkbox_by_name(self, name: str, checked: bool, force_click: bool = True):
        if checked is None:
            return
        res = self.driver.execute_script(self.JS_CHECKBOX_BY_NAME, name, bool(checked), bool(force_click))
        if not res or not res.get("ok"):
            raise RuntimeError(f"Falha checkbox {name}={checked}: {res}")

    def _fluxo_exportar_csv(
        self,
        timeout_csv,
        nome_arquivo,
        frame_index=None,
        locators_export=None,
        timeout_botao=30,
    ):
        """
        Fluxo padrão pós-Visualizar:
        - entra no frame da rotina (blindado)
        - procura botão de exportação (aceita vários locators)
        - clica via js_click_ie
        - aciona o watcher de download e RETORNA o status
        """
        self.logger.info("Aguardando tela pós-Visualizar e botão CSV/Excel...")
        self.switch_to_default_content()

        frame_index = self.FRAME_ROTINA if frame_index is None else frame_index

        if locators_export is None:
            locators_export = (self.BTN_GERA_EXCEL_1, self.BTN_GERA_EXCEL_2)

        try:
            WebDriverWait(self.driver, timeout_csv).until(
                EC.frame_to_be_available_and_switch_to_it(frame_index)
            )
        except UnexpectedAlertPresentException:
            self.lidar_com_alertas()
            self.switch_to_default_content()
            self.driver.switch_to.frame(frame_index)
        except TimeoutException:
            self.driver.switch_to.frame(frame_index)

        def _achar_botao(d):
            for locator in locators_export:
                try:
                    return d.find_element(*locator)
                except Exception:
                    pass
            return False

        try:
            btn_csv = WebDriverWait(self.driver, timeout_botao).until(_achar_botao)
        except TimeoutException:
            raise RuntimeError("Botão de exportação HTML (GeraExcel/GerExecl) não apareceu na tela.")

        # clique pelo helper padrão (Botão da Página)
        self.js_click_ie(btn_csv)
        self.logger.info("Botão HTML de exportação clicado. Acionando Watcher...")

        resultado_download = (False, "Módulos visuais ausentes")
        
        # Chama a rotina visual de download (que agora usa a barra do IE)
        if validar_elemento and salvar_arquivo_visual:
            diretorio_base = get_settings().download_dir
            subpasta = getattr(self, "subpasta_download", None)
            diretorio = diretorio_base / subpasta if subpasta else diretorio_base
            # RECEBE O RESULTADO PARA SUBIR PARA O TRACKER
            resultado_download = salvar_arquivo_visual(
                diretorio_destino=str(diretorio),
                nome_arquivo_final=nome_arquivo,
            )
        else:
            self.logger.warning("Módulos visuais não carregados.")

        self.switch_to_default_content()
        
        # Retorna a tupla (True/False, "Motivo") para o loop_unidades
        return resultado_download # <-- Correção menor aqui também, o seu estava retornando 'None'
    
    # --- MÉTODOS DE AÇÃO ---
    def js_set_checked_by_name_value(self, name: str, value: str, checked: bool, force_click: bool = True):
        if checked is None: return
        res = self.driver.execute_script(self.JS_CHECKED_BY_NAME_VALUE, name, str(value), bool(checked), bool(force_click))
        if not res or not res.get("ok"):
            raise RuntimeError(f"Falha set checked {name}[value={value}]={checked}: {res}")

    def adicionar_itens_lista_por_botao(self, nome_select: str, nome_botao: str, itens):
        """Padrão de preenchimento de listas via botão de adição ('>')"""
        if itens is None: return
        itens = itens if isinstance(itens, list) else [itens]
        for item in itens:
            self.js_set_select_by_name(nome_select, str(item))
            btn = self.find_element((By.NAME, nome_botao))
            self.js_click_ie(btn)
            self.aguardar_loader_oculto(timeout=3)

    # --- MÉTODOS DE ASSERÇÃO (VALIDAÇÃO) ---
    def _assert_checkbox(self, name, esperado: bool, tentativas=2):
        for i in range(tentativas):
            el = self.find_element((By.NAME, name))
            if bool(el.is_selected()) == bool(esperado): return True
            self.logger.warning(f"Refazendo Checkbox {name} -> {esperado}")
            self.js_set_checkbox_by_name(name, bool(esperado), force_click=True)
            self.wait_for_js_condition(
                f"var el=document.getElementsByName('{name}')[0]; return !!el && (!!el.checked === {str(bool(esperado)).lower()});",
                timeout=2,
                description=f"checkbox {name} estabilizar",
            )
        raise RuntimeError(f"Checkbox {name} falhou após {tentativas} tentativas.")

    def _assert_checked_by_name_value(self, name, value, esperado: bool, tentativas=2):
        js_get = "var els=document.getElementsByName(arguments[0]); for(var i=0;i<els.length;i++){if(els[i].value==arguments[1]) return !!els[i].checked;} return null;"
        for i in range(tentativas):
            atual = self.driver.execute_script(js_get, str(name), str(value))
            if bool(atual) == bool(esperado): return True
            self.js_set_checked_by_name_value(name, value, bool(esperado), force_click=True)
            self.wait_for_js_condition(
                (
                    f"var els=document.getElementsByName('{name}'); "
                    f"for(var i=0;i<els.length;i++){{if(els[i].value=='{value}') return (!!els[i].checked === {str(bool(esperado)).lower()});}} "
                    "return false;"
                ),
                timeout=2,
                description=f"radio/check {name}[{value}] estabilizar",
            )
        raise RuntimeError(f"Radio/Check {name}[{value}] falhou após {tentativas} tentativas.")
    
    def registrar_log_csv(self, caminho_arquivo, colunas, dados_linha):
        """Utilitário genérico para logar resultados de processamento linha a linha."""
        arquivo_existe = os.path.exists(caminho_arquivo)
        
        # <-- CORRIGIDO AQUI: dt.datetime.now()
        dados_linha['data_hora'] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Garante que a coluna data_hora seja a primeira se já não estiver em colunas
        if 'data_hora' not in colunas:
            colunas = ['data_hora'] + colunas

        with open(caminho_arquivo, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=colunas, delimiter=';')
            if not arquivo_existe:
                writer.writeheader()
            writer.writerow(dados_linha)

    def executar_gatilho_e_aguardar(self, script_gatilho, timeout=5.0):
        """Executa JS e aguarda resposta via Alert ou sumiço de Loader."""
        try:
            self.driver.execute_script(script_gatilho)
        except Exception as e:
            return False, f"Erro JS: {str(e)}"

        fim = time.time() + timeout
        while time.time() < fim:
            # 1. Checa Alertas
            try:
                alert = self.driver.switch_to.alert
                msg = alert.text
                alert.accept()
                sucesso = any(w in msg.lower() for w in ["sucesso", "salvo", "confirm", "ok", "processado"])
                return sucesso, msg
            except Exception as e:
                self.logger.debug(f"Alerta não presente ao aguardar gatilho: {e}")

            # 2. Checa Loader (imgWait)
            try:
                display = self.driver.execute_script("var el = document.getElementById('imgWait'); return el ? el.style.display : 'none';")
                if display == 'none': return True, "OK"
            except Exception as e:
                self.logger.debug(f"Fallback de loader após gatilho: {e}")
                return True, "Reloaded"
            
            time.sleep(0.1)
        return False, f"Timeout aguardando confirmação do sistema após {timeout:.1f}s"

    def preencher_campo_com_gatilho(self, nome_campo, valor, script_gatilho):
        """Atalho para Set Input + Trigger + Wait"""
        self.js_set_input_by_name(nome_campo, str(valor))
        sucesso, msg = self.executar_gatilho_e_aguardar(script_gatilho)
        if not sucesso:
            self.logger.error(f"Erro no campo {nome_campo}: {msg}")
        return sucesso, msg



