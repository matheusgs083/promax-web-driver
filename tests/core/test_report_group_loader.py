from __future__ import annotations

import json

import pytest

from core.config.report_group_loader import (
    ReportGroupManifestError,
    load_report_group_manifest,
    load_report_groups,
    report_group_catalog,
    select_report_group,
)


EXPECTED_GROUPS = {
    "adf",
    "bot_zap",
    "estoque",
    "fluxo_caixa",
    "giro",
    "inadimplencia",
    "obz",
    "outros",
}


def test_loads_all_repository_report_groups_without_importing_manifests():
    groups = load_report_groups()

    assert set(groups) == EXPECTED_GROUPS
    assert groups["outros"].routine_ids == (
        "020220_AUDITOOL",
        "020220_RECOLHAS",
    )
    assert groups["fluxo_caixa"].output_folders == (
        "140506",
        "120606",
        "020502 fluxo de caixa",
        "150501 fluxo de caixa",
    )
    assert groups["bot_zap"].output_folders == (
        "120601 bot",
        "020220 bot",
        "0105070402 bot",
        "030206 bot",
    )


def test_selects_requested_routines_in_requested_order():
    groups = load_report_groups()

    group, routines = select_report_group(
        groups,
        "fluxo_caixa",
        ["120606", "140506"],
    )

    assert group.key == "fluxo_caixa"
    assert [routine.id for routine in routines] == ["120606", "140506"]


def test_rejects_non_literal_manifest_without_executing_it(tmp_path):
    marker = tmp_path / "executed.txt"
    manifest = tmp_path / "malicioso.py"
    manifest.write_text(
        "REPORT_GROUP = __import__('pathlib').Path("
        + repr(str(marker))
        + ").write_text('executed')\n",
        encoding="utf-8",
    )

    with pytest.raises(ReportGroupManifestError, match="literal Python"):
        load_report_group_manifest(manifest)

    assert not marker.exists()


def test_rejects_duplicate_routine_ids(tmp_path):
    manifest = tmp_path / "duplicado.py"
    manifest.write_text(
        """
REPORT_GROUP = {
    "key": "duplicado",
    "name": "Duplicado",
    "description": "Teste",
    "routines": [
        {"id": "020220", "name": "A", "output_folders": ["A"]},
        {"id": "020220", "name": "B", "output_folders": ["B"]},
    ],
}
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ReportGroupManifestError, match="rotina duplicada"):
        load_report_group_manifest(manifest)


def test_catalog_is_json_serializable():
    catalog = report_group_catalog()

    encoded = json.dumps(catalog)

    assert '"report_groups"' in encoded
