import os
import time
import pandas as pd
import dotenv

from core.driver_factory import DriverFactory
from core.logger import get_logger
from pages.login_page import LoginPage
from pages.rotinas.processo_03030701_page import AlteracaoCondicaoPagtoPage

dotenv.load_dotenv()
logger = get_logger("LOTE_CONDICAO")

# --- CONFIGURAÇÕES ---
FILE_PATH = r'C:\Users\caixa.patos\Desktop\Utilidades2.0.xlsm'
FORMA_DE_PAGAMENTO = "10"
SERIE_PADRAO = "003"  

def calcular_tempo(restantes):
    segundos = restantes * 3.0 # Estimativa de 3s por nota via Injeção DOM
    return int(segundos // 60), int(segundos % 60)

def main():
    logger.info("=== INICIANDO ROBÔ LOTE CONDIÇÃO (INJEÇÃO DOM) ===")

    try:
        df = pd.read_excel(FILE_PATH, sheet_name="CEMC", engine='openpyxl', header=0, dtype=str)
        df_filtrado = df[df['COND'] != FORMA_DE_PAGAMENTO]
        total = len(df_filtrado)
        
        if total == 0:
            logger.info("Nenhuma nota pendente.")
            return
            
    except Exception as e:
        logger.error(f"Erro ao ler Excel: {e}")
        return

    driver = DriverFactory.get_driver()
    try:
        login_page = LoginPage(driver)
        menu_page = login_page.fazer_login(os.getenv("PROMAX_USER"), os.getenv("PROMAX_PASS"), nome_unidade="SOUSA")
        
        # Mude para o código numérico correto do menu se não for 02107
        janela = menu_page.acessar_rotina("03030701") 
        page = AlteracaoCondicaoPagtoPage(janela.driver, janela.handle_menu)

        sucessos = 0
        falhas = []
        contador = total

        for index, row in df_filtrado.iterrows():
            mapa = str(row['MAPA']).strip().replace('.0', '')
            nota = str(row['NOTA']).strip().replace('.0', '')
            
            logger.info(f"Processando [{total - contador + 1}/{total}]: Mapa {mapa} | Nota {nota}")
            
            # --- CHAMA A NOSSA FUNÇÃO ---
            if page.alterar_condicao(mapa, nota, FORMA_DE_PAGAMENTO, SERIE_PADRAO):
                sucessos += 1
            else:
                falhas.append(f"Mapa: {mapa} | Nota: {nota}")
                
            contador -= 1
            m, s = calcular_tempo(contador)
            logger.info(f"Faltam {contador}. Tempo estimado: {m}m {s}s")
            
            time.sleep(0.5)

        logger.info(f"=== LOTE CONCLUÍDO! Sucessos: {sucessos}/{total} ===")
        if falhas:
            logger.warning("Falharam:")
            for f in falhas: logger.warning(f"-> {f}")

        page.fechar_e_voltar()

    finally:
        time.sleep(2)
        driver.quit()

if __name__ == "__main__":
    main()