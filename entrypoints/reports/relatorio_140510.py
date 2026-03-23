import os
import time
import glob
import dotenv
from datetime import datetime, timedelta

from core.browser.driver_factory import DriverFactory
from core.observability.logger import get_logger
from core.config.project_paths import DATA_DIR, LOGS_DIR
from core.observability.relatorio_execucao import tracker
from pages.auth.login_page import LoginPage
from core.files.renomeador import limpar_nomes_relatorios
from core.files.movimentador import mover_relatorios

# >>> PAGE NOVA DA ROTINA F7188 / 14.05.10.00.00
from pages.reports.relatorio_140510_page import Relatorio140510Page

dotenv.load_dotenv()
logger = get_logger("MAIN_F7188")

driver = None
menu_page = None


# ==========================================================
# CONFIGURAÇÕES
# ==========================================================


# Período (um mês por vez, usando o último dia)
# Ex: de Jan/2025 até Dez/2025
PERIODO_INICIO = "2025-01-01"
PERIODO_FIM    = "2025-12-31"

# Rotina no menu (geralmente e o CALL "14.05.10.00.00")
CODIGO_ROTINA_MENU = "14051000000000"


# ==========================================================
# HELPERS DE DATA (último dia do mês)
# ==========================================================

def fim_do_mes(dt: datetime) -> datetime:
    prox_mes = (dt.replace(day=28) + timedelta(days=4)).replace(day=1)
    return prox_mes - timedelta(days=1)

def gerar_fins_de_mes(data_inicio: str, data_fim: str):
    """
    Retorna uma lista de datetime com o último dia de cada mês
    entre data_inicio e data_fim (inclusive).
    """
    ini = datetime.strptime(data_inicio, "%Y-%m-%d")
    fim = datetime.strptime(data_fim, "%Y-%m-%d")

    cursor = ini.replace(day=1)
    datas = []

    while cursor <= fim:
        ultimo = fim_do_mes(cursor)
        if ultimo < ini:
            cursor = (cursor + timedelta(days=32)).replace(day=1)
            continue
        if ultimo > fim:
            break
        datas.append(ultimo)
        cursor = (cursor + timedelta(days=32)).replace(day=1)

    return datas


# ==========================================================
# SESSÃO / RETRY (igual seu padrão)
# ==========================================================

def iniciar_sessao():
    global driver, menu_page

    if driver:
        try:
            driver.quit()
        except:
            pass

    logger.info(">>> Iniciando nova sessão (Browser + Login)...")
    driver = DriverFactory.get_driver()
    driver.maximize_window()

    login_page = LoginPage(driver)
    usuario = os.getenv("PROMAX_USER")
    senha = os.getenv("PROMAX_PASS")

    # ajuste o nome_unidade base do login conforme seu fluxo
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

        except Exception as e:
            msg_erro = str(e)
            logger.warning(f"Falha na {nome_tarefa}: {msg_erro}")

            erros_de_sessao = [
                "Sessão inválida", "Unable to get browser", "no such window",
                "Timed out", "timeout", "is not a valid JSON object",
                "Max retries exceeded", "10061", "10054", "Connection refused",
            ]
            eh_erro_critico = any(txt in msg_erro for txt in erros_de_sessao)

            if eh_erro_critico and tentativa < tentativas:
                logger.warning("Detecção de queda de sessão! Iniciando protocolo de Re-login...")
                iniciar_sessao()
            else:
                logger.error(f"Erro irrecuperável na {nome_tarefa}.")
                raise


# ==========================================================
# MAIN ESPECÍFICO F7188
# ==========================================================

def main():
    logger.info("=== INICIANDO ROBÔ PROMAX (F7188 / 14.05.10.00.00) ===")

    try:
        iniciar_sessao()

        fins_mes = gerar_fins_de_mes(PERIODO_INICIO, PERIODO_FIM)
        logger.info(f"Meses (último dia) a baixar: {[d.strftime('%d/%m/%Y') for d in fins_mes]}")

        def tarefa_f7188_por_data(dt_fim_mes: datetime):
            """
            Executa 1 mês por vez (data = último dia do mês),
            baixando para as 8 unidades em loop_unidades.
            """
            data_tela = dt_fim_mes.strftime("%d/%m/%Y")
            data_nome = dt_fim_mes.strftime("%d-%m-%Y")

            janela = menu_page.acessar_rotina(CODIGO_ROTINA_MENU)
            page = Relatorio140510Page(janela.driver, janela.handle_menu)

            # Nome no seu padrão (vai ser complementado pelo loop_unidades com _COD)
            nome_arquivo = f"{data_nome} 140501.csv"

            page.gerar_relatorio(
                unidade=None,   # <-- loop das 8 unidades
                data=data_tela,          # <-- último dia do mês
                pref_C=True,             # Contábil
                pref_V=False,            # Movimento (se quiser os dois, True/True)
                vencidos=True,
                a_vencer=True,
                opcao_rel="01",          # 00 ou "Numerica" dependendo do teu select
                cd_natureza="999",
                nome_arquivo=nome_arquivo,
                timeout_csv=420,
            )

            page.fechar_e_voltar()

        # RODA 1 MÊS POR VEZ (sempre último dia)
        for dt in fins_mes:
            nome_job = f"F7188 {dt.strftime('%m/%Y')} ({dt.strftime('%d/%m/%Y')})"
            executar_tarefa_com_retry(nome_job, lambda d=dt: tarefa_f7188_por_data(d))

        logger.info("=== FLUXO TOTAL CONCLUÍDO (F7188) ===")

    except Exception as e:
        logger.critical(f"ERRO FATAL NAO RECUPERAVEL: {e}", exc_info=True)

    finally:
        logger.info("Finalizando execução...")

        if driver:
            try:
                driver.quit()
            except:
                pass

        # --- TRACKER CSV ---
        pasta_destino = LOGS_DIR / "relatorios_baixados"
        pasta_destino.mkdir(parents=True, exist_ok=True)

        try:
            caminho_csv = tracker.gerar_csv(str(pasta_destino))
            if caminho_csv:
                logger.info(f"==> RELATÓRIO CONSOLIDADO SALVO EM: {caminho_csv}")
        except Exception as e:
            logger.error(f"Erro ao gerar o CSV consolidado: {e}")

        # --- HIGIENIZA NOMES ---
        try:
            pasta_download = os.getenv("DOWNLOAD_DIR", r"C:\Users\caixa.patos\Documents\Relatorios")
            arquivos_excel = [f for f in glob.glob(str(DATA_DIR / "*.xlsx"))
                              if not os.path.basename(f).startswith("~$")]

            if arquivos_excel:
                limpar_nomes_relatorios(pasta_download, arquivos_excel[0])
            else:
                logger.error("Planilha auxiliar Excel não encontrada na pasta 'data'. Higienização ignorada.")
        except Exception as e:
            logger.error(f"Falha ao executar a limpeza de nomes e organização de pastas: {e}")

        # --- MOVIMENTAÇÃO (opcional; ajuste destino) ---
        # Exemplo: jogar numa pasta por ano/mês
        try:
            pasta_download = os.getenv("DOWNLOAD_DIR", r"C:\Users\caixa.patos\Documents\Relatorios")
            pasta_origem = os.path.join(pasta_download, "F7188")  # se você separar por subpasta
            destino_base = r"M:\ADMINISTRATIVO\FINANCEIRO\GERÊNCIA\Relatorios\140510"
            mover_relatorios(pasta_origem, destino_base)
        except Exception as e:
            logger.error(f"Falha ao mover arquivos/pastas: {e}")


if __name__ == "__main__":
    main()

