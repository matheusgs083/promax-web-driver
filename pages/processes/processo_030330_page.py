import random
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from selenium.common.exceptions import NoAlertPresentException
from core.execution.execution_result import ExecutionResult, ExecutionStatus
from pages.common.rotina_page import RotinaPage


class Processo030330Page(RotinaPage):
    """
    Page Object para a rotina 030330 (Manutenção de Caução / Notas do Mapa - PW02141C).
    100% compatível com Internet Explorer 8 / Modo de Compatibilidade Promax.
    Trata automaticamente a modal 'Informações Material Controlado [ F7367 ]' (DivNumeroSerie),
    gerando etiquetas numéricas de 8 dígitos e data de fabricação (dd/mm/aaaa).
    """

    FRAME_ROTINA = 1

    def __init__(self, driver, handle_menu_original):
        super().__init__(driver, handle_menu_original)
        try:
            self.handle_rotina = self.driver.current_window_handle
        except Exception:
            self.handle_rotina = None

    @staticmethod
    def normalizar_mapa(mapa: Union[str, int, float]) -> str:
        """Normaliza e valida o número do mapa."""
        valor = str(mapa or "").strip()
        if valor.endswith(".0"):
            valor = valor[:-2]
        valor = valor.replace(".", "").replace(",", "")
        if not valor or valor == "0":
            raise ValueError("Mapa deve ser informado e diferente de zero.")
        if not valor.isdigit():
            raise ValueError(f"Mapa invalido: {mapa}")
        return valor

    def _garantir_frame_rotina(self) -> None:
        """Garante que a sessão do Selenium esteja focada no FRAME_ROTINA."""
        try:
            self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
        except Exception as e:
            self.logger.debug(f"030330 | Aviso ao alternar para FRAME_ROTINA: {e}")

    def _lidar_com_alerta_ie(self) -> Optional[str]:
        """Captura e aceita alerta se presente."""
        try:
            alerta = self.driver.switch_to.alert
            texto = alerta.text
            alerta.accept()
            return texto
        except NoAlertPresentException:
            return None
        except Exception:
            return None

    def obter_opcoes_tipo_mapa(self) -> List[Dict[str, Any]]:
        """Retorna todas as opções disponíveis no dropdown Tipo de Mapa (tpMapa)."""
        try:
            self._garantir_frame_rotina()
            script = """
                function trimStr(str) {
                    return String(str || '').replace(/^\\s+|\\s+$/g, '');
                }
                var cmpTp = document.getElementsByName('tpMapa')[0] || document.getElementById('tpMapa');
                var opts = [];
                if (cmpTp && cmpTp.options) {
                    for (var i = 0; i < cmpTp.options.length; i++) {
                        var val = trimStr(cmpTp.options[i].value);
                        var txt = trimStr(cmpTp.options[i].text);
                        if (val || (txt && txt.indexOf('--') === -1)) {
                            opts.push({ index: i, value: val, text: txt });
                        }
                    }
                }
                return opts;
            """
            return self.driver.execute_script(script) or []
        except Exception as e:
            self.logger.debug(f"030330 | Erro ao obter opcoes de tpMapa: {e}")
            return []

    def tratar_popup_pesquisa_clientes(self, timeout: int = 10) -> bool:
        """
        Detecta e trata o popup/janela 'Pesquisa Clientes' (PW00184P).
        Aguarda o carregamento das linhas via CGI (frame=9), marca explicitamente os itens
        (sem desmarcar via .click()) e aciona Confirmar().
        """
        janela_original = self.handle_rotina or self.driver.current_window_handle
        inicio = time.time()

        while time.time() - inicio < timeout:
            try:
                handles = self.driver.window_handles
                if len(handles) > 1:
                    for h in handles:
                        if h != janela_original:
                            try:
                                self.driver.switch_to.window(h)
                                time.sleep(0.3)
                                url_ou_titulo = (self.driver.current_url + " " + self.driver.title).upper()
                                if "PW00184P" in url_ou_titulo or "PESQUISA" in url_ou_titulo or "PP00100" in url_ou_titulo or len(handles) > 1:
                                    res = self._executar_selecao_e_confirmacao_pw00184p()
                                    if res and res.get("ok"):
                                        self.logger.info(f"030330 | PW00184P processado com sucesso na janela {h}: {res}")
                                        time.sleep(1.5)
                                        try:
                                            if h in self.driver.window_handles:
                                                self.driver.close()
                                        except Exception:
                                            pass
                                        self.driver.switch_to.window(janela_original)
                                        self._garantir_frame_rotina()
                                        return True
                            except Exception as e:
                                self.logger.debug(f"030330 | Tentando processar popup {h}: {e}")

                self._garantir_frame_rotina()
                res_modal = self._executar_selecao_e_confirmacao_pw00184p()
                if res_modal and res_modal.get("ok"):
                    self.logger.info(f"030330 | PW00184P processado no contexto principal: {res_modal}")
                    return True
            except Exception:
                pass

            time.sleep(0.5)

        try:
            self.driver.switch_to.window(janela_original)
            self._garantir_frame_rotina()
        except Exception:
            pass

        return False

    def _executar_selecao_e_confirmacao_pw00184p(self) -> Dict[str, Any]:
        """Executa script JS no contexto do PW00184P para definir .checked = true sem alternar estado."""
        script_pw00184p = """
            function trimStr(str) {
                return String(str || '').replace(/^\\s+|\\s+$/g, '');
            }

            function selecionarEConfirmarPW00184P(doc) {
                if (!doc) return { ok: false, reason: 'sem-doc' };

                var nrLinhasEl = doc.getElementsByName('nrLinhas')[0] || (doc.all ? doc.all['nrLinhas'] : null);
                var nrLinhas = nrLinhasEl ? parseInt(nrLinhasEl.value, 10) : 0;

                if (isNaN(nrLinhas) || nrLinhas <= 0) {
                    var allInputs = doc.getElementsByTagName('input');
                    for (var i = 0; i < allInputs.length; i++) {
                        var name = String(allInputs[i].name || allInputs[i].id || '');
                        if (name.indexOf('idSel') === 0) {
                            var num = parseInt(name.replace('idSel', ''), 10);
                            if (!isNaN(num) && num > nrLinhas) {
                                nrLinhas = num;
                            }
                        }
                    }
                }

                var chkList = [];
                var inputsAll = doc.getElementsByTagName('input');
                for (var k = 0; k < inputsAll.length; k++) {
                    var inp = inputsAll[k];
                    if (inp.type === 'checkbox' || inp.type === 'CHECKBOX') {
                        chkList.push(inp);
                    }
                }

                var marcados = 0;

                if (nrLinhas > 0) {
                    for (var aux = 1; aux <= nrLinhas; aux++) {
                        var chkItem = (doc.all ? doc.all['idSel' + aux] : null) || doc.getElementsByName('idSel' + aux)[0];
                        if (chkItem) {
                            chkItem.checked = true;
                            marcados++;
                        }
                    }
                }

                if (marcados === 0 && chkList.length > 0) {
                    for (var c = 0; c < chkList.length; c++) {
                        chkList[c].checked = true;
                        marcados++;
                    }
                }

                if (marcados === 0) {
                    return { ok: false, reason: 'aguardando-checkboxes-serem-renderizados' };
                }

                var botConfirmar = (doc.all ? doc.all['BotConfirmar'] : null) || doc.getElementsByName('BotConfirmar')[0];
                if (botConfirmar) {
                    botConfirmar.disabled = false;
                }

                if (typeof doc.defaultView !== 'undefined' && doc.defaultView.Confirmar) {
                    try {
                        doc.defaultView.Confirmar();
                        return { ok: true, marcados: marcados, trigger: 'Confirmar()' };
                    } catch(e) {}
                }

                if (botConfirmar && botConfirmar.click) {
                    botConfirmar.click();
                    return { ok: true, marcados: marcados, trigger: 'BotConfirmar.click()' };
                }

                return { ok: true, marcados: marcados, trigger: 'marcado-sem-confirmar' };
            }

            function buscarEProcessar(win) {
                if (!win) return { ok: false, reason: 'sem-janela' };
                try {
                    var rDoc = selecionarEConfirmarPW00184P(win.document);
                    if (rDoc.ok) return rDoc;
                } catch(e) {}

                try {
                    if (win.frames && win.frames.length > 0) {
                        for (var f = 0; f < win.frames.length; f++) {
                            try {
                                var rSub = buscarEProcessar(win.frames[f]);
                                if (rSub.ok) return rSub;
                            } catch(e) {}
                        }
                    }
                } catch(e) {}

                return { ok: false, reason: 'linhas-nao-carregadas' };
            }

            return buscarEProcessar(window);
        """
        try:
            return self.driver.execute_script(script_pw00184p) or {}
        except Exception as e:
            self.logger.debug(f"030330 | Script PW00184P nao executado neste contexto: {e}")
            return {}

    def carregar_mapa(
        self,
        mapa: Union[str, int, float],
        dt_emissao: Optional[str] = None,
        tp_mapa: Optional[str] = "COMODATO",
    ) -> ExecutionResult:
        """
        Carrega um mapa na rotina 030330.
        Preenche os campos nrMapa, dtEmissao, seleciona o Tipo ("COMODATO", "CONSIGNAÇÃO", etc)
        e trata automaticamente o pop-up de seleção de clientes/notas (PW00184P).
        """
        mapa_norm = self.normalizar_mapa(mapa)
        tp_alvo = str(tp_mapa or "COMODATO").strip()
        try:
            self._garantir_frame_rotina()
            self.logger.info(f"030330 | Carregando mapa: {mapa_norm} | Tipo Solicitado: {tp_alvo}")

            script_carga = """
                var mapaValor = arguments[0];
                var dtEmissaoValor = arguments[1];
                var tpMapaValor = String(arguments[2] || 'COMODATO');

                function trimStr(str) {
                    return String(str || '').replace(/^\\s+|\\s+$/g, '');
                }

                function removerAcentos(str) {
                    var s = trimStr(str);
                    try {
                        if (s.normalize) {
                            return s.normalize("NFKD").replace(/[\\u0300-\\u036f]/g, "").toUpperCase();
                        }
                    } catch(e) {}
                    return s.toUpperCase();
                }

                var cmpMapa = document.getElementsByName('nrMapa')[0] || document.getElementById('nrMapa');
                if (!cmpMapa) return { ok: false, error: 'campo-nrMapa-nao-encontrado' };

                cmpMapa.disabled = false;
                cmpMapa.readOnly = false;
                cmpMapa.value = mapaValor;

                if (dtEmissaoValor) {
                    var cmpDt = document.getElementsByName('dtEmissao')[0] || document.getElementById('dtEmissao');
                    if (cmpDt) cmpDt.value = dtEmissaoValor;
                }

                var cmpTp = document.getElementsByName('tpMapa')[0] || document.getElementById('tpMapa');
                var tpSelecionadoText = "";
                var tpSelecionadoVal = "";

                if (cmpTp && cmpTp.options) {
                    var alvoNorm = removerAcentos(tpMapaValor);
                    var selecionou = false;

                    for (var i = 0; i < cmpTp.options.length; i++) {
                        var optTextNorm = removerAcentos(cmpTp.options[i].text);
                        var optValNorm = removerAcentos(cmpTp.options[i].value);

                        if (optTextNorm.indexOf(alvoNorm) !== -1 || optValNorm === alvoNorm ||
                            (alvoNorm.indexOf('COMOD') !== -1 && (optValNorm === 'C' || optTextNorm.indexOf('COMOD') !== -1)) ||
                            (alvoNorm.indexOf('CONSIG') !== -1 && (optValNorm === 'CS' || optValNorm === 'G' || optTextNorm.indexOf('CONSIG') !== -1))) {
                            cmpTp.selectedIndex = i;
                            cmpTp.value = cmpTp.options[i].value;
                            tpSelecionadoText = cmpTp.options[i].text;
                            tpSelecionadoVal = cmpTp.options[i].value;
                            selecionou = true;
                            break;
                        }
                    }

                    if (!selecionou && cmpTp.options.length > 1) {
                        for (var k = 1; k < cmpTp.options.length; k++) {
                            if (cmpTp.options[k].value !== "") {
                                cmpTp.selectedIndex = k;
                                cmpTp.value = cmpTp.options[k].value;
                                tpSelecionadoText = cmpTp.options[k].text;
                                tpSelecionadoVal = cmpTp.options[k].value;
                                break;
                            }
                        }
                    }
                }

                if (typeof CarregarMapa === 'function') {
                    CarregarMapa();
                    return { ok: true, trigger: 'CarregarMapa()', tpText: tpSelecionadoText, tpVal: tpSelecionadoVal };
                } else {
                    document.all.opcao.value = 2;
                    if (typeof EnviarFormulario === 'function') {
                        EnviarFormulario();
                        return { ok: true, trigger: 'opcao=2; EnviarFormulario();', tpText: tpSelecionadoText, tpVal: tpSelecionadoVal };
                    }
                }
                return { ok: false, error: 'funcao-CarregarMapa-nao-encontrada' };
            """
            res_js = self.driver.execute_script(script_carga, mapa_norm, dt_emissao or "", tp_alvo)
            if not res_js or not res_js.get("ok"):
                return ExecutionResult(
                    status=ExecutionStatus.TECHNICAL_FAILURE,
                    message=f"Falha ao acionar gatilho de carga do mapa {mapa_norm} na 030330: {res_js}",
                )

            time.sleep(1.5)

            # Trata a janela / popup PW00184P de seleção de notas se ela abrir
            pop_tratado = self.tratar_popup_pesquisa_clientes(timeout=8)
            if pop_tratado:
                self.logger.info(f"030330 | Popup de clientes PW00184P tratado com sucesso para o mapa {mapa_norm}.")
                time.sleep(2.5)

            alertas = self.lidar_com_alertas(tentativas=2, timeout=2)
            if alertas:
                for alerta in alertas:
                    msg_alerta = str(alerta).strip()
                    if any(
                        kw in msg_alerta.lower()
                        for kw in ["erro", "invalido", "nao encontrado", "nao existe", "bloquead"]
                    ):
                        return ExecutionResult(
                            status=ExecutionStatus.BUSINESS_FAILURE,
                            message=f"Alerta ao carregar mapa {mapa_norm}: {msg_alerta}",
                        )

            dados_mapa = self.aguardar_carregamento_notas(timeout=6)
            tipo_selecionado = res_js.get("tpText") or tp_alvo
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Mapa {mapa_norm} carregado na 030330 com Tipo '{tipo_selecionado}'. Total de notas: {len(dados_mapa.get('notas', []))}",
                metadata={"mapa": mapa_norm, "tipo_mapa": tipo_selecionado, "dados_030330": dados_mapa},
            )
        except Exception as e:
            self.logger.error(f"030330 | Erro inesperado ao carregar mapa {mapa_norm}: {e}")
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=f"Falha ao carregar mapa {mapa_norm}: {str(e)}",
            )

    def aguardar_carregamento_notas(self, timeout: int = 6) -> Dict[str, Any]:
        """Aguarda o preenchimento da lista de notas após confirmação do popup PW00184P."""
        inicio = time.time()
        while time.time() - inicio < timeout:
            resumo = self.obter_resumo_mapa()
            linhas = resumo.get("nrLinhas") or "0"
            notas = resumo.get("notas") or []
            if str(linhas) != "0" or len(notas) > 0:
                return resumo
            time.sleep(0.5)
        return self.obter_resumo_mapa()

    def tratar_div_numero_serie(self, dt_fechamento: Optional[str] = None) -> bool:
        """
        Detecta se a modal 'Informações Material Controlado [ F7367 ]' (DivNumeroSerie) está visível ('com a telinha')
        ou se alguma linha de material controlado (idNrSerie == 'S') precisa de etiqueta de 8 dígitos ('sem a telinha').
        Gera um número de série de 8 dígitos e a data de fabricação (dd/mm/aaaa) e aciona a confirmação (ConfirmarTelaNrSerie).
        """
        self._garantir_frame_rotina()

        if not dt_fechamento:
            dt_fechamento = self.driver.execute_script(
                "return (document.all.dtEmissao ? document.all.dtEmissao.value : '') || '24/08/2026';"
            )
        if not dt_fechamento or "/" not in str(dt_fechamento):
            dt_fechamento = time.strftime("%d/%m/%Y")

        nova_etiqueta = str(random.randint(10000000, 99999999))

        script_tratar_div = """
            var serieGerada = arguments[0];
            var dtFabGerada = arguments[1];

            function trimStr(str) {
                return String(str || '').replace(/^\\s+|\\s+$/g, '');
            }

            var divSerie = document.getElementById('DivNumeroSerie') || (document.all ? document.all['DivNumeroSerie'] : null);
            var divVisivel = divSerie && divSerie.style.display !== 'none';

            var nrLinhasEl = document.getElementsByName('nrLinhas')[0] || (document.all ? document.all['nrLinhas'] : null);
            var nrLinhas = nrLinhasEl ? parseInt(nrLinhasEl.value, 10) : 0;

            var indPendente = 0;
            for (var i = 1; i <= nrLinhas; i++) {
                var elSerie = document.getElementById('nrSerie' + i) || (document.all ? document.all['nrSerie' + i] : null);
                var txtSerie = elSerie ? trimStr(String(elSerie.innerText || elSerie.textContent || elSerie.outerText || elSerie.innerHTML || '').replace(/&nbsp;/g, '')) : '';
                var lnNota = (document.all ? document.all['lnNota' + i] : null) || document.getElementsByName('lnNota' + i)[0];
                var idNrSerie = lnNota ? trimStr(String(lnNota.idNrSerie || '')) : '';
                var elDtFab = document.getElementById('dtFabricacao' + i) || (document.all ? document.all['dtFabricacao' + i] : null);
                var txtDtFab = elDtFab ? trimStr(String(elDtFab.innerText || elDtFab.textContent || elDtFab.outerText || '')) : '';

                if (txtSerie === '' || txtSerie === '0' || txtDtFab === '00/00/0000' || idNrSerie === 'S') {
                    if (txtSerie === '' || txtSerie === '0' || txtDtFab === '00/00/0000') {
                        indPendente = i;
                        break;
                    }
                }
            }

            if (!divVisivel && indPendente === 0) {
                return { ok: false, reason: 'nenhuma-linha-sem-etiqueta' };
            }

            if (indPendente > 0) {
                try {
                    document.all.indSel.value = indPendente;
                    if (typeof Editar === 'function') {
                        Editar(indPendente);
                    } else if (typeof MoverDados === 'function') {
                        MoverDados(indPendente);
                    }
                } catch(e) {}
            }

            if (divSerie) {
                divSerie.style.display = '';
            }

            var cmpSerie = document.getElementsByName('nrSerie')[0] || (document.all ? document.all['nrSerie'] : null);
            if (cmpSerie) cmpSerie.value = serieGerada;

            var cmpDt = document.getElementsByName('dtFabricacao')[0] || (document.all ? document.all['dtFabricacao'] : null);
            if (cmpDt) cmpDt.value = dtFabGerada;

            var botConfirm = (document.all ? document.all['BotConfirmNrSerie'] : null) || document.getElementsByName('BotConfirmNrSerie')[0];

            if (typeof ConfirmarTelaNrSerie === 'function') {
                try {
                    ConfirmarTelaNrSerie();
                    return { ok: true, ind: indPendente, serie: serieGerada, dtFab: dtFabGerada, trigger: 'ConfirmarTelaNrSerie()' };
                } catch(e) {}
            }

            if (botConfirm && botConfirm.click) {
                try {
                    botConfirm.click();
                    return { ok: true, ind: indPendente, serie: serieGerada, dtFab: dtFabGerada, trigger: 'BotConfirmNrSerie.click()' };
                } catch(e) {}
            }

            document.all.opcao.value = 7;
            if (typeof EnviarFormulario === 'function') {
                EnviarFormulario();
                return { ok: true, ind: indPendente, serie: serieGerada, dtFab: dtFabGerada, trigger: 'opcao=7; EnviarFormulario();' };
            }

            return { ok: false, reason: 'falha-ao-confirmar-modal' };
        """
        try:
            res = self.driver.execute_script(script_tratar_div, nova_etiqueta, dt_fechamento)
            if res and res.get("ok"):
                self.logger.info(f"030330 | Modal DivNumeroSerie tratado: Etiqueta {nova_etiqueta} (8 dígitos) cadastrada com data {dt_fechamento}.")
                time.sleep(2.0)
                self.lidar_com_alertas(tentativas=2, timeout=2)
                return True
        except Exception as e:
            self.logger.warning(f"030330 | Erro ao tratar modal DivNumeroSerie: {e}")

        return False

    def obter_resumo_mapa(self) -> Dict[str, Any]:
        """Extrai dados estruturados e notas carregadas no mapa na 030330."""
        try:
            self._garantir_frame_rotina()
            script_extracao = """
                function trimStr(str) {
                    return String(str || '').replace(/^\\s+|\\s+$/g, '');
                }

                function texto(el) {
                    if (!el) return "";
                    return trimStr(String(el.innerText || el.textContent || el.value || "").replace(/\\s+/g, " "));
                }

                var nrMapa = document.getElementsByName('nrMapa')[0] ? document.getElementsByName('nrMapa')[0].value : "";
                var dtEmissao = document.getElementsByName('dtEmissao')[0] ? document.getElementsByName('dtEmissao')[0].value : "";
                var tpMapa = document.getElementsByName('tpMapa')[0] ? document.getElementsByName('tpMapa')[0].value : "";
                var vlTotal = document.getElementById('vlTotalListaLst') ? texto(document.getElementById('vlTotalListaLst')) : "0,00";

                var notas = [];
                var divListagem = document.getElementById('listagem');
                var trs = divListagem ? divListagem.getElementsByTagName('tr') : [];
                for (var i = 0; i < trs.length; i++) {
                    var tds = trs[i].cells || trs[i].getElementsByTagName('td');
                    if (tds && tds.length >= 6) {
                        notas.push({
                            cliente: texto(tds[0]),
                            nomeCliente: texto(tds[1]),
                            notaSerie: texto(tds[2]),
                            valor: texto(tds[3]),
                            tpCaucao: texto(tds[4]),
                            nrSerie: texto(tds[5]),
                            dtFabricacao: tds.length > 6 ? texto(tds[6]) : ""
                        });
                    }
                }

                return {
                    rotina: "030330",
                    call: "PW02141C",
                    nrMapa: nrMapa,
                    dtEmissao: dtEmissao,
                    tpMapa: tpMapa,
                    vlTotalLista: vlTotal,
                    nrLinhas: document.getElementsByName('nrLinhas')[0] ? document.getElementsByName('nrLinhas')[0].value : String(notas.length),
                    notas: notas
                };
            """
            return self.driver.execute_script(script_extracao) or {}
        except Exception as e:
            self.logger.warning(f"030330 | Nao foi possivel extrair resumo do mapa: {e}")
            return {"rotina": "030330", "erro": str(e)}

    def alterar_caucao(self, ind_sel: Union[int, str], tp_caucao_novo: str) -> ExecutionResult:
        """
        Executa a alteração de caução para uma linha selecionada (AltCaucao()).
        """
        try:
            self._garantir_frame_rotina()
            script_alt = f"""
                document.all.indSel.value = '{ind_sel}';
                document.all.tpCaucao.value = '{tp_caucao_novo}';
                if (typeof AltCaucao === 'function') {{
                    AltCaucao();
                    return true;
                }}
                return false;
            """
            res = self.driver.execute_script(script_alt)
            time.sleep(1.5)
            self.lidar_com_alertas(tentativas=2, timeout=2)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS if res else ExecutionStatus.TECHNICAL_FAILURE,
                message=f"Alteracao de caucao para a linha {ind_sel} executada." if res else "Falha ao disparar AltCaucao().",
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=f"Erro ao alterar caucao: {str(e)}",
            )

    def salvar_mapa(self, dt_fechamento: Optional[str] = None) -> ExecutionResult:
        """
        Executa o salvamento e liberação do mapa na rotina 030330 (Salvar(); / opcao=6).
        Preenche a modal de Material Controlado (DivNumeroSerie) caso alguma linha necessite de etiqueta.
        """
        try:
            self._garantir_frame_rotina()
            self.logger.info("030330 | Salvando mapa na rotina 030330...")

            resumo = self.obter_resumo_mapa()
            linhas = resumo.get("nrLinhas") or "0"
            notas = resumo.get("notas") or []
            if str(linhas) == "0" and len(notas) == 0:
                self.logger.warning("030330 | Nenhuma nota carregada no mapa para salvar.")
                return ExecutionResult(
                    status=ExecutionStatus.BUSINESS_FAILURE,
                    message="Nenhuma nota de comodato/consignacao carregada no mapa para salvar na rotina 030330.",
                )

            # Preenche iterativamente quaisquer linhas sem etiqueta antes ou durante o salvamento
            qtd_linhas = int(linhas) if str(linhas).isdigit() else len(notas)
            for _ in range(max(1, qtd_linhas)):
                if not self.tratar_div_numero_serie(dt_fechamento=dt_fechamento):
                    break
                time.sleep(1.5)

            script_salvar = """
                if (typeof Salvar === 'function') {
                    Salvar();
                    return { ok: true, trigger: 'Salvar()' };
                } else {
                    document.all.opcao.value = 6;
                    if (typeof EnviarFormulario === 'function') {
                        EnviarFormulario();
                        return { ok: true, trigger: 'opcao=6; EnviarFormulario();' };
                    }
                }
                return { ok: false, error: 'funcao-Salvar-nao-encontrada' };
            """
            res_js = self.driver.execute_script(script_salvar)
            time.sleep(1.5)

            # Se o Salvar() abriu a modal DivNumeroSerie por falta de etiqueta
            if self.tratar_div_numero_serie(dt_fechamento=dt_fechamento):
                self.logger.info("030330 | Modal DivNumeroSerie preenchida apos o Salvar(). Re-executando Salvar()...")
                time.sleep(2.0)
                self.driver.execute_script(script_salvar)

            time.sleep(2.5)
            alertas = self.lidar_com_alertas(tentativas=3, timeout=3)
            msg_alertas = " | ".join(str(a) for a in alertas) if alertas else ""

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Mapa salvo com sucesso na 030330. {msg_alertas}".strip(),
                metadata={
                    "dados_030330": self.obter_resumo_mapa(),
                    "integration_code": "MAPA_030330_SALVO",
                },
            )
        except Exception as e:
            self.logger.error(f"030330 | Erro tecnico ao salvar mapa na 030330: {e}")
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=f"Erro ao salvar mapa na 030330: {str(e)}",
            )

    def cancelar(self) -> None:
        """Executa a acao de cancelar (Cancelar();) na rotina 030330."""
        try:
            self._garantir_frame_rotina()
            self.driver.execute_script(
                "if (typeof Cancelar === 'function') { Cancelar(); } else if (document.all.BotCancelar) { document.all.BotCancelar.click(); }"
            )
        except Exception as e:
            self.logger.debug(f"030330 | Erro ao cancelar na 030330: {e}")
