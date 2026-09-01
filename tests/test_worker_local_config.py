from pathlib import Path
import sys

from workers.promax_runner import PromaxRunnerConfig, PromaxRunner
from workers.promax_worker import PROJECT_ROOT, WorkerConfig


def test_worker_defaults_to_current_promax_web_driver(monkeypatch):
    monkeypatch.setenv("PROMAX_API_BASE_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("PROMAX_WORKER_TOKEN", "token")
    monkeypatch.setenv("PROMAX_WORKER_ID", "worker-local")
    monkeypatch.delenv("PROMAX_DRIVER_DIR", raising=False)
    monkeypatch.delenv("PROMAX_PYTHON", raising=False)

    config = WorkerConfig.from_env()

    assert Path(config.driver_dir).resolve() == PROJECT_ROOT
    assert Path(config.python_executable).resolve() == Path(sys.executable).resolve()


def test_worker_runner_uses_local_cli_path():
    runner_config = PromaxRunnerConfig.from_values(
        driver_dir=PROJECT_ROOT,
        python_executable=sys.executable,
    )

    command = PromaxRunner(runner_config).build_command(
        {
            "id": "job-1",
            "job_type": "bot_zap",
            "payload": {
                "profile": "bot_zap",
                "routines": ["030206_BOT"],
                "units": ["0640001"],
                "publish": True,
            },
        }
    )

    assert command[:4] == [
        str(Path(sys.executable).resolve()),
        str(PROJECT_ROOT / "cli.py"),
        "relatorios",
        "--perfil",
    ]
    assert "--job-id" in command
    assert str(PROJECT_ROOT / "cli.py") in command


def test_worker_runner_uses_fechamento_entrypoint_for_botzapfechamento():
    runner_config = PromaxRunnerConfig.from_values(
        driver_dir=PROJECT_ROOT,
        python_executable=sys.executable,
    )

    command = PromaxRunner(runner_config).build_command(
        {
            "id": "job-fechamento-relatorios",
            "job_type": "botzapfechamento",
            "payload": {
                "profile": "botzapfechamento",
                "routines": ["150501"],
                "units": ["2210003"],
                "publish": True,
            },
        }
    )

    assert command[:4] == [
        str(Path(sys.executable).resolve()),
        str(PROJECT_ROOT / "cli.py"),
        "fechamento",
        "--perfil",
    ]
    assert "relatorios" not in command
    assert command[command.index("--job-id") + 1] == "job-fechamento-relatorios"


def test_worker_runner_builds_fechamento_mapa_command():
    runner_config = PromaxRunnerConfig.from_values(
        driver_dir=PROJECT_ROOT,
        python_executable=sys.executable,
    )

    command = PromaxRunner(runner_config).build_command(
        {
            "id": "job-mapa-1",
            "job_type": "fechamento_mapa",
            "payload": {
                "mapa": "93741",
                "units": ["PATOS"],
                "ponto_apoio": "0",
            },
        }
    )

    assert command[:5] == [
        str(Path(sys.executable).resolve()),
        str(PROJECT_ROOT / "cli.py"),
        "fechamento-mapa",
        "--mapa",
        "93741",
    ]
    assert command[command.index("--unidade") + 1] == "PATOS"
    assert command[command.index("--job-id") + 1] == "job-mapa-1"
