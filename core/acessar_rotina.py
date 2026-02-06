import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from core.logger import get_logger
logger = get_logger(__name__)


def acessar_rotina_atalho(driver, codigo_rotina):
    time.sleep(1)
    logger.info("--- ACESSANDO ROTINA: %s ---", codigo_rotina)

    driver.switch_to.default_content()

    # SALVA O MENU (uma vez) antes de abrir rotina
    if not hasattr(driver, "_menu_handle") or driver._menu_handle not in driver.window_handles:
        driver._menu_handle = driver.current_window_handle
        logger.info("Menu handle salvo: %s", driver._menu_handle)

    handles_antes = list(driver.window_handles)

    try:
        WebDriverWait(driver, 10).until(EC.frame_to_be_available_and_switch_to_it("top"))
        driver.switch_to.frame(0)

        campo_atalho = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "atalho"))
        )

        logger.info("Digitando '%s' no atalho...", codigo_rotina)
        try:
            campo_atalho.clear()
        except Exception:
            pass
        campo_atalho.send_keys(codigo_rotina)
        time.sleep(0.5)

        logger.info("Disparando abertura de rotina via JS...")
        js = """
        var e = arguments[0];
        try {
            var event = document.createEventObject();
            event.keyCode = 13;
            e.fireEvent("onkeypress", event);
        } catch(err) {
            if(e.form) { e.form.submit(); }
        }
        """
        driver.execute_script(js, campo_atalho)

        logger.info("Aguardando nova janela abrir...")
        WebDriverWait(driver, 15).until(lambda d: len(d.window_handles) > len(handles_antes))

        handles_agora = list(driver.window_handles)
        novas = [h for h in handles_agora if h not in handles_antes]
        if not novas:
            raise RuntimeError("Nova janela não identificada (handles não mudaram).")

        rotina_handle = novas[0]
        driver.switch_to.window(rotina_handle)
        logger.info("Foco na rotina: %s | handle=%s", codigo_rotina, rotina_handle)

        try:
            driver.maximize_window()
        except Exception:
            logger.debug("Não foi possível maximizar a janela da rotina (ignorado).")

        # aguardar um pouco a rotina carregar para evitar erros de elementos não encontrados
        time.sleep(2)

    except Exception as e:
        logger.exception("ERRO AO ACESSAR ROTINA %s: %s", codigo_rotina, e)
        try:
            driver.save_screenshot("erro_atalho.png")
            logger.info("Screenshot salvo: erro_atalho.png")
        except Exception:
            logger.debug("Não foi possível salvar screenshot (ignorado).")
        raise


def voltar_pro_menu(driver, fechar_rotina=True):
    """
    Volta para o MENU salvo em driver._menu_handle.
    Se fechar_rotina=True, fecha a janela atual (rotina) antes de voltar.
    """
    if not hasattr(driver, "_menu_handle"):
        raise RuntimeError("Menu handle não encontrado (driver._menu_handle). Chame acessar_rotina_atalho primeiro.")

    menu_handle = driver._menu_handle
    atual = driver.current_window_handle

    if atual != menu_handle:
        if fechar_rotina:
            try:
                driver.close()
                logger.info("Rotina fechada (handle=%s).", atual)
            except Exception as e:
                logger.warning("AVISO: não consegui fechar a rotina (handle=%s): %s", atual, e)

        if menu_handle in driver.window_handles:
            driver.switch_to.window(menu_handle)
            logger.info("Voltou para o MENU (handle=%s).", menu_handle)
        else:
            handles = driver.window_handles
            if not handles:
                raise RuntimeError("Nenhuma janela disponível após fechar rotina.")
            driver.switch_to.window(handles[0])
            logger.warning("Menu handle não existe mais. Fallback para primeira janela: %s", handles[0])

    else:
        driver.switch_to.window(menu_handle)
        logger.info("Já estava no MENU (handle=%s).", menu_handle)

    driver.switch_to.default_content()
    logger.info("Contexto resetado para default_content (MENU).")
