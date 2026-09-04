from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import time
from typing import Any

from bs4 import BeautifulSoup
import pandas as pd
import requests

from core.observability.logger import get_logger

logger = get_logger("LOG_CONDICAO_SERVICE")

# Regex para identificar datas no formato DD/MM/AAAA (ex: 03/09/2026)
DATE_REGEX = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def parsear_html_logs(html_text: str, nb_formatado: str) -> list[dict[str, str]]:
    """Extrai todas as linhas de log válidas do HTML da página PW01060P."""
    logs: list[dict[str, str]] = []
    soup = BeautifulSoup(html_text, "html.parser")

    todas_linhas = soup.find_all("tr")
    for tr in todas_linhas:
        cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(cols) >= 8 and DATE_REGEX.match(cols[0]):
            logs.append({
                "NB": nb_formatado,
                "Data": cols[0],
                "Hora": cols[1],
                "Usuario": cols[2],
                "Equipe": cols[3],
                "Condicao_Anterior": cols[4],
                "Condicao_Atualizada": cols[5],
                "Limite_Anterior": cols[6],
                "Limite_Atual": cols[7],
            })
    return logs


def extrair_subsession_id(driver) -> tuple[str, str]:
    """Captura a SessionID e a SubSessionID ativas da tela do Promax."""
    driver.switch_to.default_content()
    try:
        driver.switch_to.frame(1)
    except Exception:
        try:
            driver.switch_to.frame(0)
        except Exception:
            pass

    js_get_ids = """
        var form = document.form1 || document.forms[0];
        var s = form && form.SessionID ? form.SessionID.value : '';
        var sub = form && form.SubSessionID ? form.SubSessionID.value : '';
        return { session_id: s, sub_session_id: sub };
    """
    try:
        res = driver.execute_script(js_get_ids)
        if res and res.get("session_id"):
            return res["session_id"], res.get("sub_session_id", "")
    except Exception:
        pass

    # Fallback: extrai da URL
    url = driver.current_url
    s_id, sub_id = "", ""
    if "SessionID=" in url:
        s_id = url.split("SessionID=")[1].split("&")[0]
    if "SubSessionID=" in url:
        sub_id = url.split("SubSessionID=")[1].split("&")[0]

    return s_id, sub_id


def extrair_log_nb_http(
    http_session: requests.Session,
    base_url: str,
    session_id: str,
    sub_session_id: str,
    nb: str | int,
    mes_ano: str,
    timeout: int = 15,
) -> list[dict[str, str]]:
    """Realiza a requisição HTTP POST direta no CGI para um NB específico."""
    nb_formatado = str(nb).strip().zfill(7)
    mes_ano_formatado = str(mes_ano).strip()

    url_full = f"{base_url}?SessionID={session_id}&ppopcao=6"

    payload = {
        "SessionID": session_id,
        "SubSessionID": sub_session_id,
        "ppopcao": "6",
        "call": "PW01060P",
        "opcao": "1",
        "cE1": nb_formatado,
        "mesAno": mes_ano_formatado,
    }

    try:
        resp = http_session.post(url_full, data=payload, timeout=timeout)
        resp.raise_for_status()
        return parsear_html_logs(resp.text, nb_formatado)
    except Exception as exc:
        logger.debug(f"Erro na requisição HTTP para o NB {nb_formatado}: {exc}")
        return []


def extrair_logs_lote_nbs(
    driver,
    lista_nbs: list[str | int],
    mes_ano: str,
    max_workers: int = 15,
) -> pd.DataFrame:
    """
    Extrai em lote a lista de NBs utilizando requisições HTTP paralelas (Multithread)
    com base nas credenciais e SubSessionID capturadas da sessão do navegador.
    """
    todos_logs: list[dict[str, str]] = []
    total_nbs = len(lista_nbs)
    if total_nbs == 0:
        return pd.DataFrame()

    session_id, sub_session_id = extrair_subsession_id(driver)
    logger.info(f"Sessão identificada | SessionID: {session_id} | SubSessionID: {sub_session_id}")

    # Monta a URL base do servidor
    current_url = driver.current_url
    if "/cgi-bin/" in current_url:
        base_url = current_url.split("/cgi-bin/")[0] + "/cgi-bin/PP00100.exe"
    else:
        base_url = "http://paubrasil.promaxcloud.com.br/pw/cgi-bin/PP00100.exe"

    # Prepara a sessão do Requests compartilhando os cookies do Selenium
    http_session = requests.Session()
    http_session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    try:
        for c in driver.get_cookies():
            http_session.cookies.set(c["name"], c["value"], domain=c.get("domain", ""))
    except Exception as e:
        logger.debug(f"Aviso ao copiar cookies: {e}")

    logger.info(f"Iniciando extração paralela HTTP (Workers: {max_workers}) para {total_nbs} NBs...")

    concluidos = 0
    inicio_tempo = time.time()

    def _worker(nb_val):
        return extrair_log_nb_http(http_session, base_url, session_id, sub_session_id, nb_val, mes_ano)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_worker, nb): nb for nb in lista_nbs}
        for future in as_completed(futures):
            concluidos += 1
            try:
                res = future.result()
                if res:
                    todos_logs.extend(res)
            except Exception as exc:
                logger.debug(f"Erro worker: {exc}")

            if concluidos % 100 == 0 or concluidos == total_nbs:
                decorrido = time.time() - inicio_tempo
                rate = concluidos / decorrido if decorrido > 0 else 0
                logger.info(f"Progresso: {concluidos}/{total_nbs} NBs ({concluidos/total_nbs*100:.1f}%) | Velocidade: {rate:.1f} NBs/s | Registros: {len(todos_logs)}")

    if not todos_logs:
        logger.warning("Nenhum registro extraído para a lista fornecida.")
        return pd.DataFrame(columns=[
            "NB", "Data", "Hora", "Usuario", "Equipe",
            "Condicao_Anterior", "Condicao_Atualizada", "Limite_Anterior", "Limite_Atual"
        ])

    df = pd.DataFrame(todos_logs)
    logger.info(f"Extração em lote finalizada! Total: {len(df)} registros consolidados.")
    return df
