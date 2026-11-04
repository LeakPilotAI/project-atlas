"""V6 contracts: synthetic handles only; never installed execution."""

import ast
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts.acceptance_harness_v6 import worker_log

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "scripts/acceptance_harness_v6"


@pytest.fixture
def publisher(tmp_path, monkeypatch):
    root = tmp_path / "case"
    root.mkdir()
    packet = {"pid": 1234, "created": 1000, "nonce": "a" * 32}
    (root / "outer-launch.json").write_text(json.dumps(packet))
    streams = [
        (root / f"worker-{name}.log").open("x", encoding="utf-8")
        for name in ("stdout", "stderr")
    ]
    faults = {}
    closed = []

    class Kernel:
        @staticmethod
        def GetCurrentProcess():
            return 99

        @staticmethod
        def CreateFileW(*_):
            return 11

        @staticmethod
        def GetFileInformationByHandle(handle, out):
            info = out._obj
            info.attrs = 16 if handle == 11 else faults.get("attrs", 128)
            info.links = faults.get("links", 1)
            info.volume, info.index_hi, info.index_lo = 1, 2, handle
            info.created.dwLowDateTime = faults.get("created", 1001)
            return True

        @staticmethod
        def CloseHandle(handle):
            closed.append(handle)
            return True

    # Function attributes mirror ctypes without invoking actual Windows APIs.
    class Native:
        k = Kernel

        @staticmethod
        def lifetime(_):
            return faults.get("pid", 1234), faults.get("process_created", 1000)

        @staticmethod
        def check(value):
            if not value:
                raise OSError("native fixture refusal")
            return value

    monkeypatch.setattr(worker_log, "NativeQueries", Native)
    yield root, streams, faults, closed
    for stream in streams:
        stream.close()


def test_actual_stream_handles_bind_atomically_to_original_launch(publisher):
    root, streams, _, closed = publisher
    packet = worker_log.publish_worker_logs(root, *streams)
    assert json.loads((root / "worker-logs.json").read_bytes()) == packet
    assert packet["pid"] == 1234 and packet["created"] == 1000
    assert set(packet["files"]) == {"stdout", "stderr"}
    assert packet["root_id"] == [1, 2, 11] and closed == [11]
    assert not (root / "worker-logs.pending").exists()
    assert (root / "worker-logs.ready").read_bytes() == b"1"
    streams[0].write("still writable\n")
    streams[0].flush()
    assert (root / "worker-stdout.log").read_text() == "still writable\n"


@pytest.mark.parametrize(
    "fault,value,reason",
    [
        ("pid", 1235, "LOG_ORIGINAL_LAUNCH_IDENTITY_MISMATCH"),
        ("process_created", 999, "LOG_ORIGINAL_LAUNCH_IDENTITY_MISMATCH"),
        ("attrs", 1024, "LOG_NATIVE_IDENTITY_REQUIRED"),
        ("attrs", 16, "LOG_NATIVE_IDENTITY_REQUIRED"),
        ("links", 2, "LOG_NATIVE_IDENTITY_REQUIRED"),
        ("created", 999, "LOG_NATIVE_IDENTITY_REQUIRED"),
    ],
)
def test_mismatched_launch_or_file_cannot_publish(publisher, fault, value, reason):
    root, streams, faults, _ = publisher
    faults[fault] = value
    with pytest.raises(ValueError, match=reason):
        worker_log.publish_worker_logs(root, *streams)
    assert not (root / "worker-logs.json").exists()


def test_wrong_stream_path_refuses_and_directory_handle_closes(publisher):
    root, streams, _, closed = publisher
    with (
        (root / "unapproved.log").open("x") as other,
        pytest.raises(ValueError, match="EXACT_WORKER_LOG_PATH_REQUIRED"),
    ):
        worker_log.publish_worker_logs(root, other, streams[1])
    assert closed == [11] and not (root / "worker-logs.json").exists()


def test_existing_declaration_is_never_replaced(publisher):
    root, streams, _, _ = publisher
    target = root / "worker-logs.json"
    target.write_bytes(b"original evidence")
    with pytest.raises(FileExistsError):
        worker_log.publish_worker_logs(root, *streams)
    assert target.read_bytes() == b"original evidence"


def test_failed_durable_flush_cannot_publish(publisher, monkeypatch):
    root, streams, _, closed = publisher

    def fail(_):
        raise OSError("injected flush failure")

    monkeypatch.setattr(worker_log.os, "fsync", fail)
    with pytest.raises(OSError, match="injected flush failure"):
        worker_log.publish_worker_logs(root, *streams)
    assert not (root / "worker-logs.json").exists() and closed == [11]


def test_v5_pinned_sources_and_failure_are_immutable():
    root = (
        REPO / "logs/diagnostics/qd-final-installed-nonfinancial-acceptance-v5-20261103"
    )
    for row in json.loads((root / "source-manifest.json").read_bytes())["files"]:
        raw = (REPO / row["path"]).read_bytes()
        assert (
            len(raw) == row["bytes"]
            and hashlib.sha256(raw).hexdigest() == row["sha256"]
        )
    result = json.loads((root / "supervisor-result.json").read_bytes())
    assert (
        result["status"] == "REFUSED_PRESERVE_EVIDENCE"
        and result["authorization_consumed"]
    )
    assert result["forced_job_cleanup"] and result["worker_exit"] is None


def test_v6_changes_only_bootstrap_and_preserves_whole_v5_worker_lifecycle():
    old = (REPO / "scripts/acceptance_harness_v5/worker.py").read_text()
    new = (SOURCE / "worker.py").read_text()
    assert ast.dump(ast.parse(old.split("\nimport ctypes\n", 1)[1])) == ast.dump(
        ast.parse(new.split("\nimport ctypes\n", 1)[1])
    )
    assert new.index("publish_worker_logs(e, sys.stdout, sys.stderr)") < new.index(
        "from gate import validate_scope"
    )
    assert 'encoding="utf-8"' in new
    assert "from scripts.acceptance_harness_v5.ownership import Ownership" in new


@pytest.mark.parametrize(
    "function",
    [
        "New-OwnedSuspended",
        "Creation",
        "Duplicate-ToWorker",
        "Active-JobCount",
        "Job-Pids",
        "Account-Scope",
        "Create-Json",
    ],
)
def test_original_native_ownership_job_resource_and_publication_functions_unchanged(
    function,
):
    old = (REPO / "scripts/acceptance_harness_v5/supervise.ps1").read_text()
    new = (SOURCE / "supervise.ps1").read_text().replace("V6", "V5")

    def definition(text):
        tail = text.split("function " + function, 1)[1]
        return tail.split("\nfunction ", 1)[0].split("\n$parent=", 1)[0]

    assert definition(old) == definition(new)


@pytest.mark.parametrize("entry", ["worker.py", "supervise.ps1"])
def test_v6_entries_default_refuse_without_native_or_log_actions(entry):
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("ATLAS_AUTH_", "ATLAS_V5_"))
    }
    if entry.endswith(".py"):
        import sys

        command = [sys.executable, "-I", "-B", str(SOURCE / entry)]
        expected = b"FRESH_EXPLICIT_OPERATOR_APPROVAL_REQUIRED_NO_NATIVE_ACTION"
    else:
        command = [
            str(
                Path(os.environ["SystemRoot"])
                / "System32/WindowsPowerShell/v1.0/powershell.exe"
            ),
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(SOURCE / entry),
        ]
        expected = b"FRESH_EXPLICIT_V6_APPROVAL_REQUIRED_NO_NATIVE_ACTION"
    result = subprocess.run(
        command, capture_output=True, env=env, timeout=10, check=False
    )
    assert result.returncode != 0 and expected in result.stderr


def test_failed_dispose_attempts_all_handles_and_never_claims_success():
    ps = str(
        Path(os.environ["SystemRoot"])
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    script = """
Import-Module './scripts/acceptance_harness_v6/WorkerLog.psm1' -Force
$global:closeEvents=[Collections.Generic.List[string]]::new()
$bad=[pscustomobject]@{};$bad|Add-Member ScriptMethod Dispose {$global:closeEvents.Add('first');throw 'injected disposal failure'}
$good=[pscustomobject]@{};$good|Add-Member ScriptMethod Dispose {$global:closeEvents.Add('second')}
$state=@{Closed=$false;File=$bad;Declaration=$good;Leases=[Collections.Generic.List[IntPtr]]::new();Kernel=$null;Refused=$false;Reason=$null}
try{Close-AtlasWorkerLogTail $state;throw 'UNEXPECTED_SUCCESS'}catch{if($_.Exception.Message -notmatch 'LOG_HANDLE_CLOSE_INCOMPLETE'){throw}}
if($state.Closed -or -not $state.Refused -or ($global:closeEvents -join ',') -cne 'first,second'){throw 'CLOSE_FAILURE_NOT_SAFE'}
'ALL_DISPOSALS_ATTEMPTED_NO_FALSE_SUCCESS'
"""
    result = subprocess.run(
        [ps, "-NoProfile", "-NonInteractive", "-Command", script],
        cwd=REPO,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert (
        result.returncode == 0
        and b"ALL_DISPOSALS_ATTEMPTED_NO_FALSE_SUCCESS" in result.stdout
    ), result.stderr
