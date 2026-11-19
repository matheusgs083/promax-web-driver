from pathlib import Path

import pytest

from core.config.report_group_loader import ReportGroupManifestError, load_report_group_manifest


def _manifest(tmp_path: Path, units: str) -> Path:
    caminho = tmp_path / "cora_estoque.py"
    caminho.write_text(
        'REPORT_GROUP = {"key": "cora_estoque", "name": "Cora", "description": "Estoque",'
        ' "routines": [{"id": "grade_estoque", "name": "Grade", "output_folders": ["cora_estoque"]}]'
        + units + "}",
        encoding="utf-8",
    )
    return caminho


def test_grupo_com_unidades_proprias(tmp_path: Path) -> None:
    grupo = load_report_group_manifest(_manifest(tmp_path, ', "units": ["487570", "747530", "747548"]'))
    assert grupo.units == ("487570", "747530", "747548")
    assert grupo.to_dict()["units"] == ["487570", "747530", "747548"]


def test_grupo_sem_unidades_nao_muda(tmp_path: Path) -> None:
    grupo = load_report_group_manifest(_manifest(tmp_path, ""))
    assert grupo.units == ()
    assert "units" not in grupo.to_dict()


@pytest.mark.parametrize("units", ['"units": []', '"units": ["PATOS"]', '"units": ["747530", "747530"]'])
def test_unidades_invalidas(tmp_path: Path, units: str) -> None:
    with pytest.raises(ReportGroupManifestError):
        load_report_group_manifest(_manifest(tmp_path, ", " + units))
