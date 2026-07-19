from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable

from core.config.project_paths import REPORT_GROUPS_DIR


GROUP_FIELDS = {"key", "name", "description", "routines"}
ROUTINE_FIELDS = {"id", "name", "output_folders"}
GROUP_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
ROUTINE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_]*$")


class ReportGroupManifestError(ValueError):
    """Raised when a report group manifest is invalid or unsafe."""


@dataclass(frozen=True)
class ReportRoutine:
    id: str
    name: str
    output_folders: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "output_folders": list(self.output_folders),
        }


@dataclass(frozen=True)
class ReportGroup:
    key: str
    name: str
    description: str
    routines: tuple[ReportRoutine, ...]

    @property
    def routine_ids(self) -> tuple[str, ...]:
        return tuple(routine.id for routine in self.routines)

    @property
    def output_folders(self) -> tuple[str, ...]:
        return tuple(
            folder
            for routine in self.routines
            for folder in routine.output_folders
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "routines": [routine.to_dict() for routine in self.routines],
        }


def _manifest_error(path: Path, message: str) -> ReportGroupManifestError:
    return ReportGroupManifestError(f"Manifest invalido em {path}: {message}")


def _require_non_empty_string(value: object, *, path: Path, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _manifest_error(path, f"{field} deve ser uma string nao vazia")
    if value != value.strip():
        raise _manifest_error(path, f"{field} nao pode ter espacos nas extremidades")
    return value


def _validate_output_folder(value: object, *, path: Path, field: str) -> str:
    folder = _require_non_empty_string(value, path=path, field=field)
    windows_path = PureWindowsPath(folder)
    posix_path = PurePosixPath(folder)
    if (
        windows_path.is_absolute()
        or windows_path.drive
        or posix_path.is_absolute()
        or any(part in {"", ".", ".."} for part in windows_path.parts)
        or any(part in {"", ".", ".."} for part in posix_path.parts)
    ):
        raise _manifest_error(path, f"{field} deve ser um caminho relativo seguro")
    return folder


def _literal_report_group(path: Path) -> object:
    try:
        source = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise _manifest_error(path, f"falha de leitura: {exc}") from exc

    try:
        module = ast.parse(source, filename=str(path), mode="exec")
    except SyntaxError as exc:
        raise _manifest_error(path, f"erro de sintaxe na linha {exc.lineno}") from exc

    if len(module.body) != 1:
        raise _manifest_error(
            path,
            "deve conter somente a atribuicao literal REPORT_GROUP",
        )

    statement = module.body[0]
    if (
        not isinstance(statement, ast.Assign)
        or len(statement.targets) != 1
        or not isinstance(statement.targets[0], ast.Name)
        or statement.targets[0].id != "REPORT_GROUP"
    ):
        raise _manifest_error(
            path,
            "deve conter somente a atribuicao literal REPORT_GROUP",
        )

    try:
        return ast.literal_eval(statement.value)
    except (ValueError, TypeError, SyntaxError) as exc:
        raise _manifest_error(path, "REPORT_GROUP deve ser um literal Python") from exc


def _validate_routines(raw_routines: object, *, path: Path) -> tuple[ReportRoutine, ...]:
    if not isinstance(raw_routines, list) or not raw_routines:
        raise _manifest_error(path, "routines deve ser uma lista nao vazia")

    routines: list[ReportRoutine] = []
    routine_ids: set[str] = set()
    routine_names: set[str] = set()
    output_folders: set[str] = set()

    for index, raw_routine in enumerate(raw_routines):
        prefix = f"routines[{index}]"
        if not isinstance(raw_routine, dict):
            raise _manifest_error(path, f"{prefix} deve ser um dicionario")
        if set(raw_routine) != ROUTINE_FIELDS:
            raise _manifest_error(
                path,
                f"{prefix} deve conter exatamente {sorted(ROUTINE_FIELDS)}",
            )

        routine_id = _require_non_empty_string(
            raw_routine["id"],
            path=path,
            field=f"{prefix}.id",
        )
        if not ROUTINE_ID_PATTERN.fullmatch(routine_id):
            raise _manifest_error(path, f"{prefix}.id possui identificador invalido")
        if routine_id in routine_ids:
            raise _manifest_error(path, f"rotina duplicada: {routine_id}")
        routine_ids.add(routine_id)

        name = _require_non_empty_string(
            raw_routine["name"],
            path=path,
            field=f"{prefix}.name",
        )
        normalized_name = name.casefold()
        if normalized_name in routine_names:
            raise _manifest_error(path, f"nome de rotina duplicado: {name}")
        routine_names.add(normalized_name)
        raw_folders = raw_routine["output_folders"]
        if not isinstance(raw_folders, list) or not raw_folders:
            raise _manifest_error(
                path,
                f"{prefix}.output_folders deve ser uma lista nao vazia",
            )

        folders: list[str] = []
        for folder_index, raw_folder in enumerate(raw_folders):
            folder = _validate_output_folder(
                raw_folder,
                path=path,
                field=f"{prefix}.output_folders[{folder_index}]",
            )
            if folder in output_folders:
                raise _manifest_error(path, f"output_folder duplicado: {folder}")
            output_folders.add(folder)
            folders.append(folder)

        routines.append(
            ReportRoutine(
                id=routine_id,
                name=name,
                output_folders=tuple(folders),
            )
        )

    return tuple(routines)


def load_report_group_manifest(path: str | Path) -> ReportGroup:
    path = Path(path)
    raw_group = _literal_report_group(path)
    if not isinstance(raw_group, dict):
        raise _manifest_error(path, "REPORT_GROUP deve ser um dicionario")
    if set(raw_group) != GROUP_FIELDS:
        raise _manifest_error(
            path,
            f"REPORT_GROUP deve conter exatamente {sorted(GROUP_FIELDS)}",
        )

    key = _require_non_empty_string(raw_group["key"], path=path, field="key")
    if not GROUP_KEY_PATTERN.fullmatch(key):
        raise _manifest_error(path, "key possui identificador invalido")
    if path.stem != key:
        raise _manifest_error(path, f"key deve corresponder ao arquivo {path.stem}.py")

    return ReportGroup(
        key=key,
        name=_require_non_empty_string(raw_group["name"], path=path, field="name"),
        description=_require_non_empty_string(
            raw_group["description"],
            path=path,
            field="description",
        ),
        routines=_validate_routines(raw_group["routines"], path=path),
    )


def load_report_groups(directory: str | Path = REPORT_GROUPS_DIR) -> dict[str, ReportGroup]:
    directory = Path(directory)
    if not directory.is_dir():
        raise ReportGroupManifestError(
            f"Diretorio de grupos de relatorios nao encontrado: {directory}"
        )

    manifest_paths = sorted(directory.glob("*.py"), key=lambda path: path.name.lower())
    if not manifest_paths:
        raise ReportGroupManifestError(
            f"Nenhum manifest de grupo encontrado em: {directory}"
        )

    groups: dict[str, ReportGroup] = {}
    for path in manifest_paths:
        group = load_report_group_manifest(path)
        if group.key in groups:
            raise _manifest_error(path, f"grupo duplicado: {group.key}")
        groups[group.key] = group
    return groups


def select_report_group(
    groups: dict[str, ReportGroup],
    group_key: str,
    routine_ids: Iterable[str] | None = None,
) -> tuple[ReportGroup, tuple[ReportRoutine, ...]]:
    try:
        group = groups[group_key]
    except KeyError as exc:
        available = ", ".join(groups)
        raise ValueError(
            f"Grupo de relatorios desconhecido: {group_key}. Disponiveis: {available}"
        ) from exc

    requested = tuple(routine_ids or ())
    if not requested:
        return group, group.routines

    duplicated = sorted(
        routine_id
        for routine_id in set(requested)
        if requested.count(routine_id) > 1
    )
    if duplicated:
        raise ValueError("Rotinas duplicadas na selecao: " + ", ".join(duplicated))

    routines_by_id = {routine.id: routine for routine in group.routines}
    invalid = [routine_id for routine_id in requested if routine_id not in routines_by_id]
    if invalid:
        raise ValueError(
            f"Rotinas fora do grupo {group.key}: " + ", ".join(invalid)
        )
    return group, tuple(routines_by_id[routine_id] for routine_id in requested)


def report_group_catalog(
    groups: dict[str, ReportGroup] | None = None,
) -> dict[str, object]:
    loaded_groups = groups if groups is not None else load_report_groups()
    return {
        "report_groups": [
            group.to_dict()
            for group in loaded_groups.values()
        ]
    }
