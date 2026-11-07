"""Corrupt cooperative fixture records must never prove writer drain."""
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from app.services.paper_writer_fixture import (
    close_fixture_writers,
    fixture_writer_operation,
    provision_fixture_writers,
)
from test_durable_partial_shutdown import fixture


@pytest.mark.parametrize("writer,incarnation,acked,payload", [
    ("manual", "one", None, "a" * 64),
    ("foreign", "one", 1, "a" * 64),
    ("manual", "stale", 1, "a" * 64),
    ("manual", "one", 1, "invalid"),
])
def test_corrupt_or_foreign_operation_cannot_prove_drain(tmp_path, writer, incarnation, acked, payload):
    path, _ = fixture(tmp_path)
    provision_fixture_writers(path, {"manual": "one"})
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO writer_operations VALUES(?,?,?,?,?)",
                   ("op", writer, incarnation, acked, payload))
    with pytest.raises(ValueError, match="operation"):
        close_fixture_writers(path, {"manual": "one"})
    with pytest.raises(ValueError, match="operation"):
        fixture_writer_operation(path, writer="manual", incarnation="one", operation="op",
                                 payload="a" * 64, acknowledge=True)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT stopped FROM control").fetchall() == [(0,)]
        assert db.execute("SELECT acked FROM writer_operations").fetchone() == (acked,)


@pytest.mark.parametrize("damage", [None, "null-ack", "foreign"])
def test_windows_drain_never_advances_on_corrupt_operations(tmp_path, damage):
    path, _ = fixture(tmp_path)
    provision_fixture_writers(path, {"manual": "one"})
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO writer_operations VALUES(?,?,?,?,?)",
                   ("op", "foreign" if damage == "foreign" else "manual", "one",
                    None if damage == "null-ack" else 1, "a" * 64))
    bridge = tmp_path / "drain.py"
    bridge.write_text(
        "import sys\nfrom app.services.paper_writer_fixture import close_fixture_writers\n"
        "result=close_fixture_writers(sys.argv[1],{'manual':'one'})\n"
        "sys.exit(0 if result['status']=='DRAINED_FIXTURE_ONLY' else 2)\n", encoding="utf-8")
    module = Path(__file__).resolve().parents[1] / "scripts/windows/Atlas-PaperShutdown-Fixture.psm1"
    # Following steps only leave synthetic markers, never stop any process.
    marker = tmp_path / "following.txt"
    command = (f"Import-Module '{module}';"
               f"$r=Invoke-AtlasPaperShutdownFixture {{$true}} "
               f"{{& '{sys.executable}' '{bridge}' '{path}';$LASTEXITCODE -eq 0}} "
               f"{{Add-Content -LiteralPath '{marker}' -Value 'liquidate';$true}} "
               f"{{Add-Content -LiteralPath '{marker}' -Value 'report';$true}} "
               f"{{Add-Content -LiteralPath '{marker}' -Value 'stop';$true}};"
               "$r.outcome")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command],
                            capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
    assert ("INCOMPLETE" if damage else "COMPLETE_FIXTURE_ONLY") in result.stdout
    assert marker.exists() is (damage is None)
    if marker.exists():
        assert marker.read_text().splitlines() == ["liquidate", "report", "stop"]
