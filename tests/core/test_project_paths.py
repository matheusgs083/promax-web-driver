from __future__ import annotations

from pathlib import Path

from core.config import project_paths


def test_project_root_aponta_para_raiz_do_repositorio():
    esperado = Path(project_paths.__file__).resolve().parents[2]

    assert project_paths.PROJECT_ROOT == esperado
    assert project_paths.LOGS_DIR == esperado / "logs"
    assert project_paths.DATA_DIR == esperado / "data"
    assert project_paths.DOCS_DIR == esperado / "docs"
