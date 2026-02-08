import time
import dotenv

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from core.logger import get_logger
from core.download import salvar_arquivo_visual
# from core.validador_visual import validar_elemento  # se não usa, pode remover

logger = get_logger(__name__)


def gerar_0105070401(driver, nome_arquivo: str = "0105070401.csv") -> bool:
    logger.info("--- ETAPA 1: PREPARAR E GERAR RELATÓRIO (0105070401) ---")

    # --- 1. APLICAR FILTROS (JS SEGURO) ---
    logger.info("1. Selecionando filtros na tela (JS)...")

    js_cmd = r"""
    // Marca checkboxes idAS e idGeo
    var ids = ['idAS', 'idGeo'];
    for (var k = 0; k < ids.length; k++) {
        var el = document.getElementById(ids[k]);
        if (el) {
            el.click();
            if (el.type == 'checkbox') { el.checked = true; }
        }
    }

    // Clica no link 'Todos' (Regex para compatibilidade IE)
    var links = document.getElementsByTagName('A');
    for (var i = 0; i < links.length; i++) {
        var texto = links[i].innerText || "";
        if (texto.replace(/^\s+|\s+$/g, '') == 'Todos') {
            links[i].click();
            break;
        }
    }
    """

    try:
        driver.execute_script(js_cmd)
        time.sleep(2)  # pausa visual
        logger.info("   > Filtros aplicados.")
    except Exception:
        logger.exception("ERRO ao aplicar filtros via JS.")
        return False

    # --- 2. CLICAR NO BOTÃO GERAR ---
    logger.info("2. Clicando no botão 'Gerar CSV'...")

    clicou = False
    try:
        driver.execute_script("document.getElementById('btnGerarCSV').click();")
        clicou = True
        logger.info("   > Clique via JS no btnGerarCSV OK.")
    except Exception as e:
        logger.warning("   > Clique via JS falhou (%s). Tentando clique Selenium...", e)

    if not clicou:
        try:
            driver.find_element(By.ID, "btnGerarCSV").click()
            logger.info("   > Clique Selenium no btnGerarCSV OK.")
        except Exception:
            logger.exception("ERRO: Não foi possível clicar no botão 'Gerar CSV'.")
            return False

    # --- 3. AGUARDAR POPUP (ATÉ 7 MINUTOS) ---
    tempo_maximo_segundos = 420
    logger.info("3. Aguardando processamento do servidor... (timeout=%ss)", tempo_maximo_segundos)

    try:
        WebDriverWait(driver, tempo_maximo_segundos).until(EC.alert_is_present())

        # --- 4. CLICAR NO OK ---
        alerta = driver.switch_to.alert
        texto_alerta = alerta.text
        logger.info("   > Popup detectado: '%s'", texto_alerta)

        alerta.accept()
        logger.info("   > OK clicado. Iniciando etapa de salvar arquivo...")

        time.sleep(1)

        download_dir = dotenv.get_key(dotenv.find_dotenv(), "DOWNLOAD_DIR")
        if not download_dir:
            logger.error("DOWNLOAD_DIR não encontrado no .env. Não dá pra salvar o arquivo.")
            return False

        salvar_arquivo_visual(download_dir, nome_arquivo)
        logger.info("   > Arquivo salvo com sucesso: %s", nome_arquivo)
        return True

    except TimeoutException:
        logger.error("ERRO: Timeout de %ss esgotou. Popup não apareceu.", tempo_maximo_segundos)
        return False

    except Exception:
        logger.exception("ERRO inesperado durante espera/aceite do alerta e salvamento.")
        return False
