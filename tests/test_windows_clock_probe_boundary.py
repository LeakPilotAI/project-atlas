"""Offline process-boundary checks; no native Windows, registry or clock calls."""

import base64
import json
import subprocess
from types import SimpleNamespace

import pytest

from scripts.observation_runtime import personal_windows_clock as clock


def probe():
    # Bypass native construction only in this explicitly synthetic unit test.
    value = clock._WindowsProbe.__new__(clock._WindowsProbe)
    value.system = r"D:\synthetic-windows\System32"
    return value


def response(stdout=b"{}", *, code=0, stderr=b""):
    return SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)


def test_probe_launch_is_exact_bounded_read_only_and_preserves_parent_environment(monkeypatch):
    monkeypatch.setenv("PSModulePath", "SYNTHETIC_UNTRUSTED_MODULE_DIRECTORY")
    calls = []
    expected = {"native": True, "service": "Running", "configured_source": "SYNTHETIC"}

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return response(json.dumps(expected).encode())

    monkeypatch.setattr(clock.subprocess, "run", run)
    assert probe().read() == expected
    assert len(calls) == 1
    args, options = calls[0]
    assert args[0] == r"D:\synthetic-windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    assert args[1:4] == ["-NoProfile", "-NonInteractive", "-EncodedCommand"]
    script = base64.b64decode(args[4]).decode("utf-16le")
    assert "/query /status /verbose" in script
    assert "Get-AuthenticodeSignature" in script
    assert script.count("Get-ItemProperty -LiteralPath $path") == 2
    assert "CLOCK_OBSERVATION_CHANGED" in script
    for forbidden in ("RunAs", "Start-Service", "Restart-Service", "Set-ItemProperty", "/resync", "/config", "Set-Date"):
        assert forbidden not in script
    assert options["timeout"] == 12 and options["capture_output"] is True
    assert options["check"] is False
    assert options["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert options["env"]["PSModulePath"] == r"D:\synthetic-windows\System32\WindowsPowerShell\v1.0\Modules"
    assert clock.os.environ["PSModulePath"] == "SYNTHETIC_UNTRUSTED_MODULE_DIRECTORY"


@pytest.mark.parametrize("error", [
    b"Requested registry access is not allowed",
    b"CLOCK_STATUS_QUERY_FAILED: access denied",
    b"CLOCK_OBSERVATION_CHANGED",
])
def test_read_refusal_never_retries_elevates_or_returns_invented_evidence(monkeypatch, error):
    calls = []

    def run(*args, **kwargs):
        calls.append(1)
        return response(b'{"native":true}', code=1, stderr=error)

    monkeypatch.setattr(clock.subprocess, "run", run)
    with pytest.raises(ValueError, match="CLOCK_NATIVE_QUERY_REFUSED"):
        probe().read()
    assert calls == [1]


def test_oversized_native_output_refuses_before_decoding(monkeypatch):
    monkeypatch.setattr(clock.subprocess, "run", lambda *a, **k: response(b" " * 65537))
    with pytest.raises(ValueError, match="CLOCK_NATIVE_QUERY_REFUSED"):
        probe().read()


@pytest.mark.parametrize("fault", ["timeout", "spawn_denied"])
def test_process_failure_has_no_retry_or_permission_repair(monkeypatch, fault):
    calls = []

    def run(*args, **kwargs):
        calls.append(1)
        if fault == "timeout":
            raise subprocess.TimeoutExpired("SYNTHETIC_ONLY", 12)
        raise PermissionError("SYNTHETIC_PROCESS_DENIED")

    monkeypatch.setattr(clock.subprocess, "run", run)
    with pytest.raises((subprocess.TimeoutExpired, PermissionError)):
        probe().read()
    assert calls == [1]


@pytest.mark.parametrize("data", [b"SYNTHETIC_NOT_JSON", b"\xff"])
def test_malformed_native_output_is_not_accepted(monkeypatch, data):
    monkeypatch.setattr(clock.subprocess, "run", lambda *a, **k: response(data))
    with pytest.raises(ValueError):
        probe().read()
