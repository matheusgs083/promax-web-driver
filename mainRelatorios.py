import os
import re
import time
import glob
import dotenv
from datetime import datetime, timedelta

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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

driver = None
menu_page = None

hoje = datetime.now()
ontem = hoje - timedelta(days=1)

ano_atual = hoje.strftime("%Y")
mes_atual = hoje.strftime("%m")
mes_ano_atual = hoje.strftime("%m/%Y")
data_hoje_arquivo = hoje.strftime("%d-%m-%Y")
data_ontem_formatada = ontem.strftime("%d/%m/%Y")
primeiro_dia_mes_atual = hoje.replace(day=1).strftime("%d/%m/%Y")

ultimo_dia_mes_passado_dt = hoje.replace(day=1) - timedelta(days=1)
primeiro_dia_mes_passado = ultimo_dia_mes_passado_dt.replace(day=1).strftime("%d/%m/%Y")
ultimo_dia_mes_passado = ultimo_dia_mes_passado_dt.strftime("%d/%m/%Y")
ano_mes_passado = ultimo_dia_mes_passado_dt.strftime("%Y")
mes_passado = ultimo_dia_mes_passado_dt.strftime("%m")
mes_ano_passado = ultimo_dia_mes_passado_dt.strftime("%m/%Y")

ultimo_dia_mes_retrasado_dt = ultimo_dia_mes_passado_dt.replace(day=1) - timedelta(days=1)
primeiro_dia_mes_retrasado = ultimo_dia_mes_retrasado_dt.replace(day=1).strftime("%d/%m/%Y")


def obter_codigo_rotina(nome_rotina):
    """
    Extrai o código numérico da rotina a partir de textos como:
    'Rotina 0513', '0513', 'Rotina 120616 (REPESCAGEM)' etc.
    """
    if not nome_rotina:
        return None

    match = re.search(r"\b(\d{4,6})\b", str(nome_rotina))
    return match.group(1) if match else None


def iniciar_sessao():
    global driver, menu_page

    if driver:
        try:
            driver.quit()
        except Exception:
            pass
        finally:
            driver = None
            menu_page = None

    logger.info(">>> Iniciando nova sessão (Browser + Login)...")
    driver = DriverFactory.get_driver()
    driver.maximize_window()

    usuario = os.getenv("PROMAX_USER")
    senha = os.getenv("PROMAX_PASS")

    if not usuario or not senha:
        raise ValueError("PROMAX_USER e/ou PROMAX_PASS não definidos no .env")

    login_page = LoginPage(driver)
    menu_page = login_page.fazer_login(usuario, senha, nome_unidade="SOUSA")
    logger.info("Sessão iniciada com sucesso.")
    return driver, menu_page


def executar_tarefa_com_retry(nome_tarefa, funcao_logica, tentativas=3, espera_segundos=3):
    global driver, menu_page

    erros_de_sessao = [
        "sessão inválida",
        "unable to get browser",
        "no such window",
        "timed out",
        "timeout",
        "is not a valid json object",
        "max retries exceeded",
        "10061",
        "10054",
        "connection refused",
        "invalid session id",
        "target window already closed",
        "disconnected",
        "chrome not reachable",
    ]

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
            msg_erro_lower = msg_erro.lower()

            logger.exception(f"Falha na {nome_tarefa}: {msg_erro}")

            eh_erro_critico = any(txt in msg_erro_lower for txt in erros_de_sessao)

            if tentativa < tentativas:
                if eh_erro_critico:
                    logger.warning("Detecção de queda de sessão. Iniciando protocolo de re-login...")
                    try:
                        iniciar_sessao()
                    except Exception as e_login:
                        logger.critical(f"Não foi possível fazer o re-login: {e_login}", exc_info=True)
                        raise
                else:
                    logger.warning(
                        f"Erro não crítico na {nome_tarefa}. Aguardando {espera_segundos}s para nova tentativa..."
                    )
                    time.sleep(espera_segundos)

                continue

            logger.error(f"Erro irrecuperável na {nome_tarefa} após {tentativas} tentativas.")
            raise


def main():
    logger.info("=== INICIANDO ROBÔ PROMAX (COM AUTO-RECOVERY) ===")
    
    # FLAG DE SEGURANÇA: Impede que arquivos velhos sejam movidos se o robô quebrar no meio
    sucesso_execucao = False 

    try:
        iniciar_sessao()

        def tarefa_0513(unidades_alvo=None):
            janela = menu_page.acessar_rotina("0513")
            page = Relatorio0513Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                unidade=unidades_alvo,
                opcao_rel="12",
                volume_fin="F",
                tp_equipe="A",
                mes_ano_inicial=mes_ano_atual,
                mes_ano_final=mes_ano_atual,
                quantos_clientes="99999",
                nome_arquivo=f"{data_hoje_arquivo} (nUnidade) nomeUnidade0513",
            )
            page.fechar_e_voltar()

        def tarefa_120616(unidades_alvo=None):
            janela = menu_page.acessar_rotina("120616")
            page = Relatorio120616Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                unidade=unidades_alvo,
                opcao_rel="3",
                mes_ano=mes_ano_atual,
                nome_arquivo=f"{data_hoje_arquivo} (nUnidade) 120616_nomeUnidade120616",
            )
            page.fechar_e_voltar()

        def tarefa_120601(unidades_alvo=None):
            janela = menu_page.acessar_rotina("120601")
            page = Relatorio120601Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                unidade=unidades_alvo,
                opcao_rel="01",
                id_notas_tit_nao_atu=False,
                ini_vencimento=primeiro_dia_mes_passado,
                fim_vencimento=data_ontem_formatada,
                ini_especie=4,
                fim_especie=4,
                nome_arquivo=f"{data_hoje_arquivo} 120601_nomeUnidade120601",
            )
            page.fechar_e_voltar()

        def tarefa_0512(unidades_alvo=None):
            janela = menu_page.acessar_rotina("0512")
            page = Relatorio0512Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                unidade=unidades_alvo,
                opcao_rel="11",
                ano=ano_atual,
                id_converte_hecto=True,
                nome_arquivo=f"05,12 {ano_atual} nomeUnidade0512",
            )
            page.fechar_e_voltar()

        def tarefa_150501(unidades_alvo=None):
            janela = menu_page.acessar_rotina("150501")
            page = Relatorio150501Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                unidade=unidades_alvo,
                visao="02",
                periodo="M",
                mes_ano=mes_ano_atual,
                totaliza_periodo=True,
                nome_arquivo=f"{ano_atual}-{mes_atual} nomeUnidade150501",
            )
            page.fechar_e_voltar()

        def tarefa_030237(unidades_alvo=None):
            janela = menu_page.acessar_rotina("030237")
            page = Relatorio030237Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                unidade=unidades_alvo,
                quebra1="14",
                quebra2="12",
                quebra3="16",
                data_inicial=primeiro_dia_mes_atual,
                data_final=data_ontem_formatada,
                nome_arquivo=f"{mes_atual}-{ano_atual} nomeUnidade030237",
            )
            page.fechar_e_voltar()

        def tarefa_030237_Giro(unidades_alvo=None):
            janela = menu_page.acessar_rotina("030237")
            page = Relatorio030237Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                unidade=unidades_alvo,
                quebra1="14",
                quebra2="12",
                quebra3="16",
                data_inicial=primeiro_dia_mes_passado,
                data_final=ultimo_dia_mes_passado,
                nome_arquivo=f"{mes_passado}-{ano_mes_passado}_nUnidade",
            )
            page.fechar_e_voltar()

        def tarefa_020220_Auditool(unidades_alvo=None):
            janela = menu_page.acessar_rotina("020220")
            page = Relatorio020220Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                unidade=unidades_alvo,
                opcao_rel="01",
                mercadoria_todos=False,
                mercadoria_garrafeira=True,
                mercadoria_vasilhame=True,
                mercadoria_sopi_visa=True,
                selecao_comodatos="P",
                nome_arquivo="020220 Auditool - nomeUnidade020220",
            )
            page.fechar_e_voltar()

        def tarefa_020220_Giro(unidades_alvo=None):
            janela = menu_page.acessar_rotina("020220")
            page = Relatorio020220Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                unidade=unidades_alvo or ["3610007"],
                opcao_rel="01",
                mercadoria_todos=False,
                mercadoria_garrafeira=True,
                mercadoria_sopi_visa=True,
                selecao_comodatos="T",
                nome_arquivo="020220_nUnidade",
            )
            page.fechar_e_voltar()

        def tarefa_020220_Recolhas(unidades_alvo=None):
            janela = menu_page.acessar_rotina("020220")
            page = Relatorio020220Page(janela.driver, janela.handle_menu)
            page.gerar_relatorio(
                unidade=unidades_alvo,
                opcao_rel="01",
                mercadoria_todos=False,
                mercadoria_garrafeira=True,
                mercadoria_vasilhame=True,
                selecao_comodatos="T",
                nome_arquivo="020220 Recolhas - nomeUnidade020220",
            )
            page.fechar_e_voltar()

        mapa_tarefas = {
                    #"0513": {"nome": "Rotina 0513", "func": tarefa_0513},
                    #"120616": {"nome": "Rotina 120616", "func": tarefa_120616},
                    #"120601": {"nome": "Rotina 120601", "func": tarefa_120601},
                    "0512": {"nome": "Rotina 0512", "func": tarefa_0512},
                    "150501": {"nome": "Rotina 150501", "func": tarefa_150501},
                    "030237": {"nome": "Rotina 030237", "func": tarefa_030237},
                    #"020220": {"nome": "Rotina 020220 Auditool", "func": tarefa_020220_Auditool},
                    #"020220_RECOLHAS": {"nome": "Rotina 020220 Recolhas", "func": tarefa_020220_Recolhas},
                    #"030237_GIRO": {"nome": "Rotina 030237 Giro", "func": tarefa_030237_Giro},
                    #"020220_GIRO": {"nome": "Rotina 020220 Giro", "func": tarefa_020220_Giro},
                }
        logger.info("================ FASE 1: EXECUÇÃO NORMAL ================")
        for codigo_rotina, dados in mapa_tarefas.items():
            executar_tarefa_com_retry(dados["nome"], dados["func"])

        logger.info("================ FASE 2: REPESCAGEM DE FALHAS ===============")
        falhas_por_rotina = {}

        for registro in tracker.registros:
            status = str(registro.get("Status", "")).strip().upper()
            rotina_registrada = registro.get("Rotina", "")
            unidade_falhou = str(registro.get("Unidade", "TODAS")).strip()

            if status == "SUCESSO" or rotina_registrada == "RESUMO FINAL":
                continue

            codigo_rotina = obter_codigo_rotina(rotina_registrada)
            if not codigo_rotina:
                continue

            if codigo_rotina not in falhas_por_rotina:
                falhas_por_rotina[codigo_rotina] = []

            if unidade_falhou == "TODAS":
                falhas_por_rotina[codigo_rotina] = ["TODAS"]
                continue

            if "TODAS" in falhas_por_rotina[codigo_rotina]:
                continue

            if unidade_falhou not in falhas_por_rotina[codigo_rotina]:
                falhas_por_rotina[codigo_rotina].append(unidade_falhou)

        if falhas_por_rotina:
            logger.info(f"Falhas detectadas! Iniciando retentativas: {falhas_por_rotina}")

            for codigo_rotina, unidades_com_erro in falhas_por_rotina.items():
                if codigo_rotina not in mapa_tarefas:
                    continue

                nome_rotina = mapa_tarefas[codigo_rotina]["nome"]
                func_original = mapa_tarefas[codigo_rotina]["func"]

                if unidades_com_erro == ["TODAS"] or len(unidades_com_erro) == 0:
                    logger.info(f">>> Retentando {nome_rotina} para TODAS as unidades")
                    executar_tarefa_com_retry(f"{nome_rotina} (REPESCAGEM)", func_original)
                else:
                    logger.info(f">>> Retentando {nome_rotina} apenas para as unidades: {unidades_com_erro}")

                    def func_repescagem(f=func_original, u=unidades_com_erro):
                        return f(unidades_alvo=u)

                    executar_tarefa_com_retry(f"{nome_rotina} (REPESCAGEM)", func_repescagem)
        else:
            logger.info("Nenhuma falha detectada! O robô rodou 100% perfeitamente na Fase 1.")

        logger.info("=== FLUXO TOTAL CONCLUÍDO ===")
        sucesso_execucao = True  # O código chegou até aqui sem explodir, então foi um sucesso!

    except Exception as e:
        logger.critical(f"ERRO FATAL NÃO RECUPERÁVEL: {e}", exc_info=True)

    finally:
        logger.info("Finalizando execução...")

        if driver:
            try:
                driver.quit()
            except Exception:
                pass

        pasta_destino = os.path.join(BASE_DIR, "logs", "relatorios_baixados")
        os.makedirs(pasta_destino, exist_ok=True)
        pasta_download = os.getenv("DOWNLOAD_DIR", r"C:\Users\caixa.patos\Documents\Relatorios")

        # Gerar o log do tracker sempre acontece, mesmo com erro
        try:
            caminho_csv = tracker.gerar_csv(pasta_destino)
            if caminho_csv:
                logger.info(f"==> RELATÓRIO CONSOLIDADO SALVO EM: {caminho_csv}")
        except Exception as e:
            logger.error(f"Erro ao gerar o CSV consolidado: {e}", exc_info=True)

        # BLOQUEIO DE SEGURANÇA: Só mexe nos relatórios se não houve erro crítico
        if not sucesso_execucao:
            logger.warning("Execução abortada precocemente. A limpeza e movimentação de arquivos foram CANCELADAS para proteger seus relatórios.")
        else:
            try:
                pasta_data = os.path.join(BASE_DIR, "data")
                caminho_planilha_auxiliar = os.path.join(pasta_data, "dRevendas.xlsx")

                if os.path.isfile(caminho_planilha_auxiliar):
                    limpar_nomes_relatorios(pasta_download, caminho_planilha_auxiliar)
                else:
                    logger.error(f"Planilha auxiliar não encontrada: {caminho_planilha_auxiliar}. Higienização ignorada.")
            except Exception as e:
                logger.error(f"Falha ao executar a limpeza de nomes e organização de pastas: {e}", exc_info=True)

            try:
                logger.info("Iniciando movimentação de arquivos/pastas finais...")
                pasta_origem_base = pasta_download

                mapeamento_movimentacao = {
                    os.path.join(pasta_origem_base, "0513"): r"\\dc01n\PUBLICO\REVENDA\Power BI\Inadimplência\05.13",
                    os.path.join(pasta_origem_base, "120616"): r"\\dc01n\PUBLICO\REVENDA\Power BI\Inadimplência\12.06.16",
                    os.path.join(pasta_origem_base, "120601"): r"\\dc01n\PUBLICO\REVENDA\Power BI\Inadimplência\12.06.01",
                    os.path.join(pasta_origem_base, "0512"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\05.12\{ano_atual}",
                    os.path.join(pasta_origem_base, "150501", f"{ano_atual}-{mes_atual} Sousa.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\1. SOUSA",
                    os.path.join(pasta_origem_base, "150501", f"{ano_atual}-{mes_atual} Itaporanga.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\2. ITAPORANGA",
                    os.path.join(pasta_origem_base, "150501", f"{ano_atual}-{mes_atual} Patos.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\3. PATOS",
                    os.path.join(pasta_origem_base, "150501", f"{ano_atual}-{mes_atual} Sumé.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\4. SUMÉ",
                    os.path.join(pasta_origem_base, "150501", f"{ano_atual}-{mes_atual} Guarabira.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\5. GUARABIRA",
                    os.path.join(pasta_origem_base, "150501", f"{ano_atual}-{mes_atual} Brumado.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\6. BRUMADO",
                    os.path.join(pasta_origem_base, "150501", f"{ano_atual}-{mes_atual} Barra.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\7. BARRA",
                    os.path.join(pasta_origem_base, "150501", f"{ano_atual}-{mes_atual} Caculé.csv"): fr"\\dc01n\PUBLICO\REVENDA\Power BI\OBZ\Fato\15.05.01\{ano_atual}\8. CACULÉ",
                    os.path.join(pasta_origem_base, "030237"): r"\\dc01n\PUBLICO\REVENDA\Power BI\ADF",
                    os.path.join(pasta_origem_base, "020220 Auditool"): r"M:\ADMINISTRATIVO\FINANCEIRO\GERÊNCIA\Relatorios\02.02.20 - auditool",
                    os.path.join(pasta_origem_base, "020220 Recolhas"): r"M:\ADMINISTRATIVO\FINANCEIRO\GERÊNCIA\Relatorios\02.02.20 - recolhas",
                }

                for origem, destino in mapeamento_movimentacao.items():
                    logger.info(f"Movendo: {origem} -> {destino}")
                    mover_relatorios(origem, destino)

                logger.info("Movimentação concluída com sucesso.")

            except Exception as e:
                logger.error(f"Falha ao mover arquivos/pastas: {e}", exc_info=True)

if __name__ == "__main__":
    main()