import os
import time
import glob
import dotenv
from datetime import datetime, timedelta

from selenium.common.exceptions import UnexpectedAlertPresentException, NoSuchWindowException, WebDriverException
from core.driver_factory import DriverFactory
from core.logger import get_logger
from core.relatorio_execucao import tracker
from pages.login_page import LoginPage
from core.renomeador import limpar_nomes_relatorios
from core.movimentador import mover_relatorios

from pages.rotinas.relatorio_030237_page import Relatorio030237Page
from pages.rotinas.relatorio_120601_page import Relatorio120601Page
from pages.rotinas.relatorio_0513_page import Relatorio0513Page
from pages.rotinas.relatorio_120616_page import Relatorio120616Page
from pages.rotinas.relatorio_0512_page import Relatorio0512Page
from pages.rotinas.relatorio_150501_page import Relatorio150501Page
from pages.rotinas.relatorio_020220_page import Relatorio020220Page

dotenv.load_dotenv()
logger = get_logger("MAIN_PROMAX")

driver = None
menu_page = None

hoje = datetime.now()
ontem = hoje - timedelta(days=1)

ano_atual = hoje.strftime('%Y')
mes_atual = hoje.strftime('%m')
mes_ano_atual = hoje.strftime("%m/%Y")
data_hoje_arquivo = hoje.strftime('%d-%m-%Y')
data_ontem_formatada = ontem.strftime('%d/%m/%Y')
primeiro_dia_mes_atual = hoje.replace(day=1).strftime('%d/%m/%Y')

data_ultimo_dia_mes_passado = hoje.replace(day=1) - timedelta(days=1)
ano_mes_passado = data_ultimo_dia_mes_passado.strftime('%Y')
mes_passado = data_ultimo_dia_mes_passado.strftime('%m')
mes_ano_passado = data_ultimo_dia_mes_passado.strftime("%m/%Y")
ultimo_dia_mes_passado = data_ultimo_dia_mes_passado.strftime('%d/%m/%Y')
primeiro_dia_mes_passado = data_ultimo_dia_mes_passado.replace(day=1).strftime('%d/%m/%Y')

data_ultimo_dia_mes_retrasado = data_ultimo_dia_mes_passado.replace(day=1) - timedelta(days=1)
primeiro_dia_mes_retrasado = data_ultimo_dia_mes_retrasado.replace(day=1).strftime('%d/%m/%Y')

mes_retrasado = data_ultimo_dia_mes_retrasado.strftime('%m')
ano_mes_retrasado = data_ultimo_dia_mes_retrasado.strftime("%m/%Y")

def iniciar_sessao():
    global driver, menu_page
    
    if driver:
        try: driver.quit()
        except: pass

    logger.info(">>> Iniciando nova sessão (Browser + Login)...")
    driver = DriverFactory.get_driver()
    driver.maximize_window()

    login_page = LoginPage(driver)
    usuario = os.getenv("PROMAX_USER")
    senha = os.getenv("PROMAX_PASS")
    
    menu_page = login_page.fazer_login(usuario, senha, nome_unidade="SOUSA")
    logger.info("Sessão iniciada com sucesso.")
    return driver, menu_page

def executar_tarefa_com_retry(nome_tarefa, funcao_logica, tentativas=3):
    global driver, menu_page

    for tentativa in range(1, tentativas + 1):
        try:
            logger.info(f"--- Executando: {nome_tarefa} (Tentativa {tentativa}/{tentativas}) ---")
            if not driver:
                iniciar_sessao()

            funcao_logica()
            logger.info(f"Status: {nome_tarefa} CONCLUÍDA.")
            return True

        except (UnexpectedAlertPresentException, NoSuchWindowException, WebDriverException) as e:
            msg_erro = str(e)
            logger.warning(f"Falha na {nome_tarefa}: {msg_erro}")

            erros_de_sessao = ["Sessão inválida", "Unable to get browser", "no such window", "Timed out", "timeout"]
            eh_erro_critico = any(txt in msg_erro for txt in erros_de_sessao)

            if eh_erro_critico and tentativa < tentativas:
                logger.warning("Detecção de queda de sessão! Iniciando protocolo de Re-login...")
                try:
                    iniciar_sessao() 
                except Exception as e_login:
                    logger.critical(f"Não foi possível fazer o re-login: {e_login}")
                    raise e_login
            else:
                logger.error(f"Erro irrecuperável na {nome_tarefa}.")
                raise e

def main():
    logger.info("=== INICIANDO ROBÔ PROMAX (COM AUTO-RECOVERY) ===")

    try:
        iniciar_sessao()

        def tarefa_0513(unidades_alvo=None):
            janela = menu_page.acessar_rotina("0513")
            page = Relatorio0513Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                unidade=unidades_alvo,
                opcao_rel="12", volume_fin="F", tp_equipe="E", 
                mes_ano_inicial=mes_ano_passado, mes_ano_final=mes_ano_passado,
                quantos_clientes="99999", nome_arquivo=f"{ultimo_dia_mes_passado.replace('/','-')} (nUnidade) nomeUnidade0513"
            )
            page.fechar_e_voltar()

        def tarefa_120616(unidades_alvo=None):
            janela = menu_page.acessar_rotina("120616")
            page = Relatorio120616Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                unidade=unidades_alvo, 
                opcao_rel="3", mes_ano=mes_ano_passado, 
                nome_arquivo=f"{ultimo_dia_mes_passado.replace('/','-')} (nUnidade) 120616_nomeUnidade120616"
            )
            page.fechar_e_voltar()

        def tarefa_120601(unidades_alvo=None):
            janela = menu_page.acessar_rotina("120601")
            page = Relatorio120601Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                unidade=unidades_alvo,
                opcao_rel="01", id_notas_tit_nao_atu=False, 
                ini_vencimento=primeiro_dia_mes_retrasado, fim_vencimento=ultimo_dia_mes_passado, 
                ini_especie=4, fim_especie=4, 
                nome_arquivo=f"{ultimo_dia_mes_passado.replace('/','-')} 120601_nomeUnidade120601"
            )
            page.fechar_e_voltar()

        def tarefa_0512(unidades_alvo=None):
            janela = menu_page.acessar_rotina("0512")
            page = Relatorio0512Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                unidade=unidades_alvo,
                opcao_rel="11", ano=ano_atual, id_converte_hecto=True, 
                nome_arquivo=f"0512 {ano_atual} nomeUnidade0512"
            )
            page.fechar_e_voltar()

        def tarefa_150501(unidades_alvo=None):
            janela = menu_page.acessar_rotina("150501")
            page = Relatorio150501Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                unidade=unidades_alvo, visao="02",
                periodo="M", mes_ano=mes_ano_passado, totaliza_periodo=True, 
                nome_arquivo=f"{ano_mes_passado}-{mes_passado} nomeUnidade150501"
            )
            page.fechar_e_voltar()

        def tarefa_030237(unidades_alvo=None):
            janela = menu_page.acessar_rotina("030237")
            page = Relatorio030237Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                unidade=unidades_alvo,
                quebra1="14", quebra2="12", quebra3="16", 
                data_inicial=primeiro_dia_mes_passado, data_final=ultimo_dia_mes_passado, 
                nome_arquivo=f"{mes_passado}-{ano_mes_passado} nomeUnidade030237"
            )
            page.fechar_e_voltar()

        def tarefa_030237_Giro(unidades_alvo=["3610006", "3610007", "3610008"]):
            janela = menu_page.acessar_rotina("030237")
            page = Relatorio030237Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                unidade=unidades_alvo,
                quebra1="14", itens=True,
                data_inicial=primeiro_dia_mes_passado, data_final=ultimo_dia_mes_passado,   
                nome_arquivo=f"{mes_passado}-{ano_mes_passado} nUnidade"
            )
            page.fechar_e_voltar()

        def tarefa_020220(unidades_alvo=None):
            janela = menu_page.acessar_rotina("020220")
            page = Relatorio020220Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                unidade=unidades_alvo, opcao_rel="01", mercadoria_todos=False,
                mercadoria_garrafeira=True, mercadoria_vasilhame=True,
                selecao_comodatos="T", nome_arquivo="020220 - nomeUnidade020220"
            )
            page.fechar_e_voltar()

        mapa_tarefas = {
            #"Rotina 0513": tarefa_0513,
            #"Rotina 120616": tarefa_120616,
            #"Rotina 120601": tarefa_120601,
            #"Rotina 0512": tarefa_0512,
            "Rotina 150501": tarefa_150501,
            #"Rotina 030237": tarefa_030237,
            #"Rotina 020220": tarefa_020220
            #"Rotina 030237 Giro": tarefa_030237_Giro
        }

        logger.info("================ FASE 1: EXECUÇÃO NORMAL ================")
        for nome_rotina, func in mapa_tarefas.items():
            executar_tarefa_com_retry(nome_rotina, func)

        logger.info("================ FASE 2: REPESCAGEM DE FALHAS ===============")
        falhas_por_rotina = {}
        for registro in tracker.registros:
            if registro["Status"] != "SUCESSO" and registro["Rotina"] != "RESUMO FINAL":
                rotina_falhou = registro["Rotina"]
                unidade_falhou = registro["Unidade"]
                
                if rotina_falhou not in falhas_por_rotina:
                    falhas_por_rotina[rotina_falhou] = []
                    
                if unidade_falhou not in falhas_por_rotina[rotina_falhou] and unidade_falhou != "TODAS":
                    falhas_por_rotina[rotina_falhou].append(unidade_falhou)

        if falhas_por_rotina:
            logger.info(f"Falhas detectadas! Iniciando retentativas: {falhas_por_rotina}")
            for rotina, unidades_com_erro in falhas_por_rotina.items():
                if rotina in mapa_tarefas and len(unidades_com_erro) > 0:
                    logger.info(f">>> Retentando {rotina} apenas para as unidades: {unidades_com_erro}")
                    func_repescagem = lambda r=rotina, u=unidades_com_erro: mapa_tarefas[r](unidades_alvo=u)
                    executar_tarefa_com_retry(f"{rotina} (REPESCAGEM)", func_repescagem)
        else:
            logger.info("Nenhuma falha detectada! O robô rodou 100% perfeitamente na Fase 1.")

        logger.info("=== FLUXO TOTAL CONCLUÍDO ===")

    except Exception as e:
        logger.critical(f"ERRO FATAL NÃO RECUPERÁVEL: {e}", exc_info=True)
    
    finally:
        logger.info("Finalizando execução...")
        if driver:
            try: driver.quit()
            except: pass

        pasta_destino = os.path.join(os.getcwd(), "logs", "relatorios_baixados")
        os.makedirs(pasta_destino, exist_ok=True)
        pasta_download = os.getenv("DOWNLOAD_DIR", r"C:\Users\caixa.patos\Documents\Relatorios")
        
        try:
            caminho_csv = tracker.gerar_csv(pasta_destino)
            if caminho_csv:
                logger.info(f"==> RELATÓRIO CONSOLIDADO SALVO EM: {caminho_csv}")
        except Exception as e:
            logger.error(f"Erro ao gerar o CSV consolidado: {e}")

        try:
            pasta_data = os.path.join(os.getcwd(), "data")
            arquivos_excel = [f for f in glob.glob(os.path.join(pasta_data, "*.xlsx")) if not os.path.basename(f).startswith("~$")]
            
            if arquivos_excel:
                caminho_planilha_auxiliar = arquivos_excel[0]
                limpar_nomes_relatorios(pasta_download, caminho_planilha_auxiliar)
            else:
                logger.error("Planilha auxiliar Excel não encontrada na pasta 'data'. Higienização ignorada.")
        except Exception as e:
            logger.error(f"Falha ao executar a limpeza de nomes e organização de pastas: {e}")

        try:
            logger.info("Iniciando movimentação de arquivos/pastas finais...")
            pasta_origem_base = pasta_download

            meses_pt = {
                '01': 'Janeiro', '02': 'Fevereiro', '03': 'Março', '04': 'Abril',
                '05': 'Maio', '06': 'Junho', '07': 'Julho', '08': 'Agosto',
                '09': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro'
            }
            nome_mes_passado = meses_pt[mes_passado]
            
            mapeamento_movimentacao = {
                os.path.join(pasta_origem_base, "0513"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Inadimplência\05.13\{ano_mes_passado}\{mes_passado}. {nome_mes_passado}",
                os.path.join(pasta_origem_base, "120616"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Inadimplência\12.06.16\{ano_mes_passado}\{mes_passado}. {nome_mes_passado}",
                os.path.join(pasta_origem_base, "120601"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\Inadimplência\12.06.01\{ano_mes_passado}\{mes_passado}. {nome_mes_passado}",
                os.path.join(pasta_origem_base, "0512"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\05.12\{ano_atual}",
                os.path.join(pasta_origem_base, "150501", f"{ano_mes_passado}-{mes_passado} Sousa.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\1. SOUSA",
                os.path.join(pasta_origem_base, "150501", f"{ano_mes_passado}-{mes_passado} Itaporanga.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\2. ITAPORANGA",
                os.path.join(pasta_origem_base, "150501", f"{ano_mes_passado}-{mes_passado} Patos.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\3. PATOS",
                os.path.join(pasta_origem_base, "150501", f"{ano_mes_passado}-{mes_passado} Sumé.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\4. SUMÉ",
                os.path.join(pasta_origem_base, "150501", f"{ano_mes_passado}-{mes_passado} Guarabira.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\5. GUARABIRA",
                os.path.join(pasta_origem_base, "150501", f"{ano_mes_passado}-{mes_passado} Brumado.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\6. BRUMADO",
                os.path.join(pasta_origem_base, "150501", f"{ano_mes_passado}-{mes_passado} Barra.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\7. BARRA",
                os.path.join(pasta_origem_base, "150501", f"{ano_mes_passado}-{mes_passado} Caculé.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_mes_passado}\8. CACULÉ",
                os.path.join(pasta_origem_base, "030237"): r"\\dc01n\PUBLICO\REVENDA\Power BI\ADF",
                os.path.join(pasta_origem_base, "020220"): r"M:\ADMINISTRATIVO\FINANCEIRO\GERÊNCIA\Relatorios\02.02.20 - Recolhas"
            }

            for origem, destino in mapeamento_movimentacao.items():
                logger.info(f"Movendo: {origem} -> {destino}")
                mover_relatorios(origem, destino)

            logger.info("Movimentação concluída com sucesso.")
            
        except Exception as e:
            logger.error(f"Falha ao mover arquivos/pastas: {e}")

if __name__ == "__main__":
    main()