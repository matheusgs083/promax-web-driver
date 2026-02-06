import os
import sys
import time
import dotenv

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import core.selecionar_opcao as selecionar_opcao
import core.validador_visual as validador_visual
import core.limpar_alertas as limpar_alertas

# --- CONFIGURAÇÃO DE IMPORTS DO CORE ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.logger import get_logger
logger = get_logger(__name__)

dotenv.load_dotenv()

# --- PROMAX URL VIA .ENV ---
dotenv.load_dotenv()

_EXCLUIR = {
    "PROMAX_URL",
    "DRIVER_PATH",
    "DOWNLOAD_DIR",
    "PROMAX_USER",
    "PROMAX_PASS",
    "e"
}

UNIDADES = {}
for k, v in os.environ.items():
    if k in _EXCLUIR:
        continue
    if not v:
        continue

    k_norm = k.strip().upper()
    v_norm = v.strip()

    # regra: códigos de unidade são numéricos (ex: 0640001, 2210003 etc.)
    if v_norm.isdigit() and 6 <= len(v_norm) <= 10:
        UNIDADES[k_norm] = v_norm

logger.info(
    "UNIDADES carregadas do .env: %s",
    ", ".join([f"{k}={v}" for k, v in UNIDADES.items()]) if UNIDADES else "<vazio>"
)


def verificar_e_fechar_janela_extra(driver, janela_principal_id):
    try:
        todas_janelas = driver.window_handles

        if len(todas_janelas) > 1:
            logger.info("Detectada(s) %d janela(s). Verificando extras...", len(todas_janelas))

            for janela in todas_janelas:
                if janela != janela_principal_id:
                    driver.switch_to.window(janela)
                    logger.info("Fechando janela extra: %s", driver.title)
                    driver.close()

            driver.switch_to.window(janela_principal_id)
            logger.info("Foco retornado para a janela principal.")
            return True
    except Exception as e:
        logger.error("Erro ao tentar fechar janela extra: %s", e)
        try:
            driver.switch_to.window(janela_principal_id)
        except Exception:
            logger.error("Erro ao tentar retornar o foco para a janela principal.")

    return False


def fazer_login_promax(driver, usuario, senha, nome_unidade=None):
    try:
        nome_unidade = (nome_unidade or "").strip().upper()
        logger.info("Iniciando login no Promax | unidade=%s", nome_unidade or None)

        driver.get(os.getenv("PROMAX_URL"))
        wait = WebDriverWait(driver, 10)

        logger.info("Aguardando carregamento inicial...")

        if len(driver.window_handles) > 1:
            logger.warning("Detectadas múltiplas janelas (%s). Alternando para a última.", len(driver.window_handles))
            driver.switch_to.window(driver.window_handles[-1])

        # --- PARTE 1: LOGIN INICIAL (IFRAME 0 DIRETO) ---
        frame_index = None

        frames = driver.find_elements(By.TAG_NAME, "iframe") or driver.find_elements(By.TAG_NAME, "frame")
        if frames:
            frame_index = 0
            wait.until(EC.frame_to_be_available_and_switch_to_it(0))
            wait.until(EC.presence_of_element_located((By.NAME, "Usuario")))
            logger.info("Campo Usuario encontrado no frame index=%s", frame_index)
        else:
            logger.error("Nenhum frame/iframe encontrado e campo Usuario não apareceu.")
            return False

        # ====== JS IE-SAFE (SET + CLICK) ======
        js_set_ie = """
        var el = arguments[0];
        var val = arguments[1];
        try {
            try { el.scrollIntoView(true); } catch(e) {}
            try { el.focus(); } catch(e) {}

            el.value = val;

            if (document.createEvent) {
                var ev1 = document.createEvent('HTMLEvents'); ev1.initEvent('input', true, true);  el.dispatchEvent(ev1);
                var ev2 = document.createEvent('HTMLEvents'); ev2.initEvent('change', true, true); el.dispatchEvent(ev2);
                var ev3 = document.createEvent('HTMLEvents'); ev3.initEvent('blur', true, true);   el.dispatchEvent(ev3);
            } else if (el.fireEvent) {
                try { el.fireEvent('oninput'); } catch(e) {}
                try { el.fireEvent('onchange'); } catch(e) {}
                try { el.fireEvent('onblur'); } catch(e) {}
            }

            return { ok: true, value: el.value };
        } catch (e) {
            return { ok: false, error: (e && e.message) ? e.message : String(e) };
        }
        """

        js_click_ie = """
        var el = arguments[0];
        try {
            try { el.scrollIntoView(true); } catch(e) {}
            try { el.focus(); } catch(e) {}

            if (el.click) {
                el.click();
            } else if (el.fireEvent) {
                el.fireEvent('onclick');
            }
            return { ok: true };
        } catch (e) {
            return { ok: false, error: (e && e.message) ? e.message : String(e) };
        }
        """

        campo_usuario = wait.until(EC.presence_of_element_located((By.NAME, "Usuario")))
        campo_senha = wait.until(EC.presence_of_element_located((By.NAME, "Senha")))
        botao_confirma = wait.until(EC.presence_of_element_located((By.NAME, "cmdConfirma")))

        r1 = driver.execute_script(js_set_ie, campo_usuario, usuario)
        if not r1 or not r1.get("ok") or (r1.get("value", "") != usuario):
            raise RuntimeError(f"Falha set Usuario via JS: {r1}")

        r2 = driver.execute_script(js_set_ie, campo_senha, senha)
        if not r2 or not r2.get("ok"):
            raise RuntimeError(f"Falha set Senha via JS: {r2}")

        r3 = driver.execute_script(js_click_ie, botao_confirma)
        if not r3 or not r3.get("ok"):
            raise RuntimeError(f"Falha click cmdConfirma via JS: {r3}")

        logger.info("Primeira confirmação clicada via JS (login enviado).")

        # --- PARTE 2: SELEÇÃO DE UNIDADE ---
        codigo_unidade = UNIDADES.get(nome_unidade) if nome_unidade else None

        if codigo_unidade:
            logger.info("Selecionando unidade: %s (%s)", nome_unidade, codigo_unidade)

            driver.switch_to.default_content()
            if frame_index is not None:
                try:
                    WebDriverWait(driver, 10).until(EC.frame_to_be_available_and_switch_to_it(frame_index))
                    logger.info("Retornou ao frame para seleção de unidade (index=%s).", frame_index)
                except Exception:
                    logger.warning("Não foi possível voltar ao frame index=%s. Tentando seguir no default.", frame_index)

            try:
                select_unidade = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "unidade"))
                )
                selecionar_opcao.selecionar_opcao_via_js(driver, select_unidade, codigo_unidade)
                logger.info("Unidade selecionada via JS.")
            except Exception:
                logger.exception("Erro ao tentar selecionar unidade")
        else:
            if nome_unidade:
                logger.warning("Unidade '%s' não mapeada no .env. Pulando seleção.", nome_unidade)
            else:
                logger.info("Nenhuma unidade informada. Pulando seleção de unidade.")

        # --- PARTE 3: CONFIRMAÇÃO FINAL (CLICK VIA JS IE-SAFE) ---
        try:
            botao_final = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.NAME, "cmdConfirma"))
            )
            r4 = driver.execute_script(js_click_ie, botao_final)
            if not r4 or not r4.get("ok"):
                raise RuntimeError(f"Falha click cmdConfirma final via JS: {r4}")
            logger.info("Segunda confirmação clicada via JS.")
        except Exception:
            logger.info("Botão final não necessário (cmdConfirma não encontrado).")

        verificar_e_fechar_janela_extra(driver, driver.current_window_handle)

        limpar_alertas.limpar_alertas(driver, tentativas=5)

        verificar_e_fechar_janela_extra(driver, driver.current_window_handle)

        logger.info("Validando sucesso do login visualmente...")
        if validador_visual.validar_elemento("validacaoLogin.png", timeout=15):
            logger.info("LOGIN COM SUCESSO!")
            driver.switch_to.default_content()
            return True

        logger.error("Login NÃO validado (imagem validacaoLogin.png não encontrada).")
        return False

    except Exception:
        logger.exception("Erro Fatal Login")
        return False
