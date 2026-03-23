import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from pages.rotina_page import RotinaPage

try:
    from core.manipulador_download import salvar_arquivo_visual
    from core.validador_visual import validar_elemento
except ImportError:
    salvar_arquivo_visual = None
    validar_elemento = None


class Relatorio120601Page(RotinaPage):
    """
    Rotina 120601 - Títulos Pendentes

    Campos (conforme HTML) são CHECKBOX True/False:
    - titulo, tituloPdd, idNotasTitAtu, idNotasTitNaoAtu, idPendRoyalties, idTituloRefugo
    """

    # --- LOCATORS ---
    FRAME_ROTINA = 1
    BTN_GERA_EXCEL_1 = (By.NAME, "GeraExcel")
    BTN_GERA_EXCEL_2 = (By.NAME, "GerExecl")  # fallback comum

    def gerar_relatorio(
        self,
        unidade=None,
        opcao_rel=None,           # select opcaoRel (ex: "01")
        ini_vencimento=None,
        fim_vencimento=None,
        ini_especie=None,
        fim_especie=None,

        # CHECKBOXES (True/False)
        titulo=None,
        titulo_pdd=None,
        id_notas_tit_atu=None,
        id_notas_tit_nao_atu=None,
        id_pend_royalties=None,
        id_titulo_refugo=None,

        acao="BotVisualizar",
        clicar_csv_apos_visualizar=True,
        nome_arquivo="titulos_pendentes.csv",
        timeout=15,
        timeout_csv=500,
    ):
        # === LOOP (MULTI-UNIDADES) via RotinaPage ===
        if unidade is None or isinstance(unidade, list):
            return self.loop_unidades(
                nome_arquivo=nome_arquivo,
                unidades_alvo=unidade if isinstance(unidade, list) else None,
                fn_execucao_unica=lambda cod, arq: self.gerar_relatorio(
                    unidade=cod,
                    opcao_rel=opcao_rel,
                    ini_vencimento=ini_vencimento,
                    fim_vencimento=fim_vencimento,
                    ini_especie=ini_especie,
                    fim_especie=fim_especie,
                    titulo=titulo,
                    titulo_pdd=titulo_pdd,
                    id_notas_tit_atu=id_notas_tit_atu,
                    id_notas_tit_nao_atu=id_notas_tit_nao_atu,
                    id_pend_royalties=id_pend_royalties,
                    id_titulo_refugo=id_titulo_refugo,
                    acao=acao,
                    clicar_csv_apos_visualizar=clicar_csv_apos_visualizar,
                    nome_arquivo=arq,
                    timeout=timeout,
                    timeout_csv=timeout_csv,
                ),
            )

        # === EXECUÇÃO ÚNICA ===
        self.selecionar_unidade(unidade)
        acao = (acao or "BotOk").strip()

        # 1) Entrar no frame (blindado)
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=timeout)

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.NAME, "opcaoRel"))
            )
        except TimeoutException:
            self.logger.warning("O formulário demorou a renderizar. O preenchimento pode falhar.")

        # 2) Preenchimento
        try:
            # SELECT
            if opcao_rel is not None:
                self.logger.info(f"Configurando Ordenação (opcaoRel): {opcao_rel}")
                self.js_set_select_by_name("opcaoRel", opcao_rel)


            checkboxes = [
                ("titulo", titulo),
                ("tituloPdd", titulo_pdd),
                ("idNotasTitAtu", id_notas_tit_atu),
                ("idNotasTitNaoAtu", id_notas_tit_nao_atu),
                ("idPendRoyalties", id_pend_royalties),
                ("idTituloRefugo", id_titulo_refugo),
            ]

            for name, val in checkboxes:
                if val is not None:
                    self.logger.info(f"Setando checkbox {name}={val}")
                    try:
                        self.js_set_checkbox_by_name(name, bool(val), force_click=False)
                    except Exception as e:
                        # alguns ficam disabled dependendo de opcaoRel (ex: idPendRoyalties)
                        self.logger.warning(f"[SKIP] Não foi possível setar {name}={val}: {e}")

            # INPUTS
            inputs = [
                ("iniVencimento", ini_vencimento),
                ("fimVencimento", fim_vencimento),
                ("iniEspecie", ini_especie),
                ("fimEspecie", fim_especie),
            ]
            for name, val in inputs:
                if val is not None:
                    self.logger.info(f"Preenchendo {name}: {val}")
                    self.js_set_input_by_name(name, val)

            # 3) Ação
            btn = self.find_element((By.NAME, acao))
            self.js_click_ie(btn)
            self.logger.info(f"Botão clicado via JS: {acao}")

        except UnexpectedAlertPresentException:
            self.logger.warning("Alerta durante preenchimento. Limpando e abortando unidade.")
            self.lidar_com_alertas()
            raise

        self.switch_to_default_content()

        resultado_final = True

        if acao == "BotVisualizar" and clicar_csv_apos_visualizar:

            resultado_final = self._fluxo_exportar_csv(
                timeout_csv=timeout_csv, 
                nome_arquivo=nome_arquivo,
                timeout_botao=timeout_csv
            )

        self.switch_to_default_content()
        
        # Retorna o status real para o loop_unidades acionar o Tracker
        return resultado_final
    
"""01 Numérica N 
02 Alfabética N 
03 Portador N 
04 Vínculo S 
05 Espécie S 
06 Vencimento N 
07 Vencimento / Vendedor N 
08 Vencimento / Espécie N 
09 Vencimento / Portador N 
10 Vendedor / Vencimento N 
11 Espécie / Vencimento N 
12 Portador / Vencimento N 
13 Vendedor N 
15 Vendedor / Vínculo N 
16 Espécie / Vínculo S 
17 Área N""""""
"""
