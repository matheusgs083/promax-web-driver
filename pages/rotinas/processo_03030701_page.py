import time
from selenium.common.exceptions import NoAlertPresentException
from pages.rotina_page import RotinaPage

class Processo03030701Page(RotinaPage):

    FRAME_ROTINA = 1

    def _esperar_campo_habilitado_js(self, nome_elemento, timeout_segundos=15):
        """
        Injeta JS para aguardar ativamente até que um campo exista e esteja livre para digitação.
        Retorna True se ficou pronto, False se esgotou o tempo.
        """
        script = f"""
            var el = document.getElementsByName('{nome_elemento}')[0];
            if (!el) return false;
            if (el.disabled) return false;
            if (el.readOnly) return false;
            // Verifica a classe CSS (o Promax usa 'clsDisabled')
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
        """Verifica se o Promax lançou um alerta de erro (Ex: 'Informação inválida') e fecha."""
        try:
            alerta = self.driver.switch_to.alert
            texto = alerta.text
            alerta.accept()
            return texto
        except NoAlertPresentException:
            return None
        except Exception:
            return None

    def alterar_condicao(self, mapa, numero_nota, nova_condicao, serie="003"):
        try:
            self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
            self.logger.info(f"Carregando Nota: Mapa={mapa}, Num={numero_nota}, Série={serie}")

            if not self._esperar_campo_habilitado_js("mapa", 5):
                return False, "Formulário inicial não carregou."

            # =====================================================================
            # PASSO 1: INJEÇÃO E CARREGAMENTO
            # =====================================================================
            # Usa JS puro para inserir os dados de uma vez (muito mais rápido e seguro)
            script_carga = f"""
                document.getElementsByName('mapa')[0].value = '{mapa}';
                document.getElementsByName('numero')[0].value = '{numero_nota}';
                document.getElementsByName('serie')[0].value = '{serie}';
                CarregaNota();
            """
            self.driver.execute_script(script_carga)
            
            # PAUSA VITAL: Dá tempo para o Promax processar o POST e recarregar a tela
            self.logger.info("Aguardando servidor...")
            time.sleep(3)

            # O iframe recarregou, o Selenium perdeu a referência. Precisamos entrar de novo.
            try: self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
            except: pass

            # Verifica se o Promax estourou um pop-up de erro
            alerta_texto = self._lidar_com_alerta_ie()
            if alerta_texto:
                return False, f"Recusado pelo sistema: {alerta_texto}"

            # =====================================================================
            # PASSO 2: APLICAR CONDIÇÃO E VALIDAR REGRAS DE NEGÓCIO
            # =====================================================================
            # Agora com 15 segundos, o robô vai ter paciência se o Promax estiver lento
            if not self._esperar_campo_habilitado_js("condNova", 15):
                self.logger.warning(f"Rejeitado: Nota {numero_nota} já alterada, faturada ou não encontrada.")
                return False, "Nota bloqueada para edição ou não encontrada."

            self.logger.info(f"Aplicando Condição: {nova_condicao}")
            
            script_condicao = f"""
                document.getElementsByName('condNova')[0].value = '{nova_condicao}';
                CarregaNovaCond();
            """
            self.driver.execute_script(script_condicao)
            
            time.sleep(2) # Outra recarga de tela
            
            try: self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
            except: pass
            
            alerta_texto = self._lidar_com_alerta_ie()
            if alerta_texto:
                return False, f"Condição inválida: {alerta_texto}"

            # =====================================================================
            # PASSO 3: CONFIRMAÇÃO E SALVAMENTO
            # =====================================================================
            # Se o botão Salvar não habilitar após injetar a condição, a regra quebrou
            if not self._esperar_campo_habilitado_js("BotSalvar", 5):
                return False, "Botão Salvar bloqueado. Regra de negócio não permitiu a conversão."

            # Sobrescreve a caixinha de pergunta do Promax para responder "Sim" silenciosamente
            self.driver.execute_script("""
                if(typeof window.msgbxSimNao === 'function'){ 
                    window.msgbxSimNao = function(tela, msg, fnSim, fnNao){ fnSim(); }; 
                }
                Salvar();
            """)

            self.logger.info("Salvando no banco...")
            time.sleep(2)
            
            try: self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
            except: pass

            alerta_texto = self._lidar_com_alerta_ie()
            if alerta_texto:
                return False, f"Erro ao salvar: {alerta_texto}"

            self.logger.info(f"Nota {numero_nota} gravada com SUCESSO!")
            self.switch_to_default_content()
            return True, "Alterada com sucesso"

        except Exception as e:
            self.logger.error(f"Erro inesperado no processamento da nota {numero_nota}: {e}")
            try:
                self.switch_to_default_content()
            except:
                pass
            return False, f"Falha sistêmica (Crash): {str(e)}"