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
