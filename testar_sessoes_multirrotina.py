from __future__ import annotations

import hashlib
import json
import os
import re
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from selenium.webdriver.common.by import By

from core.config.project_paths import LOGS_DIR
from core.config.settings import get_settings
from core.execution.entrypoint_helpers import encerrar_driver, iniciar_sessao_padrao
from core.observability.logger import get_logger


logger = get_logger("TESTE_SESSOES_MULTIRROTINA")
settings = get_settings()

ROTINA_A = os.getenv("PROMAX_TEST_ROUTINE_A", "020220").strip()
ROTINA_B = os.getenv("PROMAX_TEST_ROUTINE_B", "030237").strip()
UNIDADE_A = os.getenv("PROMAX_TEST_UNIT_A", "3610006").strip()
UNIDADE_B = os.getenv("PROMAX_TEST_UNIT_B", "3610007").strip()

def _fingerprint(valor: str | None) -> str | None:
    if not valor:
        return None
    return hashlib.sha256(valor.encode("utf-8", errors="ignore")).hexdigest()[:12]


def _sanitizar_url(url: str) -> dict:
    partes = urlsplit(str(url or ""))
    query = parse_qs(partes.query, keep_blank_values=True)
    return {
        "origem": f"{partes.scheme}://{partes.netloc}" if partes.netloc else "",
        "path": partes.path,
        "query_keys": sorted(query),
        "session": _fingerprint((query.get("SessionID") or [None])[0]),
        "subsession": _fingerprint((query.get("SubSessionID") or [None])[0]),
        "call": (query.get("call") or [None])[0],
        "frame": (query.get("frame") or [None])[0],
        "opcao": (query.get("opcao") or [None])[0],
    }


def _extrair_ids(textos: list[str]) -> tuple[list[str], list[str]]:
    sessions = set()
    subsessions = set()
    for texto in textos:
        for nome, valor in re.findall(
            r"(?<![A-Za-z])(SubSessionID|SessionID)=([^&\"'<> ]+)",
            str(texto or ""),
            flags=re.IGNORECASE,
        ):
            if nome.lower() == "sessionid":
                sessions.add(_fingerprint(valor))
            else:
                subsessions.add(_fingerprint(valor))
    return sorted(filter(None, sessions)), sorted(filter(None, subsessions))


def _snapshot_janela(driver, handle: str, rotina: str, etapa: str) -> dict:
    snapshot = {
        "etapa": etapa,
        "rotina": rotina,
        "handle_fingerprint": _fingerprint(handle),
        "janela_ativa": False,
        "contextos": [],
        "sessions": [],
        "subsessions": [],
        "erro": None,
    }
    textos_encontrados = []

    try:
        driver.switch_to.window(handle)
        driver.switch_to.default_content()
        snapshot["janela_ativa"] = True

        def registrar_contexto(frame):
            url_documento = driver.execute_script("return document.location.href || '';")
            formularios = driver.execute_script(
                """
                var saida = [];
                for (var i = 0; i < document.forms.length; i++) {
                    saida.push(document.forms[i].action || document.location.href || "");
                }
                return saida;
                """
            ) or []
            textos_encontrados.extend([url_documento, *formularios])
            snapshot["contextos"].append(
                {
                    "frame": frame,
                    "documento": _sanitizar_url(url_documento),
                    "formularios": [_sanitizar_url(url) for url in formularios],
                }
            )

        registrar_contexto("default")
        frames = driver.find_elements(By.TAG_NAME, "frame")
        frames += driver.find_elements(By.TAG_NAME, "iframe")

        for indice in range(len(frames)):
            try:
                driver.switch_to.default_content()
                frames_atuais = driver.find_elements(By.TAG_NAME, "frame")
                frames_atuais += driver.find_elements(By.TAG_NAME, "iframe")
                if indice >= len(frames_atuais):
                    continue
                driver.switch_to.frame(frames_atuais[indice])
                registrar_contexto(indice)
            except Exception as exc:
                snapshot["contextos"].append(
                    {"frame": indice, "erro": f"{type(exc).__name__}: {exc}"}
                )

        sessions, subsessions = _extrair_ids(textos_encontrados)
        snapshot["sessions"] = sessions
        snapshot["subsessions"] = subsessions
    except Exception as exc:
        snapshot["erro"] = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass

    return snapshot


def _comparar(antes: dict, depois: dict) -> dict:
    sessions_antes = set(antes.get("sessions", []))
    sessions_depois = set(depois.get("sessions", []))
    subsessions_antes = set(antes.get("subsessions", []))
    subsessions_depois = set(depois.get("subsessions", []))
    return {
        "janela_continua_ativa": bool(depois.get("janela_ativa")),
        "session_mudou": sessions_antes != sessions_depois,
        "subsession_mudou": subsessions_antes != subsessions_depois,
        "sessions_antes": sorted(sessions_antes),
        "sessions_depois": sorted(sessions_depois),
        "subsessions_antes": sorted(subsessions_antes),
        "subsessions_depois": sorted(subsessions_depois),
        "erro_depois": depois.get("erro"),
    }


def _salvar_relatorio(relatorio: dict) -> Path:
    pasta = Path(LOGS_DIR) / "diagnosticos_sessao"
    pasta.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = pasta / f"sessoes_multirrotina_{timestamp}.json"
    caminho.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return caminho


def main():
    driver = None
    relatorio = {
        "inicio": datetime.now().isoformat(timespec="seconds"),
        "configuracao": {
            "rotina_a": ROTINA_A,
            "rotina_b": ROTINA_B,
            "unidade_a": UNIDADE_A,
            "unidade_b": UNIDADE_B,
        },
        "snapshots": {},
        "comparacoes": {},
        "erros": [],
    }

    try:
        driver, menu = iniciar_sessao_padrao(
            logger,
            settings,
            settings.unidade_relatorios,
        )
        handle_menu = driver.current_window_handle

        pagina_a = menu.acessar_rotina(ROTINA_A)
        handle_a = driver.current_window_handle
        relatorio["snapshots"]["a_inicial"] = _snapshot_janela(
            driver, handle_a, ROTINA_A, "rotina A recém-aberta"
        )

        driver.switch_to.window(handle_menu)
        driver.switch_to.default_content()
        pagina_b = menu.acessar_rotina(ROTINA_B)
        handle_b = driver.current_window_handle
        relatorio["snapshots"]["b_inicial"] = _snapshot_janela(
            driver, handle_b, ROTINA_B, "rotina B recém-aberta"
        )

        driver.switch_to.window(handle_a)
        pagina_a.selecionar_unidade(UNIDADE_A)
        relatorio["snapshots"]["a_apos_troca_a"] = _snapshot_janela(
            driver, handle_a, ROTINA_A, f"A após trocar para {UNIDADE_A}"
        )
        relatorio["snapshots"]["b_apos_troca_a"] = _snapshot_janela(
            driver, handle_b, ROTINA_B, "B revisitada após troca na A"
        )

        driver.switch_to.window(handle_b)
        pagina_b.selecionar_unidade(UNIDADE_B)
        relatorio["snapshots"]["b_apos_troca_b"] = _snapshot_janela(
            driver, handle_b, ROTINA_B, f"B após trocar para {UNIDADE_B}"
        )
        relatorio["snapshots"]["a_apos_troca_b"] = _snapshot_janela(
            driver, handle_a, ROTINA_A, "A revisitada após troca na B"
        )

        relatorio["comparacoes"] = {
            "efeito_troca_a_na_propria_a": _comparar(
                relatorio["snapshots"]["a_inicial"],
                relatorio["snapshots"]["a_apos_troca_a"],
            ),
            "efeito_troca_a_na_b": _comparar(
                relatorio["snapshots"]["b_inicial"],
                relatorio["snapshots"]["b_apos_troca_a"],
            ),
            "efeito_troca_b_na_propria_b": _comparar(
                relatorio["snapshots"]["b_apos_troca_a"],
                relatorio["snapshots"]["b_apos_troca_b"],
            ),
            "efeito_troca_b_na_a": _comparar(
                relatorio["snapshots"]["a_apos_troca_a"],
                relatorio["snapshots"]["a_apos_troca_b"],
            ),
        }
    except Exception as exc:
        relatorio["erros"].append(
            {
                "tipo": type(exc).__name__,
                "mensagem": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        logger.exception("Diagnóstico multirrotina falhou: %s", exc)
    finally:
        relatorio["fim"] = datetime.now().isoformat(timespec="seconds")
        caminho = _salvar_relatorio(relatorio)
        encerrar_driver(driver)

    print(f"RELATORIO_DIAGNOSTICO={caminho}")
    print(json.dumps(relatorio.get("comparacoes", {}), ensure_ascii=False, indent=2))
    return 0 if not relatorio["erros"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
