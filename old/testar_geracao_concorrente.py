from __future__ import annotations

import hashlib
import json
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

import pages.common.rotina_page as rotina_page_module
from core.config.project_paths import LOGS_DIR
from core.config.settings import get_settings
from core.execution.entrypoint_helpers import encerrar_driver, iniciar_sessao_padrao
from core.files import manipulador_download
from core.observability.logger import get_logger
from pages.reports.relatorio_020220_page import Relatorio020220Page
from pages.reports.relatorio_030237_page import Relatorio030237Page


logger = get_logger("TESTE_GERACAO_CONCORRENTE")
settings = get_settings()

UNIDADE_A = "3610006"
UNIDADE_B = "3610007"
MAX_CONCORRENCIA = 2


def _fingerprint(valor: str) -> str:
    return hashlib.sha256(valor.encode("utf-8", errors="ignore")).hexdigest()[:12]


def _preparar_especificacao(driver, botao, nome, extensao) -> dict:
    formulario = manipulador_download._dados_formulario_exportacao(driver, botao)
    pares = [(str(chave), str(valor)) for chave, valor in formulario["pairs"]]
    dados = urlencode(pares).encode("ascii")
    action = urljoin(driver.current_url, formulario["action"])
    partes = urlsplit(action)
    cookies = manipulador_download._cabecalho_cookies(driver)
    try:
        user_agent = driver.execute_script("return navigator.userAgent") or ""
    except Exception:
        user_agent = ""

    headers = {
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": driver.current_url,
    }
    if cookies:
        headers["Cookie"] = cookies
    if user_agent:
        headers["User-Agent"] = user_agent

    return {
        "nome": nome,
        "extensao": extensao,
        "action": action,
        "action_segura": f"{partes.scheme}://{partes.netloc}{partes.path}",
        "session_fingerprint": _fingerprint(action),
        "metodo": formulario["method"],
        "dados": dados,
        "headers": headers,
    }


def _executar_especificacao(especificacao: dict, destino: Path) -> dict:
    inicio = time.perf_counter()
    resultado = {
        "nome": especificacao["nome"],
        "action": especificacao["action_segura"],
        "session_fingerprint": especificacao["session_fingerprint"],
        "ok": False,
        "status_http": None,
        "content_type": None,
        "bytes": 0,
        "duracao_segundos": None,
        "arquivo": str(destino),
        "erro": None,
    }

    try:
        metodo = especificacao["metodo"]
        dados = especificacao["dados"]
        action = especificacao["action"]
        url = action
        corpo = dados
        if metodo == "GET":
            url = f"{action}{'&' if '?' in action else '?'}{dados.decode('ascii')}"
            corpo = None

        request = Request(
            url,
            data=corpo,
            headers=especificacao["headers"],
            method=metodo,
        )
        with urlopen(request, timeout=240) as resposta:
            conteudo = resposta.read()
            resultado["status_http"] = getattr(resposta, "status", None)
            resultado["content_type"] = str(
                resposta.headers.get("Content-Type", "")
            ).lower()
            url_resposta = resposta.geturl()

        if "text/html" in resultado["content_type"]:
            html = conteudo.decode("latin-1", errors="ignore")
            urls = manipulador_download._extrair_urls_relatorio(
                html,
                url_resposta or action,
            )
            if not urls:
                raise RuntimeError("Resposta HTML não contém URL temporária")
            request_arquivo = Request(urls[-1], headers=especificacao["headers"])
            with urlopen(request_arquivo, timeout=240) as resposta_arquivo:
                conteudo = resposta_arquivo.read()
                resultado["status_http"] = getattr(resposta_arquivo, "status", None)
                resultado["content_type"] = str(
                    resposta_arquivo.headers.get("Content-Type", "")
                ).lower()

        if not conteudo:
            raise RuntimeError("Arquivo vazio")
        if especificacao["extensao"] == ".pdf" and not conteudo.startswith(b"%PDF-"):
            raise RuntimeError("Conteúdo não possui assinatura PDF")
        if especificacao["extensao"] == ".csv":
            inicio_conteudo = conteudo[:200].lstrip().lower()
            if inicio_conteudo.startswith((b"<html", b"<!doctype", b"<script")):
                raise RuntimeError("Conteúdo HTML recebido no lugar do CSV")

        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(conteudo)
        resultado["bytes"] = len(conteudo)
        resultado["sha256"] = hashlib.sha256(conteudo).hexdigest()
        resultado["ok"] = True
    except Exception as exc:
        resultado["erro"] = f"{type(exc).__name__}: {exc}"
    finally:
        resultado["duracao_segundos"] = round(time.perf_counter() - inicio, 3)

    return resultado


def _executar_sequencial(especificacoes: list[dict], pasta: Path) -> tuple[list[dict], float]:
    inicio = time.perf_counter()
    resultados = []
    for especificacao in especificacoes:
        destino = pasta / f"{especificacao['nome']}.csv"
        resultados.append(_executar_especificacao(especificacao, destino))
    return resultados, round(time.perf_counter() - inicio, 3)


def _executar_concorrente(
    especificacoes: list[dict],
    pasta: Path,
    max_workers: int = MAX_CONCORRENCIA,
) -> tuple[list[dict], float]:
    inicio = time.perf_counter()
    resultados = []
    with ThreadPoolExecutor(
        max_workers=max_workers,
        thread_name_prefix="promax-http",
    ) as executor:
        futuros = {
            executor.submit(
                _executar_especificacao,
                especificacao,
                pasta / f"{especificacao['nome']}.csv",
            ): especificacao["nome"]
            for especificacao in especificacoes
        }
        for futuro in as_completed(futuros):
            resultados.append(futuro.result())
    resultados.sort(key=lambda item: item["nome"])
    return resultados, round(time.perf_counter() - inicio, 3)


def _salvar_relatorio(relatorio: dict) -> Path:
    pasta = Path(LOGS_DIR) / "diagnosticos_concorrencia"
    pasta.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = pasta / f"geracao_concorrente_{timestamp}.json"
    caminho.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return caminho


def main() -> int:
    driver = None
    especificacoes = []
    original_capturador = rotina_page_module.capturar_download_por_formulario
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta_base = Path(settings.download_dir) / "teste_concorrencia" / timestamp
    relatorio = {
        "inicio": datetime.now().isoformat(timespec="seconds"),
        "concorrencia": MAX_CONCORRENCIA,
        "unidades": {"020220": UNIDADE_A, "030237": UNIDADE_B},
        "preparacao": [],
        "sequencial": {},
        "concorrente": {},
        "ganho": {},
        "erros": [],
    }

    def capturar_sem_executar(
        driver_recebido,
        botao,
        nome_arquivo_final,
        diretorio_intermediario=None,
        extensao_final=".csv",
    ):
        nome = f"{len(especificacoes) + 1}_{nome_arquivo_final.rsplit('.', 1)[0]}"
        especificacao = _preparar_especificacao(
            driver_recebido,
            botao,
            nome,
            extensao_final,
        )
        especificacoes.append(especificacao)
        relatorio["preparacao"].append(
            {
                "nome": nome,
                "action": especificacao["action_segura"],
                "session_fingerprint": especificacao["session_fingerprint"],
                "metodo": especificacao["metodo"],
                "campos": len(especificacao["dados"]),
            }
        )
        return True, "Requisição capturada para diagnóstico concorrente"

    try:
        driver, menu = iniciar_sessao_padrao(
            logger,
            settings,
            settings.unidade_relatorios,
        )
        handle_menu = driver.current_window_handle
        rotina_page_module.capturar_download_por_formulario = capturar_sem_executar

        janela_a = menu.acessar_rotina("020220")
        page_a = Relatorio020220Page(janela_a.driver, janela_a.handle_menu)
        page_a.gerar_relatorio(
            unidade=UNIDADE_A,
            opcao_rel="01",
            mercadoria_todos=False,
            mercadoria_garrafeira=True,
            mercadoria_vasilhame=True,
            selecao_comodatos="T",
            nome_arquivo="020220_concorrencia.csv",
        )

        driver.switch_to.window(handle_menu)
        driver.switch_to.default_content()
        janela_b = menu.acessar_rotina("030237")
        page_b = Relatorio030237Page(janela_b.driver, janela_b.handle_menu)
        hoje = datetime.now().strftime("%d/%m/%Y")
        page_b.gerar_relatorio(
            unidade=UNIDADE_B,
            quebra1="14",
            itens="s",
            data_inicial=hoje,
            data_final=hoje,
            nome_arquivo="030237_concorrencia.csv",
        )

        if len(especificacoes) != 2:
            raise RuntimeError(
                f"Esperadas 2 requisições preparadas; obtidas {len(especificacoes)}"
            )

        resultados_seq, tempo_seq = _executar_sequencial(
            especificacoes,
            pasta_base / "sequencial",
        )
        resultados_conc, tempo_conc = _executar_concorrente(
            especificacoes,
            pasta_base / "concorrente",
        )
        relatorio["sequencial"] = {
            "tempo_total_segundos": tempo_seq,
            "resultados": resultados_seq,
        }
        relatorio["concorrente"] = {
            "tempo_total_segundos": tempo_conc,
            "resultados": resultados_conc,
        }
        relatorio["ganho"] = {
            "segundos_economizados": round(tempo_seq - tempo_conc, 3),
            "speedup_observado": round(tempo_seq / tempo_conc, 3) if tempo_conc else None,
            "cache_detectado": any(
                concorrente["duracao_segundos"] < sequencial["duracao_segundos"] * 0.5
                for sequencial, concorrente in zip(resultados_seq, resultados_conc)
            ),
            "speedup_concorrente_sem_efeito_cache": round(
                sum(item["duracao_segundos"] for item in resultados_conc) / tempo_conc,
                3,
            )
            if tempo_conc
            else None,
            "speedup_maximo_estimado_carga_frio": round(
                tempo_seq / max(item["duracao_segundos"] for item in resultados_seq),
                3,
            )
            if resultados_seq
            else None,
            "todos_sequenciais_ok": all(item["ok"] for item in resultados_seq),
            "todos_concorrentes_ok": all(item["ok"] for item in resultados_conc),
            "conteudos_identicos_entre_rodadas": all(
                sequencial.get("bytes") == concorrente.get("bytes")
                and sequencial.get("sha256") == concorrente.get("sha256")
                for sequencial, concorrente in zip(resultados_seq, resultados_conc)
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
        logger.exception("Teste de geração concorrente falhou: %s", exc)
    finally:
        rotina_page_module.capturar_download_por_formulario = original_capturador
        relatorio["fim"] = datetime.now().isoformat(timespec="seconds")
        caminho_relatorio = _salvar_relatorio(relatorio)
        encerrar_driver(driver)

    print(f"RELATORIO_CONCORRENCIA={caminho_relatorio}")
    print(json.dumps(relatorio.get("ganho", {}), ensure_ascii=False, indent=2))
    return 0 if not relatorio["erros"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
