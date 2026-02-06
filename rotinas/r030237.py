import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from core.logger import get_logger
logger = get_logger(__name__)

import sys
import os
# garante import do projeto quando rodar via scripts/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.download import salvar_arquivo_visual
from core.validador_visual import validar_elemento


def gerar_030237(
    driver,
    *,
    # Datas (obrigatório)
    data_inicial: str,
    data_final: str,

    # Tipo de nota (entrada/saida): "NE" ou "NS" | se None, não mexe
    tipo_nota: str | None = None,

    # Itens: "S" | "N" | "C" | se None, não mexe
    itens: str | None = None,

    # Quebras (select): "00".."40" | se None, não mexe
    quebra1: str | None = None,
    quebra2: str | None = None,
    quebra3: str | None = None,

    # Faixas (inic/fim) | se None, não mexe (se "" vazio, limpa)
    quebra1_inicial: str | None = None,
    quebra1_final: str | None = None,
    quebra2_inicial: str | None = None,
    quebra2_final: str | None = None,
    quebra3_inicial: str | None = None,
    quebra3_final: str | None = None,

    # Botão final: "BotOk" ou "BotVisualizar"
    acao: str = "BotOk",

    timeout: int = 15,

    # >>> NOVO: após Visualizar, aguarda CSV e clica nele
    clicar_csv_apos_visualizar: bool = True,
    timeout_csv: int = 120,

    nome_arquivo: str = "030237.csv"
):
    """
    Só altera campos quando o parâmetro é passado (≠ None).
    - Se você passar "" (string vazia) ele LIMPA o campo.
    - Se você deixar None, ele NÃO mexe.
    Ordem: Quebras -> Faixas -> Datas -> Itens -> Tipo Nota -> Click
    """

    acao = (acao or "BotOk").strip()
    if acao not in ("BotOk", "BotVisualizar"):
        raise ValueError("acao deve ser 'BotOk' ou 'BotVisualizar'")

    if tipo_nota is not None:
        tipo_nota = tipo_nota.strip().upper()
        if tipo_nota not in ("NE", "NS"):
            raise ValueError("tipo_nota deve ser 'NE' ou 'NS'")

    if itens is not None:
        itens = itens.strip().upper()
        if itens not in ("S", "N", "C"):
            raise ValueError("itens deve ser 'S', 'N' ou 'C'")

    wait = WebDriverWait(driver, timeout)

    # --------- helpers JS IE-safe ----------
    js_set_value_ie = """
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
        if (el.click) { el.click(); }
        else if (el.fireEvent) { el.fireEvent('onclick'); }
        return { ok: true };
    } catch (e) {
        return { ok: false, error: (e && e.message) ? e.message : String(e) };
    }
    """

    js_radio_by_name_value = """
    var name = arguments[0];
    var val  = arguments[1];
    try {
        var els = document.getElementsByName(name);
        if (!els || !els.length) return { ok:false, error:"no-elements" };

        for (var i=0; i<els.length; i++) {
            var el = els[i];
            if ((el.value || "") == val) {
                try { el.scrollIntoView(true); } catch(e) {}
                try { el.focus(); } catch(e) {}
                el.checked = true;

                if (el.click) { el.click(); }
                else if (el.fireEvent) { el.fireEvent('onclick'); }

                if (document.createEvent) {
                    var ev = document.createEvent('HTMLEvents'); ev.initEvent('change', true, true); el.dispatchEvent(ev);
                } else if (el.fireEvent) {
                    try { el.fireEvent('onchange'); } catch(e) {}
                }

                return { ok:true, chosen: val };
            }
        }
        return { ok:false, error:"value-not-found", wanted: val };
    } catch(e) {
        return { ok:false, error:(e && e.message) ? e.message : String(e) };
    }
    """

    js_select_by_name_value = """
    var name = arguments[0];
    var val  = arguments[1];
    try {
        var els = document.getElementsByName(name);
        if (!els || !els.length) return { ok:false, error:"no-select" };

        var el = els[0];
        try { el.scrollIntoView(true); } catch(e) {}
        try { el.focus(); } catch(e) {}

        el.value = val;

        if (document.createEvent) {
            var ev = document.createEvent('HTMLEvents'); ev.initEvent('change', true, true); el.dispatchEvent(ev);
        } else if (el.fireEvent) {
            try { el.fireEvent('onchange'); } catch(e) {}
        }

        return { ok:true, value: el.value };
    } catch(e) {
        return { ok:false, error:(e && e.message) ? e.message : String(e) };
    }
    """

    # --------- entrar no frame da rotina ----------
    driver.switch_to.default_content()
    wait.until(EC.frame_to_be_available_and_switch_to_it(1))
    logger.info("Entrou no Frame[1] (rotina).")

    # 1) QUEBRAS
    if quebra1 is not None:
        s1 = driver.execute_script(js_select_by_name_value, "quebra1", quebra1)
        if not s1.get("ok"):
            raise RuntimeError(f"Falha select quebra1={quebra1}: {s1}")
        logger.info("Quebra1 setada: %s", quebra1)

    if quebra2 is not None:
        s2 = driver.execute_script(js_select_by_name_value, "quebra2", quebra2)
        if not s2.get("ok"):
            raise RuntimeError(f"Falha select quebra2={quebra2}: {s2}")
        logger.info("Quebra2 setada: %s", quebra2)

    if quebra3 is not None:
        s3 = driver.execute_script(js_select_by_name_value, "quebra3", quebra3)
        if not s3.get("ok"):
            raise RuntimeError(f"Falha select quebra3={quebra3}: {s3}")
        logger.info("Quebra3 setada: %s", quebra3)

    # 2) FAIXAS
    campos_faixa = [
        ("quebra1Inicial", quebra1_inicial),
        ("quebra1Final",   quebra1_final),
        ("quebra2Inicial", quebra2_inicial),
        ("quebra2Final",   quebra2_final),
        ("quebra3Inicial", quebra3_inicial),
        ("quebra3Final",   quebra3_final),
    ]
    for name, val in campos_faixa:
        if val is None:
            continue
        el = wait.until(EC.presence_of_element_located((By.NAME, name)))
        r = driver.execute_script(js_set_value_ie, el, val)  # "" limpa
        if not r.get("ok"):
            raise RuntimeError(f"Falha set {name}: {r}")
        logger.info("%s setado.", name)

    # 3) DATAS
    el_data_ini = wait.until(EC.presence_of_element_located((By.NAME, "dataInicial")))
    el_data_fim = wait.until(EC.presence_of_element_located((By.NAME, "dataFinal")))

    r1 = driver.execute_script(js_set_value_ie, el_data_ini, data_inicial)
    if not r1.get("ok"):
        raise RuntimeError(f"Falha set dataInicial: {r1}")

    r2 = driver.execute_script(js_set_value_ie, el_data_fim, data_final)
    if not r2.get("ok"):
        raise RuntimeError(f"Falha set dataFinal: {r2}")

    logger.info("Datas setadas: %s -> %s", data_inicial, data_final)

    # 4) ITENS
    if itens is not None:
        r_itens = driver.execute_script(js_radio_by_name_value, "itens", itens)
        if not r_itens.get("ok"):
            raise RuntimeError(f"Falha set radio 'itens'={itens}: {r_itens}")
        logger.info("Radio 'itens' setado: %s", itens)

    # 5) TIPO NOTA
    if tipo_nota is not None:
        r_notas = driver.execute_script(js_radio_by_name_value, "notas", tipo_nota)
        if not r_notas.get("ok"):
            raise RuntimeError(f"Falha set radio 'notas'={tipo_nota}: {r_notas}")
        logger.info("Radio 'notas' setado: %s", tipo_nota)

    # 6) CLICK AÇÃO (Visualizar/OK)
    botao = wait.until(EC.presence_of_element_located((By.NAME, acao)))
    rc = driver.execute_script(js_click_ie, botao)
    if not rc.get("ok"):
        raise RuntimeError(f"Falha click {acao}: {rc}")
    logger.info("Botão clicado via JS: %s", acao)

    # --- DEBUG / MAPEAMENTO (mantive como você colocou) ---
    time.sleep(2)

    driver.switch_to.default_content()

    # ============================================================
    # >>> APLIQUEI: após Visualizar, esperar CSV e clicar
    # (sem alert; só dispara o download)
    # Contexto continua: ROOT > Frame[1] (rotina)
    # ============================================================
    if acao == "BotVisualizar" and clicar_csv_apos_visualizar:
        logger.info("Aguardando tela pós-Visualizar e botão CSV (GerExecl/GeraExcel)...")

        # após visualizar costuma resetar frame -> volta pro default e entra no frame[1] de novo
        driver.switch_to.default_content()
        WebDriverWait(driver, timeout_csv).until(EC.frame_to_be_available_and_switch_to_it(1))

        def _achar_botao_csv(d):
            # nome reportado: GerExecl (label CSV)
            try:
                return d.find_element(By.NAME, "GerExecl")
            except Exception:
                pass
            # fallback do mapa antigo: GeraExcel
            try:
                return d.find_element(By.NAME, "GeraExcel")
            except Exception:
                return False

        try:
            botao_csv = WebDriverWait(driver, timeout_csv).until(_achar_botao_csv)
        except TimeoutException:
            raise RuntimeError(f"Botão CSV não apareceu em {timeout_csv}s (GerExecl/GeraExcel).")

        rc2 = driver.execute_script(js_click_ie, botao_csv)
        if not rc2.get("ok"):
            raise RuntimeError(f"Falha click CSV via JS: {rc2}")

        logger.info("Botão CSV clicado")

        validar_elemento("botaoDownload.png", timeout=360)
        salvar_arquivo_visual(diretorio_destino=os.getenv("DOWNLOAD_DIR", "C:\\Downloads"), nome_arquivo_final=nome_arquivo)

    driver.switch_to.default_content()
    return True

"""
00 → --Selecionar--
01 → Geral
02 → Comercial - NF
03 → Gte Vendas - NF
04 → Area - NF
05 → Setor - NF
06 → Vendedor
07 → Cliente
08 → Municipio
09 → Categoria
10 → Segmto Cerv
11 → Rede
12 → Tipo Movto
13 → CTO
14 → Operacao
15 → Forma Pagto
16 → Cond Pagto
17 → Transp.
18 → Nivel
19 → Mapa
20 → Comercial - Cli
21 → Gte Vendas - Cli
22 → Area - Cli
23 → Setor - Cli
24 → Grupo de Rede
25 → Motorista
26 → Cli Corporativo
27 → NR Roadashow
28 → Classe Road
29 → Codigo Fiscal
30 → Cli Chave SAP
31 → Conferencia SAP
32 → F A D
33 → Armazém
34 → Distrital - NF
35 → Distrital - Cli
36 → Ajudante 1
37 → Ajudante 2
38 → Codigo Contabil
39 → Veiculo
40 → VDE - Remuneração"""