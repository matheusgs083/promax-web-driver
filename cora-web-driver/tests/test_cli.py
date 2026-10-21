import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from cli import main


def test_health_reads_cora_configuration(monkeypatch, capsys):
    monkeypatch.setenv("CORA_URL", "https://cora.example.test/")
    monkeypatch.setenv("CORA_HEADLESS", "1")
    monkeypatch.setattr(sys, "argv", ["cli.py", "health"])
    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"site": "cora", "url": "https://cora.example.test/", "headless": True}


def test_unknown_operation_fails_explicitly(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["cli.py", "executar", "--operacao", "pedidos"])
    assert main() == 30
    assert "não implementada" in json.loads(capsys.readouterr().out)["message"]
