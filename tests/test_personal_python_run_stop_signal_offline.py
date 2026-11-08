"""Actual async unified run-loop handling of a synthetic Windows Stop event.

No Atlas activation, market provider, real account, browser or financial writer.
"""

import asyncio
import copy
import json
import subprocess
import uuid
from pathlib import Path

import pytest
from app.services.personal_installed_stop_owner import (
    PersonalInstalledPaperStopOwner,
    open_personal_installed_python_stop_signal,
)
from test_personal_installed_stop_owner_offline import accepted, stop_result

PS_MODULE = (Path(__file__).resolve().parents[1] /
             "scripts/windows/Atlas-Paper-Owned-Stop-Signal.psm1")


def request_signal(name):
    script = ("Import-Module '" + str(PS_MODULE) + "' -Force -ErrorAction Stop; "
              "Request-AtlasPaperOwnedStopSignal -OfflineTestId '" + name + "' | ConvertTo-Json -Compress")
    p = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, text=True, timeout=12, check=False)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)["status"] == "REQUESTED_NOT_VERIFIED"


def setup(tmp_path):
    r, installation, bridge = accepted(tmp_path)
    port = PersonalInstalledPaperStopOwner(bridge=bridge, installation=installation)
    calls = []

    def simulated_durable_stop(mode):
        calls.append(mode)
        value = stop_result()
        bridge.stop_ledger.reserve_fresh(port.session_id, mode)
        bridge.stop_ledger.finish(port.session_id, mode, value)
        bridge.progress = copy.deepcopy(value)
        bridge._receipt_persisted = True
        return copy.deepcopy(value)

    # The real Stop controller is untouched: only its synthetic callback is
    # replaced by an isolated in-memory+tmpdir ledger test double.
    bridge.request_stop = simulated_durable_stop
    return r, port, calls, bridge


def signal(port):
    name = "test-" + uuid.uuid4().hex
    return name, open_personal_installed_python_stop_signal(owner=port, offline_test_id=name)


@pytest.mark.asyncio
async def test_already_requested_stop_preempts_read_and_dispatch(tmp_path):
    r, port, calls, _ = setup(tmp_path)
    name, event = signal(port)
    with event:
        await asyncio.to_thread(request_signal, name)
        result = await r.run(seconds=.3, interval=.05, stop_signal=event)
        assert result == stop_result()
        assert calls == ["SHUTDOWN_FLATTEN"]
        assert r.state == "PAUSED"
        assert all(not lane.calls for lane in r.lanes.values())
        with pytest.raises(ValueError, match="ALREADY_USED_OR_INVALID"):
            event.poll(0)


@pytest.mark.asyncio
async def test_stop_delivered_during_observation_prevents_planner_and_dispatch(tmp_path):
    r, port, calls, _ = setup(tmp_path)
    name, event = signal(port)
    planner_calls = []
    async def planner(observation):
        planner_calls.append(observation)
        return {"kind": "ENTRY", "operation_id": "would-have-traded"}
    r.lanes["HYPERLIQUID"].next_proposal = planner
    original_poll = r.poll
    async def injected_poll():
        result = await original_poll()
        await asyncio.to_thread(request_signal, name)
        return result
    r.poll = injected_poll
    with event:
        result = await r.run(seconds=.4, interval=.05, stop_signal=event)
    assert result == stop_result()
    assert calls == ["SHUTDOWN_FLATTEN"] and planner_calls == []
    assert all(not lane.calls for lane in r.lanes.values())


@pytest.mark.asyncio
async def test_stop_delivered_inside_awaited_strategy_prevents_financial_dispatch(tmp_path):
    r, port, calls, _ = setup(tmp_path)
    name, event = signal(port)
    r.lanes["HYPERLIQUID"].closed = False
    async def planner(observation):
        await asyncio.to_thread(request_signal, name)
        return {"kind": "ENTRY", "operation_id": "refused-late-entry"}
    r.lanes["HYPERLIQUID"].next_proposal = planner
    with event:
        result = await r.run(seconds=.6, interval=.05, stop_signal=event)
    assert result == stop_result() and calls == ["SHUTDOWN_FLATTEN"]
    assert not r.lanes["HYPERLIQUID"].calls
    assert not r.portfolio.operations


@pytest.mark.asyncio
async def test_no_signal_preserves_original_bounded_run_and_scan(tmp_path):
    r, port, calls, _ = setup(tmp_path)
    _, event = signal(port)
    with event:
        result = await r.run(seconds=.12, interval=.05, stop_signal=event)
    assert result["schema"] == "ATLAS_UNIFIED_PAPER_VIEW_V1"
    assert result["state"] == "PAUSED"
    assert calls == [] and all(not lane.calls for lane in r.lanes.values())


@pytest.mark.asyncio
async def test_foreign_owner_signal_refused_before_loop(tmp_path):
    r, _, calls, _ = setup(tmp_path)
    foreign_path = tmp_path / "foreign"
    foreign_path.mkdir()
    _, other_port, _, _ = setup(foreign_path)
    _, event = signal(other_port)
    with event, pytest.raises(ValueError, match="UNIFIED_ACCEPTED_OWNER_STOP_SIGNAL_REQUIRED"):
        await r.run(seconds=.1, interval=.05, stop_signal=event)
    assert calls == [] and r.state == "RUNNING"


@pytest.mark.asyncio
async def test_unknown_result_is_latched_without_strategy_resume(tmp_path):
    r, port, calls, bridge = setup(tmp_path)
    def ambiguous(mode):
        calls.append(mode)
        raise OSError("synthetic stop ledger unavailable")
    bridge.request_stop = ambiguous
    name, event = signal(port)
    with event:
        await asyncio.to_thread(request_signal, name)
        with pytest.raises(OSError, match="synthetic stop ledger unavailable"):
            await r.run(seconds=.2, interval=.05, stop_signal=event)
        assert calls == ["SHUTDOWN_FLATTEN"]
        assert event._used is True and r.state == "STOP_INCOMPLETE"
        assert r.uncertain is True and r.entry_closed.is_set()
        assert all(not lane.calls for lane in r.lanes.values())
