"""Opt-in hourly Stop owner must work through the actual unified run loop.

All inputs are explicitly disposable/synthetic and never touch a real native
financial account, operator activation, marketplace or installed release.
"""
from __future__ import annotations

import copy
import uuid

import pytest
import test_unified_paper_runtime as synthetic_unified
from app.services.hyperliquid_intrahour_stop_supervisor import (
    NativeIntrahourPaperStopSupervisor,
)
from app.services.personal_installed_stop_owner import (
    open_personal_installed_python_stop_signal,
)
from test_personal_python_run_stop_signal_offline import setup, stop_result

BASE = 1_795_000_000 // 3600 * 3600


def prepared(monkeypatch, tmp_path, seconds):
    monkeypatch.setattr(synthetic_unified, "NOW", BASE + seconds)
    runtime, owner, calls, bridge = setup(tmp_path)
    runtime._stop_first_state = "RELEASED"
    runtime._stop_first_initial_source_lane = "HYPERLIQUID"
    guard = NativeIntrahourPaperStopSupervisor(owner=owner)
    return runtime, owner, calls, bridge, guard


def event(owner):
    return open_personal_installed_python_stop_signal(
        owner=owner, offline_test_id="test-" + uuid.uuid4().hex,
    )


@pytest.mark.asyncio
async def test_guard_reaches_once_only_original_durable_stop_path(
    monkeypatch, tmp_path,
):
    r, owner, calls, bridge, guard = prepared(
        monkeypatch, tmp_path, 3600 - 480,
    )

    def original_simulated_durable_stop(mode):
        calls.append(mode)
        report = stop_result()
        bridge.stop_ledger.reserve_fresh(owner.session_id, mode)
        bridge.stop_ledger.finish(owner.session_id, mode, report)
        bridge.progress = copy.deepcopy(report)
        bridge._receipt_persisted = True
        r.state = "STOPPED"
        return copy.deepcopy(report)

    bridge.request_stop = original_simulated_durable_stop
    with event(owner) as signal:
        result = await r.run(
            seconds=.2, interval=.05, stop_signal=signal,
            intrahour_supervisor=guard,
        )
    assert result == stop_result()
    assert calls == ["SHUTDOWN_FLATTEN"]
    assert r.state == "STOPPED"
    assert r.entry_closed.is_set()
    assert owner._used is True and guard.terminal is True
    assert owner.verify_durable_stop_receipt(
        "SHUTDOWN_FLATTEN", result,
    ) is True
    assert all(not lane.calls for lane in r.lanes.values())


@pytest.mark.asyncio
async def test_before_hour_guard_does_not_create_new_dispatch(
    monkeypatch, tmp_path,
):
    r, owner, calls, _, guard = prepared(monkeypatch, tmp_path, 100)
    with event(owner) as signal:
        view = await r.run(
            seconds=.11, interval=.05, stop_signal=signal,
            intrahour_supervisor=guard,
        )
    assert view["schema"] == "ATLAS_UNIFIED_PAPER_VIEW_V1"
    assert r.state == "PAUSED"
    assert owner._used is False
    assert not calls and all(not lane.calls for lane in r.lanes.values())


@pytest.mark.asyncio
async def test_missing_native_stop_signal_refuses_optin_guard(
    monkeypatch, tmp_path,
):
    r, _, _, _, guard = prepared(monkeypatch, tmp_path, 100)
    with pytest.raises(ValueError, match="PRE_FUNDING_EXACT_ACCEPTED_STOP_OWNER_REQUIRED"):
        await r.run(seconds=.1, interval=.05, intrahour_supervisor=guard)
    assert r.state == "RUNNING"
    assert not r.entry_closed.is_set()


@pytest.mark.asyncio
async def test_unknown_durable_stop_is_latched_once_with_no_entry(
    monkeypatch, tmp_path,
):
    r, owner, calls, bridge, guard = prepared(
        monkeypatch, tmp_path, 3600 - 480,
    )

    def unknown(mode):
        calls.append(mode)
        raise OSError("disposable native ledger cannot read stop acknowledgment")

    bridge.request_stop = unknown
    with event(owner) as signal, pytest.raises(OSError, match="disposable native ledger"):
        await r.run(
            seconds=.2, interval=.05, stop_signal=signal,
            intrahour_supervisor=guard,
        )
    assert calls == ["SHUTDOWN_FLATTEN"]
    assert r.state == "STOP_INCOMPLETE"
    assert r.uncertain is True
    assert r.entry_closed.is_set()
    assert owner._used and guard.terminal
    assert not any(lane.calls for lane in r.lanes.values())


@pytest.mark.asyncio
async def test_no_optin_preserves_regular_default_paper_observation(
    monkeypatch, tmp_path,
):
    r, owner, calls, _, _ = prepared(monkeypatch, tmp_path, 3600 - 480)
    with event(owner) as signal:
        result = await r.run(seconds=.10, interval=.05, stop_signal=signal)
    assert result["schema"] == "ATLAS_UNIFIED_PAPER_VIEW_V1"
    assert r.state == "PAUSED" and not r.entry_closed.is_set()
    assert owner._used is False and calls == []



@pytest.mark.asyncio
async def test_intrahour_active_runner_refuses_late_financial_entries(
    monkeypatch, tmp_path,
):
    # More than 8min before funding, so the session must keep observing,
    # but already be past the mandatory last-25min new entry cutoff.
    r, owner, calls, _, guard = prepared(monkeypatch, tmp_path, 35 * 60)
    r.lanes["HYPERLIQUID"].closed = False
    planner_calls = []

    async def proposal(observation):
        planner_calls.append(observation)
        return {"operation_id": "should-not-fill-late", "kind": "ENTRY"}

    r.lanes["HYPERLIQUID"].next_proposal = proposal
    with event(owner) as signal:
        result = await r.run(
            seconds=.13, interval=.05, stop_signal=signal,
            intrahour_supervisor=guard,
        )
    assert result["schema"] == "ATLAS_UNIFIED_PAPER_VIEW_V1"
    assert planner_calls
    assert not r.lanes["HYPERLIQUID"].calls
    assert not r.portfolio.operations
    assert not calls
    assert r.state == "PAUSED" and owner._used is False


@pytest.mark.asyncio
async def test_live_run_guard_does_not_block_reducing_cancellation_by_time(
    monkeypatch, tmp_path,
):
    r, owner, calls, _, guard = prepared(monkeypatch, tmp_path, 35 * 60)
    r._intrahour_supervisor = guard
    # _resting() must reach the ordinary original cancellation/custody
    # validator instead of the new ENTRY cutoff (still no synthetic order).
    with pytest.raises(ValueError) as exc:
        r.cancel_resting(
            {"kind": "CANCEL_RESTING_ORDER", "order": {}},
            lane="HYPERLIQUID",
        )
    assert "UNIFIED_HL_INTRAHOUR_RESTING_ENTRY_CLOSED" not in str(exc.value)
    assert calls == [] and owner._used is False


@pytest.mark.asyncio
async def test_active_intrahour_guard_checks_even_direct_entry_dispatch(
    monkeypatch, tmp_path,
):
    r, owner, calls, _, guard = prepared(monkeypatch, tmp_path, 35 * 60)
    r._intrahour_supervisor = guard
    with pytest.raises(ValueError, match="UNIFIED_HL_INTRAHOUR_FINANCIAL_ENTRY_CLOSED"):
        r.dispatch("HYPERLIQUID", {
            "kind": "ENTRY", "operation_id": "direct-would-have-filled",
        })
    with pytest.raises(ValueError, match="UNIFIED_HL_INTRAHOUR_RESTING_ENTRY_CLOSED"):
        r.admit_resting({
            "kind": "RESTING_ORDER", "operation_id": "resting-would-have-filled",
        }, lane="HYPERLIQUID")
    assert owner._used is False and not calls
    assert not r.portfolio.operations and all(
        not lane.calls for lane in r.lanes.values()
    )
