from pathlib import Path


def _resolve_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _resolve_project_root()
AGENTS_DIR = PROJECT_ROOT / "agents"
DATA_DIR = PROJECT_ROOT / "data"
DOCS_DIR = PROJECT_ROOT / "docs"
ENTRYPOINTS_DIR = PROJECT_ROOT / "entrypoints"
LOGS_DIR = PROJECT_ROOT / "logs"
MAPS_DIR = PROJECT_ROOT / "maps"
TESTS_DIR = PROJECT_ROOT / "tests"
