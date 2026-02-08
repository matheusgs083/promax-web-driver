from pages.base_page import BasePage

class RotinaPage(BasePage):
    """
    Classe base para todas as janelas de rotina (pop-ups) do sistema.
    Gerencia o controle de janelas e o retorno ao Menu.
    """

    def __init__(self, driver, handle_menu_original):
        """
        :param driver: Instância do Selenium.
        :param handle_menu_original: ID da janela do Menu (para onde voltar).
        """
        super().__init__(driver)
        self.handle_menu = handle_menu_original
        
        # Garante foco na janela atual (a nova rotina)
        try:
            self.driver.switch_to.window(self.driver.current_window_handle)
            self.driver.maximize_window()
        except Exception:
            pass # Se já estiver maximizado ou der erro de permissão, ignora

    def fechar_e_voltar(self):
        """
        Fecha a janela da rotina atual e devolve o foco para o Menu.
        """
        try:
            janela_atual = self.driver.current_window_handle
            self.logger.info(f"Fechando janela da rotina: {janela_atual}")
            self.driver.close()
        except Exception as e:
            self.logger.warning(f"Erro ao tentar fechar janela: {e}")

        # Volta para o menu
        self.driver.switch_to.window(self.handle_menu)
        self.logger.info(f"Foco retornado para o Menu (Handle: {self.handle_menu})")
        
        # Reseta para o frame default do menu
        self.switch_to_default_content()
        
        # Importação local para evitar Ciclo de Importação (Menu <-> Rotina)
        from pages.menu_page import MenuPage
        return MenuPage(self.driver)