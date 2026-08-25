import time
import unicodedata

from selenium.common.exceptions import NoAlertPresentException, TimeoutException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from core.execution.execution_result import ExecutionResult, ExecutionStatus
from pages.common.rotina_page import RotinaPage


class Processo030302Page(RotinaPage):
    """Processo 030302: carrega o mapa na area de mapa da rotina."""

    FRAME_ROTINA = 1

    def __init__(self, driver, handle_menu_original):
        super().__init__(driver, handle_menu_original)
        self._km_atual_030302 = None
        self._km_inicial_030302 = None
        self._km_prev_030302 = None
        try:
            self.handle_rotina = self.driver.current_window_handle
        except Exception:
            self.handle_rotina = None

    def tem_codigos_fisicos(self):
        """Informa se o mapa carregado possui ao menos um codigo fisico valido."""
        try:
            self._reentrar_frame(timeout=10)
            estado = self._estado_mapa_js() or {}
            for produto in estado.get("produtos") or []:
                codigo = str(produto.get("codigo") or "").strip()
                if codigo and codigo.lower() not in {"none", "null", "undefined", "0"}:
                    return True
            return False
        except Exception:
            # Se a leitura falhar, preserva o fluxo normal para nao pular a 030302 indevidamente.
            return True
        finally:
            try:
                self.switch_to_default_content()
            except Exception:
                pass

    @staticmethod
    def normalizar_mapa(mapa):
        valor = str(mapa or "").strip()
        if valor.endswith(".0"):
            valor = valor[:-2]
        valor = valor.replace(".", "").replace(",", "")
        if not valor or valor == "0":
            raise ValueError("Mapa deve ser informado e diferente de zero.")
        if not valor.isdigit():
            raise ValueError(f"Mapa invalido: {mapa}")
        return valor

    @staticmethod
    def normalizar_km_atual(km_atual):
        valor = str(km_atual or "").strip()
        if not valor:
            return None
        if valor.endswith(".0"):
            valor = valor[:-2]
        valor = valor.replace(".", "").replace(",", "")
        if not valor:
            return None
        if not valor.isdigit():
            raise ValueError(f"KM atual invalido: {km_atual}")
        if len(valor) > 7:
            raise ValueError("KM atual deve ter no maximo 7 digitos.")
        return valor

    def _garantir_janela_030302(self):
        if not self.handle_rotina:
            return True
        try:
            atual = self.driver.current_window_handle
            if atual == self.handle_rotina:
                return True
            self.driver.switch_to.window(self.handle_rotina)
            return True
        except UnexpectedAlertPresentException:
            self.logger.info(
                "Alerta ignorado pela 030302 porque a janela ativa nao e a janela da rotina 030302."
            )
            return False
        except Exception as exc:
            self.logger.debug("Nao foi possivel focar a janela 030302 antes de tratar alerta: %s", exc)
            return False

    def _aceitar_alerta(self):
        try:
            if not self._garantir_janela_030302():
                return None
            alerta = self.driver.switch_to.alert
            texto = str(alerta.text)
            if self._eh_alerta_recuperar_mapa(texto):
                alerta.accept()
            return texto
        except NoAlertPresentException:
            return None
        except Exception:
            return None

    def _eh_alerta_recuperar_mapa(self, texto):
        texto_normalizado = self._normalizar_texto(texto)
        return "mapa em uso" in texto_normalizado and "recuperar" in texto_normalizado

    def _clicar_sim_recuperar_mapa(self):
        try:
            if not self._garantir_janela_030302():
                return None
            alerta = self.driver.switch_to.alert
            texto = str(alerta.text or "")
            if not self._eh_alerta_recuperar_mapa(texto):
                return None
            alerta.accept()
            return {"mensagem": texto, "resposta": "sim"}
        except NoAlertPresentException:
            return None
        except Exception:
            return None

    def _aguardar_e_clicar_sim_recuperar_mapa(self, timeout=2):
        fim = time.time() + timeout
        while time.time() <= fim:
            resposta = self._clicar_sim_recuperar_mapa()
            if resposta:
                return resposta
            time.sleep(0.2)
        return None

    @staticmethod
    def _normalizar_texto(texto):
        texto = str(texto or "").lower()
        texto = unicodedata.normalize("NFKD", texto)
        return "".join(char for char in texto if not unicodedata.combining(char))

    def _eh_mensagem_sem_diferencas(self, texto):
        texto_normalizado = self._normalizar_texto(texto)
        texto_compacto = "".join(ch for ch in texto_normalizado if ch.isalnum())
        return (
            "nao existe diferenc" in texto_normalizado
            or "nao existem diferenc" in texto_normalizado
            or "nao ha diferenc" in texto_normalizado
            or "naoexistediferenc" in texto_compacto
            or "naoexistemdiferenc" in texto_compacto
            or "naohadiferenc" in texto_compacto
        )

    def _decidir_resposta_msgbox_030302(self, texto):
        texto_normalizado = self._normalizar_texto(texto)
        texto_compacto = "".join(ch for ch in texto_normalizado if ch.isalnum())
        if self._eh_mensagem_sem_diferencas(texto_normalizado):
            return {"classificacao": "ok_sem_diferencas", "resposta": "ok"}
        if "finance" in texto_normalizado or (
            "liber" in texto_normalizado and "mapa" in texto_normalizado
        ):
            return {"classificacao": "liberacao_financeira", "resposta": "sim"}
        if (
            "deseja continuar" in texto_normalizado
            and ("guia" in texto_normalizado or "guias" in texto_compacto)
            and (
                "bonus" in texto_normalizado
                or "b nus" in texto_normalizado
                or "bnus" in texto_compacto
            )
        ):
            return {"classificacao": "bonus_as_sem_guias", "resposta": "sim"}
        if (
            ("diferen" in texto_normalizado or "diferenc" in texto_normalizado)
            and not self._eh_mensagem_sem_diferencas(texto_normalizado)
        ):
            return {"classificacao": "diferencas", "resposta": "nao"}
        if self._eh_alerta_recuperar_mapa(texto_normalizado):
            return {"classificacao": "recuperar_mapa", "resposta": "sim"}
        if "impress" in texto_normalizado and "direcionad" in texto_normalizado:
            return {"classificacao": "impressao_direcionada", "resposta": "ok"}
        if "retorno nao liberado" in texto_normalizado or "retorno n" in texto_normalizado:
            return {"classificacao": "alerta_externo_ou_retorno", "resposta": "pendente"}
        if "km" in texto_normalizado or "quilometr" in texto_normalizado:
            if (
                "invalid" in texto_normalizado
                or "inval" in texto_normalizado
                or "obrig" in texto_normalizado
                or "erro" in texto_normalizado
                or "nao inform" in texto_normalizado
                or "nao preench" in texto_normalizado
            ):
                return {"classificacao": "alerta_km_bloqueador", "resposta": "pendente"}
            resposta = "sim" if ("deseja" in texto_normalizado or "continuar" in texto_normalizado or "confirma" in texto_normalizado) else "ok"
            return {"classificacao": "alerta_km", "resposta": resposta}
        return None

    def _preencher_km_fallback_para_alerta(self, texto_alerta):
        if self._km_inicial_030302 is None or self._km_prev_030302 is None:
            self.logger.warning(
                "030302 | Alerta de KM sem fallback disponivel. Alerta mantido sem confirmacao: %s",
                texto_alerta,
            )
            return {
                "ok": False,
                "error": "km-fallback-indisponivel",
                "mensagem": texto_alerta,
            }
        try:
            km_ini = int(str(self._km_inicial_030302))
            km_prv = int(str(self._km_prev_030302))
            soma_km = str(km_ini + km_prv)
            self.logger.info(
                "030302 | Alerta de KM detectado ('%s'). Preenchendo soma km_inicial (%s) + km_prev (%s) = %s",
                texto_alerta,
                km_ini,
                km_prv,
                soma_km,
            )
            resultado_km = self._preencher_km_atual_js(soma_km)
            if not (resultado_km or {}).get("ok"):
                self.logger.warning(
                    "030302 | Alerta de KM nao sera confirmado porque o preenchimento falhou: %s",
                    resultado_km,
                )
                return resultado_km or {"ok": False, "error": "preenchimento-km-falhou"}
            return resultado_km
        except Exception as exc:
            self.logger.warning("030302 | Erro ao calcular/preencher a soma de KM: %s", exc)
            return {"ok": False, "error": str(exc)}

    def _confirmacoes_tem_sem_diferencas(self, confirmacoes):
        return any(
            self._eh_mensagem_sem_diferencas(confirmacao.get("mensagem"))
            for confirmacao in confirmacoes or []
        )

    def _confirmacoes_tem_resultado_final_030302(self, confirmacoes):
        """Confirma sucesso somente quando o Promax exibiu um alerta final nativo."""
        return any(
            str((confirmacao or {}).get("tipo") or "").strip() == "alert"
            and self._classificar_alerta_030302(confirmacao)
            in ("ok_sem_diferencas", "impressao_direcionada")
            for confirmacao in confirmacoes or []
        )

    def _estado_confirmou_sem_diferencas(self, estado):
        return bool(
            estado
            and (
                estado.get("mensagemSemDiferencas")
                or self._eh_mensagem_sem_diferencas(estado.get("divMensagemTexto"))
                or self._eh_mensagem_sem_diferencas(
                    (estado.get("alertaRespondido") or {}).get("mensagem")
                )
            )
        )

    def _produtos_tem_quantidade_positiva_030302(self, produtos):
        for produto in produtos or []:
            for prefixo in ("dev", "tro", "vaz"):
                for sufixo in ("Un", "Av"):
                    valor = str(produto.get(f"{prefixo}{sufixo}") or "").strip()
                    if valor in ("", "0"):
                        continue
                    try:
                        if int(valor) > 0:
                            return True
                    except ValueError:
                        return True
        return False

    def _estado_tem_quantidade_positiva_030302(self, estado):
        return self._produtos_tem_quantidade_positiva_030302(
            (estado or {}).get("produtos") or []
        )

    def _estado_tem_valor_editavel_030302(self, estado):
        produtos_editaveis = []
        for produto in (estado or {}).get("produtos") or []:
            produto_editavel = {}
            for prefixo in ("dev", "tro", "vaz"):
                for sufixo in ("Un", "Av"):
                    campo = f"{prefixo}{sufixo}"
                    if bool(produto.get(f"{campo}Disabled")):
                        continue
                    produto_editavel[campo] = produto.get(campo)
            produtos_editaveis.append(produto_editavel)
        return self._produtos_tem_quantidade_positiva_030302(produtos_editaveis)

    def _resultado_salvar_tem_itens_030302(self, resultado_js):
        form_after = (
            (resultado_js or {}).get("formAfter")
            or (resultado_js or {}).get("ultimoSalvar")
            or {}
        )
        try:
            itens_len = int(form_after.get("itensListaLength") or 0)
        except (TypeError, ValueError):
            itens_len = 0
        try:
            numero_items = int(form_after.get("numeroItems") or 0)
        except (TypeError, ValueError):
            numero_items = 0
        return (
            itens_len > 0
            and numero_items > 0
            and str(form_after.get("opcao") or "") == "6"
        )

    def _resultado_salvar_tem_quantidade_positiva_030302(self, resultado_js):
        if self._produtos_tem_quantidade_positiva_030302(
            (resultado_js or {}).get("produtos") or []
        ):
            return True
        for chave in ("formAfter", "ultimoSalvar"):
            form = (resultado_js or {}).get(chave) or {}
            if self._produtos_tem_quantidade_positiva_030302(form.get("produtos") or []):
                return True
        return False

    def _salvar_tem_payload_com_quantidade_030302(self, *payloads):
        return any(
            self._resultado_salvar_tem_quantidade_positiva_030302(payload)
            for payload in payloads
            if isinstance(payload, dict)
        )

    def _estado_indica_retorno_pos_salvar_030302(self, estado):
        if not estado:
            return False
        try:
            lista_len = int(estado.get("listaDiferencasLength") or 0)
        except (TypeError, ValueError):
            lista_len = 0
        try:
            lista_rows = int(estado.get("listaRows") or 0)
        except (TypeError, ValueError):
            lista_rows = 0
        opcao = str(estado.get("opcao") or "").strip()
        div_diferencas_visivel = bool(estado.get("divDiferencasVisivel")) or (
            estado.get("divDiferencasDisplay") not in (None, "none", "")
        )
        mensagem_visivel = estado.get("divMensagemDisplay") not in (None, "none", "")
        produtos = estado.get("produtos") or []
        return bool(
            lista_len == 0
            and lista_rows == 0
            and not produtos
            and not div_diferencas_visivel
            and not mensagem_visivel
            and (estado.get("botSalvarDisabled") is True or opcao in ("7", "00"))
        )

    def _salvar_preenchido_retorno_confirmado_030302(
        self,
        resultado_js=None,
        dados_confirmacao=None,
        estado=None,
        estado_antes=None,
    ):
        payload_confirmacao = {
            "ultimoSalvar": (dados_confirmacao or {}).get("ultimoSalvar") or {}
        }
        try:
            submit_count = int((dados_confirmacao or {}).get("submitCount") or 0)
        except (TypeError, ValueError):
            submit_count = 0
        payload_tem_quantidade = self._salvar_tem_payload_com_quantidade_030302(
            resultado_js or {},
            payload_confirmacao,
        )
        if not payload_tem_quantidade:
            payload_tem_quantidade = self._estado_tem_quantidade_positiva_030302(
                estado_antes
            )
        if not payload_tem_quantidade:
            payload_tem_quantidade = self._produtos_tem_quantidade_positiva_030302(
                (estado_antes or {}).get("linhasDisponiveis") or []
            )
        if not payload_tem_quantidade:
            for item in (estado_antes or {}).get("aplicados") or []:
                for chave in ("faltaUn", "faltaAv"):
                    try:
                        if int(item.get(chave) or 0) > 0:
                            payload_tem_quantidade = True
                            break
                    except (TypeError, ValueError):
                        if str(item.get(chave) or "").strip():
                            payload_tem_quantidade = True
                            break
                if payload_tem_quantidade:
                    break
        return bool(
            payload_tem_quantidade
            and (submit_count > 0 or bool((resultado_js or {}).get("ok")))
            and self._estado_confirmou_sem_diferencas(estado)
        )

    def _reativar_digitacao_valores_030302(self):
        try:
            self._reentrar_frame(timeout=10)
            return self.driver.execute_script(
                """
                function auxLinha(index) {
                    if (index < 10) return '00' + index;
                    if (index < 100) return '0' + index;
                    return String(index);
                }

                function numero(valor) {
                    var n = parseInt(String(valor || '').replace(/\\D/g, ''), 10);
                    return isNaN(n) ? 0 : n;
                }

                function limparTexto(valor) {
                    return String(valor || '').replace(/^\\s+|\\s+$/g, '');
                }

                function disparar(campo, nomeEvento) {
                    try {
                        if (campo.fireEvent) {
                            campo.fireEvent('on' + nomeEvento);
                        } else if (campo.ownerDocument && campo.ownerDocument.createEvent) {
                            var evt = campo.ownerDocument.createEvent('HTMLEvents');
                            evt.initEvent(nomeEvento, false, true);
                            campo.dispatchEvent(evt);
                        }
                    } catch (e) {}
                }

                function redigitar(campo) {
                    if (!campo || campo.disabled === true || campo.readOnly === true) {
                        return null;
                    }
                    var valor = limparTexto(campo.value);
                    if (numero(valor) <= 0) {
                        return null;
                    }
                    try { campo.focus(); } catch (e) {}
                    try { campo.click(); } catch (e) {}
                    disparar(campo, 'keydown');
                    campo.value = '';
                    disparar(campo, 'propertychange');
                    disparar(campo, 'keyup');
                    campo.value = valor;
                    disparar(campo, 'keydown');
                    disparar(campo, 'keypress');
                    disparar(campo, 'propertychange');
                    disparar(campo, 'keyup');
                    disparar(campo, 'change');
                    disparar(campo, 'blur');
                    try { campo.blur(); } catch (e) {}
                    return {nome: campo.name || '', valor: campo.value};
                }

                var lista = document.getElementById('lista') || document.getElementsByName('lista')[0];
                var aplicados = [];
                if (lista && lista.rows) {
                    for (var i = 1; i < lista.rows.length; i++) {
                        var aux = auxLinha(i);
                        var nomes = [
                            'textdevUn' + aux,
                            'textdevAv' + aux,
                            'texttroUn' + aux,
                            'texttroAv' + aux,
                            'textvazUn' + aux,
                            'textvazAv' + aux
                        ];
                        for (var j = 0; j < nomes.length; j++) {
                            var campo = document.getElementsByName(nomes[j])[0];
                            var ret = redigitar(campo);
                            if (ret) aplicados.push(ret);
                        }
                    }
                }

                var botSalvar = document.getElementsByName('BotSalvar')[0];
                var botCancelarAlt = document.getElementsByName('BotCancelarAlt')[0];
                if (aplicados.length > 0 && botSalvar) botSalvar.disabled = false;
                if (aplicados.length > 0 && botCancelarAlt) botCancelarAlt.disabled = false;

                return {
                    aplicados: aplicados,
                    total: aplicados.length,
                    botSalvarDisabled: botSalvar ? !!botSalvar.disabled : null
                };
                """
            )
        except Exception as exc:
            return {"aplicados": [], "total": 0, "erro": str(exc)}

    def _zerar_valores_editaveis_primeiro_envio_030302(self):
        """Preserva e zera valores positivos editaveis antes do primeiro salvar.

        O objetivo e fazer um mapa que ja veio preenchido percorrer o mesmo fluxo
        do mapa vazio no Promax: primeiro submit com quantidades zeradas, geracao
        das diferencas, captura da lista, recarga, reaplicacao e salvar final.
        """
        try:
            self._reentrar_frame(timeout=10)
            return self.driver.execute_script(
                """
                function auxLinha(index) {
                    if (index < 10) return '00' + index;
                    if (index < 100) return '0' + index;
                    return String(index);
                }

                function numero(valor) {
                    var n = parseInt(String(valor || '').replace(/\\D/g, ''), 10);
                    return isNaN(n) ? 0 : n;
                }

                function disparar(campo, nomeEvento) {
                    try {
                        if (campo.fireEvent) {
                            campo.fireEvent('on' + nomeEvento);
                        } else if (campo.ownerDocument && campo.ownerDocument.createEvent) {
                            var evt = campo.ownerDocument.createEvent('HTMLEvents');
                            evt.initEvent(nomeEvento, false, true);
                            campo.dispatchEvent(evt);
                        }
                    } catch (e) {}
                }

                function zerarCampo(campo) {
                    if (!campo || campo.disabled === true || campo.readOnly === true) {
                        return null;
                    }
                    var valorAnterior = String(campo.value || '').replace(/^\\s+|\\s+$/g, '');
                    if (numero(valorAnterior) <= 0) {
                        return null;
                    }

                    try { campo.focus(); } catch (e) {}
                    try { campo.click(); } catch (e) {}
                    try { if (campo.select) campo.select(); } catch (e) {}

                    disparar(campo, 'keydown');
                    campo.value = '';
                    disparar(campo, 'propertychange');
                    disparar(campo, 'keyup');

                    campo.value = '0';
                    disparar(campo, 'keydown');
                    disparar(campo, 'keypress');
                    disparar(campo, 'propertychange');
                    disparar(campo, 'keyup');
                    disparar(campo, 'change');
                    disparar(campo, 'blur');
                    try { campo.blur(); } catch (e) {}

                    return {
                        nome: campo.name || '',
                        valorOriginal: valorAnterior,
                        valorZerado: String(campo.value || '')
                    };
                }

                var lista = document.getElementById('lista') || document.getElementsByName('lista')[0];
                var preservados = [];
                var porLinha = [];

                if (lista && lista.rows) {
                    for (var i = 1; i < lista.rows.length; i++) {
                        var aux = auxLinha(i);
                        var codigoCampo = document.getElementsByName('textcod' + aux)[0];
                        var linha = {
                            linha: aux,
                            codigo: codigoCampo ? String(codigoCampo.value || '') : '',
                            campos: []
                        };
                        var nomes = [
                            'textdevUn' + aux,
                            'textdevAv' + aux,
                            'texttroUn' + aux,
                            'texttroAv' + aux,
                            'textvazUn' + aux,
                            'textvazAv' + aux
                        ];
                        for (var j = 0; j < nomes.length; j++) {
                            var campo = document.getElementsByName(nomes[j])[0];
                            var ret = zerarCampo(campo);
                            if (ret) {
                                preservados.push(ret);
                                linha.campos.push(ret);
                            }
                        }
                        if (linha.campos.length > 0) porLinha.push(linha);
                    }
                }

                var botSalvar = document.getElementsByName('BotSalvar')[0];
                var botCancelarAlt = document.getElementsByName('BotCancelarAlt')[0];
                if (preservados.length > 0) {
                    if (botSalvar) botSalvar.disabled = false;
                    if (botCancelarAlt) botCancelarAlt.disabled = false;
                }

                return {
                    preservados: preservados,
                    porLinha: porLinha,
                    total: preservados.length,
                    listaRows: lista && lista.rows ? lista.rows.length : 0,
                    botSalvarDisabled: botSalvar ? !!botSalvar.disabled : null
                };
                """
            )
        except Exception as exc:
            return {
                "preservados": [],
                "porLinha": [],
                "total": 0,
                "erro": str(exc),
            }

    def _habilitar_salvar_mapa_zerado_030302(self):
        try:
            self._reentrar_frame(timeout=10)
            return self.driver.execute_script(
                """
                function auxLinha(index) {
                    if (index < 10) return '00' + index;
                    if (index < 100) return '0' + index;
                    return String(index);
                }

                function disparar(campo, nomeEvento) {
                    try {
                        if (campo.fireEvent) {
                            campo.fireEvent('on' + nomeEvento);
                        } else if (campo.ownerDocument && campo.ownerDocument.createEvent) {
                            var evt = campo.ownerDocument.createEvent('HTMLEvents');
                            evt.initEvent(nomeEvento, false, true);
                            campo.dispatchEvent(evt);
                        }
                    } catch (e) {}
                }

                function tocarCampo(campo) {
                    if (!campo || campo.disabled === true || campo.readOnly === true) {
                        return null;
                    }
                    var valorAnterior = String(campo.value || '');
                    try { campo.focus(); } catch (e) {}
                    try { campo.click(); } catch (e) {}
                    try { if (campo.select) campo.select(); } catch (e) {}
                    disparar(campo, 'keydown');
                    if (valorAnterior.replace(/^\\s+|\\s+$/g, '') === '') {
                        campo.value = '0';
                    } else {
                        campo.value = valorAnterior;
                    }
                    disparar(campo, 'keypress');
                    disparar(campo, 'propertychange');
                    disparar(campo, 'keyup');
                    disparar(campo, 'change');
                    disparar(campo, 'blur');
                    try { campo.blur(); } catch (e) {}
                    return {
                        nome: campo.name || '',
                        valorAnterior: valorAnterior,
                        valorDepois: String(campo.value || '')
                    };
                }

                var lista = document.getElementById('lista') || document.getElementsByName('lista')[0];
                var aplicados = [];
                if (lista && lista.rows) {
                    for (var i = 1; i < lista.rows.length; i++) {
                        var aux = auxLinha(i);
                        var nomes = [
                            'textdevUn' + aux,
                            'textdevAv' + aux,
                            'texttroUn' + aux,
                            'texttroAv' + aux,
                            'textvazUn' + aux,
                            'textvazAv' + aux
                        ];
                        for (var j = 0; j < nomes.length; j++) {
                            var campo = document.getElementsByName(nomes[j])[0];
                            var ret = tocarCampo(campo);
                            if (ret) aplicados.push(ret);
                        }
                    }
                }

                var botSalvar = document.getElementsByName('BotSalvar')[0];
                var botCancelarAlt = document.getElementsByName('BotCancelarAlt')[0];
                if (aplicados.length > 0) {
                    if (botSalvar) botSalvar.disabled = false;
                    if (botCancelarAlt) botCancelarAlt.disabled = false;
                }

                return {
                    aplicados: aplicados,
                    total: aplicados.length,
                    botSalvarDisabled: botSalvar ? !!botSalvar.disabled : null,
                    listaRows: lista && lista.rows ? lista.rows.length : 0
                };
                """
            )
        except Exception as exc:
            return {"aplicados": [], "total": 0, "erro": str(exc)}

    def _capturar_alertas(self, tentativas=2, timeout=2):
        return self.lidar_com_alertas(
            tentativas=tentativas,
            timeout=timeout,
            timeout_entre_alertas=1,
            max_alertas=10,
        )

    def lidar_com_alertas(self, tentativas=2, timeout=2, timeout_entre_alertas=1, max_alertas=10):
        """Na 030302, alerta nativo faz parte do fluxo e nao pode ser aceito genericamente."""
        alertas_tratados = 0
        tentativas_sem_alerta = 0
        mensagens_alerta = []

        while tentativas_sem_alerta < tentativas and alertas_tratados < max_alertas:
            try:
                WebDriverWait(
                    self.driver,
                    timeout if alertas_tratados == 0 else timeout_entre_alertas,
                    poll_frequency=0.2,
                ).until(lambda driver: driver.switch_to.alert)
                alerta = self.driver.switch_to.alert
                texto_alerta = str(alerta.text or "")
                decisao = self._decidir_resposta_msgbox_030302(texto_alerta)
                if not decisao or decisao.get("resposta") == "pendente":
                    self.logger.warning(
                        "Alerta 030302 detectado sem resposta automatica: %s",
                        texto_alerta,
                    )
                    mensagens_alerta.append(texto_alerta)
                    break

                resposta = decisao["resposta"]
                if decisao.get("classificacao") == "alerta_km":
                    resultado_km = self._preencher_km_fallback_para_alerta(texto_alerta)
                    if not (resultado_km or {}).get("ok"):
                        mensagens_alerta.append(texto_alerta)
                        break

                if resposta in ("ok", "sim"):
                    alerta.accept()
                elif resposta == "nao":
                    alerta.dismiss()
                else:
                    self.logger.warning(
                        "Alerta 030302 detectado com resposta nao suportada: %s | resposta=%s",
                        texto_alerta,
                        resposta,
                    )
                    mensagens_alerta.append(texto_alerta)
                    break

                confirmacao = {
                    "tipo": "alert",
                    "mensagem": texto_alerta,
                    "resposta": resposta,
                }
                self._registrar_alerta_030302(confirmacao, origem="lidar-com-alertas")
                mensagens_alerta.append(texto_alerta)
                self.wait_for_no_alert(timeout=max(timeout_entre_alertas, 1))
                alertas_tratados += 1
                tentativas_sem_alerta = 0
            except TimeoutException:
                tentativas_sem_alerta += 1
            except NoAlertPresentException:
                tentativas_sem_alerta += 1

        if alertas_tratados:
            self.logger.info(
                "Tratamento de alertas 030302 concluido. Total respondido(s): %s",
                alertas_tratados,
            )
        return mensagens_alerta

    def _classificar_alerta_030302(self, confirmacao):
        decisao = self._decidir_resposta_msgbox_030302((confirmacao or {}).get("mensagem"))
        if decisao:
            return decisao["classificacao"]
        return "outro"

    def _registrar_alerta_030302(self, confirmacao, origem=""):
        if not confirmacao:
            return
        tipo = self._classificar_alerta_030302(confirmacao)
        mensagem = str(confirmacao.get("mensagem") or "").replace("\r", " ").replace("\n", " ")
        if len(mensagem) > 500:
            mensagem = mensagem[:500] + "..."
        origem_texto = f" | origem={origem}" if origem else ""
        self.logger.info(
            "ALERTA 030302 CAPTURADO%s | tipo=%s | resposta=%s | mensagem=%s",
            origem_texto,
            tipo,
            confirmacao.get("resposta"),
            mensagem,
        )

    def _chave_confirmacao_030302(self, confirmacao):
        mensagem = self._normalizar_texto((confirmacao or {}).get("mensagem"))
        mensagem = " ".join(str(mensagem or "").split())
        resposta = str((confirmacao or {}).get("resposta") or "").lower().strip()
        return (self._classificar_alerta_030302(confirmacao), mensagem, resposta)

    def _adicionar_confirmacao_030302(self, confirmacoes, confirmacao, origem=""):
        if not confirmacao:
            return False
        chave = self._chave_confirmacao_030302(confirmacao)
        if any(self._chave_confirmacao_030302(item) == chave for item in confirmacoes or []):
            self.logger.debug(
                "Alerta 030302 duplicado ignorado | origem=%s | tipo=%s | mensagem=%s",
                origem,
                chave[0],
                str((confirmacao or {}).get("mensagem") or "").replace("\r", " ").replace("\n", " "),
            )
            return False
        confirmacoes.append(confirmacao)
        self._registrar_alerta_030302(confirmacao, origem=origem)
        return True

    def _extrair_alertas_capturados(self, *listas_confirmacoes):
        alertas = []
        chaves = set()
        for confirmacoes in listas_confirmacoes:
            for confirmacao in confirmacoes or []:
                tipo_origem = str(confirmacao.get("tipo") or "")
                if not (
                    tipo_origem.startswith("alert")
                    or tipo_origem == "html"
                    or tipo_origem.startswith("msgbxSimNao")
                ):
                    continue
                chave = self._chave_confirmacao_030302(confirmacao)
                if chave in chaves:
                    continue
                chaves.add(chave)
                item = dict(confirmacao)
                item["classificacao"] = self._classificar_alerta_030302(confirmacao)
                alertas.append(item)
        return alertas

    def _campo_existe_js(self, nome):
        try:
            return bool(
                self.driver.execute_script(
                    "return !!document.getElementsByName(arguments[0])[0];",
                    nome,
                )
            )
        except Exception:
            return False

    def _esperar_campo_js(self, nome, timeout_segundos=15):
        try:
            self.wait_for_js_condition(
                f"return !!document.getElementsByName('{nome}')[0];",
                timeout=timeout_segundos,
                description=f"campo {nome} existir",
            )
            return True
        except TimeoutException:
            return False

    def _reentrar_frame(self, timeout=15):
        try:
            self.switch_to_default_content()
        except UnexpectedAlertPresentException as exc:
            recuperacao = self._clicar_sim_recuperar_mapa()
            if not recuperacao:
                raise exc
            self.logger.info("Alerta de recuperacao respondido com sim antes de reentrar no frame: %s", recuperacao)
            self.switch_to_default_content()
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=timeout)

    def _estado_mapa_js(self):
        return self.driver.execute_script(
            """
            var mapa = document.getElementsByName('mapa')[0];
            var pontoApoio = document.getElementsByName('pontoApoio')[0];
            var lista = document.getElementById('lista') || document.getElementsByName('lista')[0];
            var botSalvar = document.getElementsByName('BotSalvar')[0];
            var listaDif = document.getElementsByName('listaDiferencas')[0];
            var divDif = document.getElementById('DivDiferencas');
            var divMsg = document.getElementById('DivMensagem');
            function texto(el) { return el ? String(el.innerText || el.textContent || '') : ''; }
            function auxLinha(index) {
                if (index < 10) return '00' + index;
                if (index < 100) return '0' + index;
                return String(index);
            }
            function campoValor(nome) {
                var campo = document.getElementsByName(nome)[0];
                return campo ? campo.value : null;
            }
            function campoDisabled(nome) {
                var campo = document.getElementsByName(nome)[0];
                return campo ? !!campo.disabled : null;
            }
            function campoHidden(nome) {
                var campo = document.getElementsByName(nome)[0];
                return campo ? campo.value : null;
            }
            function botaoDisabled(nome) {
                var botao = document.getElementsByName(nome)[0];
                return botao ? !!botao.disabled : null;
            }
            var produtos = [];
            if (lista && lista.rows) {
                for (var i = 1; i < lista.rows.length && produtos.length < 30; i++) {
                    var aux = auxLinha(i);
                    var codigo = campoValor('textcod' + aux);
                    if (codigo === null || String(codigo) === '') {
                        var textoLinha = texto(lista.rows[i]);
                        var matchCodigo = textoLinha.match(/\\d+/);
                        codigo = matchCodigo ? matchCodigo[0] : null;
                    }
                    produtos.push({
                        linha: aux,
                        codigo: codigo,
                        descricao: texto(lista.rows[i]).replace(/\\s+/g, ' ').substring(0, 120),
                        devUn: campoValor('textdevUn' + aux),
                        devAv: campoValor('textdevAv' + aux),
                        troUn: campoValor('texttroUn' + aux),
                        troAv: campoValor('texttroAv' + aux),
                        vazUn: campoValor('textvazUn' + aux),
                        vazAv: campoValor('textvazAv' + aux),
                        devUnDisabled: campoDisabled('textdevUn' + aux),
                        devAvDisabled: campoDisabled('textdevAv' + aux),
                        troUnDisabled: campoDisabled('texttroUn' + aux),
                        troAvDisabled: campoDisabled('texttroAv' + aux),
                        vazUnDisabled: campoDisabled('textvazUn' + aux),
                        vazAvDisabled: campoDisabled('textvazAv' + aux)
                    });
                }
            }
            return {
                mapa: mapa ? mapa.value : null,
                mapaDisabled: mapa ? !!mapa.disabled : null,
                pontoApoio: pontoApoio ? pontoApoio.value : null,
                pontoApoioDisabled: pontoApoio ? !!pontoApoio.disabled : null,
                mapaSalvo: (typeof mapaSalvo !== 'undefined') ? String(mapaSalvo) : null,
                statusMapa: (typeof statusMapa1 !== 'undefined') ? String(statusMapa1) : null,
                listaRows: lista && lista.rows ? lista.rows.length : 0,
                botSalvarDisabled: botSalvar ? !!botSalvar.disabled : null,
                botLancamentosDisabled: botaoDisabled('BotLancamentos'),
                botLancBonusASDisabled: botaoDisabled('BotLancBonusAS'),
                opcao: campoHidden('opcao'),
                numeroItems: campoHidden('numeroItems'),
                itensListaLength: campoHidden('itensLista') ? String(campoHidden('itensLista')).length : 0,
                fBotSalvar: campoHidden('fBotSalvar'),
                idMostraMsgAfericao: campoHidden('idMostraMsgAfericao'),
                idAchouGuiasSalvas: campoHidden('idAchouGuiasSalvas'),
                idAchouGuiaMapa: campoHidden('idAchouGuiaMapa'),
                listaDiferencasLength: listaDif && listaDif.options ? listaDif.options.length : 0,
                produtos: produtos,
                divDiferencasDisplay: divDif ? divDif.style.display : null,
                divMensagemDisplay: divMsg ? divMsg.style.display : null,
                divMensagemTexto: texto(divMsg).substring(0, 300)
            };
            """
        )

    def _estado_telinhas_js(self):
        return self.driver.execute_script(
            """
            function visivel(el) {
                if (!el) return false;
                if (el.style && el.style.display === 'none') return false;
                return true;
            }
            function texto(el) {
                return el ? String(el.innerText || el.textContent || '') : '';
            }
            function textoBotao(el) {
                if (!el) return '';
                return String(
                    (el.innerText || '') + ' ' +
                    (el.textContent || '') + ' ' +
                    (el.value || '') + ' ' +
                    (el.name || '') + ' ' +
                    (el.id || '')
                ).replace(/\\s+/g, ' ').substring(0, 120);
            }
            var listaDif = document.getElementsByName('listaDiferencas')[0];
            var divDif = document.getElementById('DivDiferencas');
            var divMsg = document.getElementById('DivMensagem');
            var divFila = document.getElementById('DivFila');
            var divMotivos = document.getElementById('DivMotivosReabMapa');
            var botSalvar = document.getElementsByName('BotSalvar')[0];
            var textosDif = [];
            var botoesVisiveis = [];
            if (listaDif && listaDif.options) {
                for (var i = 0; i < listaDif.options.length && i < 5; i++) {
                    textosDif.push(String(listaDif.options[i].text || listaDif.options[i].innerText || ''));
                }
            }
            var botoes = document.querySelectorAll ? document.querySelectorAll('button,input[type=button],input[type=submit],a') : [];
            for (var b = 0; b < botoes.length && botoesVisiveis.length < 20; b++) {
                if (visivel(botoes[b])) {
                    botoesVisiveis.push(textoBotao(botoes[b]));
                }
            }
            return {
                listaDiferencasLength: listaDif && listaDif.options ? listaDif.options.length : 0,
                listaDiferencasTextos: textosDif,
                botoesVisiveis: botoesVisiveis,
                divDiferencasDisplay: divDif ? divDif.style.display : null,
                divDiferencasVisivel: visivel(divDif),
                divDiferencasTexto: texto(divDif).substring(0, 500),
                divMensagemDisplay: divMsg ? divMsg.style.display : null,
                divMensagemVisivel: visivel(divMsg),
                divMensagemTexto: texto(divMsg).substring(0, 300),
                divFilaDisplay: divFila ? divFila.style.display : null,
                divFilaVisivel: visivel(divFila),
                divMotivosDisplay: divMotivos ? divMotivos.style.display : null,
                divMotivosVisivel: visivel(divMotivos),
                botSalvarDisabled: botSalvar ? !!botSalvar.disabled : null
            };
            """
        )

    def _recuperar_diferencas_de_scripts_js(self):
        try:
            return self.driver.execute_script(
                """
                function soDigitos(valor) {
                    return String(valor || '').replace(/\\D/g, '');
                }

                function numero(valor) {
                    var limpo = soDigitos(valor);
                    if (limpo === '') return 0;
                    return parseInt(limpo, 10) || 0;
                }

                function auxLinha(index) {
                    if (index < 10) return '00' + index;
                    if (index < 100) return '0' + index;
                    return String(index);
                }

                function setCampo(nome, valor) {
                    var campo = document.getElementsByName(nome)[0];
                    if (!campo) return false;
                    campo.disabled = false;
                    campo.readOnly = false;
                    campo.value = String(valor || 0);
                    try {
                        if (campo.fireEvent) {
                            campo.fireEvent('onchange');
                        } else if (document.createEvent) {
                            var evt = document.createEvent('HTMLEvents');
                            evt.initEvent('change', false, true);
                            campo.dispatchEvent(evt);
                        }
                    } catch (e) {}
                    return true;
                }

                function localizarLinhaProduto(codigo) {
                    var codigoNum = numero(codigo);
                    var lista = document.getElementById('lista') || document.getElementsByName('lista')[0];
                    if (!lista || !lista.rows) return null;
                    for (var i = 1; i < lista.rows.length; i++) {
                        var aux = auxLinha(i);
                        var campoCod = document.getElementsByName('textcod' + aux)[0];
                        if (campoCod && numero(campoCod.value) === codigoNum) {
                            return aux;
                        }
                    }
                    return null;
                }

                function snapshotLinhas() {
                    var lista = document.getElementById('lista') || document.getElementsByName('lista')[0];
                    var linhas = [];
                    if (!lista || !lista.rows) return linhas;
                    for (var i = 1; i < lista.rows.length && linhas.length < 30; i++) {
                        var aux = auxLinha(i);
                        var campoCod = document.getElementsByName('textcod' + aux)[0];
                        var codigo = campoCod ? campoCod.value : '';
                        if (codigo === '') {
                            var textoLinha = String(lista.rows[i].innerText || lista.rows[i].textContent || '');
                            var matchCodigo = textoLinha.match(/\\d+/);
                            codigo = matchCodigo ? matchCodigo[0] : '';
                        }
                        function valor(nome) {
                            var campo = document.getElementsByName(nome + aux)[0];
                            return campo ? campo.value : null;
                        }
                        function disabled(nome) {
                            var campo = document.getElementsByName(nome + aux)[0];
                            return campo ? !!campo.disabled : null;
                        }
                        linhas.push({
                            linha: aux,
                            codigo: codigo,
                            texto: String(lista.rows[i].innerText || lista.rows[i].textContent || '').replace(/\\s+/g, ' ').substring(0, 120),
                            devUn: valor('textdevUn'),
                            devAv: valor('textdevAv'),
                            troUn: valor('texttroUn'),
                            troAv: valor('texttroAv'),
                            vazUn: valor('textvazUn'),
                            vazAv: valor('textvazAv'),
                            devUnDisabled: disabled('textdevUn'),
                            devAvDisabled: disabled('textdevAv')
                        });
                    }
                    return linhas;
                }

                function textoScripts(doc) {
                    var textos = [];
                    if (!doc) return textos;
                    var scripts = doc.getElementsByTagName('script');
                    for (var i = 0; i < scripts.length; i++) {
                        textos.push(String(scripts[i].text || scripts[i].textContent || scripts[i].innerHTML || ''));
                    }
                    if (doc.body) {
                        var body = String(doc.body.innerText || doc.body.textContent || '');
                        if (body.indexOf('cdProdDif') !== -1 || body.indexOf('listaDiferencas') !== -1) {
                            textos.push(body);
                        }
                    }
                    return textos;
                }

                function coletarTextos(win, visitados, textos) {
                    try {
                        if (!win || visitados.indexOf(win) !== -1) return;
                        visitados.push(win);
                    } catch (e) {
                        return;
                    }
                    try {
                        var doc = win.document;
                        var ts = textoScripts(doc);
                        for (var t = 0; t < ts.length; t++) textos.push(ts[t]);
                    } catch (e) {}
                    try {
                        for (var i = 0; i < win.frames.length; i++) {
                            coletarTextos(win.frames[i], visitados, textos);
                        }
                    } catch (e) {}
                }

                function valorVar(bloco, nome) {
                    var re = new RegExp("var\\\\s+" + nome + "\\\\s*=\\\\s*(?:parseInt\\\\s*\\\\()?\\\\s*\\\\(?\\\\s*['\\\"]([\\\\s\\\\S]*?)['\\\"]", "i");
                    var m = re.exec(bloco);
                    return m ? m[1] : '';
                }

                function codigoOption(bloco) {
                    var m = /oOption\\.cdProdDif\\s*=\\s*['"]([\\s\\S]*?)['"]/i.exec(bloco);
                    return m ? m[1] : '';
                }

                function paresTexto(texto) {
                    var pares = [];
                    var re = /(\\d+)\\s*\\/\\s*(\\d+)/g;
                    var m;
                    while ((m = re.exec(String(texto || ''))) !== null) {
                        pares.push([numero(m[1]), numero(m[2])]);
                    }
                    return pares;
                }

                function aplicarItem(item, origem, listaDif, vistos, aplicados, naoAplicados) {
                    var codigo = item.codigo || item.cdProdDif || item.value || '';
                    if (!codigo && item.texto) {
                        codigo = String(item.texto).split(/\\s+/)[0];
                    }
                    var codigoNum = numero(codigo);
                    if (!codigoNum || vistos[codigoNum]) return;

                    var aux = localizarLinhaProduto(codigo);
                    if (!aux) {
                        naoAplicados.push({codigo: codigo, motivo: 'produto-nao-encontrado-' + origem});
                        return;
                    }

                    var texto = String(item.texto || item.text || '');
                    var pares = paresTexto(texto);
                    if (item.faltaUn === undefined && pares.length > 0) {
                        item.faltaUn = pares[pares.length - 1][0];
                        item.faltaAv = pares[pares.length - 1][1];
                    }
                    if (item.sobraUn === undefined && pares.length > 1) {
                        item.sobraUn = pares[pares.length - 2][0];
                        item.sobraAv = pares[pares.length - 2][1];
                    }
                    if (item.retornoUn === undefined && pares.length > 2) {
                        item.retornoUn = pares[pares.length - 3][0];
                        item.retornoAv = pares[pares.length - 3][1];
                    }
                    if (item.previsaoUn === undefined && pares.length > 3) {
                        item.previsaoUn = pares[pares.length - 4][0];
                        item.previsaoAv = pares[pares.length - 4][1];
                    }

                    item.codigo = codigo;
                    item.linha = aux;
                    item.faltaUn = numero(item.faltaUn);
                    item.faltaAv = numero(item.faltaAv);
                    item.sobraUn = numero(item.sobraUn);
                    item.sobraAv = numero(item.sobraAv);
                    item.retornoUn = numero(item.retornoUn);
                    item.retornoAv = numero(item.retornoAv);
                    item.previsaoUn = numero(item.previsaoUn);
                    item.previsaoAv = numero(item.previsaoAv);
                    item.origem = origem;
                    item.okUn = setCampo('textdevUn' + aux, item.faltaUn);
                    item.okAv = setCampo('textdevAv' + aux, item.faltaAv);
                    vistos[codigoNum] = true;

                    if (listaDif && listaDif.options) {
                        var opt = document.createElement('OPTION');
                        opt.value = String(codigoNum);
                        opt.cdProdDif = String(codigo);
                        opt.text = texto || [
                            codigoNum,
                            item.unidade || '',
                            item.descricao || '',
                            item.previsaoUn + '/' + item.previsaoAv,
                            item.retornoUn + '/' + item.retornoAv,
                            item.sobraUn + '/' + item.sobraAv,
                            item.faltaUn + '/' + item.faltaAv
                        ].join(' ');
                        try { listaDif.add(opt); } catch (e) {}
                    }

                    aplicados.push(item);
                }

                function blocosProdutos(texto) {
                    var blocos = [];
                    var pos = 0;
                    while (true) {
                        var idxAdd = texto.indexOf('listaDiferencas', pos);
                        if (idxAdd === -1) break;
                        var idxOpt = texto.indexOf('add', idxAdd);
                        if (idxOpt === -1) {
                            pos = idxAdd + 1;
                            continue;
                        }
                        var inicio = texto.lastIndexOf('var lenTit', idxAdd);
                        if (inicio === -1) inicio = texto.lastIndexOf('var cdProdDif', idxAdd);
                        if (inicio !== -1) {
                            blocos.push(texto.substring(inicio, Math.min(texto.length, idxOpt + 200)));
                        }
                        pos = idxOpt + 3;
                    }
                    return blocos;
                }

                var textos = [];
                var visitados = [];
                coletarTextos(window, visitados, textos);
                try { coletarTextos(window.parent, visitados, textos); } catch (e) {}
                try { coletarTextos(window.top, visitados, textos); } catch (e) {}

                var listaDif = document.getElementsByName('listaDiferencas')[0];
                var vistos = {};
                if (listaDif && listaDif.options) {
                    for (var v = 0; v < listaDif.options.length; v++) {
                        vistos[numero(listaDif.options[v].value)] = true;
                    }
                }

                var aplicados = [];
                var naoAplicados = [];
                var scriptsAnalisados = 0;
                var capturados = window.__promax030302ItensDiferencas || [];
                for (var h = 0; h < capturados.length; h++) {
                    aplicarItem(
                        {
                            codigo: capturados[h].cdProdDif || capturados[h].value,
                            texto: capturados[h].text
                        },
                        'historico-lista',
                        listaDif,
                        vistos,
                        aplicados,
                        naoAplicados
                    );
                }
                for (var t = 0; t < textos.length; t++) {
                    if (textos[t].indexOf('cdProdDif') === -1 || textos[t].indexOf('qtFalta') === -1) continue;
                    scriptsAnalisados++;
                    var blocos = blocosProdutos(textos[t]);
                    for (var b = 0; b < blocos.length; b++) {
                        var bloco = blocos[b];
                        var codigo = codigoOption(bloco) || valorVar(bloco, 'cdProdDif');
                        if (!codigo) continue;
                        var codigoNum = numero(codigo);
                        if (!codigoNum || vistos[codigoNum]) continue;

                        var aux = localizarLinhaProduto(codigo);
                        if (!aux) {
                            naoAplicados.push({codigo: codigo, motivo: 'produto-nao-encontrado-em-script'});
                            continue;
                        }

                        var item = {
                            codigo: codigo,
                            linha: aux,
                            unidade: String(valorVar(bloco, 'unVendaDif') || '').replace(/[\\r\\n]/g, '').trim(),
                            descricao: String(valorVar(bloco, 'dsProdDif') || '').replace(/[\\r\\n]/g, ' ').trim(),
                            previsaoUn: numero(valorVar(bloco, 'qtPrevUnDif')),
                            previsaoAv: numero(valorVar(bloco, 'qtPrevAvDif')),
                            retornoUn: numero(valorVar(bloco, 'qtRealUnDif')),
                            retornoAv: numero(valorVar(bloco, 'qtRealAvDif')),
                            sobraUn: numero(valorVar(bloco, 'qtSobraUnDif')),
                            sobraAv: numero(valorVar(bloco, 'qtSobraAvDif')),
                            faltaUn: numero(valorVar(bloco, 'qtFaltaUnDif')),
                            faltaAv: numero(valorVar(bloco, 'qtFaltaAvDif'))
                        };

                        aplicarItem(item, 'script-auxiliar', listaDif, vistos, aplicados, naoAplicados);
                    }
                }

                var botSalvar = document.getElementsByName('BotSalvar')[0];
                var botCancelarAlt = document.getElementsByName('BotCancelarAlt')[0];
                if (aplicados.length > 0) {
                    if (botSalvar) botSalvar.disabled = false;
                    if (botCancelarAlt) botCancelarAlt.disabled = false;
                }

                return {
                    recuperou: aplicados.length > 0,
                    aplicados: aplicados,
                    naoAplicados: naoAplicados,
                    itensHistorico: capturados.length,
                    scriptsAnalisados: scriptsAnalisados,
                    listaDiferencasLength: listaDif && listaDif.options ? listaDif.options.length : 0,
                    botSalvarDisabled: botSalvar ? !!botSalvar.disabled : null
                };
                """
            )
        except Exception as exc:
            return {"recuperou": False, "erro": str(exc)}

    def _aguardar_telinhas_pos_carga(self, timeout=10):
        ultimo_estado = None
        estados_estaveis = 0
        def _condition(_driver):
            nonlocal ultimo_estado, estados_estaveis
            try:
                estado = self._estado_telinhas_js()
                ultimo_estado = estado
                if (
                    int(estado.get("listaDiferencasLength") or 0) > 0
                    or estado.get("divDiferencasDisplay") != "none"
                    or estado.get("divMensagemDisplay") not in (None, "none")
                ):
                    self.logger.info("Telinha/lista 030302 detectada apos carga: %s", estado)
                    return estado

                if estado.get("botSalvarDisabled") is False:
                    estados_estaveis += 1
                    if estados_estaveis >= 4:
                        return estado
                else:
                    estados_estaveis = 0
            except Exception as exc:
                ultimo_estado = {"erro": str(exc)}
            return False

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.2).until(_condition)
        except TimeoutException:
            pass
        self.logger.info("Estado das telinhas 030302 apos espera: %s", ultimo_estado)
        return ultimo_estado or {}

    def _aguardar_lista_diferencas(self, timeout=15):
        ultimo_estado = None
        amostras_vazias = 0
        alertas_respondidos = []

        try:
            resposta_alerta_inicial = self._responder_alerta_nativo(acertar_diferencas=True)
            if resposta_alerta_inicial:
                self._adicionar_confirmacao_030302(
                    alertas_respondidos,
                    resposta_alerta_inicial,
                    origem="aguardar-lista-inicial",
                )
                ultimo_estado = {
                    "alertaRespondido": resposta_alerta_inicial,
                    "alertasRespondidos": list(alertas_respondidos),
                }
                if self._eh_mensagem_sem_diferencas(
                    resposta_alerta_inicial.get("mensagem")
                ):
                    ultimo_estado["mensagemOk"] = True
                    ultimo_estado["mensagemSemDiferencas"] = True
                    ultimo_estado["listaDiferencasLength"] = 0
                    self.logger.info(
                        "Alerta OK/sem diferencas 030302 detectado antes da espera da lista: %s",
                        resposta_alerta_inicial,
                    )
                    return ultimo_estado
            self._reentrar_frame(timeout=5)
        except UnexpectedAlertPresentException:
            pass
        except Exception as exc:
            ultimo_estado = {"erro": str(exc), "alertasRespondidos": list(alertas_respondidos)}

        def _condition(_driver):
            nonlocal ultimo_estado, amostras_vazias, alertas_respondidos
            resposta_alerta = self._responder_alerta_nativo(acertar_diferencas=True)
            if resposta_alerta:
                self._adicionar_confirmacao_030302(
                    alertas_respondidos,
                    resposta_alerta,
                    origem="aguardar-lista",
                )
                mensagem_alerta = resposta_alerta.get("mensagem")
                if self._eh_mensagem_sem_diferencas(mensagem_alerta):
                    estado = {
                        "alertaRespondido": resposta_alerta,
                        "alertasRespondidos": list(alertas_respondidos),
                        "mensagemOk": True,
                        "mensagemSemDiferencas": True,
                        "listaDiferencasLength": 0,
                    }
                    ultimo_estado = estado
                    self.logger.info("Alerta OK/sem diferencas 030302 detectado: %s", resposta_alerta)
                    return estado
                self.logger.info(
                    "Alerta intermediario 030302 respondido durante espera de lista: %s",
                    resposta_alerta,
                )
                return False

            resposta_html = self._responder_pergunta_html_js()
            if resposta_html:
                self._adicionar_confirmacao_030302(
                    alertas_respondidos,
                    resposta_html,
                    origem="aguardar-lista-html",
                )
                mensagem_html = resposta_html.get("mensagem")
                if (
                    resposta_html.get("resposta") != "pendente"
                    and self._eh_mensagem_sem_diferencas(mensagem_html)
                ):
                    estado = {
                        "alertaRespondido": resposta_html,
                        "alertasRespondidos": list(alertas_respondidos),
                        "mensagemOk": True,
                        "mensagemSemDiferencas": True,
                        "listaDiferencasLength": 0,
                    }
                    ultimo_estado = estado
                    self.logger.info("Mensagem HTML OK/sem diferencas 030302 clicada: %s", resposta_html)
                    return estado
                self.logger.info(
                    "Pergunta HTML 030302 clicada durante espera de lista: %s",
                    resposta_html,
                )
                return False

            try:
                estado = self._estado_telinhas_js() or {}
                ultimo_estado = estado
                estado["alertasRespondidos"] = list(alertas_respondidos)
                lista_len = int(estado.get("listaDiferencasLength") or 0)
                mensagem_visivel = estado.get("divMensagemDisplay") not in (None, "none")
                diferencas_visivel = bool(estado.get("divDiferencasVisivel"))
                mensagem_texto = estado.get("divMensagemTexto")
                if mensagem_visivel and self._eh_mensagem_sem_diferencas(mensagem_texto):
                    estado["mensagemOk"] = True
                    estado["mensagemSemDiferencas"] = True
                    self.logger.info("Mensagem OK/sem diferencas 030302 detectada: %s", estado)
                    return estado
                if (
                    lista_len > 0
                    or mensagem_visivel
                ):
                    return estado
                if diferencas_visivel and lista_len == 0:
                    recuperacao = self._recuperar_diferencas_de_scripts_js()
                    estado["recuperacaoScripts"] = recuperacao
                    ultimo_estado = estado
                    if recuperacao.get("recuperou"):
                        estado = self._estado_telinhas_js()
                        estado["recuperacaoScripts"] = recuperacao
                        ultimo_estado = estado
                        self.logger.info(
                            "Lista de diferencas 030302 recuperada dos scripts auxiliares: %s",
                            recuperacao,
                        )
                        return estado
                    amostras_vazias += 1
                    if amostras_vazias in (1, 5, 10, 20):
                        self.logger.info(
                            "Telinha de diferencas 030302 visivel, mas lista ainda vazia. Estado: %s",
                            estado,
                        )
            except Exception as exc:
                ultimo_estado = {"erro": str(exc)}
            return False

        try:
            estado = WebDriverWait(self.driver, timeout, poll_frequency=1).until(_condition)
            self.logger.info("Lista/mensagem de diferencas 030302 disponivel: %s", estado)
            return estado
        except TimeoutException:
            self.logger.info("Lista/mensagem de diferencas 030302 nao apareceu. Estado: %s", ultimo_estado)
            estado_timeout = ultimo_estado or {}
            estado_timeout["alertasRespondidos"] = list(alertas_respondidos)
            return estado_timeout

    def _aguardar_carga_mapa(self, mapa_normalizado, timeout):
        alertas = []
        def _condition(_driver):
            recuperacao = self._clicar_sim_recuperar_mapa()
            if recuperacao:
                self.logger.info(
                    "Alerta de recuperacao do mapa %s respondido: %s",
                    mapa_normalizado,
                    recuperacao,
                )
                return False

            alerta = self._aceitar_alerta()
            if alerta:
                if self._eh_alerta_recuperar_mapa(alerta):
                    self.logger.info(
                        "Alerta de recuperacao do mapa %s aceito como sim. Continuando carga: %s",
                        mapa_normalizado,
                        alerta,
                    )
                    return False
                self._registrar_alerta_030302(
                    {"tipo": "alert", "mensagem": alerta, "resposta": "ok"},
                    origem="carga-mapa",
                )
                alertas.append(alerta)
                return "alerta"

            try:
                carregou = self.driver.execute_script(
                    """
                    var mapaEsperado = arguments[0];
                    var mapa = document.getElementsByName('mapa')[0];
                    var lista = document.getElementById('lista') || document.getElementsByName('lista')[0];
                    var botSalvar = document.getElementsByName('BotSalvar')[0];
                    var listaRows = lista && lista.rows ? lista.rows.length : 0;
                    var carregouPorBotao = !!(botSalvar && botSalvar.disabled === false);
                    var carregouPorLista = !!(mapa && mapa.value == mapaEsperado && listaRows > 1);
                    if (carregouPorBotao || carregouPorLista) {
                        return {
                            ok: true,
                            motivo: carregouPorBotao ? 'botao-salvar-habilitado' : 'lista-carregada',
                            mapa: mapa ? mapa.value : null,
                            listaRows: listaRows,
                            botSalvarDisabled: botSalvar ? !!botSalvar.disabled : null
                        };
                    }
                    return false;
                    """,
                    mapa_normalizado,
                )
            except UnexpectedAlertPresentException:
                recuperacao = self._clicar_sim_recuperar_mapa()
                if recuperacao:
                    self.logger.info(
                        "Alerta de recuperacao do mapa %s respondido com sim durante espera de carga: %s",
                        mapa_normalizado,
                        recuperacao,
                    )
                    return False
                raise
            if carregou:
                self.logger.info("Carga do mapa 030302 confirmada: %s", carregou)
                return carregou
            return False

        try:
            resultado = WebDriverWait(self.driver, timeout, poll_frequency=0.2).until(_condition)
            return bool(resultado and resultado != "alerta"), alertas
        except TimeoutException:
            return False, alertas

    def _aguardar_estado_pos_mapa_js(self, timeout=10):
        ultimo_estado = None

        def _condition(_driver):
            nonlocal ultimo_estado
            try:
                estado = self.driver.execute_script(
                    """
                    var campoPonto = document.getElementsByName('pontoApoio')[0];
                    var botSalvar = document.getElementsByName('BotSalvar')[0];
                    return {
                        submitCount: window.__promax030302SubmitCount || 0,
                        activeName: document.activeElement ? document.activeElement.name : '',
                        pontoApoioDisabled: campoPonto ? !!campoPonto.disabled : null,
                        pontoApoioValue: campoPonto ? campoPonto.value : null,
                        botSalvarDisabled: botSalvar ? !!botSalvar.disabled : null
                    };
                    """
                )
                ultimo_estado = estado
                if (
                    int(estado.get("submitCount") or 0) > 0
                    or estado.get("pontoApoioDisabled") is False
                    or estado.get("botSalvarDisabled") is False
                ):
                    return estado
            except Exception as exc:
                ultimo_estado = {"erro": str(exc)}
            return False

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.2).until(_condition)
        except TimeoutException:
            self.logger.info("Estado pos-mapa 030302 nao estabilizou antes do fallback: %s", ultimo_estado)
            return ultimo_estado or {"submitCount": 1}

    def _instalar_monitor_envio_js(self, interceptar_msgbx=False):
        self.driver.execute_script(
            """
            var interceptarMsgbx = arguments[0] === true;
            window.__promax030302SubmitCount = 0;
            window.__promax030302Confirmacoes = [];
            window.__promax030302UltimoSalvar = null;
            window.__promax030302UltimaDiferencaEm = window.__promax030302UltimaDiferencaEm || 0;
            try {
                if (window.sessionStorage) {
                    window.sessionStorage.removeItem('__promax030302Confirmacoes');
                    window.sessionStorage.removeItem('__promax030302UltimoSalvar');
                }
            } catch (e) {}
            try {
                if (!window.__promax030302Confirmacoes.__persistencia030302) {
                    var pushOriginal030302 = window.__promax030302Confirmacoes.push;
                    window.__promax030302Confirmacoes.push = function() {
                        var retorno = pushOriginal030302.apply(this, arguments);
                        try {
                            if (window.sessionStorage) {
                                window.sessionStorage.setItem(
                                    '__promax030302Confirmacoes',
                                    JSON.stringify(this)
                                );
                            }
                        } catch (e) {}
                        return retorno;
                    };
                    window.__promax030302Confirmacoes.__persistencia030302 = true;
                }
            } catch (e) {}
            function compatibilizarIeLegado030302(win) {
                try {
                    if (win && win.document && !win.document.parentWindow) {
                        win.document.parentWindow = win;
                    }
                } catch (e) {}
                try {
                    if (win && win.parent && win.parent.document && !win.parent.document.parentWindow) {
                        win.parent.document.parentWindow = win.parent;
                    }
                } catch (e) {}
                try {
                    if (win && win.top && win.top.document && !win.top.document.parentWindow) {
                        win.top.document.parentWindow = win.top;
                    }
                } catch (e) {}
            }
            function normaliza030302(txt) {
                return String(txt || '')
                    .toLowerCase()
                    .replace(/[Ã¡Ã Ã£Ã¢Ã¤]/g, 'a')
                    .replace(/[Ã©Ã¨ÃªÃ«]/g, 'e')
                    .replace(/[Ã­Ã¬Ã®Ã¯]/g, 'i')
                    .replace(/[Ã³Ã²ÃµÃ´Ã¶]/g, 'o')
                    .replace(/[ÃºÃ¹Ã»Ã¼]/g, 'u')
                    .replace(/[Ã§]/g, 'c');
            }
            function valorCampo030302(nome) {
                var campo = document.getElementsByName(nome)[0];
                return campo ? String(campo.value || '') : '';
            }
            function decidirMsgbox030302(titulo, mensagem) {
                var texto = normaliza030302(String(titulo || '') + ' ' + String(mensagem || ''));
                var compacto = texto.replace(/[^a-z0-9]/g, '');
                if (
                    texto.indexOf('nao existe diferenc') !== -1
                    || texto.indexOf('nao existem diferenc') !== -1
                    || texto.indexOf('nao ha diferenc') !== -1
                    || compacto.indexOf('naoexistediferenc') !== -1
                    || compacto.indexOf('naoexistemdiferenc') !== -1
                    || compacto.indexOf('naohadiferenc') !== -1
                ) {
                    return {tipo: 'ok_sem_diferencas', resposta: 'ok'};
                }
                if (texto.indexOf('finance') !== -1 || (texto.indexOf('liber') !== -1 && texto.indexOf('mapa') !== -1)) {
                    return {tipo: 'financeiro', resposta: 'sim'};
                }
                if (
                    texto.indexOf('deseja continuar') !== -1
                    && (texto.indexOf('guia') !== -1 || compacto.indexOf('guias') !== -1)
                    && (
                        texto.indexOf('bonus') !== -1
                        || texto.indexOf('b nus') !== -1
                        || compacto.indexOf('bnus') !== -1
                    )
                ) {
                    return {tipo: 'continuar', resposta: 'sim'};
                }
                if (
                    (texto.indexOf('diferen') !== -1 || texto.indexOf('diferenc') !== -1)
                    && compacto.indexOf('naoexistediferenc') === -1
                    && compacto.indexOf('naoexistemdiferenc') === -1
                    && compacto.indexOf('naohadiferenc') === -1
                ) {
                    return {tipo: 'diferencas', resposta: 'nao'};
                }
                return {tipo: 'outro', resposta: ''};
            }
            function snapshotSalvar030302() {
                var lista = document.getElementById('lista') || document.getElementsByName('lista')[0];
                var itens = valorCampo030302('itensLista');
                var produtos = [];
                if (lista && lista.rows) {
                    for (var i = 1; i < lista.rows.length && produtos.length < 12; i++) {
                        var aux = i < 10 ? '00' + i : (i < 100 ? '0' + i : String(i));
                        produtos.push({
                            linha: aux,
                            codigo: valorCampo030302('textcod' + aux),
                            devUn: valorCampo030302('textdevUn' + aux),
                            devAv: valorCampo030302('textdevAv' + aux),
                            troUn: valorCampo030302('texttroUn' + aux),
                            troAv: valorCampo030302('texttroAv' + aux),
                            vazUn: valorCampo030302('textvazUn' + aux),
                            vazAv: valorCampo030302('textvazAv' + aux)
                        });
                    }
                }
                return {
                    mapa: valorCampo030302('mapa'),
                    opcao: valorCampo030302('opcao'),
                    numeroItems: valorCampo030302('numeroItems'),
                    itensLista: itens ? String(itens) : '',
                    itensListaLength: itens ? itens.length : 0,
                    itensListaPrefix: itens ? itens.substring(0, 80) : '',
                    listaRows: lista && lista.rows ? lista.rows.length : 0,
                    fBotSalvar: valorCampo030302('fBotSalvar'),
                    idMostraMsgAfericao: valorCampo030302('idMostraMsgAfericao'),
                    idAchouGuiasSalvas: valorCampo030302('idAchouGuiasSalvas'),
                    idAchouGuiaMapa: valorCampo030302('idAchouGuiaMapa'),
                    produtos: produtos,
                    capturedAt: new Date().getTime()
                };
            }
            function gravarSnapshotSalvar030302() {
                try {
                    window.__promax030302UltimoSalvar = snapshotSalvar030302();
                    try {
                        if (window.sessionStorage) {
                            window.sessionStorage.setItem(
                                '__promax030302UltimoSalvar',
                                JSON.stringify(window.__promax030302UltimoSalvar)
                            );
                        }
                    } catch (e) {}
                } catch (e) {}
            }
            function instalarMsgbxRotina030302(alvo, chave) {
                try {
                    if (!alvo || typeof alvo.msgbxSimNao !== 'function') return;
                    var nomeOriginal = '__promax030302MsgbxOriginal';
                    if (!interceptarMsgbx && alvo[nomeOriginal]) {
                        alvo.msgbxSimNao = alvo[nomeOriginal];
                        alvo[nomeOriginal] = null;
                        alvo.__promax030302MsgbxWrapperAtivo = false;
                    }
                    if (!interceptarMsgbx || alvo.__promax030302MsgbxWrapperAtivo) return;
                    alvo[nomeOriginal] = alvo.msgbxSimNao;
                    alvo.__promax030302MsgbxWrapperAtivo = true;
                    alvo.msgbxSimNao = function(titulo, mensagem, fnSim, fnNao) {
                        var texto = normaliza030302(String(titulo || '') + ' ' + String(mensagem || ''));
                        var args = [];
                        for (var a = 0; a < arguments.length; a++) args.push(arguments[a]);
                        var callbacks = [];
                        for (var i = 0; i < args.length; i++) {
                            if (typeof args[i] === 'function') callbacks.push(args[i]);
                        }
                        var callbackSim = typeof fnSim === 'function' ? fnSim : callbacks[0];
                        var callbackNao = typeof fnNao === 'function' ? fnNao : callbacks[1];
                        for (var c = 0; c < callbacks.length; c++) {
                            var fonte = String(callbacks[c] || '').toLowerCase();
                            if (fonte.indexOf('//sim') !== -1) callbackSim = callbacks[c];
                            if (fonte.indexOf('//nao') !== -1 || fonte.indexOf('//n') !== -1) callbackNao = callbacks[c];
                        }
                        var decisao = decidirMsgbox030302(titulo, mensagem);
                        var tipo = decisao.tipo;
                        var chavePergunta = tipo + '|' + String(mensagem || titulo || '');
                        window.__promax030302MsgbxRespondidas = window.__promax030302MsgbxRespondidas || {};
                        var agora030302 = new Date().getTime();
                        if (
                            (tipo === 'financeiro' || tipo === 'continuar')
                            && window.__promax030302MsgbxRespondidas[chavePergunta]
                            && agora030302 - window.__promax030302MsgbxRespondidas[chavePergunta] < 3000
                        ) {
                            window.__promax030302Confirmacoes.push({
                                tipo: 'msgbxSimNao-duplicado-ignorado',
                                mensagem: String(mensagem || titulo || ''),
                                resposta: 'sim',
                                contexto: chave
                            });
                            return true;
                        }
                        window.__promax030302Confirmacoes.push({
                            tipo: 'msgbxSimNao-aberto',
                            mensagem: String(mensagem || titulo || ''),
                            resposta: '',
                            contexto: chave
                        });
                        function registrarCallback(fn, resposta) {
                            window.__promax030302Confirmacoes.push({
                                tipo: 'msgbxSimNao',
                                mensagem: String(mensagem || titulo || ''),
                                resposta: resposta,
                                contexto: chave
                            });
                            if (typeof fn !== 'function') return false;
                            window.setTimeout(function() {
                                try {
                                    compatibilizarIeLegado030302(window);
                                    fn.call(window);
                                } catch (e) {
                                    window.__promax030302Confirmacoes.push({
                                        tipo: 'msgbxSimNao-callback-erro',
                                        mensagem: String(mensagem || titulo || ''),
                                        resposta: resposta,
                                        contexto: chave,
                                        erro: String(e && e.message ? e.message : e)
                                    });
                                }
                            }, resposta === 'sim' ? 250 : 0);
                            return resposta === 'sim';
                        }
                        if (tipo === 'financeiro' || tipo === 'continuar') {
                            window.__promax030302MsgbxRespondidas[chavePergunta] = agora030302;
                            return registrarCallback(callbackSim, 'sim');
                        }
                        if (tipo === 'diferencas') {
                            return registrarCallback(callbackNao, 'nao');
                        }
                        if (tipo === 'ok_sem_diferencas') {
                            window.__promax030302Confirmacoes.push({
                                tipo: 'msgbxSimNao',
                                mensagem: String(mensagem || titulo || ''),
                                resposta: 'ok',
                                contexto: chave
                            });
                            return true;
                        }
                        return alvo[nomeOriginal].apply(this, arguments);
                    };
                } catch (e) {}
            }
            window.__instalarMonitor030302 = function() {
                if (typeof window.EnviarFormulario === 'function' && !window.__promax030302EnviarOriginal) {
                    window.__promax030302EnviarOriginal = window.EnviarFormulario;
                    window.EnviarFormulario = function() {
                        gravarSnapshotSalvar030302();
                        window.__promax030302SubmitCount = (window.__promax030302SubmitCount || 0) + 1;
                        return window.__promax030302EnviarOriginal.apply(this, arguments);
                    };
                }
                if (!interceptarMsgbx && window.__promax030302MsgbxOriginal) {
                    window.msgbxSimNao = window.__promax030302MsgbxOriginal;
                    window.__promax030302MsgbxOriginal = null;
                }
                if (interceptarMsgbx && typeof window.msgbxSimNao === 'function' && !window.__promax030302MsgbxOriginal) {
                    window.__promax030302MsgbxOriginal = window.msgbxSimNao;
                    window.msgbxSimNao = function(titulo, mensagem, fnSim, fnNao) {
                        var texto = normaliza030302(String(titulo || '') + ' ' + String(mensagem || ''));
                        var args = [];
                        for (var a = 0; a < arguments.length; a++) {
                            args.push(arguments[a]);
                        }
                        var callbacks = [];
                        for (var i = 0; i < args.length; i++) {
                            if (typeof args[i] === 'function') {
                                callbacks.push(args[i]);
                            }
                        }
                        var callbackSim = typeof fnSim === 'function' ? fnSim : callbacks[0];
                        var callbackNao = typeof fnNao === 'function' ? fnNao : callbacks[1];
                        for (var c = 0; c < callbacks.length; c++) {
                            var fonte = String(callbacks[c] || '').toLowerCase();
                            if (fonte.indexOf('//sim') !== -1) {
                                callbackSim = callbacks[c];
                            }
                            if (fonte.indexOf('//nao') !== -1 || fonte.indexOf('//n') !== -1) {
                                callbackNao = callbacks[c];
                            }
                        }
                        var decisao = decidirMsgbox030302(titulo, mensagem);
                        var tipo = decisao.tipo;
                        window.__promax030302UltimoMsgbx = {
                            titulo: String(titulo || ''),
                            mensagem: String(mensagem || ''),
                            tipo: tipo
                        };
                        window.__promax030302UltimoMsgbxSim = callbackSim;
                        window.__promax030302UltimoMsgbxNao = callbackNao;
                        window.__promax030302Confirmacoes.push({
                            tipo: 'msgbxSimNao-aberto',
                            mensagem: String(mensagem || titulo || ''),
                            resposta: ''
                        });
                        function executarCallback030302(fn, resposta) {
                            window.__promax030302Confirmacoes.push({
                                tipo: 'msgbxSimNao',
                                mensagem: String(mensagem || titulo || ''),
                                resposta: resposta
                            });
                            if (typeof fn !== 'function') {
                                window.__promax030302Confirmacoes.push({
                                    tipo: 'msgbxSimNao-callback-ausente',
                                    mensagem: String(mensagem || titulo || ''),
                                    resposta: resposta
                                });
                                return false;
                            }
                            window.setTimeout(function() {
                                try {
                                    compatibilizarIeLegado030302(window);
                                    fn.call(window);
                                } catch (e) {
                                    window.__promax030302Confirmacoes.push({
                                        tipo: 'msgbxSimNao-callback-erro',
                                        mensagem: String(mensagem || titulo || ''),
                                        resposta: resposta,
                                        erro: String(e && e.message ? e.message : e)
                                    });
                                }
                            }, resposta === 'sim' ? 250 : 0);
                            return resposta === 'sim';
                        }
                        if (tipo === 'financeiro') {
                            return executarCallback030302(callbackSim, 'sim');
                        }
                        if (tipo === 'continuar') {
                            return executarCallback030302(callbackSim, 'sim');
                        }
                        if (tipo === 'diferencas') {
                            return executarCallback030302(callbackNao, 'nao');
                        }
                        if (tipo === 'ok_sem_diferencas') {
                            window.__promax030302Confirmacoes.push({
                                tipo: 'msgbxSimNao',
                                mensagem: String(mensagem || titulo || ''),
                                resposta: 'ok'
                            });
                            return true;
                        }
                        return window.__promax030302MsgbxOriginal.apply(this, arguments);
                    };
                }
                try { instalarMsgbxRotina030302(window.parent && window.parent.rotina, 'parent_rotina'); } catch (e) {}
                try { instalarMsgbxRotina030302(window.top && window.top.rotina, 'top_rotina'); } catch (e) {}
                // Nao envelopar listaDiferencas.add: no IE Mode esse metodo legado
                // pode falhar quando chamado via Function.call, deixando a telinha vazia.
            };
            window.__instalarMonitor030302();
            """,
            interceptar_msgbx,
        )

    def _obter_confirmacoes_salvar_js(self):
        try:
            dados = self.driver.execute_script(
                """
                function coletarConfirmacoes030302() {
                    var resultado = [];
                    var vistos = {};
                    function adicionarLista(lista) {
                        if (!lista || !lista.length) return;
                        for (var i = 0; i < lista.length; i++) {
                            var item = lista[i];
                            if (!item) continue;
                            var chave = String(item.tipo || '') + '|' + String(item.mensagem || '') + '|' + String(item.resposta || '');
                            if (vistos[chave]) continue;
                            vistos[chave] = true;
                            resultado.push(item);
                        }
                    }
                    function lerWin(win) {
                        try { adicionarLista(win.__promax030302Confirmacoes); } catch (e) {}
                        try { adicionarLista(win.rotina && win.rotina.__promax030302Confirmacoes); } catch (e) {}
                    }
                    lerWin(window);
                    try { lerWin(window.parent); } catch (e) {}
                    try { lerWin(window.top); } catch (e) {}
                    try {
                        if (window.sessionStorage) {
                            var rawConfirmacoes = window.sessionStorage.getItem('__promax030302Confirmacoes');
                            if (rawConfirmacoes) adicionarLista(JSON.parse(rawConfirmacoes));
                        }
                    } catch (e) {}
                    return resultado;
                }
                var ultimoSalvar = window.__promax030302UltimoSalvar || null;
                if (!ultimoSalvar) {
                    try {
                        if (window.sessionStorage) {
                            var raw = window.sessionStorage.getItem('__promax030302UltimoSalvar');
                            if (raw) ultimoSalvar = JSON.parse(raw);
                        }
                    } catch (e) {}
                }
                return {
                    confirmacoes: coletarConfirmacoes030302(),
                    submitCount: window.__promax030302SubmitCount || 0,
                    ultimoSalvar: ultimoSalvar
                };
                """
            )
            if not isinstance(dados, dict):
                return {"confirmacoes": [], "submitCount": 0, "raw": dados}
            return dados
        except Exception:
            return {"confirmacoes": [], "submitCount": 0}

    def preencher_diferencas(self, timeout=15):
        try:
            self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
            resultado = None

            def _condition(_driver):
                nonlocal resultado
                resultado = self.driver.execute_script(
                    """
                function normaliza(txt) {
                    return String(txt || '')
                        .toLowerCase()
                        .replace(/[áàãâä]/g, 'a')
                        .replace(/[éèêë]/g, 'e')
                        .replace(/[íìîï]/g, 'i')
                        .replace(/[óòõôö]/g, 'o')
                        .replace(/[úùûü]/g, 'u')
                        .replace(/[ç]/g, 'c');
                }

                function soDigitos(valor) {
                    return String(valor || '').replace(/\\D/g, '');
                }

                function numero(valor) {
                    var limpo = soDigitos(valor);
                    if (limpo === '') return 0;
                    return parseInt(limpo, 10) || 0;
                }

                function setCampo(nome, valor) {
                    var campo = document.getElementsByName(nome)[0];
                    if (!campo) return false;
                    campo.disabled = false;
                    campo.readOnly = false;
                    campo.value = String(valor || 0);
                    try {
                        if (campo.fireEvent) {
                            campo.fireEvent('onchange');
                        } else if (document.createEvent) {
                            var evt = document.createEvent('HTMLEvents');
                            evt.initEvent('change', false, true);
                            campo.dispatchEvent(evt);
                        }
                    } catch (e) {}
                    return true;
                }

                function auxLinha(index) {
                    if (index < 10) return '00' + index;
                    if (index < 100) return '0' + index;
                    return String(index);
                }

                function localizarLinhaProduto(codigo) {
                    var lista = document.getElementById('lista') || document.getElementsByName('lista')[0];
                    if (!lista || !lista.rows) return null;
                    var codigoNum = numero(codigo);
                    for (var i = 1; i < lista.rows.length; i++) {
                        var aux = auxLinha(i);
                        var campoCod = document.getElementsByName('textcod' + aux)[0];
                        if (campoCod && numero(campoCod.value) === codigoNum) {
                            return aux;
                        }
                    }
                    return null;
                }

                function parseOpcao(opt) {
                    var texto = String(opt.text || opt.innerText || '');
                    var pares = [];
                    var re = /(\\d+)\\s*\\/\\s*(\\d+)/g;
                    var match;
                    while ((match = re.exec(texto)) !== null) {
                        pares.push([numero(match[1]), numero(match[2])]);
                    }

                    return {
                        codigo: soDigitos(opt.value || texto.split(/\\s+/)[0]),
                        texto: texto,
                        previsao: pares.length >= 4 ? pares[pares.length - 4] : null,
                        retorno: pares.length >= 3 ? pares[pares.length - 3] : null,
                        sobra: pares.length >= 2 ? pares[pares.length - 2] : [0, 0],
                        falta: pares.length >= 1 ? pares[pares.length - 1] : [0, 0]
                    };
                }

                var divDif = document.getElementById('DivDiferencas');
                var divMsg = document.getElementById('DivMensagem');
                var listaDif = document.getElementsByName('listaDiferencas')[0];
                var itens = [];
                var aplicados = [];
                var naoAplicados = [];
                var mensagemTexto = divMsg ? String(divMsg.innerText || divMsg.textContent || '') : '';
                if (divMsg && divMsg.style.display !== 'none') {
                    if (typeof OkMensagem === 'function') {
                        OkMensagem();
                    } else {
                        divMsg.style.display = 'none';
                    }
                    return {
                        encontrou: false,
                        mensagem: mensagemTexto,
                        mensagemRespondida: true,
                        aplicados: aplicados,
                        naoAplicados: naoAplicados,
                        listaDiferencasLength: listaDif && listaDif.options ? listaDif.options.length : 0,
                        divVisivel: divDif ? divDif.style.display !== 'none' : false,
                        divMensagemVisivel: false
                    };
                }

                if (!listaDif || !listaDif.options || listaDif.options.length === 0) {
                    return {
                        encontrou: false,
                        aplicados: aplicados,
                        naoAplicados: naoAplicados,
                        listaDiferencasLength: 0,
                        divVisivel: divDif ? divDif.style.display !== 'none' : false,
                        divMensagemVisivel: divMsg ? divMsg.style.display !== 'none' : false
                    };
                }

                for (var i = 0; i < listaDif.options.length; i++) {
                    itens.push(parseOpcao(listaDif.options[i]));
                }

                for (var j = 0; j < itens.length; j++) {
                    var item = itens[j];
                    var aux = localizarLinhaProduto(item.codigo);
                    if (!aux) {
                        naoAplicados.push({codigo: item.codigo, motivo: 'produto-nao-encontrado', item: item});
                        continue;
                    }

                    var faltaUn = item.falta ? item.falta[0] : 0;
                    var faltaAv = item.falta ? item.falta[1] : 0;
                    var sobraUn = item.sobra ? item.sobra[0] : 0;
                    var sobraAv = item.sobra ? item.sobra[1] : 0;

                    var okUn = setCampo('textdevUn' + aux, faltaUn);
                    var okAv = setCampo('textdevAv' + aux, faltaAv);
                    aplicados.push({
                        codigo: item.codigo,
                        linha: aux,
                        previsaoUn: item.previsao ? item.previsao[0] : 0,
                        previsaoAv: item.previsao ? item.previsao[1] : 0,
                        retornoUn: item.retorno ? item.retorno[0] : 0,
                        retornoAv: item.retorno ? item.retorno[1] : 0,
                        faltaUn: faltaUn,
                        faltaAv: faltaAv,
                        sobraUn: sobraUn,
                        sobraAv: sobraAv,
                        destino: 'devolucao',
                        okUn: okUn,
                        okAv: okAv,
                        texto: item.texto
                    });
                }

                var botSalvar = document.getElementsByName('BotSalvar')[0];
                var botCancelarAlt = document.getElementsByName('BotCancelarAlt')[0];
                if (botSalvar) {
                    botSalvar.disabled = false;
                }
                if (botCancelarAlt) {
                    botCancelarAlt.disabled = false;
                }

                return {
                    encontrou: true,
                    aplicados: aplicados,
                    naoAplicados: naoAplicados,
                    listaDiferencasLength: listaDif.options.length,
                    divVisivel: divDif ? divDif.style.display !== 'none' : false,
                    divMensagemVisivel: divMsg ? divMsg.style.display !== 'none' : false,
                    botSalvarDisabled: botSalvar ? !!botSalvar.disabled : null
                };
                """
                )
                if resultado.get("encontrou") or resultado.get("mensagemRespondida"):
                    return resultado
                if (
                    resultado.get("divVisivel")
                    and int(resultado.get("listaDiferencasLength") or 0) == 0
                ):
                    return False
                return False

            try:
                resultado = WebDriverWait(self.driver, timeout, poll_frequency=0.2).until(_condition)
            except TimeoutException:
                pass

            if resultado is None:
                resultado = {
                    "encontrou": False,
                    "aplicados": [],
                    "naoAplicados": [{"motivo": "sem-retorno-js"}],
                }
            self.logger.info(
                "Diferencas 030302 preenchidas: encontrou=%s, divVisivel=%s, %s aplicado(s), %s pendente(s).",
                resultado.get("encontrou"),
                resultado.get("divVisivel"),
                len(resultado.get("aplicados") or []),
                len(resultado.get("naoAplicados") or []),
            )
            if not resultado.get("encontrou") and not resultado.get("mensagemRespondida"):
                self.logger.info("Nenhuma diferenca/telinha 030302 detectada. Estado: %s", resultado)
            return resultado
        except Exception as exc:
            self.logger.warning("Falha ao preencher diferencas da 030302: %s", exc)
            return {
                "encontrou": False,
                "aplicados": [],
                "naoAplicados": [{"motivo": str(exc)}],
            }

    def _capturar_diferencas_lista_js(self):
        try:
            return self.driver.execute_script(
                """
                function soDigitos(valor) {
                    return String(valor || '').replace(/\\D/g, '');
                }

                function numero(valor) {
                    var limpo = soDigitos(valor);
                    if (limpo === '') return 0;
                    return parseInt(limpo, 10) || 0;
                }

                function paresTexto(texto) {
                    var pares = [];
                    var re = /(\\d+)\\s*\\/\\s*(\\d+)/g;
                    var m;
                    while ((m = re.exec(String(texto || ''))) !== null) {
                        pares.push([numero(m[1]), numero(m[2])]);
                    }
                    return pares;
                }

                function parseOpcao(opt) {
                    var texto = String(opt.text || opt.innerText || '');
                    var pares = paresTexto(texto);
                    return {
                        codigo: soDigitos(opt.value || texto.split(/\\s+/)[0]),
                        value: String(opt.value || ''),
                        texto: texto,
                        previsaoUn: pares.length >= 4 ? pares[pares.length - 4][0] : 0,
                        previsaoAv: pares.length >= 4 ? pares[pares.length - 4][1] : 0,
                        retornoUn: pares.length >= 3 ? pares[pares.length - 3][0] : 0,
                        retornoAv: pares.length >= 3 ? pares[pares.length - 3][1] : 0,
                        sobraUn: pares.length >= 2 ? pares[pares.length - 2][0] : 0,
                        sobraAv: pares.length >= 2 ? pares[pares.length - 2][1] : 0,
                        faltaUn: pares.length >= 1 ? pares[pares.length - 1][0] : 0,
                        faltaAv: pares.length >= 1 ? pares[pares.length - 1][1] : 0
                    };
                }

                var listaDif = document.getElementsByName('listaDiferencas')[0];
                var itens = [];
                if (listaDif && listaDif.options) {
                    for (var i = 0; i < listaDif.options.length; i++) {
                        itens.push(parseOpcao(listaDif.options[i]));
                    }
                }
                return {
                    encontrou: itens.length > 0,
                    total: itens.length,
                    itens: itens
                };
                """
            )
        except Exception as exc:
            return {"encontrou": False, "total": 0, "itens": [], "erro": str(exc)}

    def _preencher_km_atual_js(self, km_atual):
        try:
            km_normalizado = self.normalizar_km_atual(km_atual)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        if not km_normalizado:
            return {"ok": True, "skipped": True}
        try:
            self._reentrar_frame(timeout=10)
            return self.driver.execute_script(
                """
                var valor = arguments[0];
                var campo = document.getElementsByName('kmAtual')[0];
                if (!campo) {
                    return {ok: false, error: 'campo-km-atual-nao-encontrado'};
                }
                campo.disabled = false;
                campo.readOnly = false;
                campo.className = 'campo';
                campo.focus();
                campo.value = valor;
                try {
                    if (campo.fireEvent) {
                        campo.fireEvent('onkeyup');
                        campo.fireEvent('onchange');
                        campo.fireEvent('onblur');
                    } else if (document.createEvent) {
                        var evtKey = document.createEvent('HTMLEvents');
                        evtKey.initEvent('keyup', false, true);
                        campo.dispatchEvent(evtKey);
                        var evtChange = document.createEvent('HTMLEvents');
                        evtChange.initEvent('change', false, true);
                        campo.dispatchEvent(evtChange);
                        var evtBlur = document.createEvent('HTMLEvents');
                        evtBlur.initEvent('blur', false, true);
                        campo.dispatchEvent(evtBlur);
                    }
                } catch (e) {}
                return {
                    ok: true,
                    kmAtualDigitado: campo.value,
                    disabled: !!campo.disabled,
                    readOnly: !!campo.readOnly
                };
                """,
                km_normalizado,
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _recarregar_mapa_para_acerto(self, mapa, ponto_apoio=None, timeout=45):
        try:
            self.logger.info("Reiniciando rotina 030302 para recarregar mapa %s apos captura.", mapa)
            try:
                self.switch_to_default_content()
            except Exception:
                pass

            try:
                handles = list(self.driver.window_handles)
                if self.handle_rotina in handles:
                    self.driver.switch_to.window(self.handle_rotina)
                    self.switch_to_default_content()
                    self.logger.info(
                        "030302 | Aba atual da rotina focada para fechar antes de digitar novamente: %s",
                        self.handle_rotina,
                    )
            except Exception as exc:
                self.logger.warning(
                    "030302 | Nao foi possivel focar a aba da rotina antes de recarregar o mapa %s: %s",
                    mapa,
                    exc,
                )

            menu_page = self.fechar_e_voltar()
            janela = menu_page.acessar_rotina("030302")
            self.handle_menu = janela.handle_menu
            self.handle_rotina = self.driver.current_window_handle
            self.logger.info(
                "Rotina 030302 reiniciada para acerto do mapa %s. Nova janela: %s",
                mapa,
                self.driver.current_window_handle,
            )
            return self.carregar_mapa(
                mapa,
                ponto_apoio=ponto_apoio,
                km_atual=self._km_atual_030302,
                km_inicial=self._km_inicial_030302,
                km_prev=self._km_prev_030302,
                timeout=timeout,
            )
        except Exception as exc:
            self.logger.warning("Falha ao recarregar mapa %s para acerto na 030302: %s", mapa, exc)
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=f"Falha ao recarregar mapa {mapa} para acerto na 030302: {exc}",
            )

    def _aplicar_diferencas_capturadas_js(self, itens, destinos_permitidos=None):
        try:
            self._reentrar_frame(timeout=10)
            return self.driver.execute_script(
                """
                var itens = arguments[0] || [];
                var destinosPermitidos = arguments[1] || null;

                function soDigitos(valor) {
                    return String(valor || '').replace(/\\D/g, '');
                }

                function numero(valor) {
                    var limpo = soDigitos(valor);
                    if (limpo === '') return 0;
                    return parseInt(limpo, 10) || 0;
                }

                function auxLinha(index) {
                    if (index < 10) return '00' + index;
                    if (index < 100) return '0' + index;
                    return String(index);
                }

                function localizarLinhaProduto(codigo) {
                    var codigoNum = numero(codigo);
                    var lista = document.getElementById('lista') || document.getElementsByName('lista')[0];
                    if (!lista || !lista.rows) return null;
                    for (var i = 1; i < lista.rows.length; i++) {
                        var aux = auxLinha(i);
                        var campoCod = document.getElementsByName('textcod' + aux)[0];
                        if (campoCod && numero(campoCod.value) === codigoNum) {
                            return aux;
                        }
                    }
                    return null;
                }

                function snapshotLinhas() {
                    var lista = document.getElementById('lista') || document.getElementsByName('lista')[0];
                    var linhas = [];
                    if (!lista || !lista.rows) return linhas;
                    for (var i = 1; i < lista.rows.length && linhas.length < 30; i++) {
                        var aux = auxLinha(i);
                        var campoCod = document.getElementsByName('textcod' + aux)[0];
                        var codigo = campoCod ? campoCod.value : '';
                        if (codigo === '') {
                            var textoLinha = String(lista.rows[i].innerText || lista.rows[i].textContent || '');
                            var matchCodigo = textoLinha.match(/\\d+/);
                            codigo = matchCodigo ? matchCodigo[0] : '';
                        }
                        function valor(nome) {
                            var campo = document.getElementsByName(nome + aux)[0];
                            return campo ? campo.value : null;
                        }
                        function disabled(nome) {
                            var campo = document.getElementsByName(nome + aux)[0];
                            return campo ? !!campo.disabled : null;
                        }
                        linhas.push({
                            linha: aux,
                            codigo: codigo,
                            texto: String(lista.rows[i].innerText || lista.rows[i].textContent || '').replace(/\\s+/g, ' ').substring(0, 120),
                            devUn: valor('textdevUn'),
                            devAv: valor('textdevAv'),
                            troUn: valor('texttroUn'),
                            troAv: valor('texttroAv'),
                            vazUn: valor('textvazUn'),
                            vazAv: valor('textvazAv'),
                            devUnDisabled: disabled('textdevUn'),
                            devAvDisabled: disabled('textdevAv'),
                            troUnDisabled: disabled('texttroUn'),
                            troAvDisabled: disabled('texttroAv'),
                            vazUnDisabled: disabled('textvazUn'),
                            vazAvDisabled: disabled('textvazAv')
                        });
                    }
                    return linhas;
                }

                function campoEditavel(nome) {
                    var campo = document.getElementsByName(nome)[0];
                    if (!campo) return false;
                    return campo.disabled !== true && campo.readOnly !== true;
                }

                function setCampo(nome, valor) {
                    var campo = document.getElementsByName(nome)[0];
                    if (!campo) return {ok: false, motivo: 'campo-nao-encontrado', nome: nome};
                    if (campo.disabled === true || campo.readOnly === true) {
                        return {ok: false, motivo: 'campo-bloqueado', nome: nome};
                    }
                    campo.focus();
                    try { campo.click(); } catch (e) {}
                    campo.value = String(valor || 0);
                    try {
                        if (campo.fireEvent) {
                            campo.fireEvent('onkeydown');
                            campo.fireEvent('onkeyup');
                            campo.fireEvent('onpropertychange');
                            campo.fireEvent('onchange');
                            campo.fireEvent('onblur');
                        } else if (document.createEvent) {
                            var evtKeyDown = document.createEvent('HTMLEvents');
                            evtKeyDown.initEvent('keydown', false, true);
                            campo.dispatchEvent(evtKeyDown);
                            var evtKeyUp = document.createEvent('HTMLEvents');
                            evtKeyUp.initEvent('keyup', false, true);
                            campo.dispatchEvent(evtKeyUp);
                            var evtChange = document.createEvent('HTMLEvents');
                            evtChange.initEvent('change', false, true);
                            campo.dispatchEvent(evtChange);
                            var evtBlur = document.createEvent('HTMLEvents');
                            evtBlur.initEvent('blur', false, true);
                            campo.dispatchEvent(evtBlur);
                        }
                    } catch (e) {}
                    return {ok: true, nome: nome, valor: campo.value};
                }

                function primeiraColunaDisponivel(aux) {
                    var colunas = [
                        {nome: 'devolucao', un: 'textdevUn' + aux, av: 'textdevAv' + aux},
                        {nome: 'troca', un: 'texttroUn' + aux, av: 'texttroAv' + aux},
                        {nome: 'vazio', un: 'textvazUn' + aux, av: 'textvazAv' + aux}
                    ];
                    for (var i = 0; i < colunas.length; i++) {
                        if (campoEditavel(colunas[i].un) || campoEditavel(colunas[i].av)) {
                            return colunas[i];
                        }
                    }
                    return null;
                }

                function destinoPermitido(nome) {
                    if (!destinosPermitidos || destinosPermitidos.length === 0) return true;
                    for (var i = 0; i < destinosPermitidos.length; i++) {
                        if (String(destinosPermitidos[i] || '').toLowerCase() === String(nome || '').toLowerCase()) {
                            return true;
                        }
                    }
                    return false;
                }

                var aplicados = [];
                var naoAplicados = [];
                for (var i = 0; i < itens.length; i++) {
                    var item = itens[i] || {};
                    var codigo = item.codigo || item.value || '';
                    var aux = localizarLinhaProduto(codigo);
                    if (!aux) {
                        naoAplicados.push({codigo: codigo, motivo: 'produto-nao-encontrado', item: item});
                        continue;
                    }

                    var faltaUn = numero(item.faltaUn);
                    var faltaAv = numero(item.faltaAv);
                    var coluna = primeiraColunaDisponivel(aux);
                    if (!coluna) {
                        naoAplicados.push({
                            codigo: codigo,
                            linha: aux,
                            motivo: 'nenhuma-coluna-editavel',
                            item: item
                        });
                        continue;
                    }
                    if (!destinoPermitido(coluna.nome)) {
                        naoAplicados.push({
                            codigo: codigo,
                            linha: aux,
                            motivo: 'destino-nao-permitido',
                            destino: coluna.nome,
                            item: item
                        });
                        continue;
                    }

                    var resultadoUn = campoEditavel(coluna.un)
                        ? setCampo(coluna.un, faltaUn)
                        : {ok: false, motivo: 'un-bloqueado', nome: coluna.un};
                    var resultadoAv = campoEditavel(coluna.av)
                        ? setCampo(coluna.av, faltaAv)
                        : {ok: false, motivo: 'av-bloqueado', nome: coluna.av};

                    if (!resultadoUn.ok && !resultadoAv.ok) {
                        naoAplicados.push({
                            codigo: codigo,
                            linha: aux,
                            motivo: 'coluna-sem-campo-editavel',
                            coluna: coluna.nome,
                            resultadoUn: resultadoUn,
                            resultadoAv: resultadoAv,
                            item: item
                        });
                        continue;
                    }

                    aplicados.push({
                        codigo: codigo,
                        linha: aux,
                        faltaUn: faltaUn,
                        faltaAv: faltaAv,
                        destino: coluna.nome,
                        campoUn: coluna.un,
                        campoAv: coluna.av,
                        okUn: resultadoUn.ok,
                        okAv: resultadoAv.ok,
                        resultadoUn: resultadoUn,
                        resultadoAv: resultadoAv,
                        texto: item.texto || ''
                    });
                }

                var botSalvar = document.getElementsByName('BotSalvar')[0];
                var botCancelarAlt = document.getElementsByName('BotCancelarAlt')[0];
                if (botSalvar) botSalvar.disabled = false;
                if (botCancelarAlt) botCancelarAlt.disabled = false;

                return {
                    encontrou: aplicados.length > 0,
                    aplicados: aplicados,
                    naoAplicados: naoAplicados,
                    linhasDisponiveis: snapshotLinhas(),
                    totalRecebido: itens.length,
                    botSalvarDisabled: botSalvar ? !!botSalvar.disabled : null
                };
                """,
                itens,
                list(destinos_permitidos or []),
            )
        except Exception as exc:
            return {
                "encontrou": False,
                "aplicados": [],
                "naoAplicados": [{"motivo": str(exc)}],
            }

    def _classificar_itens_diferencas_030302(self, itens):
        try:
            self._reentrar_frame(timeout=10)
            resultado = self.driver.execute_script(
                """
                var itens = arguments[0] || [];

                function soDigitos(valor) {
                    return String(valor || '').replace(/\\D/g, '');
                }

                function numero(valor) {
                    var limpo = soDigitos(valor);
                    if (limpo === '') return 0;
                    return parseInt(limpo, 10) || 0;
                }

                function auxLinha(index) {
                    if (index < 10) return '00' + index;
                    if (index < 100) return '0' + index;
                    return String(index);
                }

                function localizarLinhaProduto(codigo) {
                    var codigoNum = numero(codigo);
                    var lista = document.getElementById('lista') || document.getElementsByName('lista')[0];
                    if (!lista || !lista.rows) return null;
                    for (var i = 1; i < lista.rows.length; i++) {
                        var aux = auxLinha(i);
                        var campoCod = document.getElementsByName('textcod' + aux)[0];
                        if (campoCod && numero(campoCod.value) === codigoNum) {
                            return aux;
                        }
                    }
                    return null;
                }

                function campoEditavel(nome) {
                    var campo = document.getElementsByName(nome)[0];
                    if (!campo) return false;
                    return campo.disabled !== true && campo.readOnly !== true;
                }

                function primeiraColunaDisponivel(aux) {
                    var colunas = [
                        {nome: 'devolucao', un: 'textdevUn' + aux, av: 'textdevAv' + aux},
                        {nome: 'troca', un: 'texttroUn' + aux, av: 'texttroAv' + aux},
                        {nome: 'vazio', un: 'textvazUn' + aux, av: 'textvazAv' + aux}
                    ];
                    for (var i = 0; i < colunas.length; i++) {
                        if (campoEditavel(colunas[i].un) || campoEditavel(colunas[i].av)) {
                            return colunas[i].nome;
                        }
                    }
                    return '';
                }

                var produtos = [];
                var materiais = [];
                var indefinidos = [];
                for (var i = 0; i < itens.length; i++) {
                    var item = itens[i] || {};
                    var codigo = item.codigo || item.value || '';
                    var aux = localizarLinhaProduto(codigo);
                    var destino = aux ? primeiraColunaDisponivel(aux) : '';
                    item.destinoDetectado = destino;
                    item.linhaDetectada = aux || '';
                    if (destino && destino !== 'vazio') {
                        produtos.push(item);
                    } else if (destino === 'vazio') {
                        materiais.push(item);
                    } else {
                        indefinidos.push(item);
                    }
                }
                return {
                    produtos: produtos,
                    materiais: materiais,
                    indefinidos: indefinidos,
                    total: itens.length
                };
                """,
                itens,
            )
            if not isinstance(resultado, dict):
                raise ValueError("classificacao invalida")
            return resultado
        except Exception as exc:
            log_warning = getattr(self.logger, "warning", None)
            if callable(log_warning):
                log_warning(
                    "Nao foi possivel classificar produtos/material da 030302; preservando fluxo antigo: %s",
                    exc,
                )
            return {
                "produtos": [],
                "materiais": list(itens or []),
                "indefinidos": [],
                "total": len(itens or []),
                "erro": str(exc),
            }

    def _seguir_fluxo_tela_diferencas_js(self, timeout=20):
        try:
            self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=timeout)
            dados_antes = self._obter_confirmacoes_salvar_js()
            submit_antes = int(dados_antes.get("submitCount") or 0)
            resultado = self.driver.execute_script(
                """
                function visivel(el) {
                    if (!el) return false;
                    if (el.style && el.style.display === 'none') return false;
                    return true;
                }

                function texto(el) {
                    return String(
                        (el && (el.innerText || el.textContent || el.value || el.name || el.id)) || ''
                    ).toLowerCase();
                }

                function chamarFuncao(nome) {
                    try {
                        if (typeof window[nome] === 'function') {
                            window[nome]();
                            return {ok: true, trigger: nome + '()'};
                        }
                    } catch (e) {
                        return {
                            ok: false,
                            trigger: nome + '()',
                            error: String(e && e.message ? e.message : e)
                        };
                    }
                    return {ok: false, trigger: nome + '()', error: 'funcao-nao-encontrada'};
                }

                function clicarElementoPorOnclick(container, padrao) {
                    if (!container) return null;
                    var elementos = [];
                    try {
                        elementos = Array.prototype.slice.call(container.querySelectorAll('[onclick]'));
                    } catch (e) {
                        elementos = [];
                    }
                    for (var i = 0; i < elementos.length; i++) {
                        if (!visivel(elementos[i])) continue;
                        var onclick = String(elementos[i].getAttribute('onclick') || '');
                        if (onclick.toLowerCase().indexOf(padrao.toLowerCase()) === -1) continue;
                        try { elementos[i].focus(); } catch (e) {}
                        elementos[i].click();
                        return {
                            clicou: true,
                            onclick: onclick,
                            texto: texto(elementos[i]),
                            name: elementos[i].name || '',
                            id: elementos[i].id || ''
                        };
                    }
                    return null;
                }

                function clicarBotaoVisivel(container, preferidos) {
                    if (!container) return null;
                    var botoes = [];
                    try {
                        botoes = Array.prototype.slice.call(
                            container.querySelectorAll('button,input[type=button],input[type=submit],a,[onclick]')
                        );
                    } catch (e) {
                        botoes = [];
                    }
                    for (var p = 0; p < preferidos.length; p++) {
                        for (var i = 0; i < botoes.length; i++) {
                            if (!visivel(botoes[i])) continue;
                            var tx = texto(botoes[i]);
                            if (tx.indexOf(preferidos[p]) !== -1) {
                                try { botoes[i].focus(); } catch (e) {}
                                botoes[i].click();
                                return {
                                    clicou: true,
                                    texto: texto(botoes[i]),
                                    name: botoes[i].name || '',
                                    id: botoes[i].id || ''
                                };
                            }
                        }
                    }
                    for (var j = 0; j < botoes.length; j++) {
                        if (!visivel(botoes[j])) continue;
                        try { botoes[j].focus(); } catch (e) {}
                        botoes[j].click();
                        return {
                            clicou: true,
                            texto: texto(botoes[j]),
                            name: botoes[j].name || '',
                            id: botoes[j].id || ''
                        };
                    }
                    return null;
                }

                var divDif = document.getElementById('DivDiferencas');
                var divFila = document.getElementById('DivFila');
                var listaDif = document.getElementsByName('listaDiferencas')[0];
                var acoes = [];

                if (visivel(divDif)) {
                    var fluxoDif = chamarFuncao('ConfiguraFila');
                    if (fluxoDif.ok) {
                        acoes.push(fluxoDif.trigger);
                    } else {
                        var cliqueConfigura = clicarElementoPorOnclick(divDif, 'ConfiguraFila');
                        if (cliqueConfigura) {
                            acoes.push('DivDiferencas.ConfiguraFila.click');
                        } else {
                            var cliqueDif = clicarBotaoVisivel(divDif, ['ok', 'confirmar', 'x', 'fechar']);
                            if (cliqueDif) {
                                acoes.push('DivDiferencas.botao.click');
                            }
                        }
                    }
                }

                divFila = document.getElementById('DivFila');
                if (visivel(divFila)) {
                    var fluxoFila = chamarFuncao('OkFila');
                    if (fluxoFila.ok) {
                        acoes.push(fluxoFila.trigger);
                    } else {
                        var cliqueFila = clicarBotaoVisivel(divFila, ['ok', 'confirmar', 'sim']);
                        if (cliqueFila) {
                            acoes.push('DivFila.botao.click');
                        }
                    }
                }

                divDif = document.getElementById('DivDiferencas');
                divFila = document.getElementById('DivFila');
                return {
                    ok: acoes.length > 0,
                    acoes: acoes,
                    listaDiferencasLength: listaDif && listaDif.options ? listaDif.options.length : 0,
                    divDiferencasVisivel: visivel(divDif),
                    divFilaVisivel: visivel(divFila),
                    submitCount: window.__promax030302SubmitCount || 0
                };
                """
            )
            self.logger.info("Fluxo da tela de diferencas 030302 acionado: %s", resultado)
            if not resultado or not resultado.get("ok"):
                return resultado or {"ok": False, "error": "fluxo-diferencas-nao-acionado"}

            def _condition(_driver):
                try:
                    try:
                        self._reentrar_frame(timeout=2)
                    except Exception:
                        pass
                    dados = self._obter_confirmacoes_salvar_js()
                    estado = self._estado_telinhas_js()
                    submit_atual = int(dados.get("submitCount") or 0)
                    if submit_atual > submit_antes or not estado.get("divDiferencasVisivel"):
                        return {
                            "ok": True,
                            "submitCountAntes": submit_antes,
                            "submitCountDepois": submit_atual,
                            "estado": estado,
                            "acoes": resultado.get("acoes"),
                        }
                except Exception:
                    return False
                return False

            try:
                return WebDriverWait(self.driver, timeout, poll_frequency=0.2).until(_condition)
            except TimeoutException:
                estado = self._estado_telinhas_js()
                return {
                    "ok": False,
                    "error": "timeout-fluxo-diferencas",
                    "acoes": resultado.get("acoes"),
                    "estado": estado,
                }
        except UnexpectedAlertPresentException:
            return {"ok": True, "trigger": "fluxo-diferencas-alerta"}
        except Exception as exc:
            self.logger.warning("Falha ao seguir fluxo da tela de diferencas 030302: %s", exc)
            return {"ok": False, "error": str(exc)}

    def _executar_callback_msgbx_js(self, resposta):
        try:
            return self.driver.execute_script(
                """
                var resposta = arguments[0] || '';
                var fn = resposta === 'sim'
                    ? window.__promax030302UltimoMsgbxSim
                    : window.__promax030302UltimoMsgbxNao;
                var msg = window.__promax030302UltimoMsgbx || {};
                if (typeof fn !== 'function') {
                    return {ok: false, error: 'callback-nao-encontrado', resposta: resposta, msg: msg};
                }
                window.__promax030302Confirmacoes = window.__promax030302Confirmacoes || [];
                window.__promax030302Confirmacoes.push({
                    tipo: 'msgbxSimNao-callback-recuperado',
                    mensagem: msg.mensagem || msg.titulo || '',
                    resposta: resposta
                });
                window.setTimeout(function() { fn(); }, 0);
                return {ok: true, resposta: resposta, msg: msg};
                """,
                resposta,
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc), "resposta": resposta}

    def _executar_funcao_alerta_promax_js(self, codigo_funcao):
        try:
            return self.driver.execute_script(
                """
                var fonte = String(arguments[0] || '');
                window.__promax030302Confirmacoes = window.__promax030302Confirmacoes || [];
                try {
                    try {
                        if (!document.parentWindow) {
                            document.parentWindow = window;
                        }
                    } catch (e) {}
                    try {
                        if (window.parent && window.parent.document && !window.parent.document.parentWindow) {
                            window.parent.document.parentWindow = window.parent;
                        }
                    } catch (e) {}
                    try {
                        if (window.top && window.top.document && !window.top.document.parentWindow) {
                            window.top.document.parentWindow = window.top;
                        }
                    } catch (e) {}
                    var fn = null;
                    if (/^\\s*function\\s*\\(/i.test(fonte)) {
                        fn = eval('(' + fonte + ')');
                    }
                    if (typeof fn !== 'function') {
                        return {ok: false, error: 'alerta-funcao-invalido'};
                    }
                    fn();
                    window.__promax030302Confirmacoes.push({
                        tipo: 'alert-callback-promax-executado',
                        mensagem: fonte.substring(0, 200),
                        resposta: fonte.toLowerCase().indexOf('//sim') !== -1 ? 'sim' : 'nao'
                    });
                    return {ok: true};
                } catch (e) {
                    return {ok: false, error: String(e && e.message ? e.message : e)};
                }
                """,
                codigo_funcao,
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _responder_alerta_nativo(self, acertar_diferencas=False):
        try:
            if not self._garantir_janela_030302():
                return None
            alerta = self.driver.switch_to.alert
            texto = str(alerta.text or "")
            texto_normalizado = self._normalizar_texto(texto)
            decisao = self._decidir_resposta_msgbox_030302(texto)
            if (
                texto_normalizado.strip().startswith("function")
                or "document.parentwindow.parent.rotina" in texto_normalizado
            ):
                return {
                    "tipo": "alert-script-aberto",
                    "mensagem": texto,
                    "resposta": "pendente",
                    "bloqueia_fluxo": True,
                }
            if decisao and decisao.get("classificacao") == "alerta_km":
                resultado_km = self._preencher_km_fallback_para_alerta(texto)
                if not (resultado_km or {}).get("ok"):
                    return {
                        "tipo": "alert-nao-tratado",
                        "mensagem": texto,
                        "resposta": "pendente",
                        "classificacao": "alerta_km",
                        "preenchimentoKm": resultado_km,
                        "bloqueia_fluxo": True,
                    }
            if decisao and decisao["resposta"] in ("ok", "sim"):
                alerta.accept()
                return {
                    "tipo": "alert",
                    "mensagem": texto,
                    "resposta": decisao["resposta"],
                    "preenchimentoKm": resultado_km if decisao.get("classificacao") == "alerta_km" else None,
                }
            if decisao and decisao["resposta"] == "nao":
                alerta.dismiss()
                return {"tipo": "alert", "mensagem": texto, "resposta": "nao"}
            if decisao:
                return {
                    "tipo": "alert-nao-tratado",
                    "mensagem": texto,
                    "resposta": decisao["resposta"],
                    "bloqueia_fluxo": True,
                }
            return {
                "tipo": "alert-nao-tratado",
                "mensagem": texto,
                "resposta": "pendente",
                "bloqueia_fluxo": True,
            }
        except NoAlertPresentException:
            return None
        except Exception:
            return None

    def _responder_pergunta_html_js(self):
        try:
            if not self._garantir_janela_030302():
                return None
            self.switch_to_default_content()
            return self.driver.execute_script(
                """
                function normaliza030302(txt) {
                    return String(txt || '')
                        .toLowerCase()
                        .replace(/[áàãâä]/g, 'a')
                        .replace(/[éèêë]/g, 'e')
                        .replace(/[íìîï]/g, 'i')
                        .replace(/[óòõôö]/g, 'o')
                        .replace(/[úùûü]/g, 'u')
                        .replace(/[ç]/g, 'c');
                }

                function visivel(el) {
                    if (!el) return false;
                    var st = el.currentStyle || (
                        el.ownerDocument.defaultView && el.ownerDocument.defaultView.getComputedStyle
                            ? el.ownerDocument.defaultView.getComputedStyle(el)
                            : null
                    );
                    if (st && (st.display === 'none' || st.visibility === 'hidden' || st.opacity === '0')) return false;
                    if (!el.getBoundingClientRect) return true;
                    var r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                }

                function textoEl(el) {
                    return normaliza030302(
                        (el.innerText || '') + ' ' +
                        (el.value || '') + ' ' +
                        (el.name || '') + ' ' +
                        (el.id || '') + ' ' +
                        (el.title || '')
                    );
                }
                function decidirMsgbox030302(textoOriginal) {
                    var texto = normaliza030302(textoOriginal);
                    var compacto = texto.replace(/[^a-z0-9]/g, '');
                    if (
                        texto.indexOf('nao existe diferenc') !== -1
                        || texto.indexOf('nao existem diferenc') !== -1
                        || texto.indexOf('nao ha diferenc') !== -1
                        || compacto.indexOf('naoexistediferenc') !== -1
                        || compacto.indexOf('naoexistemdiferenc') !== -1
                        || compacto.indexOf('naohadiferenc') !== -1
                    ) {
                        return {classificacao: 'ok_sem_diferencas', resposta: 'ok'};
                    }
                    if (texto.indexOf('finance') !== -1 || (texto.indexOf('liber') !== -1 && texto.indexOf('mapa') !== -1)) {
                        return {classificacao: 'liberacao_financeira', resposta: 'sim'};
                    }
                    if (
                        texto.indexOf('deseja continuar') !== -1
                        && (texto.indexOf('guia') !== -1 || compacto.indexOf('guias') !== -1)
                        && (
                            texto.indexOf('bonus') !== -1
                            || texto.indexOf('b nus') !== -1
                            || compacto.indexOf('bnus') !== -1
                        )
                    ) {
                        return {classificacao: 'bonus_as_sem_guias', resposta: 'sim'};
                    }
                    if (
                        (texto.indexOf('diferen') !== -1 || texto.indexOf('diferenc') !== -1)
                        && compacto.indexOf('naoexistediferenc') === -1
                        && compacto.indexOf('naoexistemdiferenc') === -1
                        && compacto.indexOf('naohadiferenc') === -1
                    ) {
                        return {classificacao: 'diferencas', resposta: 'nao'};
                    }
                    return null;
                }

                function clicarResposta(doc, resposta) {
                    var botoes = Array.prototype.slice.call(
                        doc.querySelectorAll('button,input[type=button],input[type=submit],a')
                    ).filter(visivel);
                    var alvos = resposta === 'nao'
                        ? ['nao', 'não', 'no']
                        : ['ok', 'sim', 'yes', 'confirmar'];

                    for (var i = 0; i < botoes.length; i++) {
                        var texto = textoEl(botoes[i]);
                        for (var j = 0; j < alvos.length; j++) {
                            if (texto === alvos[j] || texto.indexOf(alvos[j]) !== -1) {
                                botoes[i].focus();
                                botoes[i].click();
                                return true;
                            }
                        }
                    }
                    return false;
                }

                function procurar(win) {
                    var doc;
                    try { doc = win.document; } catch (e) { return null; }
                    if (!doc || !doc.body) return null;

                    var divMsg = doc.getElementById('DivMensagem');
                    if (divMsg && divMsg.style.display !== 'none') {
                        var msgTexto = divMsg.innerText || divMsg.textContent || '';
                        var decisaoMsg = decidirMsgbox030302(msgTexto) || {resposta: 'ok', classificacao: 'mensagem'};
                        var clicouMsg = clicarResposta(doc, decisaoMsg.resposta);
                        return {
                            tipo: 'html',
                            componente: 'DivMensagem',
                            mensagem: msgTexto,
                            resposta: clicouMsg ? decisaoMsg.resposta : 'pendente',
                            classificacao: decisaoMsg.classificacao,
                            clicouBotao: clicouMsg
                        };
                    }

                    var divFila = doc.getElementById('DivFila');
                    if (divFila && divFila.style.display !== 'none') {
                        var filaTexto = divFila.innerText || divFila.textContent || '';
                        var clicouFila = clicarResposta(doc, 'ok');
                        return {
                            tipo: 'html',
                            componente: 'DivFila',
                            mensagem: filaTexto,
                            resposta: clicouFila ? 'ok' : 'pendente',
                            clicouBotao: clicouFila
                        };
                    }

                    var divMotivos = doc.getElementById('DivMotivosReabMapa');
                    if (divMotivos && divMotivos.style.display !== 'none') {
                        return {
                            tipo: 'html',
                            componente: 'DivMotivosReabMapa',
                            mensagem: divMotivos.innerText || divMotivos.textContent || '',
                            resposta: 'pendente'
                        };
                    }

                    var candidatos = Array.prototype.slice.call(
                        doc.querySelectorAll('div,table,td')
                    ).filter(visivel);
                    var texto = '';
                    for (var c = 0; c < candidatos.length; c++) {
                        var parcial = normaliza030302(candidatos[c].innerText || candidatos[c].textContent || '');
                        if (
                            parcial.indexOf('diferen') !== -1 ||
                            parcial.indexOf('diferenc') !== -1 ||
                            parcial.indexOf('finance') !== -1 ||
                            parcial.indexOf('liberar mapa') !== -1 ||
                            parcial.indexOf('nao existem') !== -1 ||
                            parcial.indexOf('deseja continuar') !== -1
                        ) {
                            texto = parcial;
                            break;
                        }
                    }
                    var decisao = decidirMsgbox030302(texto);
                    var resposta = decisao ? decisao.resposta : null;

                    if (resposta && clicarResposta(doc, resposta)) {
                        return {
                            tipo: 'html',
                            mensagem: doc.body.innerText || doc.body.textContent || '',
                            resposta: resposta,
                            classificacao: decisao.classificacao
                        };
                    }

                    for (var i = 0; i < win.frames.length; i++) {
                        var ret = procurar(win.frames[i]);
                        if (ret) return ret;
                    }
                    return null;
                }

                var raizes = [window];
                try { if (window.parent && window.parent !== window) raizes.push(window.parent); } catch (e) {}
                try { if (window.top && window.top !== window && window.top !== window.parent) raizes.push(window.top); } catch (e) {}
                for (var r = 0; r < raizes.length; r++) {
                    var ret = procurar(raizes[r]);
                    if (ret) return ret;
                }
                return null;
                """
            )
        except Exception:
            try:
                self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=2)
            except Exception:
                pass
            return None
        finally:
            try:
                self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=2)
            except Exception:
                pass

    def _responder_perguntas_salvar(
        self,
        timeout=20,
        acertar_diferencas=False,
        exigir_financeiro=False,
        aceitar_financeiro=False,
    ):
        respostas = []
        respondeu_financeiro = False

        def _tem_lista_diferencas():
            try:
                estado = self._estado_telinhas_js() or {}
                return (
                    int(estado.get("listaDiferencasLength") or 0) > 0
                    or estado.get("divDiferencasDisplay") != "none"
                )
            except Exception:
                return False

        def _condition(_driver):
            nonlocal respondeu_financeiro
            resposta = self._responder_alerta_nativo(acertar_diferencas=acertar_diferencas)
            if resposta:
                self._adicionar_confirmacao_030302(respostas, resposta, origem="nativo")
                self.logger.info("Pergunta/alerta 030302 respondido: %s", resposta)
                mensagem = self._normalizar_texto(resposta.get("mensagem"))
                if self._eh_mensagem_sem_diferencas(mensagem):
                    return True
                if "finance" in mensagem or "liberar mapa" in mensagem:
                    respondeu_financeiro = True
                    if aceitar_financeiro:
                        return True
                if acertar_diferencas and respondeu_financeiro:
                    return True
                if acertar_diferencas and not exigir_financeiro and _tem_lista_diferencas():
                    return True
                return False

            dados_envio = self._obter_confirmacoes_salvar_js() or {"confirmacoes": [], "submitCount": 0}

            resposta = self._responder_pergunta_html_js()
            if resposta:
                self._adicionar_confirmacao_030302(respostas, resposta, origem="html")
                self.logger.info("Pergunta HTML 030302 respondida: %s", resposta)
                mensagem = self._normalizar_texto(resposta.get("mensagem"))
                resposta_pendente = resposta.get("resposta") == "pendente"
                if resposta_pendente:
                    return False
                if self._eh_mensagem_sem_diferencas(mensagem):
                    return True
                if "finance" in mensagem or "liberar mapa" in mensagem:
                    respondeu_financeiro = True
                    if aceitar_financeiro:
                        return True
                if acertar_diferencas and respondeu_financeiro:
                    return True
                if acertar_diferencas and not exigir_financeiro and _tem_lista_diferencas():
                    return True
                return False

            if acertar_diferencas and not exigir_financeiro and _tem_lista_diferencas():
                return True

            if int(dados_envio.get("submitCount") or 0) > 0 and respostas:
                tem_ok = self._confirmacoes_tem_sem_diferencas(respostas)
                tem_financeiro = any(
                    self._classificar_alerta_030302(resposta) == "liberacao_financeira"
                    for resposta in respostas
                )
                if tem_financeiro and not tem_ok and not _tem_lista_diferencas():
                    return False
                self.logger.info(
                    "Envio 030302 detectado apos respostas. submitCount=%s",
                    dados_envio.get("submitCount"),
                )
                return True
            return False

        try:
            WebDriverWait(self.driver, timeout, poll_frequency=0.2).until(_condition)
        except TimeoutException:
            self.logger.info("Fim da espera por perguntas 030302. respostas=%s", respostas)
        return respostas

    def _seguir_fluxo_salvar_030302(
        self,
        timeout=30,
        exigir_financeiro=True,
        parar_apos_financeiro=True,
        aceitar_retorno_sem_alerta=False,
        usar_fluxo_tela_diferencas=False,
    ):
        """Segue a ordem da tela: diferencas, financeiro e resultado."""
        confirmacoes = []
        etapas = {
            "diferencas": False,
            "financeiro": False,
            "resultado": False,
        }
        resultado = {}
        resultado_pendente = {}
        fluxo_tela_diferencas_acionado = False
        fluxo_tela_diferencas_resultado = None
        deadline = time.time() + timeout

        while time.time() <= deadline:
            if resultado_pendente and (not exigir_financeiro or etapas["financeiro"]):
                resultado = resultado_pendente
                etapas["resultado"] = True
                break

            resposta = self._responder_alerta_nativo(acertar_diferencas=True)
            if not resposta:
                resposta = self._responder_pergunta_html_js()

            if resposta:
                self._adicionar_confirmacao_030302(
                    confirmacoes,
                    resposta,
                    origem="fluxo-obrigatorio",
                )
                tipo = self._classificar_alerta_030302(resposta)
                mensagem = resposta.get("mensagem")
                self.logger.info(
                    "Fluxo 030302 respondeu etapa: tipo=%s | resposta=%s | mensagem=%s",
                    tipo,
                    resposta.get("resposta"),
                    mensagem,
                )
                if resposta.get("bloqueia_fluxo") or tipo == "outro" and resposta.get("tipo") == "alert-script-aberto":
                    resultado = {
                        "erro": "msgbox-script-aberta",
                        "alertaRespondido": resposta,
                        "alertasRespondidos": list(confirmacoes),
                        "listaDiferencasLength": 0,
                    }
                    break
                if tipo == "diferencas":
                    etapas["diferencas"] = True
                    continue
                if tipo == "liberacao_financeira":
                    etapas["financeiro"] = True
                    if resultado_pendente:
                        resultado = resultado_pendente
                        resultado["financeiroConfirmado"] = True
                        resultado["alertasRespondidos"] = list(confirmacoes)
                        etapas["resultado"] = True
                        break
                    if parar_apos_financeiro:
                        resultado = {
                            "financeiroConfirmado": True,
                            "alertaRespondido": resposta,
                            "alertasRespondidos": list(confirmacoes),
                            "listaDiferencasLength": 0,
                        }
                        break
                    else:
                        continue
                if tipo == "ok_sem_diferencas":
                    resultado_pendente = {
                        "alertaRespondido": resposta,
                        "alertasRespondidos": list(confirmacoes),
                        "mensagemOk": True,
                        "mensagemSemDiferencas": True,
                        "listaDiferencasLength": 0,
                    }
                    if not exigir_financeiro or etapas["financeiro"]:
                        etapas["resultado"] = True
                        resultado = resultado_pendente
                        break
                    continue
                continue

            dados_confirmacao_js = self._obter_confirmacoes_salvar_js() or {}
            for confirmacao_js in dados_confirmacao_js.get("confirmacoes") or []:
                if not self._adicionar_confirmacao_030302(
                    confirmacoes,
                    confirmacao_js,
                    origem="fluxo-obrigatorio-js",
                ):
                    continue
                tipo_js = self._classificar_alerta_030302(confirmacao_js)
                self.logger.info(
                    "Fluxo 030302 leu msgbox JS: tipo=%s | resposta=%s | mensagem=%s",
                    tipo_js,
                    confirmacao_js.get("resposta"),
                    confirmacao_js.get("mensagem"),
                )
                resposta_js = str(confirmacao_js.get("resposta") or "").lower().strip()
                if not resposta_js:
                    continue
                if tipo_js == "diferencas" and resposta_js == "nao":
                    etapas["diferencas"] = True
                elif tipo_js == "liberacao_financeira" and resposta_js == "sim":
                    etapas["financeiro"] = True
                    if resultado_pendente:
                        resultado = resultado_pendente
                        resultado["financeiroConfirmado"] = True
                        resultado["alertasRespondidos"] = list(confirmacoes)
                        etapas["resultado"] = True
                        break
                    if parar_apos_financeiro:
                        resultado = {
                            "financeiroConfirmado": True,
                            "alertaRespondido": confirmacao_js,
                            "alertasRespondidos": list(confirmacoes),
                            "listaDiferencasLength": 0,
                        }
                        break
                    else:
                        continue
                elif tipo_js == "ok_sem_diferencas" and resposta_js == "ok":
                    resultado_pendente = {
                        "alertaRespondido": confirmacao_js,
                        "alertasRespondidos": list(confirmacoes),
                        "mensagemOk": True,
                        "mensagemSemDiferencas": True,
                        "listaDiferencasLength": 0,
                    }
                    if not exigir_financeiro or etapas["financeiro"]:
                        etapas["resultado"] = True
                        resultado = resultado_pendente
                        break
            if resultado:
                break

            try:
                estado = self._estado_telinhas_js() or {}
            except UnexpectedAlertPresentException:
                continue
            except Exception as exc:
                estado = {"erro": str(exc)}

            # O fluxo original da telinha (ConfiguraFila/OkFila) e propositalmente
            # habilitado apenas quando solicitado pelo chamador. No salvar inicial
            # ele permanece desligado; no salvar FINAL, apos reaplicar as diferencas,
            # deixa o proprio Promax continuar a sequencia e abrir os msgbox nativos.
            if (
                usar_fluxo_tela_diferencas
                and not fluxo_tela_diferencas_acionado
                and (
                    bool(estado.get("divDiferencasVisivel"))
                    or bool(estado.get("divFilaVisivel"))
                )
            ):
                restante = max(1, int(deadline - time.time()))
                fluxo_tela_diferencas_resultado = self._seguir_fluxo_tela_diferencas_js(
                    timeout=min(8, restante)
                )
                self.logger.info(
                    "Fluxo original da telinha 030302 acionado somente no salvar final: %s",
                    fluxo_tela_diferencas_resultado,
                )
                if fluxo_tela_diferencas_resultado and fluxo_tela_diferencas_resultado.get("ok"):
                    fluxo_tela_diferencas_acionado = True
                    # Nao consultar/forcar resposta de msgbox aqui. Volta ao loop para
                    # que _responder_alerta_nativo capture o alerta real do Promax.
                    time.sleep(0.1)
                    continue

            # Retorno para opcao=7/00, tela vazia ou botao desabilitado nao confirma
            # sucesso sozinho. O fluxo somente conclui OK quando um alerta final
            # valido do Promax for efetivamente capturado.

            lista_len = int(estado.get("listaDiferencasLength") or 0)
            diferencas_visivel = bool(estado.get("divDiferencasVisivel"))
            mensagem_visivel = estado.get("divMensagemDisplay") not in (None, "none")
            mensagem_texto = estado.get("divMensagemTexto")

            if mensagem_visivel and self._eh_mensagem_sem_diferencas(mensagem_texto):
                resposta_msg = self._responder_pergunta_html_js()
                if resposta_msg:
                    self._adicionar_confirmacao_030302(
                        confirmacoes,
                        resposta_msg,
                        origem="fluxo-obrigatorio-resultado",
                    )
                estado["mensagemOk"] = True
                estado["mensagemSemDiferencas"] = True
                estado["alertasRespondidos"] = list(confirmacoes)
                resultado_pendente = estado
                if not exigir_financeiro or etapas["financeiro"]:
                    etapas["resultado"] = True
                    resultado = estado
                    break

            if lista_len > 0:
                estado["alertasRespondidos"] = list(confirmacoes)
                resultado_pendente = estado
                if not exigir_financeiro or etapas["financeiro"]:
                    etapas["resultado"] = True
                    resultado = estado
                    break

            if diferencas_visivel and lista_len == 0:
                recuperacao = self._recuperar_diferencas_de_scripts_js()
                estado["recuperacaoScripts"] = recuperacao
                if recuperacao.get("recuperou"):
                    estado = self._estado_telinhas_js() or estado
                    estado["recuperacaoScripts"] = recuperacao
                    estado["alertasRespondidos"] = list(confirmacoes)
                    resultado_pendente = estado
                    if not exigir_financeiro or etapas["financeiro"]:
                        etapas["resultado"] = True
                        resultado = estado
                        break

            time.sleep(0.25)

        if (
            exigir_financeiro
            and not etapas["financeiro"]
            and not (resultado or {}).get("retornoPosSalvar")
        ):
            self.logger.info(
                "Fluxo 030302 terminou sem confirmacao financeira. etapas=%s | confirmacoes=%s | resultado=%s",
                etapas,
                confirmacoes,
                resultado,
            )
        if not resultado:
            if exigir_financeiro:
                resultado = resultado_pendente or self._aguardar_lista_diferencas(timeout=5)
                for alerta_intermediario in resultado.get("alertasRespondidos") or []:
                    self._adicionar_confirmacao_030302(
                        confirmacoes,
                        alerta_intermediario,
                        origem="fluxo-obrigatorio-lista",
                    )
                if (
                    int(resultado.get("listaDiferencasLength") or 0) > 0
                    or self._estado_confirmou_sem_diferencas(resultado)
                ):
                    etapas["resultado"] = True
            else:
                resultado = resultado_pendente or {}

        return {
            "confirmacoes": confirmacoes,
            "etapas": etapas,
            "resultado": resultado or {},
            "fluxoTelaDiferencas": fluxo_tela_diferencas_resultado,
        }

    def _aguardar_envio_salvar_030302(self, timeout=8):
        ultimo = {}

        def _condition(_driver):
            nonlocal ultimo
            dados = self._obter_confirmacoes_salvar_js()
            submit_count = int((dados or {}).get("submitCount") or 0)
            estado = {}
            try:
                estado = self._estado_telinhas_js() or {}
            except UnexpectedAlertPresentException:
                return False
            except Exception as exc:
                estado = {"erro_estado": str(exc)}

            ultimo = {"dados": dados, "submit_count": submit_count, "estado": estado}
            lista_len = int(estado.get("listaDiferencasLength") or 0)
            mensagem_visivel = estado.get("divMensagemDisplay") not in (None, "none")
            if (
                submit_count > 0
                or lista_len > 0
                or mensagem_visivel
                or self._estado_confirmou_sem_diferencas(estado)
            ):
                return ultimo
            return False

        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=0.25).until(_condition)
        except TimeoutException:
            dados = self._obter_confirmacoes_salvar_js()
            submit_count = int((dados or {}).get("submitCount") or 0)
            if submit_count > 0:
                ultimo = {"dados": dados, "submit_count": submit_count, "estado": ultimo.get("estado", {})}
            self.logger.info("Fim da espera pelo envio salvar 030302. estado=%s", ultimo)
            return ultimo

    def _detectar_msgbox_script_pendente_030302(self):
        try:
            if not self._garantir_janela_030302():
                return {"ok": False, "error": "janela-030302-nao-encontrada"}
            self.switch_to_default_content()
            return self.driver.execute_script(
                """
                function normaliza030302(txt) {
                    return String(txt || '')
                        .toLowerCase()
                        .replace(/[áàãâä]/g, 'a')
                        .replace(/[éèêë]/g, 'e')
                        .replace(/[íìîï]/g, 'i')
                        .replace(/[óòõôö]/g, 'o')
                        .replace(/[úùûü]/g, 'u')
                        .replace(/[ç]/g, 'c')
                        .replace(/[Ã¡Ã Ã£Ã¢Ã¤]/g, 'a')
                        .replace(/[Ã©Ã¨ÃªÃ«]/g, 'e')
                        .replace(/[Ã­Ã¬Ã®Ã¯]/g, 'i')
                        .replace(/[Ã³Ã²ÃµÃ´Ã¶]/g, 'o')
                        .replace(/[ÃºÃ¹Ã»Ã¼]/g, 'u')
                        .replace(/[Ã§]/g, 'c');
                }
                function visitar(win, achados, visitados) {
                    if (!win) return;
                    for (var v = 0; v < visitados.length; v++) {
                        if (visitados[v] === win) return;
                    }
                    visitados.push(win);
                    var doc = null;
                    try { doc = win.document; } catch (e) { doc = null; }
                    if (doc) {
                        var scripts = doc.getElementsByTagName ? doc.getElementsByTagName('script') : [];
                        for (var i = 0; i < scripts.length; i++) {
                            var fonte = normaliza030302(scripts[i].text || scripts[i].textContent || scripts[i].innerText || '');
                            if (fonte.indexOf('msgbxsimnao') === -1) continue;
                            if (fonte.indexOf('existem diferenc') !== -1 || fonte.indexOf('existem diferen') !== -1) {
                                achados.temDiferencas = true;
                            }
                            if (fonte.indexOf('libera mapa') !== -1 || fonte.indexOf('financeiro') !== -1) {
                                achados.temFinanceiro = true;
                            }
                            if (fonte.indexOf('nao existem diferenc') !== -1 || fonte.indexOf('nao existem diferen') !== -1) {
                                achados.temSemDiferencas = true;
                            }
                            achados.scripts++;
                        }
                    }
                    try {
                        for (var f = 0; f < win.frames.length; f++) {
                            visitar(win.frames[f], achados, visitados);
                        }
                    } catch (e) {}
                }
                var achados = {
                    ok: true,
                    scripts: 0,
                    temDiferencas: false,
                    temFinanceiro: false,
                    temSemDiferencas: false
                };
                var visitados = [];
                visitar(window, achados, visitados);
                try { visitar(window.parent, achados, visitados); } catch (e) {}
                try { visitar(window.top, achados, visitados); } catch (e) {}
                return achados;
                """
            )
        except Exception as exc:
            try:
                self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=2)
            except Exception:
                pass
            return {"ok": False, "error": str(exc)}
        finally:
            try:
                self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=2)
            except Exception:
                pass

    def _enviar_opcao_030302_js(self, opcao, trigger_suffix=""):
        try:
            self._reentrar_frame(timeout=10)
            return self.driver.execute_script(
                """
                var opcaoValor = String(arguments[0] || '');
                var sufixo = arguments[1] || '';
                function getByName(doc, nome) {
                    if (!doc) return null;
                    var porName = doc.getElementsByName ? doc.getElementsByName(nome)[0] : null;
                    if (porName) return porName;
                    try { return doc.all ? doc.all[nome] : null; } catch (e) { return null; }
                }
                function valor(doc, nome) {
                    var campo = getByName(doc, nome);
                    return campo ? String(campo.value || '') : '';
                }
                function snapshot(doc) {
                    return {
                        opcao: valor(doc, 'opcao'),
                        mapa: valor(doc, 'mapa'),
                        numeroItems: valor(doc, 'numeroItems'),
                        itensListaLength: valor(doc, 'itensLista').length,
                        idAchouGuiaMapa: valor(doc, 'idAchouGuiaMapa'),
                        idAchouGuiasSalvas: valor(doc, 'idAchouGuiasSalvas'),
                        idMostraMsgAfericao: valor(doc, 'idMostraMsgAfericao')
                    };
                }
                var doc = document;
                var campoOpcao = getByName(doc, 'opcao');
                if (!campoOpcao) {
                    return {ok: false, error: 'campo-opcao-nao-encontrado'};
                }
                var antes = snapshot(doc);
                campoOpcao.value = opcaoValor;
                if (typeof window.EnviarFormulario === 'function') {
                    window.EnviarFormulario();
                    return {
                        ok: true,
                        trigger: 'EnviarFormulario.opcao-' + opcaoValor + sufixo,
                        formBefore: antes,
                        formAfter: snapshot(doc)
                    };
                }
                var form = doc.forms ? doc.forms['form1'] : null;
                if (form && form.submit) {
                    form.submit();
                    return {
                        ok: true,
                        trigger: 'form-submit.opcao-' + opcaoValor + sufixo,
                        formBefore: antes,
                        formAfter: snapshot(doc)
                    };
                }
                return {ok: false, error: 'enviar-formulario-nao-encontrado', formBefore: antes};
                """,
                str(opcao),
                trigger_suffix,
            )
        except UnexpectedAlertPresentException:
            return {"ok": True, "trigger": f"EnviarFormulario.opcao-{opcao}{trigger_suffix}-alerta"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _enviar_opcao_com_payload_salvo_030302(self, opcao, snapshot, trigger_suffix=""):
        snapshot = snapshot or {}
        try:
            self._reentrar_frame(timeout=5)
            return self.driver.execute_script(
                """
                var snapshot = arguments[0] || {};
                var opcaoValor = String(arguments[1] || '8');
                var sufixo = arguments[2] || '';

                function getByName(doc, nome) {
                    if (!doc) return null;
                    var porName = doc.getElementsByName ? doc.getElementsByName(nome)[0] : null;
                    if (porName) return porName;
                    try { return doc.all ? doc.all[nome] : null; } catch (e) { return null; }
                }

                function contextoFormulario() {
                    var visitados = [];
                    function visto(win) {
                        for (var i = 0; i < visitados.length; i++) {
                            if (visitados[i] === win) return true;
                        }
                        return false;
                    }
                    function visitar(win) {
                        if (!win || visto(win)) return null;
                        visitados.push(win);
                        var doc = null;
                        try { doc = win.document; } catch (e) { doc = null; }
                        if (doc && (getByName(doc, 'opcao') || getByName(doc, 'itensLista'))) {
                            return {win: win, doc: doc};
                        }
                        try {
                            if (win.frames) {
                                for (var i = 0; i < win.frames.length; i++) {
                                    var ret = visitar(win.frames[i]);
                                    if (ret) return ret;
                                }
                            }
                        } catch (e) {}
                        return null;
                    }
                    return visitar(window) || visitar(window.parent) || visitar(window.top);
                }

                function setValor(doc, nome, valor) {
                    var campo = getByName(doc, nome);
                    if (!campo) return false;
                    campo.value = valor === null || valor === undefined ? '' : String(valor);
                    return true;
                }

                function valor(doc, nome) {
                    var campo = getByName(doc, nome);
                    return campo ? String(campo.value || '') : '';
                }

                function snapshotAtual(ctx) {
                    var itens = valor(ctx.doc, 'itensLista');
                    return {
                        mapa: valor(ctx.doc, 'mapa'),
                        opcao: valor(ctx.doc, 'opcao'),
                        numeroItems: valor(ctx.doc, 'numeroItems'),
                        itensLista: itens,
                        itensListaLength: itens ? itens.length : 0,
                        itensListaPrefix: itens ? itens.substring(0, 80) : '',
                        idAchouGuiaMapa: valor(ctx.doc, 'idAchouGuiaMapa'),
                        idAchouGuiasSalvas: valor(ctx.doc, 'idAchouGuiasSalvas'),
                        idMostraMsgAfericao: valor(ctx.doc, 'idMostraMsgAfericao')
                    };
                }

                var itensLista = String(snapshot.itensLista || snapshot.itensListaCompleto || '');
                if (!itensLista) {
                    return {
                        ok: false,
                        error: 'snapshot-sem-itensLista',
                        trigger: 'EnviarFormulario.payload-salvo' + sufixo
                    };
                }

                var ctx = contextoFormulario();
                if (!ctx || !ctx.doc) {
                    return {
                        ok: false,
                        error: 'formulario-nao-encontrado',
                        trigger: 'EnviarFormulario.payload-salvo' + sufixo
                    };
                }

                var formBefore = snapshotAtual(ctx);
                var mapa = snapshot.mapa || snapshot.mapaSalvo || formBefore.mapa;
                setValor(ctx.doc, 'mapa', mapa);
                setValor(ctx.doc, 'numeroItems', snapshot.numeroItems || formBefore.numeroItems || '0');
                setValor(ctx.doc, 'itensLista', itensLista);
                setValor(ctx.doc, 'idAchouGuiaMapa', snapshot.idAchouGuiaMapa || 'N');
                setValor(ctx.doc, 'idAchouGuiasSalvas', snapshot.idAchouGuiasSalvas || ' ');
                setValor(ctx.doc, 'idMostraMsgAfericao', snapshot.idMostraMsgAfericao || 'N');
                setValor(ctx.doc, 'opcao', opcaoValor);

                var formAfter = snapshotAtual(ctx);
                try {
                    ctx.win.__promax030302UltimoSalvar = formAfter;
                    if (ctx.win.sessionStorage) {
                        ctx.win.sessionStorage.setItem(
                            '__promax030302UltimoSalvar',
                            JSON.stringify(formAfter)
                        );
                    }
                } catch (e) {}

                if (typeof ctx.win.EnviarFormulario === 'function') {
                    ctx.win.EnviarFormulario();
                    return {
                        ok: true,
                        trigger: 'EnviarFormulario.payload-salvo-opcao-' + opcaoValor + sufixo,
                        formBefore: formBefore,
                        formAfter: formAfter
                    };
                }

                var form = ctx.doc.forms ? ctx.doc.forms['form1'] : null;
                if (form && form.submit) {
                    form.submit();
                    return {
                        ok: true,
                        trigger: 'form-submit.payload-salvo-opcao-' + opcaoValor + sufixo,
                        formBefore: formBefore,
                        formAfter: formAfter
                    };
                }

                return {
                    ok: false,
                    error: 'enviar-formulario-nao-encontrado',
                    trigger: 'EnviarFormulario.payload-salvo' + sufixo,
                    formBefore: formBefore,
                    formAfter: formAfter
                };
                """,
                snapshot,
                str(opcao),
                trigger_suffix,
            )
        except UnexpectedAlertPresentException:
            return {
                "ok": True,
                "trigger": f"EnviarFormulario.payload-salvo-opcao-{opcao}{trigger_suffix}-alerta",
            }
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "trigger": f"EnviarFormulario.payload-salvo-opcao-{opcao}{trigger_suffix}",
            }

    def _liberar_financeiro_pos_salvar_js(self, trigger_suffix=""):
        try:
            self._reentrar_frame(timeout=10)
            self._instalar_monitor_envio_js(interceptar_msgbx=False)
            resultado = self.driver.execute_script(
                """
                var sufixo = arguments[0] || '';
                function getByName(doc, nome) {
                    if (!doc) return null;
                    var porName = doc.getElementsByName ? doc.getElementsByName(nome)[0] : null;
                    if (porName) return porName;
                    try {
                        return doc.all ? doc.all[nome] : null;
                    } catch (e) {
                        return null;
                    }
                }
                function valorCampo(doc, nome) {
                    var campo = getByName(doc, nome);
                    return campo ? String(campo.value || '') : '';
                }
                function contexto() {
                    var visitados = [];
                    function visto(win) {
                        for (var i = 0; i < visitados.length; i++) {
                            if (visitados[i] === win) return true;
                        }
                        return false;
                    }
                    function visitar(win) {
                        if (!win || visto(win)) return null;
                        visitados.push(win);
                        var doc = null;
                        try { doc = win.document; } catch (e) { doc = null; }
                        if (doc && getByName(doc, 'statusMapa') && getByName(doc, 'opcao')) {
                            return {win: win, doc: doc};
                        }
                        try {
                            if (win.frames) {
                                for (var i = 0; i < win.frames.length; i++) {
                                    var achou = visitar(win.frames[i]);
                                    if (achou) return achou;
                                }
                            }
                        } catch (e) {}
                        return null;
                    }
                    return visitar(window) || visitar(window.parent) || visitar(window.top) || {win: window, doc: document};
                }

                var ctx = contexto();
                var doc = ctx.doc;
                var win = ctx.win;
                var statusMapa = getByName(doc, 'statusMapa');
                var opcao = getByName(doc, 'opcao');
                if (!statusMapa || !opcao) {
                    return {ok: false, error: 'campos-financeiro-nao-encontrados'};
                }
                var statusAntes = valorCampo(doc, 'statusMapa');
                var opcaoAntes = valorCampo(doc, 'opcao');
                if (statusAntes === '') {
                    return {
                        ok: false,
                        error: 'status-mapa-vazio',
                        statusMapa: statusAntes,
                        opcao: opcaoAntes
                    };
                }
                opcao.value = '99';
                if (typeof win.EnviarFormulario === 'function') {
                    win.EnviarFormulario();
                    return {
                        ok: true,
                        trigger: 'financeiro.EnviarFormulario' + sufixo,
                        statusMapaAntes: statusAntes,
                        opcaoAntes: opcaoAntes,
                        opcaoDepois: valorCampo(doc, 'opcao')
                    };
                }
                var form = doc.forms ? doc.forms['form1'] : null;
                if (form && form.submit) {
                    form.submit();
                    return {
                        ok: true,
                        trigger: 'financeiro.form-submit' + sufixo,
                        statusMapaAntes: statusAntes,
                        opcaoAntes: opcaoAntes,
                        opcaoDepois: valorCampo(doc, 'opcao')
                    };
                }
                return {
                    ok: false,
                    error: 'enviar-formulario-financeiro-nao-encontrado',
                    statusMapa: statusAntes,
                    opcao: opcaoAntes
                };
                """,
                trigger_suffix,
            )
            if resultado is None:
                return {"ok": True, "trigger": f"financeiro.EnviarFormulario{trigger_suffix}-sem-retorno"}
            return resultado
        except UnexpectedAlertPresentException:
            return {"ok": True, "trigger": f"financeiro.EnviarFormulario{trigger_suffix}-alerta"}
        except Exception as exc:
            return {
                "ok": False,
                "error": "liberacao-financeira-js-falhou",
                "message": str(exc),
            }

    def _clicar_salvar_js(self, trigger_suffix="", prefer_click=False, clique_simples=False):
        try:
            resultado = self.driver.execute_script(
                """
                var sufixo = arguments[0] || '';
                var preferClick = arguments[1] === true;
                var cliqueSimples = arguments[2] === true;
                function getByName(doc, nome) {
                    if (!doc) return null;
                    var porName = doc.getElementsByName ? doc.getElementsByName(nome)[0] : null;
                    if (porName) return porName;
                    try {
                        return doc.all ? doc.all[nome] : null;
                    } catch (e) {
                        return null;
                    }
                }

                function contextoSalvar() {
                    var visitados = [];
                    function jaVisto(win) {
                        for (var i = 0; i < visitados.length; i++) {
                            if (visitados[i] === win) return true;
                        }
                        return false;
                    }
                    function visitar(win) {
                        if (!win || jaVisto(win)) return null;
                        visitados.push(win);
                        var doc = null;
                        try { doc = win.document; } catch (e) { doc = null; }
                        if (doc && getByName(doc, 'BotSalvar')) {
                            return {win: win, doc: doc};
                        }
                        try {
                            if (win.frames) {
                                for (var i = 0; i < win.frames.length; i++) {
                                    var achou = visitar(win.frames[i]);
                                    if (achou) return achou;
                                }
                            }
                        } catch (e) {}
                        return null;
                    }
                    return visitar(window) || visitar(window.parent) || visitar(window.top) || {win: window, doc: document};
                }

                function padNumero(valor, tamanho) {
                    var n = parseInt(String(valor || '').replace(/\\D/g, ''), 10);
                    if (isNaN(n)) n = 0;
                    var s = String(n);
                    while (s.length < tamanho) s = '0' + s;
                    return s;
                }

                function auxLinha(index) {
                    if (index < 10) return '00' + index;
                    if (index < 100) return '0' + index;
                    return String(index);
                }

                function valorCampo(doc, nome) {
                    var campo = getByName(doc, nome);
                    return campo ? campo.value : '';
                }

                function checkedCampo(doc, nome) {
                    var campo = getByName(doc, nome);
                    return !!(campo && campo.checked);
                }

                function setValor(doc, nome, valor) {
                    var campo = getByName(doc, nome);
                    if (campo) campo.value = valor;
                    return campo;
                }

                function snapshotFormulario(ctx) {
                    var doc = ctx.doc;
                    var lista = doc.getElementById ? doc.getElementById('lista') : null;
                    if (!lista) lista = getByName(doc, 'lista');
                    var produtos = [];
                    if (lista && lista.rows) {
                        for (var i = 1; i < lista.rows.length && produtos.length < 12; i++) {
                            var aux = auxLinha(i);
                            produtos.push({
                                linha: aux,
                                codigo: valorCampo(doc, 'textcod' + aux),
                                devUn: valorCampo(doc, 'textdevUn' + aux),
                                devAv: valorCampo(doc, 'textdevAv' + aux),
                                troUn: valorCampo(doc, 'texttroUn' + aux),
                                troAv: valorCampo(doc, 'texttroAv' + aux),
                                vazUn: valorCampo(doc, 'textvazUn' + aux),
                                vazAv: valorCampo(doc, 'textvazAv' + aux)
                            });
                        }
                    }
                    var itens = valorCampo(doc, 'itensLista');
                    return {
                        mapa: valorCampo(doc, 'mapa'),
                        mapaSalvo: (typeof ctx.win.mapaSalvo !== 'undefined') ? String(ctx.win.mapaSalvo) : null,
                        statusMapa: (typeof ctx.win.statusMapa1 !== 'undefined') ? String(ctx.win.statusMapa1) : null,
                        opcao: valorCampo(doc, 'opcao'),
                        numeroItems: valorCampo(doc, 'numeroItems'),
                        itensLista: itens ? String(itens) : '',
                        itensListaLength: itens ? String(itens).length : 0,
                        itensListaPrefix: itens ? String(itens).substring(0, 80) : '',
                        listaRows: lista && lista.rows ? lista.rows.length : 0,
                        fBotSalvar: valorCampo(doc, 'fBotSalvar'),
                        idMostraMsgAfericao: valorCampo(doc, 'idMostraMsgAfericao'),
                        idAchouGuiasSalvas: valorCampo(doc, 'idAchouGuiasSalvas'),
                        idAchouGuiaMapa: valorCampo(doc, 'idAchouGuiaMapa'),
                        produtos: produtos
                    };
                }

                function salvarManual(ctx) {
                    var doc = ctx.doc;
                    var win = ctx.win;
                    var lista = doc.getElementById ? doc.getElementById('lista') : null;
                    if (!lista) lista = getByName(doc, 'lista');
                    if (!lista || !lista.rows || lista.rows.length <= 1) {
                        return {ok: false, error: 'lista-sem-itens'};
                    }

                    var result = '';
                    for (var i = 1; i < lista.rows.length; i++) {
                        var aux = auxLinha(i);
                        var cobrarRepack = checkedCampo(doc, 'textcobrarRepack' + aux) ? 'S' : 'N';
                        result += padNumero(valorCampo(doc, 'textcod' + aux), 7);
                        result += padNumero(valorCampo(doc, 'textdevUn' + aux), 5);
                        result += padNumero(valorCampo(doc, 'textdevAv' + aux), 2);
                        result += padNumero(valorCampo(doc, 'texttroUn' + aux), 5);
                        result += padNumero(valorCampo(doc, 'texttroAv' + aux), 2);
                        result += padNumero(valorCampo(doc, 'textvazUn' + aux), 5);
                        result += padNumero(valorCampo(doc, 'textvazAv' + aux), 2);
                        result += cobrarRepack;
                        result += padNumero(valorCampo(doc, 'texttabCustoRepack' + aux), 3);
                        result += padNumero(valorCampo(doc, 'textqtdeRepack' + aux), 5);
                    }

                    try {
                        if (typeof win.nomeArqwor !== 'undefined') {
                            setValor(doc, 'nomeArquivo', win.nomeArqwor);
                        }
                    } catch (e) {}
                    setValor(doc, 'idMostraMsgAfericao', 'N');
                    setValor(doc, 'numeroItems', lista.rows.length - 1);
                    setValor(doc, 'itensLista', result);
                    setValor(doc, 'opcao', 6);

                    var bot = getByName(doc, 'BotSalvar');
                    var botLanc = getByName(doc, 'BotLancamentos');
                    if (bot) bot.disabled = true;
                    if (botLanc) botLanc.disabled = true;
                    try {
                        var botBonus = getByName(doc, 'BotLancBonusAS');
                        if (botBonus) botBonus.disabled = true;
                    } catch (e) {}

                    if (typeof win.EnviarFormulario === 'function') {
                        win.EnviarFormulario();
                        return {
                            ok: true,
                            trigger: 'Salvar.manual-EnviarFormulario' + sufixo,
                            numeroItems: lista.rows.length - 1,
                            itensListaLength: result.length,
                            opcao: valorCampo(doc, 'opcao')
                        };
                    }

                    var form = doc.forms ? doc.forms['form1'] : null;
                    if (form && form.submit) {
                        form.submit();
                        return {
                            ok: true,
                            trigger: 'Salvar.manual-form-submit' + sufixo,
                            numeroItems: lista.rows.length - 1,
                            itensListaLength: result.length,
                            opcao: valorCampo(doc, 'opcao')
                        };
                    }
                    return {ok: false, error: 'enviar-formulario-nao-encontrado'};
                }

                var ctx = contextoSalvar();
                var botSalvar = getByName(ctx.doc, 'BotSalvar');
                if (!botSalvar) {
                    return {ok: false, error: 'botao-salvar-nao-encontrado'};
                }
                if (botSalvar.disabled) {
                    return {ok: false, error: 'botao-salvar-desabilitado'};
                }

                var ativoAntes = ctx.doc.activeElement
                    ? {
                        name: ctx.doc.activeElement.name || '',
                        id: ctx.doc.activeElement.id || '',
                        value: ctx.doc.activeElement.value || ''
                    }
                    : null;
                var formBefore = snapshotFormulario(ctx);
                if (!cliqueSimples) {
                    try {
                        if (
                            ctx.doc.activeElement
                            && ctx.doc.activeElement !== botSalvar
                            && ctx.doc.activeElement.blur
                        ) {
                            if (ctx.doc.activeElement.fireEvent) {
                                try { ctx.doc.activeElement.fireEvent('onchange'); } catch (e) {}
                                try { ctx.doc.activeElement.fireEvent('onblur'); } catch (e) {}
                            }
                            ctx.doc.activeElement.blur();
                        }
                    } catch (e) {}

                    try { botSalvar.focus(); } catch (e) {}
                }

                if (preferClick) {
                    try {
                        if (!botSalvar.click) {
                            return {
                                ok: false,
                                error: 'dom-click-nao-disponivel',
                                message: 'BotSalvar nao expoe click() no DOM do IE.',
                                formBefore: formBefore,
                                formAfter: snapshotFormulario(ctx),
                                activeBefore: ativoAntes,
                                activeAfter: ctx.doc.activeElement
                                    ? {name: ctx.doc.activeElement.name || '', id: ctx.doc.activeElement.id || ''}
                                    : null
                            };
                        }
                        // IMPORTANTE: nao consultar o DOM apos o click.
                        // No fluxo validado do Promax, o click inicia navegacao/alertas nativos.
                        // Retornar null imediatamente faz o Python registrar
                        // BotSalvar.click...-sem-retorno e deixa o fluxo de alertas seguir.
                        botSalvar.click();
                        return null;
                    } catch (clickError) {
                        return {
                            ok: false,
                            error: 'dom-click-falhou',
                            message: String(clickError && clickError.message ? clickError.message : clickError),
                            formBefore: formBefore,
                            formAfter: snapshotFormulario(ctx),
                            activeBefore: ativoAntes,
                            activeAfter: ctx.doc.activeElement
                                ? {name: ctx.doc.activeElement.name || '', id: ctx.doc.activeElement.id || ''}
                                : null
                        };
                    }
                }

                if (botSalvar.fireEvent) {
                    botSalvar.fireEvent('onclick');
                    return {
                        ok: true,
                        trigger: 'BotSalvar.fireEvent(onclick)' + sufixo,
                        formBefore: formBefore,
                        formAfter: snapshotFormulario(ctx),
                        activeBefore: ativoAntes,
                        activeAfter: ctx.doc.activeElement
                            ? {name: ctx.doc.activeElement.name || '', id: ctx.doc.activeElement.id || ''}
                            : null
                    };
                }

                if (typeof botSalvar.onclick === 'function') {
                    botSalvar.onclick.call(botSalvar);
                    return {
                        ok: true,
                        trigger: 'BotSalvar.onclick' + sufixo,
                        formBefore: formBefore,
                        formAfter: snapshotFormulario(ctx),
                        activeBefore: ativoAntes,
                        activeAfter: ctx.doc.activeElement
                            ? {name: ctx.doc.activeElement.name || '', id: ctx.doc.activeElement.id || ''}
                            : null
                    };
                }

                if (typeof ctx.win.Salvar === 'function') {
                    ctx.win.Salvar();
                    return {
                        ok: true,
                        trigger: 'Salvar()' + sufixo,
                        formBefore: formBefore,
                        formAfter: snapshotFormulario(ctx),
                        activeBefore: ativoAntes,
                        activeAfter: ctx.doc.activeElement
                            ? {name: ctx.doc.activeElement.name || '', id: ctx.doc.activeElement.id || ''}
                            : null
                    };
                }

                var manual = salvarManual(ctx);
                if (manual && manual.ok) {
                    manual.formBefore = formBefore;
                    manual.formAfter = snapshotFormulario(ctx);
                    manual.activeBefore = ativoAntes;
                    manual.activeAfter = ctx.doc.activeElement
                        ? {name: ctx.doc.activeElement.name || '', id: ctx.doc.activeElement.id || ''}
                        : null;
                    return manual;
                }

                return {
                    ok: false,
                    error: 'salvar-js-nao-encontrado',
                    manualError: manual,
                    hasSalvar: typeof ctx.win.Salvar === 'function',
                    hasEnviarFormulario: typeof ctx.win.EnviarFormulario === 'function',
                    onclickType: typeof botSalvar.onclick,
                    formBefore: formBefore,
                    formAfter: snapshotFormulario(ctx),
                    activeBefore: ativoAntes,
                    activeAfter: ctx.doc.activeElement
                        ? {name: ctx.doc.activeElement.name || '', id: ctx.doc.activeElement.id || ''}
                        : null
                };
                """,
                trigger_suffix,
                prefer_click,
                clique_simples,
            )
            if resultado is None:
                trigger = "BotSalvar.click" if prefer_click else "BotSalvar.fireEvent(onclick)"
                return {"ok": True, "trigger": f"{trigger}{trigger_suffix}-sem-retorno"}
            return resultado
        except UnexpectedAlertPresentException:
            return {"ok": True, "trigger": f"BotSalvar.click{trigger_suffix}-alerta"}

    def _clicar_salvar_webdriver(self, trigger_suffix=""):
        try:
            estado_antes = self._estado_mapa_js()
            self.driver.execute_script(
                """
                try {
                    var ativo = document.activeElement;
                    if (ativo && ativo.blur) {
                        if (ativo.fireEvent) {
                            try { ativo.fireEvent('onchange'); } catch (e) {}
                            try { ativo.fireEvent('onblur'); } catch (e) {}
                        }
                        ativo.blur();
                    }
                    var bot = document.getElementsByName('BotSalvar')[0];
                    if (bot) {
                        try { bot.scrollIntoView(true); } catch (e) {}
                        try { bot.focus(); } catch (e) {}
                    }
                } catch (e) {}
                """
            )
            botao = self.find_element((By.NAME, "BotSalvar"))
            botao.click()
            return {
                "ok": True,
                "trigger": f"BotSalvar.webdriver-click{trigger_suffix}",
                "estado_antes": estado_antes,
            }
        except UnexpectedAlertPresentException:
            return {
                "ok": True,
                "trigger": f"BotSalvar.webdriver-click{trigger_suffix}-alerta",
                "estado_antes": estado_antes if "estado_antes" in locals() else None,
            }
        except Exception as exc:
            return {
                "ok": False,
                "error": "webdriver-click-falhou",
                "message": str(exc),
                "estado_antes": estado_antes if "estado_antes" in locals() else None,
            }

    def _salvar_corrigindo_diferencas(self, timeout=30):
        resultado_js = self._clicar_salvar_js(".verificar-diferencas")
        self.logger.info("Clique inicial em salvar 030302 executado: %s", resultado_js)
        if not resultado_js or not resultado_js.get("ok"):
            return resultado_js, [], None

        respostas_iniciais = self._responder_perguntas_salvar(
            timeout=timeout,
            acertar_diferencas=True,
            exigir_financeiro=False,
        )
        abriu_acerto = any(
            (
                "diferen" in self._normalizar_texto(resp.get("mensagem"))
                or "diferenc" in self._normalizar_texto(resp.get("mensagem"))
            )
            and "nao existem diferenc" not in self._normalizar_texto(resp.get("mensagem"))
            and "nao existem diferen" not in self._normalizar_texto(resp.get("mensagem"))
            for resp in respostas_iniciais
        )
        respondeu_financeiro = any(
            "finance" in self._normalizar_texto(resp.get("mensagem"))
            or "liberar mapa" in self._normalizar_texto(resp.get("mensagem"))
            for resp in respostas_iniciais
        )
        respondeu_mensagem_ok = any(
            resp.get("resposta") == "ok"
            and (
                "nao existem diferenc" in self._normalizar_texto(resp.get("mensagem"))
                or "nao existem diferen" in self._normalizar_texto(resp.get("mensagem"))
                or resp.get("componente") == "DivMensagem"
            )
            for resp in respostas_iniciais
        )
        recusou_acerto_diferencas = any(
            (
                "diferen" in self._normalizar_texto(resp.get("mensagem"))
                or "diferenc" in self._normalizar_texto(resp.get("mensagem"))
            )
            and "nao existem diferenc" not in self._normalizar_texto(resp.get("mensagem"))
            and "nao existem diferen" not in self._normalizar_texto(resp.get("mensagem"))
            and resp.get("resposta") == "nao"
            for resp in respostas_iniciais
        )
        aceitou_acerto_diferencas = any(
            (
                "diferen" in self._normalizar_texto(resp.get("mensagem"))
                or "diferenc" in self._normalizar_texto(resp.get("mensagem"))
            )
            and "nao existem diferenc" not in self._normalizar_texto(resp.get("mensagem"))
            and "nao existem diferen" not in self._normalizar_texto(resp.get("mensagem"))
            and resp.get("resposta") == "sim"
            for resp in respostas_iniciais
        )

        if recusou_acerto_diferencas and not aceitou_acerto_diferencas:
            self.logger.info(
                "Acerto de diferencas 030302 recusado conforme regra. "
                "Aguardando o Promax gerar a lista/telinha apos a liberacao financeira."
            )

        diferencas = None
        if abriu_acerto or respondeu_financeiro or respondeu_mensagem_ok:
            self.logger.info(
                "Fluxo pos-salvar 030302 detectado. Aguardando financeiro opcional, lista ou mensagem OK."
            )
            if not respondeu_financeiro:
                respostas_pos_diferencas = self._responder_perguntas_salvar(
                    timeout=min(timeout, 8),
                    acertar_diferencas=True,
                    exigir_financeiro=False,
                )
                respostas_iniciais.extend(respostas_pos_diferencas)
                respondeu_financeiro = any(
                    "finance" in self._normalizar_texto(resp.get("mensagem"))
                    or "liberar mapa" in self._normalizar_texto(resp.get("mensagem"))
                    for resp in respostas_iniciais
                )
                respondeu_mensagem_ok = any(
                    resp.get("resposta") == "ok"
                    and (
                        "nao existem diferenc" in self._normalizar_texto(resp.get("mensagem"))
                        or "nao existem diferen" in self._normalizar_texto(resp.get("mensagem"))
                        or resp.get("componente") == "DivMensagem"
                    )
                    for resp in respostas_iniciais
                )

            if respondeu_financeiro:
                self.logger.info("Liberacao financeira confirmada. Aguardando lista/telinha de diferencas.")
            else:
                self.logger.info("Liberacao financeira nao apareceu. Aguardando lista/telinha de diferencas.")

            estado_diferencas = self._aguardar_lista_diferencas(timeout=15)
            lista_diferencas_len = int(estado_diferencas.get("listaDiferencasLength") or 0)
            mensagem_visivel = estado_diferencas.get("divMensagemDisplay") not in (None, "none")
            if mensagem_visivel:
                resposta_msg = self._responder_pergunta_html_js()
                if resposta_msg:
                    respostas_iniciais.append(resposta_msg)
                    respondeu_mensagem_ok = True
                    diferencas = {
                        "encontrou": False,
                        "mensagemRespondida": True,
                        "listaDiferencasLength": lista_diferencas_len,
                        "estadoDiferencas": estado_diferencas,
                        "mensagem": resposta_msg,
                    }
                    self.logger.info("Mensagem OK da 030302 tratada antes da lista: %s", resposta_msg)

            if lista_diferencas_len == 0:
                if respondeu_mensagem_ok:
                    if diferencas is None:
                        diferencas = {
                            "encontrou": False,
                            "mensagemRespondida": True,
                            "listaDiferencasLength": lista_diferencas_len,
                            "estadoDiferencas": estado_diferencas,
                        }
                    self.logger.info(
                        "Promax informou mensagem OK/sem diferencas uteis. Seguindo sem preenchimento de lista."
                    )
                    return resultado_js, respostas_iniciais, diferencas

                try:
                    estado = self._estado_mapa_js() or {}
                except Exception as exc:
                    estado = {
                        "erro": str(exc),
                        "estadoDiferencas": estado_diferencas,
                    }
                diferencas = {
                    "encontrou": False,
                    "mensagemRespondida": False,
                    "listaDiferencasLength": lista_diferencas_len,
                    "estadoDiferencas": estado_diferencas,
                }
                return {
                    "ok": False,
                    "error": "lista-diferencas-nao-gerada",
                    "message": (
                        "O Promax abriu/entrou no fluxo de diferencas, mas a lista "
                        "ficou vazia e nao apareceu mensagem OK para concluir a etapa."
                    ),
                    "estado": estado,
                    "diferencas_corrigidas": diferencas,
                }, respostas_iniciais, diferencas

            diferencas = self.preencher_diferencas(timeout=30)
            if diferencas.get("encontrou"):
                fluxo_diferencas = self._seguir_fluxo_tela_diferencas_js(timeout=timeout)
                diferencas["fluxoTelaDiferencas"] = fluxo_diferencas
                if not fluxo_diferencas or not fluxo_diferencas.get("ok"):
                    estado = self._estado_mapa_js() or {}
                    return {
                        "ok": False,
                        "error": "fluxo-tela-diferencas-nao-concluido",
                        "message": (
                            "As diferencas foram preenchidas, mas o fechamento da "
                            "telinha nao concluiu pelo fluxo original."
                        ),
                        "estado": estado,
                        "diferencas_corrigidas": diferencas,
                    }, respostas_iniciais, diferencas
            self.logger.info("Resultado do acerto de diferencas no salvar 030302: %s", diferencas)
            if not diferencas.get("encontrou") and not diferencas.get("mensagemRespondida"):
                if diferencas.get("fluxoTelaDiferencas", {}).get("ok"):
                    self.logger.info(
                        "Telinha de diferencas 030302 tratada pelo fluxo original sem itens na lista."
                    )
                else:
                    estado = self._estado_mapa_js() or {}
                    self.logger.warning(
                        "Promax pediu acerto de diferencas, mas a lista nao foi preenchida. "
                        "Salvamento final abortado para evitar sucesso falso. diferencas=%s | estado=%s",
                        diferencas,
                        estado,
                    )
                    return {
                        "ok": False,
                        "error": "diferencas-solicitadas-mas-lista-nao-capturada",
                        "message": (
                            "Promax pediu acerto de diferencas, mas a telinha/lista de "
                            "diferencas nao ficou disponivel para preenchimento."
                        ),
                        "estado": estado,
                        "diferencas_corrigidas": diferencas,
                    }, respostas_iniciais, diferencas
            self.wait_for_js_condition(
                """
                var botSalvar = document.getElementsByName('BotSalvar')[0];
                return !!(botSalvar && botSalvar.disabled === false);
                """,
                timeout=timeout,
                description="botao salvar habilitado apos acerto de diferencas na 030302",
            )
            resultado_final = self._clicar_salvar_js(".apos-diferencas")
            self.logger.info("Clique final em salvar 030302 apos diferencas: %s", resultado_final)
            if resultado_final and resultado_final.get("ok"):
                resultado_js = resultado_final

        return resultado_js, respostas_iniciais, diferencas

    def salvar_mapa(self, timeout=30):
        try:
            self.logger.info("Iniciando salvamento da 030302.")
            self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
            self._instalar_monitor_envio_js(interceptar_msgbx=False)
            estado_pre_salvar = self._estado_mapa_js()
            mapa_tem_valor_editavel = self._estado_tem_valor_editavel_030302(estado_pre_salvar)
            valores_originais_primeiro_envio = None

            # CASO ESPECIAL ISOLADO:
            # Se a grade nao possui nenhum codigo fisico, nao entra no primeiro fluxo
            # (zeragem/diferencas/financeiro). Executa somente o envio de liberacao.
            codigos_validos_pre_salvar = []
            for produto_pre in (estado_pre_salvar or {}).get("produtos") or []:
                codigo_pre = str(produto_pre.get("codigo") or "").strip()
                if codigo_pre and codigo_pre.lower() not in {"none", "null", "undefined", "0"}:
                    codigos_validos_pre_salvar.append(codigo_pre)

            if not codigos_validos_pre_salvar:
                mapa_sem_codigos = str(
                    (estado_pre_salvar or {}).get("mapaSalvo")
                    or (estado_pre_salvar or {}).get("mapa")
                    or ""
                ).strip()

                self.logger.info(
                    "030302 | Sem codigos fisicos | executando somente liberacao final | mapa=%s",
                    mapa_sem_codigos,
                )

                # Mantem o mesmo clique de Salvar usado pela rotina, mas NAO chama
                # _seguir_fluxo_salvar_030302, que pertence ao primeiro processo.
                resultado_direto = self._clicar_salvar_js(
                    ".verificar-diferencas",
                    prefer_click=True,
                    clique_simples=False,
                )

                if not resultado_direto or not resultado_direto.get("ok"):
                    self.switch_to_default_content()
                    return ExecutionResult(
                        status=ExecutionStatus.TECHNICAL_FAILURE,
                        message="Nao foi possivel executar a liberacao da 030302 sem codigos fisicos.",
                        retry=False,
                        metadata={
                            "integration_code": "ERRO_LIBERACAO_030302_SEM_CODIGOS",
                            "mapa": mapa_sem_codigos,
                            "sem_codigos_fisicos": True,
                            "resultado_js": resultado_direto,
                        },
                    )

                fechamento_direto = self._aguardar_fechamento_final_isolado_030302(
                    resultado_direto,
                    timeout=min(max(int(timeout or 30), 8), 12),
                )
                confirmacoes_diretas = fechamento_direto.get("confirmacoes") or []
                alerta_bloqueador = fechamento_direto.get("alerta_bloqueador")

                if alerta_bloqueador:
                    classificacao = str(
                        fechamento_direto.get("classificacao_bloqueio") or ""
                    )
                    self.switch_to_default_content()
                    return ExecutionResult(
                        status=(
                            ExecutionStatus.BUSINESS_FAILURE
                            if classificacao == "retorno_nao_liberado"
                            else ExecutionStatus.TECHNICAL_FAILURE
                        ),
                        message=str(
                            alerta_bloqueador.get("mensagem")
                            or "Promax bloqueou a liberacao da 030302."
                        ),
                        retry=False,
                        metadata={
                            "integration_code": "BLOQUEIO_030302_SEM_CODIGOS",
                            "mapa": mapa_sem_codigos,
                            "sem_codigos_fisicos": True,
                            "classificacao_bloqueio": classificacao,
                        },
                    )

                financeiro_liberado = any(
                    str((item or {}).get("classificacao_final") or "") == "liberacao_financeira"
                    and str((item or {}).get("resposta") or "").lower().strip() == "sim"
                    for item in confirmacoes_diretas
                )

                self.switch_to_default_content()
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    message=(
                        f"Mapa {mapa_sem_codigos} liberado para o financeiro com sucesso."
                        if financeiro_liberado
                        else f"Mapa {mapa_sem_codigos} concluido na 030302 sem codigos fisicos."
                    ),
                    metadata={
                        "integration_code": (
                            "MAPA_LIBERADO_FINANCEIRO"
                            if financeiro_liberado
                            else "MAPA_030302_SEM_CODIGOS_CONCLUIDO"
                        ),
                        "mapa": mapa_sem_codigos,
                        "sucesso": True,
                        "sem_codigos_fisicos": True,
                        "financeiro_liberado": financeiro_liberado,
                        "executar_proximo_processo": True,
                    },
                )

            # A PARTIR DAQUI: FLUXO NORMAL ORIGINAL, SEM ALTERACOES.
            if mapa_tem_valor_editavel:
                # Mapa ja preenchido: o primeiro submit precisa sair zerado para
                # reproduzir o mesmo fluxo do mapa vazio no Promax. Os valores
                # originais ficam preservados no snapshot abaixo; depois a lista
                # de diferencas do proprio Promax sera capturada e reaplicada.
                valores_originais_primeiro_envio = (estado_pre_salvar or {}).get("produtos") or []
                zeragem = self._zerar_valores_editaveis_primeiro_envio_030302()
                self.logger.info(
                    "Mapa 030302 preenchido: valores preservados e zerados antes do primeiro salvar: %s",
                    zeragem,
                )
                try:
                    total_zerado = int((zeragem or {}).get("total") or 0)
                except (TypeError, ValueError):
                    total_zerado = 0

                if total_zerado <= 0:
                    self.switch_to_default_content()
                    return ExecutionResult(
                        status=ExecutionStatus.TECHNICAL_FAILURE,
                        message=(
                            "Mapa 030302 tem valores preenchidos, mas nenhum campo positivo "
                            "foi zerado antes do primeiro salvar."
                        ),
                        retry=False,
                        metadata={
                            "estado_pre_salvar": estado_pre_salvar,
                            "zeragem_primeiro_envio": zeragem,
                            "valores_originais_primeiro_envio": valores_originais_primeiro_envio,
                            "confirmacoes": [],
                            "diferencas_corrigidas": None,
                        },
                    )

                estado_apos_zeragem = self._estado_mapa_js()
                if self._estado_tem_valor_editavel_030302(estado_apos_zeragem):
                    self.switch_to_default_content()
                    return ExecutionResult(
                        status=ExecutionStatus.TECHNICAL_FAILURE,
                        message=(
                            "Mapa 030302 continuou com quantidade positiva apos a zeragem; "
                            "primeiro salvar bloqueado para nao enviar o mapa preenchido."
                        ),
                        retry=False,
                        metadata={
                            "estado_pre_salvar": estado_pre_salvar,
                            "estado_apos_zeragem": estado_apos_zeragem,
                            "zeragem_primeiro_envio": zeragem,
                            "valores_originais_primeiro_envio": valores_originais_primeiro_envio,
                            "confirmacoes": [],
                            "diferencas_corrigidas": None,
                        },
                    )

                self.logger.info(
                    "Primeiro envio 030302 confirmado zerado antes do clique em Salvar. estado=%s",
                    estado_apos_zeragem,
                )
            elif (estado_pre_salvar or {}).get("botSalvarDisabled") is True:
                habilitacao = self._habilitar_salvar_mapa_zerado_030302()
                self.logger.info(
                    "Tentativa de habilitar salvar da 030302 com mapa zerado: %s",
                    habilitacao,
                )
            self.wait_for_js_condition(
                """
                var botSalvar = document.getElementsByName('BotSalvar')[0];
                return !!(botSalvar && botSalvar.disabled === false);
                """,
                timeout=timeout,
                description="botao salvar habilitado na 030302",
            )

            estado_antes_salvar = self._estado_mapa_js()
            tem_valor_editavel = self._estado_tem_valor_editavel_030302(estado_antes_salvar)
            usar_click_humano = True
            clique_simples_salvar = False
            # A partir daqui, mapa preenchido e mapa vazio seguem exatamente o mesmo fluxo de envio.
            trigger_salvar = ".verificar-diferencas"
            resultado_js = self._clicar_salvar_js(
                trigger_salvar,
                prefer_click=usar_click_humano,
                clique_simples=clique_simples_salvar,
            )
            self.logger.info("Clique em salvar 030302 executado: %s", resultado_js)
            if not resultado_js or not resultado_js.get("ok"):
                status = ExecutionStatus.TECHNICAL_FAILURE
                if resultado_js and resultado_js.get("error") == "botao-salvar-desabilitado":
                    status = ExecutionStatus.BUSINESS_FAILURE
                return ExecutionResult(
                    status=status,
                    message=(
                        resultado_js.get("message")
                        if resultado_js
                        else "Nao foi possivel clicar em salvar na 030302."
                    ),
                    retry=False,
                    metadata={
                        "resultado_js": resultado_js,
                        "estado_antes_salvar": estado_antes_salvar,
                        "valores_originais_primeiro_envio": valores_originais_primeiro_envio,
                        "confirmacoes": [],
                        "diferencas_corrigidas": None,
                    },
                )

            alertas = []
            payload_tem_quantidade_envio = (
                self._resultado_salvar_tem_quantidade_positiva_030302(resultado_js)
            )
            timeout_fluxo_salvar = min(timeout, 25)
            fluxo_salvar = self._seguir_fluxo_salvar_030302(
                timeout=timeout_fluxo_salvar,
                exigir_financeiro=True,
                parar_apos_financeiro=False,
                aceitar_retorno_sem_alerta=False,
            )
            confirmacoes = fluxo_salvar.get("confirmacoes") or []
            estado_fluxo_resultado = fluxo_salvar.get("resultado") or {}
            etapas_fluxo = fluxo_salvar.get("etapas") or {}
            diferencas_corrigidas = None
            estado_pos_financeiro_lista = None

            # Nao considerar retorno de tela como sucesso sem alerta final.

            msgbox_script_aberta = next(
                (
                    confirmacao
                    for confirmacao in confirmacoes
                    if confirmacao.get("tipo") == "alert-script-aberto"
                ),
                None,
            )
            if msgbox_script_aberta:
                return ExecutionResult(
                    status=ExecutionStatus.TECHNICAL_FAILURE,
                    message=(
                        "Msgbox de script apareceu na 030302 e nao foi fechada automaticamente."
                    ),
                    retry=False,
                    metadata={
                        "trigger": resultado_js.get("trigger"),
                        "fluxo": "msgbox-script-aberta",
                        "alertas": alertas + self._extrair_alertas_capturados(confirmacoes),
                        "confirmacoes": confirmacoes,
                        "etapas": etapas_fluxo,
                        "estado_antes_salvar": estado_antes_salvar,
                        "resultado_js": resultado_js,
                        "estado": estado_fluxo_resultado,
                        "diferencas_corrigidas": diferencas_corrigidas,
                    },
                )
            espera_envio = self._aguardar_envio_salvar_030302(timeout=12)
            if estado_fluxo_resultado and not espera_envio.get("estado"):
                espera_envio["estado"] = estado_fluxo_resultado
            dados_confirmacao = espera_envio.get("dados") or self._obter_confirmacoes_salvar_js()
            if dados_confirmacao.get("ultimoSalvar") and not resultado_js.get("ultimoSalvar"):
                resultado_js["ultimoSalvar"] = dados_confirmacao.get("ultimoSalvar")
            submit_count = int(dados_confirmacao.get("submitCount") or 0)
            confirmou_financeiro = any(
                self._classificar_alerta_030302(confirmacao) == "liberacao_financeira"
                and str(confirmacao.get("resposta") or "").lower().strip() == "sim"
                for confirmacao in confirmacoes
            )
            confirmou_ok = self._confirmacoes_tem_resultado_final_030302(confirmacoes)
            fluxo_visual_completo = bool(
                (etapas_fluxo or {}).get("diferencas")
                and (etapas_fluxo or {}).get("financeiro")
            )
            self.logger.info(
                "Apos fluxo obrigatorio 030302: submitCount=%s, etapas=%s, confirmacoes=%s, "
                "mapa_veio_preenchido=%s, primeiro_envio_tem_valor_editavel=%s, espera_envio=%s",
                submit_count,
                etapas_fluxo,
                confirmacoes,
                mapa_tem_valor_editavel,
                tem_valor_editavel,
                espera_envio,
            )

            if submit_count > 0 or resultado_js.get("ok"):
                payload_com_itens = self._resultado_salvar_tem_itens_030302(resultado_js)
                payload_tem_quantidade = self._resultado_salvar_tem_quantidade_positiva_030302(
                    resultado_js
                )
                if payload_com_itens and not payload_tem_quantidade:
                    self.logger.info(
                        "Primeiro salvar 030302 enviou payload zerado; aguardando telinha/lista "
                        "de diferencas para capturar valores e reaplicar."
                    )
                    if not confirmou_ok:
                        if confirmou_financeiro:
                            self.logger.info(
                                "Financeiro 030302 ja foi confirmado apos payload zerado; "
                                "aguardando retorno real do Promax antes de qualquer fallback."
                            )
                        else:
                            self.logger.info(
                                "Payload zerado da 030302 foi enviado, mas o Promax nao "
                                "exibiu confirmacao financeira; aguardando lista/alerta "
                                "antes da continuidade controlada."
                            )
                        timeout_pos_confirmacoes = 25 if confirmou_financeiro else 8
                        estado_pos_confirmacoes = self._aguardar_lista_diferencas(
                            timeout=timeout_pos_confirmacoes
                        )
                        estado_pos_financeiro_lista = estado_pos_confirmacoes
                        for alerta_intermediario in estado_pos_confirmacoes.get("alertasRespondidos") or []:
                            self._adicionar_confirmacao_030302(
                                confirmacoes,
                                alerta_intermediario,
                                origem="pos-financeiro-lista",
                            )
                        alerta_pos_confirmacoes = estado_pos_confirmacoes.get("alertaRespondido")
                        self._adicionar_confirmacao_030302(
                            confirmacoes,
                            alerta_pos_confirmacoes,
                            origem="pos-financeiro-lista",
                        )
                        if (
                            int(estado_pos_confirmacoes.get("listaDiferencasLength") or 0) > 0
                            or self._estado_confirmou_sem_diferencas(estado_pos_confirmacoes)
                        ):
                            estado_fluxo_resultado = estado_pos_confirmacoes
                            espera_envio["estado"] = estado_pos_confirmacoes
                        else:
                            self.logger.info(
                                "Promax nao exibiu a lista apos o fluxo real da 030302 zerada. "
                                "Solicitando retorno de diferencas por opcao=8 apos submit "
                                "real de opcao=6 com payload salvo."
                            )
                            snapshot_zerado = (
                                (resultado_js or {}).get("formAfter")
                                or (resultado_js or {}).get("ultimoSalvar")
                                or (dados_confirmacao or {}).get("ultimoSalvar")
                                or {}
                            )
                            if snapshot_zerado.get("itensLista"):
                                resultado_opcao8 = self._enviar_opcao_com_payload_salvo_030302(
                                    "8",
                                    snapshot_zerado,
                                    ".retorno-diferencas-pos-submit-zerado",
                                )
                            else:
                                resultado_opcao8 = {
                                    "ok": False,
                                    "error": "snapshot-zerado-sem-itensLista",
                                    "trigger": "EnviarFormulario.payload-salvo-opcao-8"
                                    ".retorno-diferencas-pos-submit-zerado",
                                }
                            resultado_js["retornoDiferencas"] = resultado_opcao8
                            self.logger.info(
                                "Retorno de diferencas 030302 solicitado apos submit zerado: %s",
                                resultado_opcao8,
                            )
                            if resultado_opcao8.get("ok"):
                                estado_pos_confirmacoes = self._aguardar_lista_diferencas(timeout=20)
                                estado_pos_financeiro_lista = estado_pos_confirmacoes
                                for alerta_intermediario in estado_pos_confirmacoes.get(
                                    "alertasRespondidos"
                                ) or []:
                                    self._adicionar_confirmacao_030302(
                                        confirmacoes,
                                        alerta_intermediario,
                                        origem="retorno-diferencas-pos-submit",
                                    )
                                alerta_pos_confirmacoes = estado_pos_confirmacoes.get(
                                    "alertaRespondido"
                                )
                                self._adicionar_confirmacao_030302(
                                    confirmacoes,
                                    alerta_pos_confirmacoes,
                                    origem="retorno-diferencas-pos-submit",
                                )
                            estado_fluxo_resultado = estado_pos_confirmacoes
                            espera_envio["estado"] = estado_pos_confirmacoes
                if payload_com_itens and not confirmou_financeiro:
                    self.logger.info(
                        "Salvar 030302 enviou payload, mas nenhuma confirmacao financeira "
                        "real foi capturada. Nao sera enviado fallback de opcao."
                    )
                if self._confirmacoes_tem_resultado_final_030302(confirmacoes):
                    estado = self._estado_mapa_js() or {}
                    estado["resultadoDiferencas"] = {
                        "mensagemOk": True,
                        "mensagemSemDiferencas": self._confirmacoes_tem_sem_diferencas(
                            confirmacoes
                        ),
                        "listaDiferencasLength": 0,
                    }
                    self.switch_to_default_content()
                    return ExecutionResult(
                        status=ExecutionStatus.SUCCESS,
                        message="Salvar da 030302 confirmado sem diferencas.",
                        metadata={
                            "trigger": resultado_js.get("trigger"),
                            "alertas": alertas + self._extrair_alertas_capturados(confirmacoes),
                            "confirmacoes": confirmacoes,
                            "submit_count": submit_count,
                            "estado_antes_salvar": estado_antes_salvar,
                            "resultado_js": resultado_js,
                            "estado": estado,
                            "diferencas_corrigidas": diferencas_corrigidas,
                        },
                    )
                estado_envio = espera_envio.get("estado") or {}
                if estado_pos_financeiro_lista is not None:
                    estado_resultado_diferencas = estado_pos_financeiro_lista
                else:
                    self._reentrar_frame(timeout=timeout)
                    timeout_lista = 35
                    estado_resultado_diferencas = self._aguardar_lista_diferencas(timeout=timeout_lista)
                for alerta_intermediario in estado_resultado_diferencas.get("alertasRespondidos") or []:
                    self._adicionar_confirmacao_030302(
                        confirmacoes,
                        alerta_intermediario,
                        origem="resultado-diferencas",
                    )
                alerta_resultado = estado_resultado_diferencas.get("alertaRespondido")
                self._adicionar_confirmacao_030302(
                    confirmacoes,
                    alerta_resultado,
                    origem="resultado-diferencas",
                )
                if estado_resultado_diferencas.get("divMensagemDisplay") not in (None, "none"):
                    resposta_msg = self._responder_pergunta_html_js()
                    if resposta_msg:
                        self._adicionar_confirmacao_030302(
                            confirmacoes,
                            resposta_msg,
                            origem="mensagem-html",
                        )
                estado = self._estado_mapa_js() or {}
                estado["resultadoDiferencas"] = estado_resultado_diferencas
                lista_diferencas_len = max(
                    int(estado.get("listaDiferencasLength") or 0),
                    int(estado_resultado_diferencas.get("listaDiferencasLength") or 0),
                )
                resultado_sem_diferencas_confirmado = (
                    self._confirmacoes_tem_resultado_final_030302(confirmacoes)
                )
                if lista_diferencas_len > 0:
                    captura_diferencas = self._capturar_diferencas_lista_js()
                    self.logger.info("Diferencas 030302 capturadas apos primeiro salvar: %s", captura_diferencas)
                    itens_diferencas = captura_diferencas.get("itens") or []
                    if itens_diferencas:
                        mapa_recarga = (
                            estado.get("mapaSalvo")
                            or estado.get("mapa")
                            or estado_antes_salvar.get("mapaSalvo")
                            or estado_antes_salvar.get("mapa")
                        )
                        ponto_apoio_recarga = estado.get("pontoApoio") or estado_antes_salvar.get(
                            "pontoApoio"
                        )
                        resultado_recarga = self._recarregar_mapa_para_acerto(
                            mapa_recarga,
                            ponto_apoio=ponto_apoio_recarga,
                            timeout=timeout,
                        )
                        if resultado_recarga.status != ExecutionStatus.SUCCESS:
                            self.switch_to_default_content()
                            return ExecutionResult(
                                status=ExecutionStatus.TECHNICAL_FAILURE,
                                message=resultado_recarga.message,
                                metadata={
                                    "trigger": resultado_js.get("trigger"),
                                    "alertas": alertas
                                    + self._extrair_alertas_capturados(confirmacoes),
                                    "confirmacoes": confirmacoes,
                                    "submit_count": submit_count,
                                    "estado_antes_salvar": estado_antes_salvar,
                                    "estado_primeiro_salvar": estado,
                                    "captura_diferencas": captura_diferencas,
                                    "resultado_recarga": resultado_recarga.metadata,
                                },
                            )

                        self._reentrar_frame(timeout=timeout)
                        self._instalar_monitor_envio_js(interceptar_msgbx=False)
                        classificacao_diferencas = self._classificar_itens_diferencas_030302(
                            itens_diferencas
                        )
                        itens_produtos = classificacao_diferencas.get("produtos") or []
                        itens_materiais = classificacao_diferencas.get("materiais") or []
                        itens_indefinidos = classificacao_diferencas.get("indefinidos") or []
                        confirmacoes_produtos = []
                        if itens_produtos:
                            self.logger.info(
                                "030302 | Aplicando produtos antes do material: produtos=%s | materiais=%s | indefinidos=%s",
                                len(itens_produtos),
                                len(itens_materiais),
                                len(itens_indefinidos),
                            )
                            aplicacao_produtos = self._aplicar_diferencas_capturadas_js(
                                itens_produtos,
                                destinos_permitidos=("devolucao", "troca"),
                            )
                            self.logger.info(
                                "030302 | Produtos aplicados antes do material: %s",
                                aplicacao_produtos,
                            )
                            if not aplicacao_produtos.get("encontrou"):
                                estado_aplicacao = self._estado_mapa_js()
                                self.switch_to_default_content()
                                return ExecutionResult(
                                    status=ExecutionStatus.TECHNICAL_FAILURE,
                                    message=(
                                        "Diferencas de produto da 030302 foram capturadas, "
                                        "mas nao foram aplicadas antes do material."
                                    ),
                                    metadata={
                                        "trigger": resultado_js.get("trigger"),
                                        "alertas": alertas + self._extrair_alertas_capturados(confirmacoes),
                                        "confirmacoes": confirmacoes,
                                        "submit_count": submit_count,
                                        "estado_antes_salvar": estado_antes_salvar,
                                        "estado_primeiro_salvar": estado,
                                        "captura_diferencas": captura_diferencas,
                                        "classificacao_diferencas": classificacao_diferencas,
                                        "aplicacao_produtos": aplicacao_produtos,
                                        "estado_aplicacao": estado_aplicacao,
                                    },
                                )

                            resultado_produtos = self._clicar_salvar_js(
                                ".apos-aplicar-produtos",
                                prefer_click=True,
                                clique_simples=False,
                            )
                            self.logger.info(
                                "030302 | Clique em salvar apos aplicar produtos: %s",
                                resultado_produtos,
                            )
                            if not resultado_produtos or not resultado_produtos.get("ok"):
                                estado_aplicacao = self._estado_mapa_js()
                                self.switch_to_default_content()
                                return ExecutionResult(
                                    status=ExecutionStatus.TECHNICAL_FAILURE,
                                    message="Produtos da 030302 aplicados, mas o salvar antes do material falhou.",
                                    metadata={
                                        "trigger": resultado_js.get("trigger"),
                                        "alertas": alertas + self._extrair_alertas_capturados(confirmacoes),
                                        "confirmacoes": confirmacoes,
                                        "submit_count": submit_count,
                                        "estado_antes_salvar": estado_antes_salvar,
                                        "estado_primeiro_salvar": estado,
                                        "captura_diferencas": captura_diferencas,
                                        "classificacao_diferencas": classificacao_diferencas,
                                        "aplicacao_produtos": aplicacao_produtos,
                                        "resultado_produtos": resultado_produtos,
                                        "estado_aplicacao": estado_aplicacao,
                                    },
                                )

                            fluxo_produtos = self._seguir_fluxo_salvar_030302(
                                timeout=timeout,
                                exigir_financeiro=False,
                                parar_apos_financeiro=False,
                            )
                            confirmacoes_produtos = fluxo_produtos.get("confirmacoes") or []
                            estado_material = self._aguardar_lista_diferencas(timeout=35)
                            lista_material_len = int(
                                estado_material.get("listaDiferencasLength") or 0
                            )
                            if lista_material_len <= 0:
                                sem_diferencas_produtos = (
                                    self._confirmacoes_tem_sem_diferencas(confirmacoes_produtos)
                                    or self._confirmacoes_tem_resultado_final_030302(confirmacoes_produtos)
                                    or bool((fluxo_produtos.get("resultado") or {}).get("mensagemSemDiferencas"))
                                )
                                if sem_diferencas_produtos:
                                    self.switch_to_default_content()
                                    return ExecutionResult(
                                        status=ExecutionStatus.SUCCESS,
                                        message=(
                                            "Salvar da 030302 concluido apos aplicar produtos; "
                                            "Promax nao retornou material pendente."
                                        ),
                                        metadata={
                                            "trigger": resultado_produtos.get("trigger"),
                                            "fluxo": "produtos-sem-material-pendente",
                                            "alertas": alertas
                                            + self._extrair_alertas_capturados(
                                                confirmacoes,
                                                confirmacoes_produtos,
                                            ),
                                            "confirmacoes": confirmacoes,
                                            "confirmacoes_produtos": confirmacoes_produtos,
                                            "submit_count": submit_count,
                                            "estado_antes_salvar": estado_antes_salvar,
                                            "estado_primeiro_salvar": estado,
                                            "captura_diferencas": captura_diferencas,
                                            "classificacao_diferencas": classificacao_diferencas,
                                            "aplicacao_produtos": aplicacao_produtos,
                                            "resultado_produtos": resultado_produtos,
                                            "estado_material": estado_material,
                                            "sem_diferencas": True,
                                        },
                                    )
                                self.switch_to_default_content()
                                return ExecutionResult(
                                    status=ExecutionStatus.TECHNICAL_FAILURE,
                                    message=(
                                        "Produtos da 030302 foram salvos, mas a segunda tela "
                                        "com material nao apareceu e nao houve mensagem de conclusao."
                                    ),
                                    metadata={
                                        "trigger": resultado_produtos.get("trigger"),
                                        "fluxo": "produtos-sem-lista-material",
                                        "alertas": alertas
                                        + self._extrair_alertas_capturados(
                                            confirmacoes,
                                            confirmacoes_produtos,
                                        ),
                                        "confirmacoes": confirmacoes,
                                        "confirmacoes_produtos": confirmacoes_produtos,
                                        "submit_count": submit_count,
                                        "estado_antes_salvar": estado_antes_salvar,
                                        "estado_primeiro_salvar": estado,
                                        "captura_diferencas": captura_diferencas,
                                        "classificacao_diferencas": classificacao_diferencas,
                                        "aplicacao_produtos": aplicacao_produtos,
                                        "resultado_produtos": resultado_produtos,
                                        "estado_material": estado_material,
                                    },
                                )

                            captura_material = self._capturar_diferencas_lista_js()
                            self.logger.info(
                                "030302 | Material capturado apos salvar produtos: %s",
                                captura_material,
                            )
                            itens_material = captura_material.get("itens") or []
                            if not itens_material:
                                self.switch_to_default_content()
                                return ExecutionResult(
                                    status=ExecutionStatus.TECHNICAL_FAILURE,
                                    message="A segunda tela da 030302 apareceu, mas nao trouxe itens de material.",
                                    metadata={
                                        "trigger": resultado_produtos.get("trigger"),
                                        "fluxo": "lista-material-sem-itens",
                                        "alertas": alertas
                                        + self._extrair_alertas_capturados(
                                            confirmacoes,
                                            confirmacoes_produtos,
                                        ),
                                        "confirmacoes": confirmacoes,
                                        "confirmacoes_produtos": confirmacoes_produtos,
                                        "submit_count": submit_count,
                                        "estado_antes_salvar": estado_antes_salvar,
                                        "estado_primeiro_salvar": estado,
                                        "captura_diferencas": captura_diferencas,
                                        "captura_material": captura_material,
                                        "classificacao_diferencas": classificacao_diferencas,
                                        "aplicacao_produtos": aplicacao_produtos,
                                        "resultado_produtos": resultado_produtos,
                                        "estado_material": estado_material,
                                    },
                                )

                            resultado_recarga_material = self._recarregar_mapa_para_acerto(
                                mapa_recarga,
                                ponto_apoio=ponto_apoio_recarga,
                                timeout=timeout,
                            )
                            if resultado_recarga_material.status != ExecutionStatus.SUCCESS:
                                self.switch_to_default_content()
                                return ExecutionResult(
                                    status=ExecutionStatus.TECHNICAL_FAILURE,
                                    message=resultado_recarga_material.message,
                                    metadata={
                                        "trigger": resultado_produtos.get("trigger"),
                                        "alertas": alertas
                                        + self._extrair_alertas_capturados(
                                            confirmacoes,
                                            confirmacoes_produtos,
                                        ),
                                        "confirmacoes": confirmacoes,
                                        "confirmacoes_produtos": confirmacoes_produtos,
                                        "submit_count": submit_count,
                                        "estado_antes_salvar": estado_antes_salvar,
                                        "estado_primeiro_salvar": estado,
                                        "captura_diferencas": captura_diferencas,
                                        "captura_material": captura_material,
                                        "classificacao_diferencas": classificacao_diferencas,
                                        "aplicacao_produtos": aplicacao_produtos,
                                        "resultado_recarga_material": resultado_recarga_material.metadata,
                                    },
                                )
                            self._reentrar_frame(timeout=timeout)
                            self._instalar_monitor_envio_js(interceptar_msgbx=False)
                            aplicacao_material = self._aplicar_diferencas_capturadas_js(
                                itens_material,
                                destinos_permitidos=("vazio",),
                            )
                            aplicacao_diferencas = {
                                "encontrou": bool(aplicacao_material.get("encontrou")),
                                "fluxoSeparadoProdutoMaterial": True,
                                "produtos": aplicacao_produtos,
                                "material": aplicacao_material,
                                "aplicados": (
                                    (aplicacao_produtos.get("aplicados") or [])
                                    + (aplicacao_material.get("aplicados") or [])
                                ),
                                "naoAplicados": (
                                    (aplicacao_produtos.get("naoAplicados") or [])
                                    + (aplicacao_material.get("naoAplicados") or [])
                                ),
                            }
                            captura_diferencas = {
                                **dict(captura_diferencas or {}),
                                "fluxoSeparadoProdutoMaterial": True,
                                "captura_inicial": captura_diferencas,
                                "captura_material": captura_material,
                            }
                        else:
                            aplicacao_diferencas = self._aplicar_diferencas_capturadas_js(
                                itens_diferencas
                            )
                        self.logger.info(
                            "Diferencas 030302 aplicadas apos reabrir rotina: %s",
                            aplicacao_diferencas,
                        )
                        if not aplicacao_diferencas.get("encontrou"):
                            estado_aplicacao = self._estado_mapa_js()
                            self.switch_to_default_content()
                            return ExecutionResult(
                                status=ExecutionStatus.TECHNICAL_FAILURE,
                                message=(
                                    "Diferencas da 030302 foram capturadas, mas nao foram "
                                    "aplicadas nas linhas do mapa recarregado."
                                ),
                                metadata={
                                    "trigger": resultado_js.get("trigger"),
                                    "alertas": alertas + self._extrair_alertas_capturados(confirmacoes),
                                    "confirmacoes": confirmacoes,
                                    "submit_count": submit_count,
                                    "estado_antes_salvar": estado_antes_salvar,
                                    "estado_primeiro_salvar": estado,
                                    "captura_diferencas": captura_diferencas,
                                    "aplicacao_diferencas": aplicacao_diferencas,
                                    "estado_aplicacao": estado_aplicacao,
                                },
                            )

                        # ============================================================
                        # FINAL ISOLADO DA 030302
                        # Tudo acima deste ponto permanece IDENTICO a base que ja
                        # carregava o mapa, salvava zerado, abria/capturava a telinha,
                        # reabria a rotina e aplicava as diferencas corretamente.
                        # ============================================================
                        estado_pos_preenchimento_final = self._estado_mapa_js() or {}
                        if not self._estado_final_tem_quantidade_positiva_030302(
                            estado_pos_preenchimento_final
                        ):
                            self.switch_to_default_content()
                            return ExecutionResult(
                                status=ExecutionStatus.BUSINESS_FAILURE,
                                message=(
                                    "Diferencas da 030302 foram aplicadas, mas o mapa ficou "
                                    "sem nenhuma quantidade positiva antes do salvar final."
                                ),
                                retry=False,
                                metadata={
                                    "trigger": resultado_js.get("trigger"),
                                    "fluxo": "final-sem-quantidade-positiva",
                                    "alertas": alertas
                                    + self._extrair_alertas_capturados(confirmacoes),
                                    "confirmacoes": confirmacoes,
                                    "submit_count": submit_count,
                                    "estado_antes_salvar": estado_antes_salvar,
                                    "estado_primeiro_salvar": estado,
                                    "captura_diferencas": captura_diferencas,
                                    "diferencas_corrigidas": aplicacao_diferencas,
                                    "estado_pos_preenchimento_final": estado_pos_preenchimento_final,
                                },
                            )

                        # Redigita SOMENTE aqui, depois de as diferencas ja terem sido
                        # aplicadas. Nenhuma funcao compartilhada da primeira etapa e alterada.
                        redigitacao_final = self._reativar_digitacao_valores_030302()
                        self.logger.info(
                            "Valores da 030302 redigitados SOMENTE antes do salvar final: %s",
                            redigitacao_final,
                        )
                        estado_pre_salvar_final = self._estado_mapa_js() or {}
                        if not self._estado_final_tem_quantidade_positiva_030302(
                            estado_pre_salvar_final
                        ):
                            self.switch_to_default_content()
                            return ExecutionResult(
                                status=ExecutionStatus.BUSINESS_FAILURE,
                                message=(
                                    "Salvar final da 030302 bloqueado porque nao existe "
                                    "quantidade positiva no mapa depois do preenchimento."
                                ),
                                retry=False,
                                metadata={
                                    "trigger": resultado_js.get("trigger"),
                                    "fluxo": "final-bloqueado-sem-quantidade",
                                    "alertas": alertas
                                    + self._extrair_alertas_capturados(confirmacoes),
                                    "confirmacoes": confirmacoes,
                                    "submit_count": submit_count,
                                    "estado_antes_salvar": estado_antes_salvar,
                                    "estado_primeiro_salvar": estado,
                                    "captura_diferencas": captura_diferencas,
                                    "diferencas_corrigidas": aplicacao_diferencas,
                                    "redigitacao_final": redigitacao_final,
                                    "estado_pre_salvar_final": estado_pre_salvar_final,
                                },
                            )

                        resultado_final = self._clicar_salvar_js(
                            ".verificar-diferencas",
                            prefer_click=True,
                            clique_simples=False,
                        )
                        self.logger.info(
                            "Clique final em salvar 030302 apos reabrir e aplicar diferencas: %s",
                            resultado_final,
                        )
                        if not resultado_final or not resultado_final.get("ok"):
                            estado_aplicacao = self._estado_mapa_js()
                            self.switch_to_default_content()
                            return ExecutionResult(
                                status=ExecutionStatus.TECHNICAL_FAILURE,
                                message=(
                                    "Diferencas da 030302 foram aplicadas apos reabrir, "
                                    "mas o clique final em salvar falhou."
                                ),
                                metadata={
                                    "trigger": resultado_js.get("trigger"),
                                    "alertas": alertas
                                    + self._extrair_alertas_capturados(confirmacoes),
                                    "confirmacoes": confirmacoes,
                                    "submit_count": submit_count,
                                    "estado_antes_salvar": estado_antes_salvar,
                                    "estado_primeiro_salvar": estado,
                                    "captura_diferencas": captura_diferencas,
                                    "diferencas_corrigidas": aplicacao_diferencas,
                                    "estado_aplicacao": estado_aplicacao,
                                    "resultado_final": resultado_final,
                                },
                            )

                        # O segundo envio NUNCA pode ser aceito se o proprio payload
                        # capturado pelo monitor estiver zerado.
                        payload_final_tem_itens = self._resultado_salvar_final_tem_itens_030302(
                            resultado_final
                        )
                        payload_final_tem_quantidade = (
                            self._resultado_salvar_final_tem_quantidade_positiva_030302(
                                resultado_final
                            )
                        )
                        if payload_final_tem_itens and not payload_final_tem_quantidade:
                            estado_final = self._estado_mapa_js() or {}
                            self.switch_to_default_content()
                            return ExecutionResult(
                                status=ExecutionStatus.BUSINESS_FAILURE,
                                message=(
                                    "Salvar da 030302 enviou lista de itens sem nenhuma "
                                    "quantidade positiva; processo bloqueado para nao aceitar "
                                    "lancamento zerado."
                                ),
                                retry=False,
                                metadata={
                                    "trigger": resultado_final.get("trigger"),
                                    "fluxo": "payload-final-zerado-bloqueado",
                                    "alertas": alertas
                                    + self._extrair_alertas_capturados(confirmacoes),
                                    "confirmacoes": confirmacoes,
                                    "submit_count": submit_count,
                                    "estado_antes_salvar": estado_antes_salvar,
                                    "estado_primeiro_salvar": estado,
                                    "estado_pre_salvar_final": estado_pre_salvar_final,
                                    "resultado_final": resultado_final,
                                    "estado": estado_final,
                                    "diferencas_corrigidas": aplicacao_diferencas,
                                },
                            )

                        # A partir daqui so existe logica do SEGUNDO SALVAR.
                        # Perguntas podem aparecer em qualquer ordem ou nao aparecer.
                        # "Nao existem diferencas" e a confirmacao mais forte, mas a
                        # ausencia dela nao invalida um envio positivo sem bloqueios.
                        fechamento_final = self._aguardar_fechamento_final_isolado_030302(
                            resultado_final,
                            timeout=min(max(timeout, 35), 50),
                        )
                        confirmacoes_final = fechamento_final.get("confirmacoes") or []
                        dados_confirmacao_final = self._obter_confirmacoes_salvar_js() or {}
                        submit_count_final = int(
                            dados_confirmacao_final.get("submitCount") or 0
                        )
                        estado_final = self._estado_mapa_js() or {}

                        alerta_bloqueador = fechamento_final.get("alerta_bloqueador")
                        if alerta_bloqueador:
                            classificacao_bloqueio = str(
                                fechamento_final.get("classificacao_bloqueio") or ""
                            )
                            self.switch_to_default_content()
                            status_bloqueio = (
                                ExecutionStatus.BUSINESS_FAILURE
                                if classificacao_bloqueio == "retorno_nao_liberado"
                                else ExecutionStatus.TECHNICAL_FAILURE
                            )
                            return ExecutionResult(
                                status=status_bloqueio,
                                message=str(alerta_bloqueador.get("mensagem") or "Alerta bloqueador no salvar final."),
                                retry=False,
                                metadata={
                                    "trigger": resultado_final.get("trigger"),
                                    "fluxo": "final-alerta-bloqueador",
                                    "classificacao_bloqueio": classificacao_bloqueio,
                                    "alertas": alertas
                                    + self._extrair_alertas_capturados(
                                        confirmacoes,
                                        confirmacoes_final,
                                    ),
                                    "confirmacoes": confirmacoes,
                                    "confirmacoes_final": confirmacoes_final,
                                    "submit_count": submit_count,
                                    "submit_count_final": submit_count_final,
                                    "estado_antes_salvar": estado_antes_salvar,
                                    "estado_primeiro_salvar": estado,
                                    "estado_pre_salvar_final": estado_pre_salvar_final,
                                    "estado": estado_final,
                                    "captura_diferencas": captura_diferencas,
                                    "diferencas_corrigidas": aplicacao_diferencas,
                                    "resultado_final": resultado_final,
                                    "envio_final_positivo": payload_final_tem_quantidade,
                                },
                            )

                        tem_sem_diferencas = bool(
                            fechamento_final.get("sem_diferencas")
                            or self._confirmacoes_tem_sem_diferencas(confirmacoes_final)
                        )
                        envio_final_sem_retorno = (
                            self._envio_final_sem_retorno_adicional_030302(
                                resultado_final,
                                submit_count_final=submit_count_final,
                                confirmacoes_final=confirmacoes_final,
                            )
                        )

                        if tem_sem_diferencas or envio_final_sem_retorno:
                            self.switch_to_default_content()
                            return ExecutionResult(
                                status=ExecutionStatus.SUCCESS,
                                message=(
                                    "Salvar da 030302 concluido com alerta 'Nao existem diferencas'."
                                    if tem_sem_diferencas
                                    else (
                                        "Salvar da 030302 concluido com payload positivo e sem "
                                        "retorno adicional bloqueador do Promax."
                                    )
                                ),
                                metadata={
                                    "trigger": resultado_final.get("trigger"),
                                    "fluxo": (
                                        "final-nao-existem-diferencas"
                                        if tem_sem_diferencas
                                        else "final-payload-positivo-sem-retorno-adicional"
                                    ),
                                    "alertas": alertas
                                    + self._extrair_alertas_capturados(
                                        confirmacoes,
                                        confirmacoes_final,
                                    ),
                                    "confirmacoes": confirmacoes,
                                    "confirmacoes_final": confirmacoes_final,
                                    "submit_count": submit_count,
                                    "submit_count_final": submit_count_final,
                                    "estado_antes_salvar": estado_antes_salvar,
                                    "estado_primeiro_salvar": estado,
                                    "estado_pre_salvar_final": estado_pre_salvar_final,
                                    "estado": estado_final,
                                    "captura_diferencas": captura_diferencas,
                                    "diferencas_corrigidas": aplicacao_diferencas,
                                    "resultado_final": resultado_final,
                                    "envio_final_positivo": payload_final_tem_quantidade,
                                    "sem_diferencas": tem_sem_diferencas,
                                },
                            )

                        self.switch_to_default_content()
                        return ExecutionResult(
                            status=ExecutionStatus.TECHNICAL_FAILURE,
                            message=(
                                "Salvar final da 030302 nao confirmou envio positivo nem "
                                "retornou um encerramento reconhecido."
                            ),
                            metadata={
                                "trigger": resultado_final.get("trigger"),
                                "fluxo": "final-sem-confirmacao",
                                "alertas": alertas
                                + self._extrair_alertas_capturados(
                                    confirmacoes,
                                    confirmacoes_final,
                                ),
                                "confirmacoes": confirmacoes,
                                "confirmacoes_final": confirmacoes_final,
                                "submit_count": submit_count,
                                "submit_count_final": submit_count_final,
                                "estado_antes_salvar": estado_antes_salvar,
                                "estado_primeiro_salvar": estado,
                                "estado_pre_salvar_final": estado_pre_salvar_final,
                                "estado": estado_final,
                                "captura_diferencas": captura_diferencas,
                                "diferencas_corrigidas": aplicacao_diferencas,
                                "resultado_final": resultado_final,
                                "envio_final_positivo": payload_final_tem_quantidade,
                            },
                        )

                if not resultado_sem_diferencas_confirmado:
                    self.switch_to_default_content()
                    return ExecutionResult(
                        status=ExecutionStatus.TECHNICAL_FAILURE,
                        message=(
                            "Salvar da 030302 enviou formulario sem alerta de confirmacao e "
                            "sem lista de diferencas; o Promax voltou para a tela inicial."
                        ),
                        metadata={
                            "trigger": resultado_js.get("trigger"),
                            "alertas": alertas + self._extrair_alertas_capturados(confirmacoes),
                            "confirmacoes": confirmacoes,
                            "submit_count": submit_count,
                            "estado_antes_salvar": estado_antes_salvar,
                            "resultado_js": resultado_js,
                            "estado": estado,
                            "resultado_diferencas": estado_resultado_diferencas,
                            "diferencas_corrigidas": diferencas_corrigidas,
                        },
                    )

                self.switch_to_default_content()
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    message="Salvar da 030302 acionado e formulario enviado.",
                    metadata={
                        "trigger": resultado_js.get("trigger"),
                        "alertas": alertas + self._extrair_alertas_capturados(confirmacoes),
                        "confirmacoes": confirmacoes,
                        "submit_count": submit_count,
                        "estado_antes_salvar": estado_antes_salvar,
                        "resultado_js": resultado_js,
                        "estado": estado,
                        "diferencas_corrigidas": diferencas_corrigidas,
                    },
                )

            dados_confirmacao = self._obter_confirmacoes_salvar_js()
            submit_count = int(dados_confirmacao.get("submitCount") or 0)
            estado = self._estado_mapa_js() or {}
            self.switch_to_default_content()
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message="Timeout aguardando o script Salvar enviar formulario na 030302.",
                metadata={
                    "trigger": resultado_js.get("trigger"),
                    "alertas": alertas + self._extrair_alertas_capturados(confirmacoes),
                    "confirmacoes": confirmacoes,
                    "submit_count": submit_count,
                    "estado_antes_salvar": estado_antes_salvar,
                    "resultado_js": resultado_js,
                    "estado": estado,
                    "diferencas_corrigidas": diferencas_corrigidas,
                },
            )
        except Exception as exc:
            self.logger.exception("Falha tecnica ao salvar mapa na 030302: %s", exc)
            try:
                self.switch_to_default_content()
            except Exception:
                pass
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=f"Falha tecnica ao salvar mapa na 030302: {exc}",
            )

    def _produtos_final_tem_quantidade_positiva_030302(self, produtos):
        for produto in produtos or []:
            for campo in ("devUn", "devAv", "troUn", "troAv", "vazUn", "vazAv"):
                valor = str(produto.get(campo) or "").strip()
                if not valor:
                    continue
                try:
                    if int(valor) > 0:
                        return True
                except ValueError:
                    if valor not in {"0", "0,0", "0.0"}:
                        return True
        return False

    def _resultado_salvar_final_tem_quantidade_positiva_030302(self, resultado_js):
        if self._produtos_final_tem_quantidade_positiva_030302(
            (resultado_js or {}).get("produtos") or []
        ):
            return True
        for chave in ("formAfter", "ultimoSalvar"):
            form = (resultado_js or {}).get(chave) or {}
            if self._produtos_final_tem_quantidade_positiva_030302(
                form.get("produtos") or []
            ):
                return True
        return False

    def _estado_final_tem_quantidade_positiva_030302(self, estado):
        return self._produtos_final_tem_quantidade_positiva_030302(
            (estado or {}).get("produtos") or []
        )

    def _estado_final_tem_valor_editavel_030302(self, estado):
        produtos_editaveis = []
        for produto in (estado or {}).get("produtos") or []:
            produto_editavel = {}
            for prefixo in ("dev", "tro", "vaz"):
                for sufixo in ("Un", "Av"):
                    campo = f"{prefixo}{sufixo}"
                    if bool(produto.get(f"{campo}Disabled")):
                        continue
                    produto_editavel[campo] = produto.get(campo)
            produtos_editaveis.append(produto_editavel)
        return self._produtos_final_tem_quantidade_positiva_030302(produtos_editaveis)

    def _resultado_salvar_final_tem_itens_030302(self, resultado_js):
        for chave in ("formAfter", "ultimoSalvar"):
            form = (resultado_js or {}).get(chave) or {}
            try:
                itens_len = int(form.get("itensListaLength") or 0)
            except (TypeError, ValueError):
                itens_len = 0
            try:
                numero_items = int(form.get("numeroItems") or 0)
            except (TypeError, ValueError):
                numero_items = 0
            if itens_len > 0 or numero_items > 0 or (form.get("produtos") or []):
                return True
        return False

    def _envio_final_sem_retorno_adicional_030302(
        self,
        resultado_js,
        submit_count_final=0,
        confirmacoes_final=None,
    ):
        if not resultado_js:
            return False
        if not (
            int(submit_count_final or 0) > 0
            or bool((resultado_js or {}).get("ok"))
        ):
            return False
        if not self._resultado_salvar_final_tem_itens_030302(resultado_js):
            return False
        if not self._resultado_salvar_final_tem_quantidade_positiva_030302(resultado_js):
            return False

        for confirmacao in confirmacoes_final or []:
            if bool((confirmacao or {}).get("bloqueia_fluxo")):
                return False
            tipo_final = str((confirmacao or {}).get("classificacao_final") or "")
            if tipo_final in {
                "retorno_nao_liberado",
                "modulo_nao_encontrado",
                "desconhecido",
            }:
                return False
        return True

    def _aguardar_fechamento_final_isolado_030302(self, resultado_js, timeout=40):
        confirmacoes = []
        fim = time.time() + max(5, int(timeout or 40))
        sem_diferencas = False
        alerta_bloqueador = None
        classificacao_bloqueio = None
        ultimo_submit = 0

        while time.time() < fim:
            try:
                if self._garantir_janela_030302():
                    try:
                        alerta = self.driver.switch_to.alert
                        texto = str(alerta.text or "")
                        normalizado = self._normalizar_texto(texto)
                        decisao = self._decidir_resposta_msgbox_030302(texto)

                        if self._eh_mensagem_sem_diferencas(texto):
                            alerta.accept()
                            item = {
                                "tipo": "alert",
                                "mensagem": texto,
                                "resposta": "ok",
                                "classificacao_final": "ok_sem_diferencas",
                            }
                            self._adicionar_confirmacao_030302(
                                confirmacoes,
                                item,
                                origem="segundo-salvar-final-isolado",
                            )
                            sem_diferencas = True
                            break

                        if "retorno nao liberado" in normalizado:
                            try:
                                alerta.accept()
                            except Exception:
                                pass
                            item = {
                                "tipo": "alert",
                                "mensagem": texto,
                                "resposta": "ok",
                                "bloqueia_fluxo": True,
                                "classificacao_final": "retorno_nao_liberado",
                            }
                            self._adicionar_confirmacao_030302(
                                confirmacoes,
                                item,
                                origem="segundo-salvar-final-isolado",
                            )
                            alerta_bloqueador = item
                            classificacao_bloqueio = "retorno_nao_liberado"
                            break

                        if "modulo nao encontrado" in normalizado:
                            try:
                                alerta.accept()
                            except Exception:
                                pass
                            item = {
                                "tipo": "alert",
                                "mensagem": texto,
                                "resposta": "ok",
                                "bloqueia_fluxo": True,
                                "classificacao_final": "modulo_nao_encontrado",
                            }
                            self._adicionar_confirmacao_030302(
                                confirmacoes,
                                item,
                                origem="segundo-salvar-final-isolado",
                            )
                            alerta_bloqueador = item
                            classificacao_bloqueio = "modulo_nao_encontrado"
                            break

                        if decisao and decisao.get("resposta") in ("ok", "sim"):
                            alerta.accept()
                            item = {
                                "tipo": "alert",
                                "mensagem": texto,
                                "resposta": decisao.get("resposta"),
                                "classificacao_final": decisao.get("classificacao"),
                            }
                            self._adicionar_confirmacao_030302(
                                confirmacoes,
                                item,
                                origem="segundo-salvar-final-isolado",
                            )
                            time.sleep(0.2)
                            continue

                        if decisao and decisao.get("resposta") == "nao":
                            alerta.dismiss()
                            item = {
                                "tipo": "alert",
                                "mensagem": texto,
                                "resposta": "nao",
                                "classificacao_final": decisao.get("classificacao"),
                            }
                            self._adicionar_confirmacao_030302(
                                confirmacoes,
                                item,
                                origem="segundo-salvar-final-isolado",
                            )
                            time.sleep(0.2)
                            continue

                        # Alerta desconhecido nao recebe resposta inventada.
                        item = {
                            "tipo": "alert-nao-tratado",
                            "mensagem": texto,
                            "resposta": "pendente",
                            "bloqueia_fluxo": True,
                            "classificacao_final": "desconhecido",
                        }
                        self._adicionar_confirmacao_030302(
                            confirmacoes,
                            item,
                            origem="segundo-salvar-final-isolado",
                        )
                        alerta_bloqueador = item
                        classificacao_bloqueio = "desconhecido"
                        break
                    except NoAlertPresentException:
                        pass
                    except UnexpectedAlertPresentException:
                        # O loop volta imediatamente e captura o alerta pela API nativa.
                        pass
            except Exception:
                pass

            # Apenas observa o submit do segundo envio; nao chama carregar_mapa,
            # nao reabre rotina e nao altera campos da primeira etapa.
            try:
                dados = self._obter_confirmacoes_salvar_js() or {}
                ultimo_submit = max(ultimo_submit, int(dados.get("submitCount") or 0))
            except Exception:
                pass

            time.sleep(0.25)

        return {
            "confirmacoes": confirmacoes,
            "sem_diferencas": sem_diferencas,
            "alerta_bloqueador": alerta_bloqueador,
            "classificacao_bloqueio": classificacao_bloqueio,
            "submitCountObservado": ultimo_submit,
            "payloadPositivo": self._resultado_salvar_final_tem_quantidade_positiva_030302(
                resultado_js
            ),
        }

    def carregar_mapa(self, mapa, ponto_apoio=None, km_atual=None, km_inicial=None, km_prev=None, timeout=45):
        try:
            mapa_normalizado = self.normalizar_mapa(mapa)
            km_atual_normalizado = self.normalizar_km_atual(km_atual)
            km_inicial_normalizado = self.normalizar_km_atual(km_inicial) if km_inicial else None
            km_prev_normalizado = self.normalizar_km_atual(km_prev) if km_prev else None
        except ValueError as exc:
            return ExecutionResult(
                status=ExecutionStatus.BUSINESS_FAILURE,
                message=str(exc),
                retry=False,
            )
        self._km_atual_030302 = km_atual_normalizado
        self._km_inicial_030302 = km_inicial_normalizado
        self._km_prev_030302 = km_prev_normalizado

        try:
            self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
            if not self._esperar_campo_js("mapa", timeout_segundos=10):
                return ExecutionResult(
                    status=ExecutionStatus.TECHNICAL_FAILURE,
                    message="Campo mapa da rotina 030302 nao carregou.",
                )

            self.logger.info("Carregando mapa %s na rotina 030302.", mapa_normalizado)
            ponto_apoio_normalizado = "" if ponto_apoio is None else str(ponto_apoio).strip()
            deve_carregar_ponto_apoio = bool(
                ponto_apoio_normalizado and ponto_apoio_normalizado not in {"0", "00", "000"}
            )
            script_preencher_mapa = """
                var valor = arguments[0];
                var campo = document.getElementsByName('mapa')[0];
                if (!campo) {
                    return {ok: false, error: 'campo-mapa-nao-encontrado'};
                }

                campo.disabled = false;
                campo.readOnly = false;
                campo.className = 'campo';
                campo.focus();
                campo.value = valor;
                var trigger = 'js-set-value-events';
                var retornoCarregaMapa = null;

                try {
                    if (typeof CarregaMapa === 'function') {
                        retornoCarregaMapa = CarregaMapa();
                        trigger = 'CarregaMapa';
                    } else if (campo.fireEvent) {
                        campo.fireEvent('onkeyup');
                        campo.fireEvent('onchange');
                        campo.fireEvent('onblur');
                    } else if (document.createEvent) {
                        var evtKey = document.createEvent('HTMLEvents');
                        evtKey.initEvent('keyup', false, true);
                        campo.dispatchEvent(evtKey);
                        var evtChange = document.createEvent('HTMLEvents');
                        evtChange.initEvent('change', false, true);
                        campo.dispatchEvent(evtChange);
                        var evtBlur = document.createEvent('HTMLEvents');
                        evtBlur.initEvent('blur', false, true);
                        campo.dispatchEvent(evtBlur);
                    }
                } catch (e) {}

                return {
                    ok: true,
                    trigger: trigger,
                    mapaDigitado: campo.value,
                    retornoCarregaMapa: retornoCarregaMapa,
                    submitCount: window.__promax030302SubmitCount || 0,
                    pontoApoioDisabled: document.getElementsByName('pontoApoio')[0]
                        ? !!document.getElementsByName('pontoApoio')[0].disabled
                        : null,
                    pontoApoioValue: document.getElementsByName('pontoApoio')[0]
                        ? document.getElementsByName('pontoApoio')[0].value
                        : null,
                    activeName: document.activeElement ? document.activeElement.name : ''
                };
                """

            def executar_preenchimento_mapa():
                return self.driver.execute_script(script_preencher_mapa, mapa_normalizado)

            resultado_js = executar_preenchimento_mapa()
            if (
                resultado_js
                and resultado_js.get("ok") is False
                and resultado_js.get("error") == "campo-mapa-nao-encontrado"
            ):
                self.logger.warning(
                    "Campo mapa nao encontrado no contexto atual da 030302; reentrando no frame e tentando novamente."
                )
                self._reentrar_frame(timeout=10)
                self._esperar_campo_js("mapa", timeout_segundos=8)
                resultado_js = executar_preenchimento_mapa()
                if resultado_js and resultado_js.get("ok"):
                    resultado_js["retryCampoMapa"] = True

            if not resultado_js or not resultado_js.get("ok"):
                return ExecutionResult(
                    status=ExecutionStatus.TECHNICAL_FAILURE,
                    message=(
                        resultado_js.get("error")
                        if resultado_js
                        else "Nao foi possivel preencher o mapa da rotina 030302 via JS."
                    ),
                    metadata={"resultado_js": resultado_js},
                )

            recuperacao = self._aguardar_e_clicar_sim_recuperar_mapa(timeout=3)
            if recuperacao:
                self.logger.info(
                    "Alerta de recuperacao do mapa %s respondido com sim apos carga por blur/change: %s",
                    mapa_normalizado,
                    recuperacao,
                )

            status_pos_mapa = self._aguardar_estado_pos_mapa_js(timeout=8)
            self.logger.info(
                "Mapa 030302 preenchido via JS e estado pos-carga inicial: resultado=%s | estado=%s",
                resultado_js,
                status_pos_mapa,
            )

            if (
                deve_carregar_ponto_apoio
                and int(status_pos_mapa.get("submitCount") or 0) == 0
                and status_pos_mapa.get("pontoApoioDisabled") is False
            ):
                self.logger.info(
                    "Campo ponto de apoio liberado apos mapa %s; preenchendo PA %s e carregando.",
                    mapa_normalizado,
                    ponto_apoio_normalizado,
                )
                resultado_pa = self.driver.execute_script(
                    """
                    var pontoValor = arguments[0];
                    var campoPonto = document.getElementsByName('pontoApoio')[0];
                    if (!campoPonto) {
                        return {ok: false, error: 'campo-ponto-apoio-nao-encontrado'};
                    }
                    campoPonto.readOnly = false;
                    campoPonto.value = pontoValor || '0';
                    campoPonto.focus();
                    campoPonto.click();
                    if (typeof CarregaPontoApoio === 'function') {
                        CarregaPontoApoio();
                        return {
                            ok: true,
                            trigger: 'CarregaPontoApoio',
                            pontoApoioDigitado: campoPonto.value,
                            submitCount: window.__promax030302SubmitCount || 0
                        };
                    }
                    campoPonto.blur();
                    return {
                        ok: true,
                        trigger: 'pontoApoio.blur',
                        pontoApoioDigitado: campoPonto.value,
                        submitCount: window.__promax030302SubmitCount || 0
                    };
                    """,
                    ponto_apoio_normalizado,
                )
                if resultado_pa and resultado_pa.get("ok"):
                    resultado_js["trigger"] = resultado_pa.get("trigger")
                    resultado_js["ponto_apoio"] = resultado_pa

            try:
                recuperacao = self._aguardar_e_clicar_sim_recuperar_mapa(timeout=3)
                if recuperacao:
                    self.logger.info(
                        "Alerta de recuperacao do mapa %s respondido com sim antes da espera de carga: %s",
                        mapa_normalizado,
                        recuperacao,
                    )
                self._reentrar_frame(timeout=timeout)
                carregou, alertas = self._aguardar_carga_mapa(mapa_normalizado, timeout)
                if alertas:
                    return ExecutionResult(
                        status=ExecutionStatus.BUSINESS_FAILURE,
                        message=f"Mapa {mapa_normalizado} recusado pelo sistema: {' | '.join(alertas)}",
                        retry=False,
                        metadata={"alertas": alertas},
                    )
                if not carregou:
                    estado_timeout = self._estado_mapa_js()
                    return ExecutionResult(
                        status=ExecutionStatus.TECHNICAL_FAILURE,
                        message=f"Timeout aguardando conteudo do mapa {mapa_normalizado} carregar na 030302.",
                        metadata={"estado": estado_timeout, "status_pos_mapa": status_pos_mapa},
                    )
            except TimeoutException:
                estado_timeout = self._estado_mapa_js()
                return ExecutionResult(
                    status=ExecutionStatus.TECHNICAL_FAILURE,
                    message=f"Timeout aguardando conteudo do mapa {mapa_normalizado} carregar na 030302.",
                    metadata={"estado": estado_timeout, "status_pos_mapa": status_pos_mapa},
                )

            alerta = self._aceitar_alerta()
            if alerta:
                if self._eh_alerta_recuperar_mapa(alerta):
                    self.logger.info(
                        "Alerta de recuperacao do mapa %s aceito como sim apos carga: %s",
                        mapa_normalizado,
                        alerta,
                    )
                else:
                    return ExecutionResult(
                        status=ExecutionStatus.BUSINESS_FAILURE,
                        message=f"Mapa {mapa_normalizado} recusado pelo sistema: {alerta}",
                        retry=False,
                    )

            alerta = self._aceitar_alerta()
            if alerta:
                return ExecutionResult(
                    status=ExecutionStatus.BUSINESS_FAILURE,
                    message=f"Mapa {mapa_normalizado} recusado pelo sistema: {alerta}",
                    retry=False,
                )

            resultado_km = None
            if km_atual_normalizado:
                self.logger.info("Preenchendo KM atual %s no mapa %s da 030302.", km_atual_normalizado, mapa_normalizado)
                resultado_km = self._preencher_km_atual_js(km_atual_normalizado)
                if not resultado_km or not resultado_km.get("ok"):
                    return ExecutionResult(
                        status=ExecutionStatus.TECHNICAL_FAILURE,
                        message=(
                            f"Nao foi possivel preencher o KM atual do mapa {mapa_normalizado} na 030302: "
                            f"{(resultado_km or {}).get('error') or 'erro desconhecido'}"
                        ),
                        metadata={"resultado_km": resultado_km},
                    )

            estado_telinhas = self._aguardar_telinhas_pos_carga(timeout=10)
            estado = self._estado_mapa_js()
            self.logger.info("Estado do mapa 030302 apos carga: %s", estado)
            self.switch_to_default_content()
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Mapa {mapa_normalizado} carregado na 030302.",
                metadata={
                    "mapa": mapa_normalizado,
                    "ponto_apoio": ponto_apoio_normalizado,
                    "km_atual": km_atual_normalizado,
                    "trigger": resultado_js.get("trigger"),
                    "resultado_km": resultado_km,
                    "estado": estado,
                    "estado_telinhas": estado_telinhas,
                },
            )
        except Exception as exc:
            self.logger.exception("Falha tecnica ao carregar mapa %s na 030302: %s", mapa_normalizado, exc)
            try:
                self.switch_to_default_content()
            except Exception:
                pass
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=f"Falha tecnica ao carregar mapa {mapa_normalizado} na 030302: {exc}",
            )

    preencher_mapa = carregar_mapa
