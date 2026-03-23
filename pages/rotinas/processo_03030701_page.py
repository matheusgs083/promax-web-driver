import time
from selenium.common.exceptions import NoAlertPresentException
from core.execution_result import ExecutionResult, ExecutionStatus
from pages.rotina_page import RotinaPage


class Processo03030701Page(RotinaPage):

    FRAME_ROTINA = 1

    def _esperar_campo_habilitado_js(self, nome_elemento, timeout_segundos=15):
        """
        Injeta JS para aguardar ativamente atÃ© que um campo exista e esteja livre para digitaÃ§Ã£o.
        Retorna True se ficou pronto, False se esgotou o tempo.
        """
        script = f"""
            var el = document.getElementsByName('{nome_elemento}')[0];
            if (!el) return false;
            if (el.disabled) return false;
            if (el.readOnly) return false;
            if (el.className && typeof el.className === 'string' && el.className.toLowerCase().indexOf('disabled') !== -1) return false;
            if (el.style.display === 'none' || el.style.visibility === 'hidden') return false;
            return true;
        """
        fim = time.time() + timeout_segundos
        while time.time() < fim:
            try:
                pronto = self.driver.execute_script(script)
                if pronto:
                    return True
            except Exception:
                pass
            time.sleep(0.5)

        return False

    def _lidar_com_alerta_ie(self):
        """Verifica se o Promax lanÃ§ou um alerta de erro (Ex: 'InformaÃ§Ã£o invÃ¡lida') e fecha."""
        try:
            alerta = self.driver.switch_to.alert
            texto = alerta.text
            alerta.accept()
            return texto
        except NoAlertPresentException:
            return None
        except Exception:
            return None

    def _reentrar_frame_apos_postback(self, nome_campo_esperado=None, timeout=10):
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=timeout)
        if nome_campo_esperado:
            return self._esperar_campo_habilitado_js(nome_campo_esperado, timeout)
        return True

    def alterar_condicao(self, mapa, numero_nota, nova_condicao, serie="003"):
        try:
            self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
            self.logger.info(f"Carregando Nota: Mapa={mapa}, Num={numero_nota}, SÃ©rie={serie}")

            if not self._esperar_campo_habilitado_js("mapa", 5):
                return ExecutionResult(
                    status=ExecutionStatus.TECHNICAL_FAILURE,
                    message="FormulÃ¡rio inicial nÃ£o carregou.",
                )

            script_carga = f"""
                document.getElementsByName('mapa')[0].value = '{mapa}';
                document.getElementsByName('numero')[0].value = '{numero_nota}';
                document.getElementsByName('serie')[0].value = '{serie}';
                CarregaNota();
            """
            self.driver.execute_script(script_carga)

            self.logger.info("Aguardando servidor...")
            self._reentrar_frame_apos_postback(nome_campo_esperado="condNova", timeout=15)

            alerta_texto = self._lidar_com_alerta_ie()
            if alerta_texto:
                return ExecutionResult(
                    status=ExecutionStatus.BUSINESS_FAILURE,
                    message=f"Recusado pelo sistema: {alerta_texto}",
                )

            if not self._esperar_campo_habilitado_js("condNova", 15):
                self.logger.warning(f"Rejeitado: Nota {numero_nota} jÃ¡ alterada, faturada ou nÃ£o encontrada.")
                return ExecutionResult(
                    status=ExecutionStatus.BUSINESS_FAILURE,
                    message="Nota bloqueada para ediÃ§Ã£o ou nÃ£o encontrada.",
                )

            self.logger.info(f"Aplicando CondiÃ§Ã£o: {nova_condicao}")

            script_condicao = f"""
                document.getElementsByName('condNova')[0].value = '{nova_condicao}';
                CarregaNovaCond();
            """
            self.driver.execute_script(script_condicao)

            self._reentrar_frame_apos_postback(nome_campo_esperado="BotSalvar", timeout=10)

            alerta_texto = self._lidar_com_alerta_ie()
            if alerta_texto:
                return ExecutionResult(
                    status=ExecutionStatus.BUSINESS_FAILURE,
                    message=f"CondiÃ§Ã£o invÃ¡lida: {alerta_texto}",
                )

            if not self._esperar_campo_habilitado_js("BotSalvar", 5):
                return ExecutionResult(
                    status=ExecutionStatus.BUSINESS_FAILURE,
                    message="BotÃ£o Salvar bloqueado. Regra de negÃ³cio nÃ£o permitiu a conversÃ£o.",
                )

            self.driver.execute_script("""
                if(typeof window.msgbxSimNao === 'function'){
                    window.msgbxSimNao = function(tela, msg, fnSim, fnNao){ fnSim(); };
                }
                Salvar();
            """)

            self.logger.info("Salvando no banco...")
            self._reentrar_frame_apos_postback(nome_campo_esperado="mapa", timeout=10)

            alerta_texto = self._lidar_com_alerta_ie()
            if alerta_texto:
                return ExecutionResult(
                    status=ExecutionStatus.BUSINESS_FAILURE,
                    message=f"Erro ao salvar: {alerta_texto}",
                )

            self.logger.info(f"Nota {numero_nota} gravada com SUCESSO!")
            self.switch_to_default_content()
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="Alterada com sucesso",
            )

        except Exception as e:
            self.logger.error(f"Erro inesperado no processamento da nota {numero_nota}: {e}")
            try:
                self.switch_to_default_content()
            except Exception as switch_error:
                self.logger.debug(f"NÃ£o foi possÃ­vel voltar ao conteÃºdo padrÃ£o apÃ³s falha da nota {numero_nota}: {switch_error}")
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=f"Falha sistÃªmica (Crash): {str(e)}",
            )
