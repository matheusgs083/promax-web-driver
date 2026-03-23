import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import dotenv


dotenv.load_dotenv()


@dataclass(frozen=True)
class Settings:
    promax_url: str
    promax_user: str
    promax_pass: str
    # Pasta intermediaria onde o arquivo capturado pelo IE fica antes do
    # pos-processamento, organizacao e movimentacao final.
    download_dir: Path
    driver_path: str | None
    edge_path: str | None
    require_window_focus: bool
    unidade_relatorios: str
    unidade_pedidos: str
    unidade_lote_condicao: str
    pedidos_planilha_path: Path
    cemc_file_path: Path


def _env_path(name: str, default: str) -> Path:
    return Path(os.getenv(name, default)).expanduser()


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on", "sim", "s"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off", "nao"}:
        return False
    return default


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        promax_url=os.getenv("PROMAX_URL", "").strip(),
        promax_user=os.getenv("PROMAX_USER", "").strip(),
        promax_pass=os.getenv("PROMAX_PASS", "").strip(),
        download_dir=_env_path("DOWNLOAD_DIR", r"C:\Users\caixa.patos\Documents\Relatorios"),
        driver_path=os.getenv("DRIVER_PATH"),
        edge_path=os.getenv("EDGE_PATH"),
        require_window_focus=_env_bool("PROMAX_REQUIRE_WINDOW_FOCUS", False),
        unidade_relatorios=os.getenv("PROMAX_REPORT_UNIT", "SOUSA").strip().upper(),
        unidade_pedidos=os.getenv("PROMAX_PEDIDOS_UNIT", "PATOS").strip().upper(),
        unidade_lote_condicao=os.getenv("PROMAX_LOTE_UNIT", "PATOS").strip().upper(),
        pedidos_planilha_path=_env_path("PEDIDOS_PLANILHA_PATH", r"C:\Users\caixa.patos\Desktop\pedidos.xlsx"),
        cemc_file_path=_env_path("CEMC_FILE_PATH", r"C:\Users\caixa.patos\Desktop\Utilidades2.0.xlsm"),
    )
