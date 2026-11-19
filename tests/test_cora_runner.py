from pathlib import Path
import sys

from workers.promax_runner import PromaxRunner, PromaxRunnerConfig


def test_runner_dispatches_cora_job_to_isolated_subproject(tmp_path: Path) -> None:
    (tmp_path / "cli.py").write_text("", encoding="utf-8")
    (tmp_path / "cora-web-driver").mkdir()
    (tmp_path / "cora-web-driver" / "cli.py").write_text("", encoding="utf-8")
    config = PromaxRunnerConfig.from_values(
        driver_dir=tmp_path,
        python_executable=sys.executable,
    )

    command = PromaxRunner(config).build_command(
        {
            "job_id": "cora-123",
            "job_type": "cora_consulta",
            "payload": {"site": "cora", "operation": "consulta"},
        }
    )

    assert command[1:] == [
        str(tmp_path / "cora-web-driver" / "cli.py"),
        "executar",
        "--operacao",
        "consulta",
        "--job-id",
        "cora-123",
    ]


def _runner(tmp_path: Path) -> PromaxRunner:
    (tmp_path / "cli.py").write_text("", encoding="utf-8")
    (tmp_path / "cora-web-driver").mkdir(exist_ok=True)
    (tmp_path / "cora-web-driver" / "cli.py").write_text("", encoding="utf-8")
    return PromaxRunner(PromaxRunnerConfig.from_values(driver_dir=tmp_path, python_executable=sys.executable))


def test_grade_de_estoque_do_cora_passa_cada_unidade_de_entrega(tmp_path: Path) -> None:
    command = _runner(tmp_path).build_command(
        {
            "job_id": "est-1",
            "job_type": "relatorios",
            "payload": {"category": "cora_estoque", "units": ["747530", "747548"]},
        }
    )

    assert command[2:] == [
        "executar", "--operacao", "grade_estoque", "--job-id", "est-1",
        "--filial", "747530", "--filial", "747548",
    ]


def test_grade_de_estoque_sem_unidade_exporta_todas(tmp_path: Path) -> None:
    command = _runner(tmp_path).build_command(
        {"job_id": "est-2", "job_type": "cora_estoque", "payload": {"site": "cora", "operation": "cora_estoque"}}
    )

    assert "--filial" not in command
    assert command[2:5] == ["executar", "--operacao", "grade_estoque"]


def test_critica_continua_igual(tmp_path: Path) -> None:
    command = _runner(tmp_path).build_command(
        {"job_id": "c-1", "job_type": "relatorios", "payload": {"category": "cora_critica", "units": ["0640001"]}}
    )

    assert command[2:] == ["executar", "--operacao", "critica", "--job-id", "c-1"]


def test_unidade_invalida_e_recusada(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ValueError, match="invalida"):
        _runner(tmp_path).build_command(
            {"job_id": "e", "job_type": "cora_estoque", "payload": {"category": "cora_estoque", "units": ["PATOS"]}}
        )
