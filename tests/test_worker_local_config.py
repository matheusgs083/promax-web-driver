import io
from pathlib import Path
import sys
import tempfile
from unittest.mock import Mock

from workers.promax_client import PromaxApiUnavailable
from workers.promax_runner import PromaxRunnerConfig, PromaxRunner
from workers.promax_worker import PROJECT_ROOT, PromaxWorker, WorkerConfig


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


def test_worker_runner_prioritizes_botzapfechamento_category_over_stale_profile():
    runner_config = PromaxRunnerConfig.from_values(
        driver_dir=PROJECT_ROOT,
        python_executable=sys.executable,
    )

    command = PromaxRunner(runner_config).build_command(
        {
            "id": "job-fechamento-stale-profile",
            "job_type": "relatorios",
            "payload": {
                "profile": "relatorios",
                "category": "botzapfechamento",
                "groups": [{"category": "botzapfechamento", "routines": ["0513"]}],
                "units": ["0640001"],
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
    assert command[command.index("--perfil") + 1] == "botzapfechamento"
    assert command[command.index("--rotinas") + 1] == "0513"


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


def test_worker_runner_builds_standalone_030322_with_routine_date():
    runner_config = PromaxRunnerConfig.from_values(
        driver_dir=PROJECT_ROOT,
        python_executable=sys.executable,
    )

    command = PromaxRunner(runner_config).build_command(
        {
            "id": "job-prestacao-1",
            "job_type": "fechamento_mapa",
            "payload": {
                "operation": "fechamento-mapa",
                "mapa": "94041",
                "filial": "3",
                "data_rotina": "2026-09-03",
                "modo": "030322",
                "fechar_ao_falhar": True,
                "units": ["2210003"],
            },
        }
    )

    assert command[command.index("--modo") + 1] == "030322"
    assert command[command.index("--data") + 1] == "2026-09-03"
    assert command[command.index("--unidade") + 1] == "2210003"
    assert "--fechar-ao-falhar" in command


def test_partial_result_is_retained_and_retried_after_temporary_api_failure():
    client = Mock()
    client.sync_financeiro_fechamento_mapa.side_effect = PromaxApiUnavailable(
        "temporariamente fora"
    )
    worker = PromaxWorker(
        config=WorkerConfig(
            api_url="http://localhost:8080",
            token="token",
            worker_id="worker",
            driver_dir="C:/driver",
            python_executable="C:/driver/python.exe",
            lease_seconds=960,
        ),
        client=client,
        runner=Mock(),
        visual_lock=Mock(),
    )
    job = {
        "id": "job-fechamento",
        "lease_token": "lease",
        "job_type": "fechamento_mapa",
        "payload": {
            "operation": "fechamento-mapa",
            "mapa": "94041",
            "filial": "3",
            "data": "2026-09-05",
        },
    }
    worker._pending_partial_results["job-fechamento"] = []

    worker._handle_partial_result_event(
        job,
        "job-fechamento",
        "lease",
        {
            "event": "promax_partial_result",
            "sync_scope": "030302",
            "routine": "030302",
            "metadata": {"resultado_fisico": {"status": "SUCESSO"}},
        },
    )

    assert len(worker._pending_partial_results["job-fechamento"]) == 1
    client.sync_financeiro_fechamento_mapa.side_effect = None
    client.sync_financeiro_fechamento_mapa.return_value = {
        "ok": True,
        "conferencia": {"itens": 3, "itens_gravados": 3},
    }

    worker._sync_pending_partial_results(job, "job-fechamento", "lease")

    assert worker._pending_partial_results["job-fechamento"] == []


def test_worker_runner_terminates_process_after_maximum_runtime():
    class HangingProcess:
        def __init__(self) -> None:
            self.pid = 9876
            self.stdout = io.StringIO("")
            self.stderr = io.StringIO("")
            self.done = False

        def poll(self):
            return 1 if self.done else None

        def wait(self, timeout=None):
            self.done = True
            return 1

        def kill(self):
            self.done = True

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        driver_dir = root / "driver"
        driver_dir.mkdir()
        (driver_dir / "cli.py").write_text("", encoding="ascii")
        python_executable = root / "python.exe"
        python_executable.write_bytes(b"")
        config = PromaxRunnerConfig.from_values(
            driver_dir=driver_dir,
            python_executable=python_executable,
            heartbeat_interval_seconds=1,
            control_interval_seconds=1,
            max_runtime_seconds=1,
        )
        taskkill = Mock()
        ticks = iter([0.0, 2.0, 3.0, 4.0])
        runner = PromaxRunner(
            config,
            popen_factory=Mock(return_value=HangingProcess()),
            monotonic=lambda: next(ticks, 5.0),
            taskkill_runner=taskkill,
            platform="nt",
        )

        result = runner.run(
            {"id": "job-timeout", "payload": {"category": "adf", "routines": ["030237"]}},
            on_line=lambda *_args: None,
            heartbeat=lambda: None,
            cancel_requested=lambda: False,
        )

    assert result.status == "failed"
    assert "tempo limite" in str(result.error).lower()
    taskkill.assert_called()
