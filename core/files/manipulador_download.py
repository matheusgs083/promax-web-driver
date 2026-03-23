import re
import shutil
import time
from pathlib import Path

import pyautogui

from core.config.settings import get_settings
from core.observability.logger import get_logger
from core.tools.validador_visual import validar_elemento

try:
    from pywinauto import Desktop
except Exception:  # pragma: no cover - dependencia opcional em runtime
    Desktop = None


logger = get_logger(__name__)
DOWNLOAD_TRIGGER_TIMEOUT_SECONDS = 15
DOWNLOAD_WATCH_TIMEOUT_SECONDS = 500
DOWNLOAD_STALE_GUARD_SECONDS = 5
DOWNLOAD_BUTTON_LABELS = {
    "save",
    "salvar",
    "save as",
    "salvar como",
}
DOWNLOAD_CLOSE_LABELS = {
    "close",
    "fechar",
    "x",
}
DOWNLOAD_WINDOW_KEYWORDS = (
    "promax",
    "edge",
    "internet explorer",
)
DOWNLOAD_WINDOW_CLASSES = {
    "ieframe",
    "chrome_widgetwin_1",
}
LAST_DOWNLOAD_CONTROL_SIGNATURE = None


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


def _validar_arquivo_final(caminho_final: Path) -> tuple[bool, str]:
    if not caminho_final.exists():
        return False, "Arquivo final não existe após a movimentação"
    if not caminho_final.is_file():
        return False, "Caminho final não é um arquivo"
    if caminho_final.suffix.lower() != ".csv":
        return False, f"Extensão final inválida: {caminho_final.suffix}"
    tamanho = caminho_final.stat().st_size
    if tamanho <= 0:
        return False, "Arquivo final foi gerado vazio"
    return True, f"Download validado com sucesso ({tamanho} bytes)"


def _normalizar_texto(texto) -> str:
    return " ".join(str(texto or "").strip().lower().split())


def _window_text_safe(control) -> str:
    try:
        return control.window_text()
    except Exception:
        return ""


def _class_name_safe(control) -> str:
    try:
        return control.class_name()
    except Exception:
        return ""


def _janela_parece_download_browser(window) -> bool:
    titulo = _normalizar_texto(_window_text_safe(window))
    classe = _normalizar_texto(_class_name_safe(window))

    if any(keyword in titulo for keyword in DOWNLOAD_WINDOW_KEYWORDS):
        return True
    if classe in DOWNLOAD_WINDOW_CLASSES:
        return True
    return False


def _controle_parece_botao_download(control) -> bool:
    texto = _normalizar_texto(_window_text_safe(control))
    return texto in DOWNLOAD_BUTTON_LABELS


def _controle_parece_botao_fechar_download(control) -> bool:
    texto = _normalizar_texto(_window_text_safe(control))
    return texto in DOWNLOAD_CLOSE_LABELS


def _is_enabled_safe(control) -> bool:
    for method_name in ("is_enabled", "is_active"):
        method = getattr(control, method_name, None)
        if callable(method):
            try:
                return bool(method())
            except Exception:
                continue
    return True


def _is_visible_safe(control) -> bool:
    method = getattr(control, "is_visible", None)
    if callable(method):
        try:
            return bool(method())
        except Exception:
            pass
    return True


def _rect_sort_key(control) -> tuple[int, int]:
    try:
        rect = control.rectangle()
        return int(getattr(rect, "bottom", 0)), int(getattr(rect, "left", 0))
    except Exception:
        return (0, 0)


def _control_signature(control, window) -> tuple:
    return (
        _normalizar_texto(_window_text_safe(window)),
        _normalizar_texto(_class_name_safe(window)),
        _normalizar_texto(_window_text_safe(control)),
        _normalizar_texto(_class_name_safe(control)),
        _rect_sort_key(control),
    )


def _coletar_candidatos_download(window):
    candidatos = []
    for control in window.descendants():
        if not _controle_parece_botao_download(control):
            continue
        if not _is_visible_safe(control):
            continue
        if not _is_enabled_safe(control):
            continue
        candidatos.append(control)
    return candidatos


def _coletar_candidatos_fechar_download(window):
    candidatos = []
    for control in window.descendants():
        if not _controle_parece_botao_fechar_download(control):
            continue
        if not _is_visible_safe(control):
            continue
        if not _is_enabled_safe(control):
            continue
        candidatos.append(control)
    return candidatos


def _acionar_controle(control) -> bool:
    for method_name in ("invoke", "select", "click"):
        method = getattr(control, method_name, None)
        if not callable(method):
            continue
        try:
            method()
            return True
        except Exception:
            continue
    return False


def _acionar_barra_download_pywinauto(
    timeout_segundos=DOWNLOAD_TRIGGER_TIMEOUT_SECONDS,
):
    global LAST_DOWNLOAD_CONTROL_SIGNATURE

    if Desktop is None:
        return False, "pywinauto indisponivel no ambiente atual"

    logger.info("Tentando acionar a barra de download via pywinauto...")
    tempo_limite = time.time() + timeout_segundos
    inicio_busca = time.time()
    ultimo_erro = None
    encontrou_somente_barra_anterior = False

    while time.time() < tempo_limite:
        for backend in ("uia", "win32"):
            try:
                desktop = Desktop(backend=backend)
                for window in desktop.windows():
                    if not _janela_parece_download_browser(window):
                        continue

                    candidatos = sorted(
                        _coletar_candidatos_download(window),
                        key=_rect_sort_key,
                    )
                    if not candidatos:
                        continue

                    logger.info(
                        "Barra de download encontrada via pywinauto (%s) com %s candidato(s).",
                        backend,
                        len(candidatos),
                    )

                    candidatos_ordenados = list(reversed(candidatos))
                    candidatos_prioritarios = []
                    candidatos_repetidos = []

                    for control in candidatos_ordenados:
                        assinatura = _control_signature(control, window)
                        if assinatura == LAST_DOWNLOAD_CONTROL_SIGNATURE:
                            candidatos_repetidos.append((control, assinatura))
                        else:
                            candidatos_prioritarios.append((control, assinatura))

                    if (
                        LAST_DOWNLOAD_CONTROL_SIGNATURE is not None
                        and not candidatos_prioritarios
                        and candidatos_repetidos
                    ):
                        encontrou_somente_barra_anterior = True
                        logger.info(
                            "Apenas a barra anterior foi detectada via pywinauto (%s). "
                            "Aguardando uma nova barra de download aparecer...",
                            backend,
                        )
                        continue

                    for control, assinatura in candidatos_prioritarios + candidatos_repetidos:
                        if _acionar_controle(control):
                            LAST_DOWNLOAD_CONTROL_SIGNATURE = assinatura
                            logger.info(
                                "Barra de download acionada via pywinauto (%s). Janela: %s. Botao: %s",
                                backend,
                                _window_text_safe(window),
                                _window_text_safe(control),
                            )
                            return True, f"Barra de download acionada via pywinauto ({backend})"
            except Exception as exc:
                ultimo_erro = exc
                logger.debug("Falha ao procurar a barra via pywinauto (%s): %s", backend, exc)

        time.sleep(0.5)

    if encontrou_somente_barra_anterior and ultimo_erro is None:
        return False, "Apenas a barra anterior foi encontrada; uma nova barra de download nao apareceu"
    if ultimo_erro:
        return False, f"pywinauto nao encontrou o botao de download: {ultimo_erro}"
    return False, "pywinauto nao encontrou o botao de download"


def _acionar_barra_download_pyautogui(timeout_segundos=120):
    logger.info("Tentando acionar a barra de download via pyautogui...")
    box_btn = validar_elemento("botaoDownload.png", timeout=timeout_segundos, confidence=0.8)

    if not box_btn:
        logger.error("Timeout critico: a barra de download do IE nao apareceu apos a espera visual.")
        return False, "Barra de download nativa nao apareceu"

    x, y = pyautogui.center(box_btn)
    logger.info("Barra do IE detectada via imagem. Movendo o mouse para clicar...")
    pyautogui.moveTo(x, y, duration=0.3)
    time.sleep(0.2)
    pyautogui.click()
    time.sleep(0.5)
    pyautogui.hotkey("alt", "s")
    return True, "Barra de download acionada via pyautogui"


def _acionar_barra_download():
    ok, motivo = _acionar_barra_download_pywinauto()
    if ok:
        return True, motivo

    logger.warning(
        "pywinauto nao conseguiu acionar a barra de download. Fallback visual sera usado: %s",
        motivo,
    )
    return _acionar_barra_download_pyautogui()


def _fechar_barra_download_pywinauto():
    global LAST_DOWNLOAD_CONTROL_SIGNATURE

    if Desktop is None:
        return False, "pywinauto indisponivel no ambiente atual"

    for backend in ("uia", "win32"):
        try:
            desktop = Desktop(backend=backend)
            for window in desktop.windows():
                if not _janela_parece_download_browser(window):
                    continue

                candidatos = sorted(
                    _coletar_candidatos_fechar_download(window),
                    key=_rect_sort_key,
                )
                if not candidatos:
                    continue

                for control in reversed(candidatos):
                    if _acionar_controle(control):
                        LAST_DOWNLOAD_CONTROL_SIGNATURE = None
                        logger.info(
                            "Barra de download fechada via pywinauto (%s). Janela: %s. Botao: %s",
                            backend,
                            _window_text_safe(window),
                            _window_text_safe(control),
                        )
                        return True, f"Barra de download fechada via pywinauto ({backend})"
        except Exception as exc:
            logger.debug("Falha ao tentar fechar a barra via pywinauto (%s): %s", backend, exc)

    return False, "Barra de download nao foi fechada via pywinauto"


def _monitorar_download_e_mover(
    *,
    pasta_downloads: Path,
    arquivos_antes: set[Path],
    caminho_final: Path,
    timeout_segundos=DOWNLOAD_WATCH_TIMEOUT_SECONDS,
):
    tempo_limite = time.time() + timeout_segundos
    logger.info(f"Aguardando arquivo novo em: {pasta_downloads}")

    extensoes_ignoradas = {".tmp", ".crdownload", ".part", ".partial", ".ini"}

    while time.time() < tempo_limite:
        arquivos_agora = set(pasta_downloads.iterdir())
        novos_arquivos = arquivos_agora - arquivos_antes

        for arquivo in novos_arquivos:
            if not arquivo.is_file():
                continue

            if arquivo.suffix.lower() in extensoes_ignoradas:
                continue

            try:
                if not _arquivo_pronto_para_mover(arquivo):
                    continue

                if caminho_final.exists():
                    logger.warning(f"Arquivo já existe no destino. Removendo antigo: {caminho_final}")
                    caminho_final.unlink()

                shutil.move(str(arquivo), str(caminho_final))
                ok_validacao, motivo_validacao = _validar_arquivo_final(caminho_final)
                if not ok_validacao:
                    logger.error(f"Arquivo movido, mas inválido: {motivo_validacao}")
                    return False, motivo_validacao

                logger.info(f"Sucesso! Relatório capturado e salvo em: {caminho_final}")
                return True, motivo_validacao
            except PermissionError:
                logger.debug("Arquivo bloqueado (ainda baixando). Aguardando liberacao do SO...")
            except Exception as e:
                logger.error(f"Erro inesperado ao mover o arquivo: {e}")

        time.sleep(1)

    logger.error(f"Timeout: Nenhum arquivo novo apareceu apos {timeout_segundos}s.")
    return False, "Timeout na espera da rede/download do arquivo"


def salvar_arquivo_visual(diretorio_destino, nome_arquivo_final):
    logger.info("--- INICIANDO SALVAMENTO OTIMIZADO (WATCHER DE PASTA) ---")

    settings = get_settings()
    pasta_downloads = Path.home() / "Downloads"
    pasta_intermediaria = Path(diretorio_destino) if diretorio_destino else settings.download_dir

    pasta_intermediaria.mkdir(parents=True, exist_ok=True)
    pasta_downloads.mkdir(parents=True, exist_ok=True)

    logger.info(f"Watcher de origem configurado em: {pasta_downloads}")
    logger.info(f"Pasta intermediaria configurada em: {pasta_intermediaria}")

    nome_limpo = re.sub(r'[\\/*?:"<>|]', "_", nome_arquivo_final)
    if not nome_limpo.lower().endswith(".csv"):
        nome_limpo += ".csv"

    caminho_final = pasta_intermediaria / nome_limpo
    arquivos_antes = set(pasta_downloads.iterdir())

    ok_acionamento, motivo_acionamento = _acionar_barra_download()
    if not ok_acionamento:
        return False, motivo_acionamento

    time.sleep(1)
    resultado = _monitorar_download_e_mover(
        pasta_downloads=pasta_downloads,
        arquivos_antes=arquivos_antes,
        caminho_final=caminho_final,
    )
    if resultado[0]:
        ok_fechamento, motivo_fechamento = _fechar_barra_download_pywinauto()
        if ok_fechamento:
            logger.info(motivo_fechamento)
        else:
            logger.debug("Fechamento da barra de download nao confirmado: %s", motivo_fechamento)
    return resultado
