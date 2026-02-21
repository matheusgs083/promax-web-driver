import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from pages.rotina_page import RotinaPage

class AlteracaoCondicaoPagtoPage(RotinaPage):
    """
    Rotina: Alteração de Condição de Pagamento
    Call: PW02107C
    Interno: PW02107C
    """

    FRAME_ROTINA = 1

    def alterar_condicao(self, mapa, numero_nota, nova_condicao, serie="003"):

        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)

        # =====================================================================
        # PASSO 1: INJEÇÃO E CARREGAMENTO (Equivale ao POST opcao=2)
        # =====================================================================
        self.logger.info(f"Carregando Nota: Mapa={mapa}, Num={numero_nota}, Série={serie}")
        
        self.js_set_input_by_name("mapa", str(mapa))
        self.js_set_input_by_name("numero", str(numero_nota))
        self.js_set_input_by_name("serie", str(serie))
        
        # Dispara o gatilho nativo do Promax
        self.driver.execute_script("CarregaNota();")
        self._aguardar_processamento_visual()

        # =====================================================================
        # PASSO 2: APLICAR CONDIÇÃO E VALIDAR (Equivale ao POST opcao=3)
        # =====================================================================
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
        
        el_cond = self.find_element((By.NAME, "condNova"))
        if not el_cond.is_enabled():
            self.logger.warning(f"Rejeitado: Nota {numero_nota} não encontrada ou não editável.")
            return False

        self.logger.info(f"Aplicando Condição: {nova_condicao}")
        self.js_set_input_by_name("condNova", str(nova_condicao))
        
        # Dispara a validação nativa
        self.driver.execute_script("CarregaNovaCond();")
        self._aguardar_processamento_visual()

        # =====================================================================
        # PASSO 3: HACK DE CONFIRMAÇÃO E SALVAMENTO (Equivale ao POST opcao=6)
        # =====================================================================
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
        
        btn_salvar = self.find_element((By.NAME, "BotSalvar"))
        if not btn_salvar.is_enabled():
            self.logger.warning(f"Rejeitado: Botão Salvar bloqueado. Condição inválida?")
            return False

        # Sobrescreve a caixinha de pergunta do Promax para responder "Sim" na hora
        self.driver.execute_script("""
            if(typeof window.msgbxSimNao === 'function'){ 
                window.msgbxSimNao = function(tela, msg, fnSim, fnNao){ 
                    console.log('Robô confirmou: ' + msg); fnSim(); 
                }; 
            }
        """)

        self.logger.info("Salvando no banco...")
        try:
            self.driver.execute_script("Salvar();")
        
            WebDriverWait(self.driver, 2).until(EC.alert_is_present())
            alert = self.driver.switch_to.alert
            texto_alerta = alert.text
            alert.accept()
            
            if "já conciliada" in texto_alerta.lower() or "inválida" in texto_alerta.lower():
                self.logger.error(f"Erro do Sistema: {texto_alerta}")
                return False
                
        except TimeoutException:
            pass # Sem alertas de erro, sucesso!

        self._aguardar_processamento_visual()
        self.logger.info(f"Nota {numero_nota} gravada com SUCESSO!")
        self.switch_to_default_content()
        return True

    def _aguardar_processamento_visual(self):
            """
            Monitora o loader do sistema burlando o bug 'HTMLFormElement' nativo do IE Mode.
            """
            # Dá 500ms pro sistema processar o clique e engatilhar o postback
            time.sleep(0.5) 
            
            timeout = time.time() + 5.0
            
            while time.time() < timeout:
                try:
                    # Injeta JS puro do IE antigo em vez de usar is_displayed() do Selenium
                    estado_loader = self.driver.execute_script(
                        "var loader = document.getElementById('imgWait');"
                        "return loader ? loader.style.display : 'none';"
                    )
                    
                    if estado_loader == 'none':
                        break # O loader sumiu visualmente
                        
                except Exception:
                    # Se cair aqui (JavascriptException, StaleElement, NoSuchWindow), 
                    # significa que o HTML velho morreu e o Promax recarregou a tela. Sucesso!
                    break 
                    
                time.sleep(0.5)
                
            # Tenta reentrar no frame após o reload para a próxima ação
            try:
                self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
            except:
                pass