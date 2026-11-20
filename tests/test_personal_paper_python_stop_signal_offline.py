"""Windows Python-owned event interoperability with a credentialless PS requester.

Everything is synthetic: zero Atlas runtime, provider, financial records or sockets.
"""
import json
import subprocess
import threading
import uuid
from pathlib import Path

import pytest

from app.services.personal_installed_stop_owner import PersonalInstalledPaperStopOwner
from scripts.observation_runtime.personal_paper_python_stop_signal import (
    InstalledPythonPaperStopSignal, WindowsStopEvents,
)

REQUEST_MODULE = Path(__file__).resolve().parents[1] / "scripts/windows/Atlas-Paper-Owned-Stop-Signal.psm1"


def new_name():
    return "test-" + uuid.uuid4().hex


def dummy_owner(*, accepted=True, outcome_valid=True, crash=False):
    # Deliberately inert, uninitialized instance: never construct/install a
    # financial runtime, broker, account, native ledger or accepted grant.
    owner = object.__new__(PersonalInstalledPaperStopOwner)
    owner._session = "offline-synthetic-python-owner"
    calls = []
    owner.verify_session = lambda: accepted

    def stop(mode):
        calls.append(mode)
        if crash:
            raise OSError("synthetic reply unavailable after dispatch")
        return {"schema": "QD_CONTROL_STOP_V1", "phase": "FINISHED",
                "outcome": {"schema": "QD_AUTO_SHUTDOWN_V1", "mode": mode,
                            "status": "FLATTENED", "position_state": "FLAT",
                            "process_shutdown": "VERIFIED_EXIT",
                            "lanes": {"QUALITY_DIPS": {"state": "ACKNOWLEDGED_FLAT_AND_DRAINED"},
                                      "HYPERLIQUID": {"state": "ACKNOWLEDGED_FLAT_AND_DRAINED"}}}}
    owner.request_stop = stop
    owner.verify_durable_stop_receipt = lambda mode, receipt: outcome_valid
    return owner, calls


def send(name):
    code = ("Import-Module '" + str(REQUEST_MODULE) + "' -Force -ErrorAction Stop; "
            "Request-AtlasPaperOwnedStopSignal -OfflineTestId '" + name + "' | ConvertTo-Json -Compress")
    return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", code],
                          text=True, capture_output=True, timeout=12, check=False)


def test_exact_python_owner_receives_real_cross_process_power_shell_signal_without_secret():
    owner, calls = dummy_owner()
    with InstalledPythonPaperStopSignal(owner=owner, offline_test_id=new_name()) as signal:
        name = signal_name_for_test(signal)
        assert signal.poll(0) == {"status": "NO_STOP_SIGNAL", "financial_flatness_verified": False}
        response = send(name)
        assert response.returncode == 0, response.stderr
        body = json.loads(response.stdout)
        assert body == {"schema": "ATLAS_PAPER_STOP_SIGNAL_REQUEST_V1",
                        "status": "REQUESTED_NOT_VERIFIED", "financial_flatness_verified": False}
        done = signal.poll(1000)
        assert done["phase"] == "FINISHED" and done["outcome"]["status"] == "FLATTENED"
        assert calls == ["SHUTDOWN_FLATTEN"]
        with pytest.raises(ValueError, match="ALREADY_USED_OR_INVALID"):
            signal.poll(0)
        assert calls == ["SHUTDOWN_FLATTEN"]


def signal_name_for_test(signal):
    # The internal name is deliberately not exported as session credentials.
    # Test namespace is a fresh GUID, not a production event.
    assert signal._test_name.startswith("test-")
    return signal._test_name


@pytest.mark.parametrize("bad", [None, object(), "forged", 1])
def test_noninstalled_owner_refused_before_event_creation(bad):
    with pytest.raises(ValueError, match="INSTALLED_OWNER_REQUIRED"):
        InstalledPythonPaperStopSignal(owner=bad, offline_test_id=new_name())


def test_unverified_installed_owner_refused_before_event_creation():
    owner, _ = dummy_owner(accepted=False)
    with pytest.raises(ValueError, match="INSTALLED_OWNER_REQUIRED"):
        InstalledPythonPaperStopSignal(owner=owner, offline_test_id=new_name())


def test_invalid_test_name_refused_no_production_namespace_fallback():
    owner, _ = dummy_owner()
    with pytest.raises(ValueError, match="TEST_ID_INVALID"):
        InstalledPythonPaperStopSignal(owner=owner, offline_test_id="not-a-valid-test-id")


def test_duplicate_owner_of_same_sid_and_session_refused_without_breaking_first():
    owner, calls = dummy_owner()
    name = new_name()
    with InstalledPythonPaperStopSignal(owner=owner, offline_test_id=name) as original:
        with pytest.raises(ValueError, match="OTHER_OWNER_OR_EVENT_EXISTS"):
            InstalledPythonPaperStopSignal(owner=owner, offline_test_id=name)
        assert send(name).returncode == 0
        assert original.poll(1000)["phase"] == "FINISHED"
        assert calls == ["SHUTDOWN_FLATTEN"]


def test_after_owner_closed_request_cannot_falsely_report_stop_received():
    owner, calls = dummy_owner()
    name = new_name()
    with InstalledPythonPaperStopSignal(owner=owner, offline_test_id=name) as signal:
        assert signal.poll(0)["status"] == "NO_STOP_SIGNAL"
    assert send(name).returncode != 0
    assert calls == []


def test_foreign_or_changed_session_cannot_dispatch_even_with_signalled_event():
    owner, calls = dummy_owner()
    name = new_name()
    with InstalledPythonPaperStopSignal(owner=owner, offline_test_id=name) as signal:
        assert send(name).returncode == 0
        owner._session = "synthetic-foreign-session"
        with pytest.raises(ValueError, match="OWNER_IDENTITY_CHANGED"):
            signal.poll(1000)
        assert calls == []
        with pytest.raises(ValueError, match="ALREADY_USED_OR_INVALID"):
            signal.poll(0)


def test_unverified_durable_stop_result_refuses_and_never_replays_dispatch():
    owner, calls = dummy_owner(outcome_valid=False)
    name = new_name()
    with InstalledPythonPaperStopSignal(owner=owner, offline_test_id=name) as signal:
        assert send(name).returncode == 0
        with pytest.raises(ValueError, match="DURABLE_RECEIPT_UNVERIFIED"):
            signal.poll(1000)
        assert calls == ["SHUTDOWN_FLATTEN"]
        with pytest.raises(ValueError, match="ALREADY_USED_OR_INVALID"):
            signal.poll(0)


def test_unknown_dispatch_result_refuses_and_never_retries():
    owner, calls = dummy_owner(crash=True)
    name = new_name()
    with InstalledPythonPaperStopSignal(owner=owner, offline_test_id=name) as signal:
        assert send(name).returncode == 0
        with pytest.raises(OSError, match="synthetic reply unavailable"):
            signal.poll(1000)
        assert calls == ["SHUTDOWN_FLATTEN"]
        with pytest.raises(ValueError, match="ALREADY_USED_OR_INVALID"):
            signal.poll(0)


def test_wrong_owner_thread_cannot_wait_or_release_native_mutex():
    owner, calls = dummy_owner()
    with InstalledPythonPaperStopSignal(owner=owner, offline_test_id=new_name()) as signal:
        failures = []
        def cross_thread():
            for fn in (lambda: signal.poll(0), signal.close):
                try:
                    fn()
                except Exception as exc:
                    failures.append(str(exc))
        t = threading.Thread(target=cross_thread)
        t.start(); t.join(2)
        assert not t.is_alive()
        assert failures == ["PERSONAL_PAPER_STOP_OWNER_THREAD_CHANGED"] * 2
        assert signal.poll(0)["status"] == "NO_STOP_SIGNAL"
    assert calls == []


def test_native_owner_identity_matches_current_user_local_windows_session():
    sid, session = WindowsStopEvents().identity()
    assert sid.startswith("S-1-") and session >= 0


def test_opt_in_python_owner_event_entry_point_requires_existing_owner():
    from app.services.personal_installed_stop_owner import open_personal_installed_python_stop_signal
    with pytest.raises(ValueError, match="ACCEPTED_OWNER_REQUIRED"):
        open_personal_installed_python_stop_signal(owner=object(), offline_test_id=new_name())
    owner, calls = dummy_owner()
    name = new_name()
    with open_personal_installed_python_stop_signal(owner=owner, offline_test_id=name) as signal:
        assert signal.poll(0)["status"] == "NO_STOP_SIGNAL"
        assert send(name).returncode == 0
        assert signal.poll(1000)["phase"] == "FINISHED"
        assert calls == ["SHUTDOWN_FLATTEN"]
