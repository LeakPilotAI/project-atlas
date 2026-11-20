"""Offline refusals for the resource fixture, without Windows or listener calls."""
import builtins
import sys

import personal_nonfinancial_resource_host as host
import pytest


def test_empty_session_cannot_read_journals_or_manufacture_financial_state(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No observation/financial file reads")

    monkeypatch.setattr(builtins, "open", forbidden)
    state = {"status": "DISCONNECTED", "financial_writers": False}
    session = host.EmptySession(lambda: dict(state))
    assert session.snapshot() == state
    assert session.history()["sessions"] == []
    assert session.history()["status"] == "UNAVAILABLE"
    assert session.research()["status"] == session.diagnostics()["status"] == "UNAVAILABLE"
    assert not hasattr(session, "root")


@pytest.mark.parametrize("seconds", ["0", "121", "-1"])
def test_invalid_duration_refuses_before_candidate_or_listener_access(monkeypatch, seconds):
    monkeypatch.setattr(sys, "argv", ["fixture", "--candidate", "SYNTHETIC", "--seconds", seconds])
    monkeypatch.setattr(host, "metrics", lambda: pytest.fail("Native metrics before admission"))
    with pytest.raises(ValueError, match="BOUNDED_NONFINANCIAL_HOST_REQUIRED"):
        host.main()


def test_foreign_interpreter_refuses_before_importing_installed_modules(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["fixture", "--candidate", str(tmp_path / "candidate")])
    monkeypatch.setattr(host, "metrics", lambda: pytest.fail("Native metrics before admission"))
    with pytest.raises(ValueError, match="EXACT_INSTALLED_INTERPRETER_REQUIRED"):
        host.main()


def test_mixed_interpreter_base_refuses_before_service_construction(monkeypatch, tmp_path):
    candidate = tmp_path / "candidate"
    monkeypatch.setattr(sys, "argv", ["fixture", "--candidate", str(candidate)])
    monkeypatch.setattr(sys, "executable", str(candidate / "python/python.exe"))
    monkeypatch.setattr(sys, "base_prefix", str(tmp_path / "foreign-python"))
    monkeypatch.setattr(host, "metrics", lambda: pytest.fail("Native metrics before admission"))
    with pytest.raises(ValueError, match="EXACT_INSTALLED_BASE_REQUIRED"):
        host.main()


@pytest.mark.parametrize("field,value", [
    ("working_set_bytes", 512 * 1024**2 + 1), ("private_bytes", 512 * 1024**2 + 1),
    ("working_set_bytes", -1), ("working_set_bytes", True),
    ("cpu_seconds", 15.001), ("cpu_seconds", True), ("cpu_seconds", float("nan")),
    ("cpu_seconds", float("inf")),
])
def test_limits_include_bootstrap_cpu_and_refuse_invalid_measurements(field, value):
    sample = {"working_set_bytes": 1024, "private_bytes": 1024, "cpu_seconds": 1.0}
    sample[field] = value
    with pytest.raises(ValueError, match="NONFINANCIAL_RESOURCE_LIMIT"):
        host.verify_resource_limits(sample)


def test_resource_limit_boundary_and_missing_measurement():
    host.verify_resource_limits({"working_set_bytes": 512 * 1024**2, "private_bytes": 512 * 1024**2, "cpu_seconds": 15.0})
    with pytest.raises(ValueError, match="MEASUREMENT_INCOMPLETE"):
        host.verify_resource_limits({"cpu_seconds": 1.0})
