import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

from core.tools.windows_display import ensure_windows_dpi_aware

ensure_windows_dpi_aware()

import pyautogui

from core.observability.logger import get_logger
from core.tools.validador_visual import validar_elemento

logger = get_logger(__name__)

URL_RELATORIO_RE = re.compile(
    r"""(?P<url>(?:https?://[^"'<> ]+)?(?:\.\./)*(?:/pw)?/tmp/rels/[^"'<> ]+\.(?:csv|pdf)(?:\.inf)?)""",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DownloadHttpPreparado:
    """Requisicao completa, sem dependencia posterior do WebDriver."""

    nome_arquivo: str
    caminho_final: Path
    extensao_final: str
    metodo: str
    action: str = field(repr=False)
    dados: bytes = field(repr=False)
    headers: dict[str, str] = field(repr=False)


def _arquivo_pronto_para_mover(arquivo: Path) -> bool:
    if not arquivo.is_file():
        return False
    if arquivo.stat().st_size <= 0:
        return False
    try:
        with arquivo.open("rb"):
            return True
    except PermissionError:
        return False


def _validar_arquivo_final(caminho_final: Path, extensao_esperada: str = ".csv") -> tuple[bool, str]:
    if not caminho_final.exists():
        return False, "Arquivo final não existe após a movimentação"
    if not caminho_final.is_file():
        return False, "Caminho final não é um arquivo"
    if caminho_final.suffix.lower() != extensao_esperada.lower():
        return False, f"Extensão final inválida: {caminho_final.suffix}"
    tamanho = caminho_final.stat().st_size
    if tamanho <= 0:
        return False, "Arquivo final foi gerado vazio"
    return True, f"Download validado com sucesso ({tamanho} bytes)"


def _houve_atividade_download(pasta_downloads: Path, arquivos_antes: set[Path]) -> bool:
    try:
        arquivos_agora = set(pasta_downloads.iterdir())
    except Exception:
        return False
    return any(arquivo not in arquivos_antes for arquivo in arquivos_agora)


def _extrair_urls_relatorio(texto: str, url_base: str) -> list[str]:
    urls = []
    for match in URL_RELATORIO_RE.finditer(texto or ""):
        url = urljoin(url_base, match.group("url").replace("&amp;", "&"))
        if url not in urls:
            urls.append(url)
    return urls


def _coletar_urls_relatorio_driver(driver) -> list[str]:
    urls = []
    url_base = getattr(driver, "current_url", "")

    def adicionar_texto(texto):
        for url in _extrair_urls_relatorio(texto, url_base):
            if url not in urls:
                urls.append(url)

    def inspecionar_contexto():
        try:
            adicionar_texto(driver.page_source)
            adicionar_texto(getattr(driver, "current_url", ""))
        except Exception as exc:
            logger.debug("Não foi possível inspecionar o contexto atual para download direto: %s", exc)

        try:
            driver.switch_to.default_content()
            adicionar_texto(driver.page_source)
            frames = driver.find_elements("tag name", "frame")
            frames += driver.find_elements("tag name", "iframe")
            for indice in range(len(frames)):
                try:
                    driver.switch_to.default_content()
                    frames_atuais = driver.find_elements("tag name", "frame")
                    frames_atuais += driver.find_elements("tag name", "iframe")
                    if indice >= len(frames_atuais):
                        continue
                    driver.switch_to.frame(frames_atuais[indice])
                    adicionar_texto(driver.page_source)
                    adicionar_texto(getattr(driver, "current_url", ""))
                except Exception as exc:
                    logger.debug("Frame %s ignorado durante busca da URL de relatório: %s", indice, exc)
        except Exception as exc:
            logger.debug("Não foi possível percorrer os frames para download direto: %s", exc)
        finally:
            try:
                driver.switch_to.default_content()
            except Exception:
                pass

    handle_original = None
    try:
        handle_original = driver.current_window_handle
    except Exception:
        handle_original = None

    try:
        handles = list(driver.window_handles)
    except Exception:
        handles = []

    if not handles:
        inspecionar_contexto()
    else:
        for handle in handles:
            try:
                driver.switch_to.window(handle)
                url_base = getattr(driver, "current_url", "") or url_base
                inspecionar_contexto()
            except Exception as exc:
                logger.debug("Janela %s ignorada durante busca da URL de relatório: %s", handle, exc)

    if handle_original:
        try:
            driver.switch_to.window(handle_original)
            driver.switch_to.default_content()
        except Exception:
            pass

    return urls


def _cabecalho_cookies(driver) -> str:
    try:
        cookies = driver.get_cookies()
        pares = [
            f"{cookie['name']}={cookie['value']}"
            for cookie in cookies
            if isinstance(cookie, dict)
            and cookie.get("name")
            and cookie.get("value") is not None
        ]
        if pares:
            return "; ".join(pares)
    except Exception as exc:
        logger.debug("Cookies WebDriver indisponíveis: %s", exc)
    try:
        return str(driver.execute_script("return document.cookie || ''") or "")
    except Exception:
        return ""


def _baixar_url_com_headers(
    url: str,
    caminho_final: Path,
    extensao_final: str,
    headers: dict[str, str],
) -> tuple[bool, str]:
    caminho_final.parent.mkdir(parents=True, exist_ok=True)

    try:
        with urlopen(Request(url, headers=headers), timeout=180) as resposta:
            conteudo = resposta.read()
            content_type = str(resposta.headers.get("Content-Type", "")).lower()
    except Exception as exc:
        return False, f"Falha no GET direto: {exc}"

    if not conteudo:
        return False, "GET direto retornou arquivo vazio"

    extensao = extensao_final.lower()
    if extensao == ".pdf" and not conteudo.startswith(b"%PDF-"):
        return False, f"GET direto não retornou PDF válido ({content_type or 'sem Content-Type'})"
    if extensao == ".csv":
        inicio = conteudo[:200].lstrip().lower()
        if inicio.startswith((b"<html", b"<!doctype", b"<script")) or "text/html" in content_type:
            return False, f"GET direto retornou HTML em vez de CSV ({content_type or 'sem Content-Type'})"

    caminho_final.write_bytes(conteudo)
    ok, motivo = _validar_arquivo_final(caminho_final, extensao_final)
    if not ok:
        caminho_final.unlink(missing_ok=True)
        return False, motivo
    return True, f"Download HTTP direto validado ({len(conteudo)} bytes)"


def _baixar_url_relatorio(driver, url: str, caminho_final: Path, extensao_final: str) -> tuple[bool, str]:
    cookies = _cabecalho_cookies(driver)
    try:
        user_agent = driver.execute_script("return navigator.userAgent") or ""
    except Exception:
        user_agent = ""

    headers = {"Accept": "*/*", "Referer": getattr(driver, "current_url", "")}
    if cookies:
        headers["Cookie"] = cookies
    if user_agent:
        headers["User-Agent"] = user_agent
    return _baixar_url_com_headers(url, caminho_final, extensao_final, headers)


def _dados_formulario_exportacao(driver, botao) -> dict:
    script = r"""
    var botao = arguments[0];
    var form = botao && botao.form;
    if (!form) return {ok:false, error:"botao sem formulario"};
    function textoBotao(el) {
        return String((el && (el.innerText || el.textContent || el.value || el.name)) || '').toUpperCase();
    }
    function campo(nome) {
        return form.elements[nome] || (document.getElementsByName(nome)[0] || null);
    }
    function setCampo(nome, valor) {
        var el = campo(nome);
        if (!el) return false;
        el.value = valor;
        return true;
    }
    function aplicarExportacaoPorBotao() {
        var nome = String((botao && botao.name) || '').toUpperCase();
        var texto = textoBotao(botao);
        var csv = nome === 'GEREXECL' || nome === 'GERAEXCEL' || nome === 'GEREXCEL' || texto.indexOf('CSV') >= 0;
        var pdf = nome === 'GERPDF' || texto.indexOf('PDF') >= 0;
        if (!csv && !pdf) return {ok:true, mapped:false};
        setCampo('opcao', '88');
        setCampo('opcaorelat', csv ? '3' : '6');
        return {ok:true, mapped:true, tipo:csv ? 'csv' : 'pdf'};
    }
    var mapaAntes = aplicarExportacaoPorBotao();
    var submitOriginal = form.submit;
    var openOriginal = window.open;
    try {
        form.submit = function() { return false; };
        window.open = function() { return null; };
        if (typeof botao.onclick === "function") {
            var eventOriginal = window.event;
            try { window.event = {srcElement: botao, target: botao}; } catch (eEvent) {}
            try {
                botao.onclick();
            } finally {
                try { window.event = eventOriginal; } catch (eEventRestore) {}
            }
        } else {
            var onclickAttr = botao.getAttribute ? botao.getAttribute('onclick') : '';
            if (onclickAttr) {
                var fn = new Function(onclickAttr);
                fn.call(botao);
            }
        }
    } catch (eOnClick) {
        return {ok:false, error:"onclick: " + (eOnClick.message || String(eOnClick))};
    } finally {
        form.submit = submitOriginal;
        window.open = openOriginal;
    }
    var mapaDepois = aplicarExportacaoPorBotao();
    var pares = [];
    var elementos = form.elements || [];
    for (var i = 0; i < elementos.length; i++) {
        var el = elementos[i];
        if (!el.name || el.disabled) continue;
        var tipo = String(el.type || "").toLowerCase();
        if (tipo === "file" || tipo === "reset") continue;
        if ((tipo === "checkbox" || tipo === "radio") && !el.checked) continue;
        if (tipo === "submit" || tipo === "button" || tipo === "image") continue;
        if (tipo === "select-multiple") {
            for (var j = 0; j < el.options.length; j++) {
                if (el.options[j].selected) pares.push([el.name, el.options[j].value]);
            }
            continue;
        }
        pares.push([el.name, el.value == null ? "" : String(el.value)]);
    }
    if (botao.name) pares.push([botao.name, botao.value == null ? "" : String(botao.value)]);
    return {
        ok:true,
        action:form.action || document.location.href,
        method:String(form.method || "GET").toUpperCase(),
        pairs:pares,
        exportMapping: mapaDepois.mapped ? mapaDepois : mapaAntes
    };
    """
    resultado = driver.execute_script(script, botao)
    if not resultado or not resultado.get("ok"):
        raise RuntimeError(f"Não foi possível serializar o formulário: {resultado}")
    return resultado


def preparar_download_http_formulario(
    driver,
    botao,
    diretorio_destino,
    nome_arquivo_final,
    extensao_final=".csv",
) -> DownloadHttpPreparado:
    pasta_destino = Path(diretorio_destino)
    pasta_destino.mkdir(parents=True, exist_ok=True)
    extensao_final = extensao_final if str(extensao_final).startswith(".") else f".{extensao_final}"
    nome_limpo = re.sub(r'[\\/*?:"<>|]', "_", nome_arquivo_final)
    if not nome_limpo.lower().endswith(extensao_final.lower()):
        nome_limpo += extensao_final
    caminho_final = pasta_destino / nome_limpo

    formulario = _dados_formulario_exportacao(driver, botao)
    pares = [(str(nome), str(valor)) for nome, valor in formulario["pairs"]]
    dados = urlencode(pares).encode("ascii")
    url_atual = getattr(driver, "current_url", "")
    action = urljoin(url_atual, formulario["action"])

    cookies = _cabecalho_cookies(driver)
    try:
        user_agent = driver.execute_script("return navigator.userAgent") or ""
    except Exception:
        user_agent = ""
    headers = {
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": url_atual,
    }
    if cookies:
        headers["Cookie"] = cookies
    if user_agent:
        headers["User-Agent"] = user_agent

    return DownloadHttpPreparado(
        nome_arquivo=nome_limpo,
        caminho_final=caminho_final,
        extensao_final=extensao_final,
        metodo=formulario["method"],
        action=action,
        dados=dados,
        headers=headers,
    )


def executar_download_http_preparado(download: DownloadHttpPreparado) -> tuple[bool, str]:
    try:
        action = download.action
        metodo = download.metodo
        request = Request(
            action
            if metodo != "GET"
            else f"{action}{'&' if '?' in action else '?'}{download.dados.decode('ascii')}",
            data=download.dados if metodo != "GET" else None,
            headers=download.headers,
            method=metodo,
        )
        action_partes = urlsplit(action)
        action_segura = f"{action_partes.scheme}://{action_partes.netloc}{action_partes.path}"
        logger.info(
            "Enviando formulário de exportação diretamente: %s %s [%s]",
            metodo,
            action_segura,
            download.nome_arquivo,
        )
        with urlopen(request, timeout=180) as resposta:
            conteudo = resposta.read()
            content_type = str(resposta.headers.get("Content-Type", "")).lower()
            url_resposta = resposta.geturl()

        if conteudo and "text/html" not in content_type:
            extensao = download.extensao_final.lower()
            inicio = conteudo[:200].lstrip().lower()
            if extensao == ".pdf" and not conteudo.startswith(b"%PDF-"):
                return False, f"POST não retornou PDF válido ({content_type or 'sem Content-Type'})"
            if extensao == ".csv" and inicio.startswith((b"<html", b"<!doctype", b"<script")):
                return False, f"POST retornou HTML em vez de CSV ({content_type or 'sem Content-Type'})"

            download.caminho_final.write_bytes(conteudo)
            ok, motivo = _validar_arquivo_final(download.caminho_final, download.extensao_final)
            if not ok:
                download.caminho_final.unlink(missing_ok=True)
                return False, motivo
            return True, f"Download HTTP direto validado ({len(conteudo)} bytes)"

        html = conteudo.decode("latin-1", errors="ignore")
        urls = _extrair_urls_relatorio(html, url_resposta or action)
        if not urls:
            return False, "Resposta HTML sem URL temporária"

        headers_get = dict(download.headers)
        headers_get.pop("Content-Type", None)
        return _baixar_url_com_headers(
            urls[-1],
            download.caminho_final,
            download.extensao_final,
            headers_get,
        )
    except Exception as exc:
        return False, f"Falha ao reproduzir formulário de exportação: {exc}"


def salvar_arquivo_http_formulario(
    driver,
    botao,
    diretorio_destino,
    nome_arquivo_final,
    extensao_final=".csv",
) -> tuple[bool, str]:
    try:
        download = preparar_download_http_formulario(
            driver,
            botao,
            diretorio_destino,
            nome_arquivo_final,
            extensao_final,
        )
        return executar_download_http_preparado(download)
    except Exception as exc:
        return False, f"Falha ao preparar formulário de exportação: {exc}"


def _tentar_download_http(
    driver,
    caminho_final: Path,
    extensao_final: str,
    timeout_segundos: float = 12,
) -> tuple[bool, str]:
    if driver is None:
        return False, "Driver não informado"

    prazo = time.time() + timeout_segundos
    ultimo_motivo = "URL temporária não encontrada"
    urls_testadas = set()

    while time.time() < prazo:
        for url in reversed(_coletar_urls_relatorio_driver(driver)):
            if url in urls_testadas:
                continue
            urls_testadas.add(url)
            logger.info("URL temporária encontrada; tentando download HTTP direto: %s", url)
            ok, motivo = _baixar_url_relatorio(driver, url, caminho_final, extensao_final)
            if ok:
                return True, motivo
            ultimo_motivo = motivo
            logger.warning("Download HTTP direto rejeitado: %s", motivo)
        time.sleep(0.5)

    return False, ultimo_motivo


def salvar_url_temporaria_relatorio(
    driver,
    diretorio_destino,
    nome_arquivo_final,
    extensao_final=".csv",
    timeout_segundos=15,
) -> tuple[bool, str]:
    pasta_destino = Path(diretorio_destino)
    pasta_destino.mkdir(parents=True, exist_ok=True)
    extensao_final = extensao_final if str(extensao_final).startswith(".") else f".{extensao_final}"
    nome_limpo = re.sub(r'[\\/*?:"<>|]', "_", nome_arquivo_final)
    if not nome_limpo.lower().endswith(extensao_final.lower()):
        nome_limpo += extensao_final
    caminho_final = pasta_destino / nome_limpo
    return _tentar_download_http(
        driver,
        caminho_final,
        extensao_final,
        timeout_segundos=timeout_segundos,
    )


def salvar_arquivo_visual(
    diretorio_destino,
    nome_arquivo_final,
    extensao_final=".csv",
    *,
    driver=None,
    timeout_http_direto=12,
):
    logger.info("--- INICIANDO SALVAMENTO OTIMIZADO (WATCHER DE PASTA) ---")

    pasta_downloads = Path.home() / "Downloads"
    pasta_intermediaria = Path(diretorio_destino)

    pasta_intermediaria.mkdir(parents=True, exist_ok=True)
    pasta_downloads.mkdir(parents=True, exist_ok=True)

    logger.info(f"Watcher de origem configurado em: {pasta_downloads}")
    logger.info(f"Pasta intermediaria configurada em: {pasta_intermediaria}")

    nome_limpo = re.sub(r'[\\/*?:"<>|]', "_", nome_arquivo_final)
    extensao_final = extensao_final if str(extensao_final).startswith(".") else f".{extensao_final}"
    if not nome_limpo.lower().endswith(extensao_final.lower()):
        nome_limpo += extensao_final

    caminho_final = pasta_intermediaria / nome_limpo
    arquivos_antes = set(pasta_downloads.iterdir())

    if driver is not None:
        logger.info("Tentando capturar o relatório pela URL temporária do Promax...")
        ok_http, motivo_http = _tentar_download_http(
            driver,
            caminho_final,
            extensao_final,
            timeout_segundos=timeout_http_direto,
        )
        if ok_http:
            logger.info("Sucesso! Relatório salvo sem interação visual: %s", caminho_final)
            return True, motivo_http
        logger.warning("Download HTTP direto indisponível (%s). Usando fallback visual.", motivo_http)

    logger.info("Aguardando o servidor processar e a barra do IE aparecer...")
    box_btn = validar_elemento("botaoDownload.png", timeout=60, confidence=0.8)

    if box_btn:
        x, y = pyautogui.center(box_btn)
        logger.info("Barra do IE detectada! Movendo o mouse para clicar...")
        pyautogui.moveTo(x, y, duration=0.3)
        time.sleep(0.2)
        pyautogui.click()

        # Evita ativar duas vezes a mesma barra de download.
        tempo_limite_fallback = time.time() + 2.5
        iniciou_download = False
        while time.time() < tempo_limite_fallback:
            if _houve_atividade_download(pasta_downloads, arquivos_antes):
                iniciou_download = True
                logger.info("Atividade de download detectada após clique visual. Fallback Alt+S ignorado.")
                break
            time.sleep(0.2)

        if not iniciou_download:
            logger.info("Nenhuma atividade detectada após clique visual. Enviando Alt+S como fallback.")
            pyautogui.hotkey("alt", "s")
    else:
        logger.error("Timeout Crítico: A barra de download do IE não apareceu após 1 minuto.")
        return False, "Barra de download nativa não apareceu"

    time.sleep(1)

    timeout_segundos = 550
    tempo_limite = time.time() + timeout_segundos
    logger.info(f"Aguardando arquivo novo em: {pasta_downloads}")

    extensoes_ignoradas = {".tmp", ".crdownload", ".part", ".partial", ".ini"}

    while time.time() < tempo_limite:
        arquivos_agora = set(pasta_downloads.iterdir())
        novos_arquivos = arquivos_agora - arquivos_antes

        for arquivo in novos_arquivos:
            if not arquivo.is_file():
                continue

            extensao_atual = arquivo.suffix.lower()
            if extensao_atual in extensoes_ignoradas:
                continue

            try:
                if not _arquivo_pronto_para_mover(arquivo):
                    continue

                if caminho_final.exists():
                    logger.warning(f"Arquivo já existe no destino. Removendo antigo: {caminho_final}")
                    caminho_final.unlink()

                shutil.move(str(arquivo), str(caminho_final))
                ok_validacao, motivo_validacao = _validar_arquivo_final(caminho_final, extensao_final)
                if not ok_validacao:
                    logger.error(f"Arquivo movido, mas inválido: {motivo_validacao}")
                    return False, motivo_validacao

                logger.info(f"Sucesso! Relatório capturado e salvo em: {caminho_final}")
                return True, motivo_validacao

            except PermissionError:
                logger.debug("Arquivo bloqueado (ainda baixando). Aguardando liberação do SO...")
            except Exception as e:
                logger.error(f"Erro inesperado ao mover o arquivo: {e}")

        time.sleep(1)

    logger.error(f"Timeout: Nenhum arquivo novo apareceu após {timeout_segundos}s.")
    return False, "Timeout na espera da rede/download do arquivo"
