"""Pre-funding stop is owner-bound and never substitutes for native finance."""
from __future__ import annotations

from threading import Event

import pytest
from app.services import hyperliquid_intrahour_stop_supervisor as stop
from app.services.hyperliquid_forward_flat_paper_policy import HOUR

HOUR_START = 1_795_000_000 // HOUR * HOUR


class StubRuntime:
    def __init__(self, seconds):
        self.value = HOUR_START + seconds
        self._stop_first_state = "RELEASED"
        self._stop_first_initial_source_lane = "HYPERLIQUID"
        self.state = "RUNNING"
        self.uncertain = False
        self.entry_closed = Event()
        self.installation = object()
        self.clock = self.read_clock

    def read_clock(self):
        return self.value


class StubOriginalStopOwner:
    def __init__(self, seconds=60):
        self._runtime = StubRuntime(seconds)
        self._installation = self._runtime.installation
        self.session_id = "synthetic-disposable-not-accepted"
        self._used = False
        self.callbacks = []
        self.reply = {
            "schema": "QD_CONTROL_STOP_V1",
            "phase": "FINISHED",
            "outcome": {
                "status": "FLATTENED",
                "position_state": "FLAT",
                "process_shutdown": "VERIFIED_EXIT",
            },
        }
        self.durable = True

    def verify_session(self):
        return not self._used and self._runtime.state == "RUNNING"

    def request_stop(self, mode):
        if self._used:
            raise ValueError("SYNTHETIC_STOP_ALREADY_USED")
        self._used = True
        self.callbacks.append(mode)
        self._runtime.state = "STOPPED"
        return self.reply

    def verify_durable_stop_receipt(self, mode, receipt):
        return (
            self._used and self.durable
            and mode == "SHUTDOWN_FLATTEN" and receipt == self.reply
        )


@pytest.fixture
def original(monkeypatch):
    monkeypatch.setattr(stop, "PersonalInstalledPaperStopOwner", StubOriginalStopOwner)
    return StubOriginalStopOwner()


def test_only_genuine_owned_stop_class_may_enter_supervisor(original):
    with pytest.raises(ValueError, match="REAL_SELECTED_NATIVE_STOP_OWNER_REQUIRED"):
        stop.NativeIntrahourPaperStopSupervisor(owner=object())
    original._runtime._stop_first_state = "ARMED"
    with pytest.raises(ValueError, match="HL_ONLY_STOP_FIRST_NOT_ACCEPTED"):
        stop.NativeIntrahourPaperStopSupervisor(owner=original)
    original._runtime._stop_first_state = "RELEASED"
    original._runtime._stop_first_initial_source_lane = "BOTH"
    with pytest.raises(ValueError, match="HL_ONLY_STOP_FIRST_NOT_ACCEPTED"):
        stop.NativeIntrahourPaperStopSupervisor(owner=original)


def test_before_boundary_guard_issues_no_financial_effect_and_can_recheck(original):
    guard = stop.NativeIntrahourPaperStopSupervisor(owner=original)
    receipt = guard.tick()
    assert receipt["status"] == "STILL_SUPERVISING_NO_FINANCIAL_PERMISSION"
    assert receipt["new_entries_authorized"] is False
    assert receipt["funding_cost_assumed_zero"] is False
    assert guard.entry_window() is True
    assert original.callbacks == []
    original._runtime.value += 1
    assert guard.tick()["status"] == "STILL_SUPERVISING_NO_FINANCIAL_PERMISSION"
    assert guard.terminal is False


@pytest.mark.parametrize("seconds,expected", (
    (32, True),
    (34 * 60, True),
    (35 * 60, False),
    (54 * 60, False),
    (3599, False),
))
def test_no_intrahour_new_entry_near_funding(original, seconds, expected):
    original._runtime.value = HOUR_START + seconds
    guard = stop.NativeIntrahourPaperStopSupervisor(owner=original)
    assert guard.entry_window() is expected
    assert original.callbacks == []


def test_original_one_shot_stop_proves_durable_flat_only_before_cutoff(original):
    guard = stop.NativeIntrahourPaperStopSupervisor(owner=original)
    original._runtime.value = HOUR_START + 3600 - stop.STOP_AHEAD_SECONDS
    result = guard.tick()
    assert result["status"] == "ORIGINAL_NATIVE_DURABLE_STOP_FLAT_BEFORE_FUNDING"
    assert result["original_native_durable_stop_verified"] is True
    assert result["funding_cost_assumed_zero"] is False
    assert result["provider_actual_funding_settlement_verified"] is False
    assert result["automatic_restart_authorized"] is False
    assert result["live_trading_authorized"] is False
    assert original.callbacks == ["SHUTDOWN_FLATTEN"]
    assert guard.terminal is True
    assert original._runtime.entry_closed.is_set()
    with pytest.raises(ValueError, match="CHANGED_OR_REVOKED"):
        guard.tick()
    assert original.callbacks == ["SHUTDOWN_FLATTEN"]


@pytest.mark.parametrize("damage", (
    "lost_receipt", "wrong_cash", "wrong_process", "clock_crossed",
    "late_tick", "callback_raises", "uncertain_native_flat",
))
def test_unknown_or_late_stop_latches_and_cannot_replay(original, damage):
    guard = stop.NativeIntrahourPaperStopSupervisor(owner=original)
    original._runtime.value = HOUR_START + 3600 - stop.STOP_AHEAD_SECONDS
    if damage == "lost_receipt":
        original.durable = False
    elif damage == "wrong_cash":
        original.reply["outcome"]["status"] = "SHUTDOWN_INCOMPLETE"
    elif damage == "wrong_process":
        original.reply["outcome"]["process_shutdown"] = "NOT_VERIFIED"
    elif damage == "clock_crossed":
        old = original.request_stop

        def advanced(mode):
            original._runtime.value = HOUR_START + 3600 - 299
            return old(mode)

        original.request_stop = advanced
    elif damage == "late_tick":
        original._runtime.value = HOUR_START + 3600 + 1
    elif damage == "callback_raises":
        def broken(mode):
            original._used = True
            original.callbacks.append(mode)
            raise OSError("disposable unknown")
        original.request_stop = broken
    else:
        original.reply["outcome"]["position_state"] = "UNKNOWN"
    with pytest.raises((ValueError, OSError)):
        guard.tick()
    assert guard.terminal is True
    assert original._runtime.entry_closed.is_set()
    assert original._runtime.uncertain is True
    assert original._runtime.state == "STOP_INCOMPLETE"
    assert original.callbacks == ["SHUTDOWN_FLATTEN"]
    with pytest.raises(ValueError, match="CHANGED_OR_REVOKED"):
        guard.tick()
    assert len(original.callbacks) == 1


def test_revoked_clock_or_owner_cannot_requalify(original):
    guard = stop.NativeIntrahourPaperStopSupervisor(owner=original)
    original._runtime.value -= 10
    guard.tick()  # first non-stop tick; clock is now the baseline
    original._runtime.value -= 1
    with pytest.raises(ValueError, match="UTC_ROLLBACK"):
        guard.tick()
    assert original.callbacks == []
    assert guard.terminal is True
    assert original._runtime.entry_closed.is_set()
    assert original._runtime.uncertain is True
    assert original._runtime.state == "STOP_INCOMPLETE"


def test_source_class_does_not_change_original_financial_oracle_or_startup():
    import inspect

    from app.services.hyperliquid_consensus_settlement import (
        require_consensus_settlement_oracle,
    )
    from app.services.unified_paper_runtime import UnifiedPaperRuntime

    assert "intrahour_supervisor" in inspect.signature(UnifiedPaperRuntime.run).parameters
    assert stop.STOP_AHEAD_SECONDS == 480
    assert stop.CLOCK_MARGIN_SECONDS == 2
    with pytest.raises(ValueError):
        require_consensus_settlement_oracle(None, symbol="BTC", at=HOUR_START + HOUR,
                                            funding_record={"hourly_rate": "0"})



def test_an_unverifiable_initial_clock_latches_already_running_paper(original):
    original._runtime.value = 0
    with pytest.raises(ValueError, match="GENUINE_INTEGER_UTC_REQUIRED"):
        stop.NativeIntrahourPaperStopSupervisor(owner=original)
    assert original._runtime.entry_closed.is_set()
    assert original._runtime.uncertain is True
    assert original._runtime.state == "STOP_INCOMPLETE"
    assert original.callbacks == []


def test_a_revoked_selected_stop_owner_latches_new_entries_before_next_tick(original):
    guard = stop.NativeIntrahourPaperStopSupervisor(owner=original)
    original.session_id = "different-session"
    with pytest.raises(ValueError, match="STOP_OWNER_CHANGED_OR_REVOKED"):
        guard.entry_window()
    assert guard.terminal is True
    assert original._runtime.entry_closed.is_set()
    assert original._runtime.uncertain is True
    assert original._runtime.state == "STOP_INCOMPLETE"
    assert original.callbacks == []
