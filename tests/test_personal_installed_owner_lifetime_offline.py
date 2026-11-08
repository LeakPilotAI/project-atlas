"""Synthetic owner lifetime and tokenless desktop Stop behavior, no real Atlas."""
import asyncio
import copy
import uuid
from threading import Event

import pytest
from app.services.personal_installed_stop_owner import (
    run_personal_installed_owner_session,
)
from test_personal_paper_python_stop_signal_offline import send
from test_personal_python_run_stop_signal_offline import (
    request_signal,
    setup,
    stop_result,
)


def harness(tmp_path):
    runtime, owner, calls, bridge = setup(tmp_path)
    def recorded_stop(mode):
        calls.append(mode)
        receipt = stop_result()
        bridge.stop_ledger.reserve_fresh(owner.session_id, mode)
        bridge.stop_ledger.finish(owner.session_id, mode, receipt)
        bridge.progress = copy.deepcopy(receipt)
        bridge._receipt_persisted = True
        runtime.entry_closed.set()
        runtime.state = 'STOPPED'
        return copy.deepcopy(receipt)
    bridge.request_stop = recorded_stop
    return runtime, owner, calls, bridge


def identity():
    return 'test-' + uuid.uuid4().hex


@pytest.mark.asyncio
async def test_requested_stop_verified_and_event_closed_after_run(tmp_path):
    runtime, owner, calls, _ = harness(tmp_path)
    name = identity()
    original_poll = runtime.poll
    async def poll_and_signal():
        result = await original_poll()
        await asyncio.to_thread(request_signal, name)
        return result
    runtime.poll = poll_and_signal
    result = await run_personal_installed_owner_session(
        owner=owner, seconds=.5, interval=.05, offline_test_id=name)
    assert result == stop_result()
    assert calls == ['SHUTDOWN_FLATTEN']
    assert runtime.state == 'STOPPED' and runtime.entry_closed.is_set()
    assert owner._used
    assert send(name).returncode != 0  # No orphan desktop Stop event after close.


@pytest.mark.asyncio
async def test_bounded_expiry_automatically_uses_same_durable_stop_once(tmp_path):
    runtime, owner, calls, _ = harness(tmp_path)
    name = identity()
    result = await run_personal_installed_owner_session(
        owner=owner, seconds=.12, interval=.05, offline_test_id=name)
    assert result == stop_result()
    assert send(name).returncode != 0  # Bound handle removed after expiry.
    assert calls == ['SHUTDOWN_FLATTEN']
    assert runtime.state == 'STOPPED' and runtime.entry_closed.is_set()


@pytest.mark.asyncio
async def test_explicit_bounded_cancellation_also_verifies_stop(tmp_path):
    _, owner, calls, _ = harness(tmp_path)
    cancel = Event()
    cancel.set()
    result = await run_personal_installed_owner_session(
        owner=owner, seconds=.2, interval=.05, stop=cancel, offline_test_id=identity())
    assert result == stop_result() and calls == ['SHUTDOWN_FLATTEN']


@pytest.mark.asyncio
async def test_ambiguous_desktop_stop_exits_fail_closed_without_replay(tmp_path):
    runtime, owner, calls, bridge = harness(tmp_path)
    def failed(mode):
        calls.append(mode)
        raise OSError('synthetic receipt missing')
    bridge.request_stop = failed
    name = identity()
    original_poll = runtime.poll
    async def poll_and_signal():
        value = await original_poll()
        await asyncio.to_thread(request_signal, name)
        return value
    runtime.poll = poll_and_signal
    with pytest.raises(OSError, match='synthetic receipt missing'):
        await run_personal_installed_owner_session(
            owner=owner, seconds=.3, interval=.05, offline_test_id=name)
    assert calls == ['SHUTDOWN_FLATTEN']
    assert runtime.entry_closed.is_set() and runtime.uncertain
    assert runtime.state == 'STOP_INCOMPLETE'


@pytest.mark.asyncio
async def test_expiry_without_durable_receipt_never_claims_success(tmp_path):
    runtime, owner, calls, bridge = harness(tmp_path)
    bridge.request_stop = lambda mode: calls.append(mode) or stop_result()
    with pytest.raises(ValueError, match='EXPIRY_FLATNESS_UNVERIFIED'):
        await run_personal_installed_owner_session(
            owner=owner, seconds=.12, interval=.05, offline_test_id=identity())
    assert calls == ['SHUTDOWN_FLATTEN']
    assert runtime.state == 'STOP_INCOMPLETE' and runtime.uncertain


@pytest.mark.asyncio
async def test_unexpected_supervisor_error_closes_entry_without_second_stop(tmp_path):
    runtime, owner, calls, _ = harness(tmp_path)
    async def fail_run(**kwargs):
        raise RuntimeError('synthetic monitoring error')
    runtime.run = fail_run
    with pytest.raises(RuntimeError, match='synthetic monitoring error'):
        await run_personal_installed_owner_session(
            owner=owner, seconds=.2, interval=.05, offline_test_id=identity())
    assert calls == [] and runtime.entry_closed.is_set()
    assert runtime.state == 'STOP_INCOMPLETE'


@pytest.mark.asyncio
async def test_task_cancellation_cannot_mark_positions_flat(tmp_path):
    runtime, owner, calls, _ = harness(tmp_path)
    async def cancel_run(**kwargs):
        raise asyncio.CancelledError()
    runtime.run = cancel_run
    with pytest.raises(asyncio.CancelledError):
        await run_personal_installed_owner_session(
            owner=owner, seconds=.2, interval=.05, offline_test_id=identity())
    assert not calls and runtime.uncertain and runtime.entry_closed.is_set()


@pytest.mark.asyncio
async def test_invalid_owner_rejected_without_opening_any_event():
    with pytest.raises(ValueError, match='ACTIVE_SESSION_REQUIRED'):
        await run_personal_installed_owner_session(owner=object(), seconds=.2)


@pytest.mark.asyncio
async def test_one_owner_session_cannot_run_again_after_verified_stop(tmp_path):
    _, owner, calls, _ = harness(tmp_path)
    await run_personal_installed_owner_session(
        owner=owner, seconds=.1, interval=.05, offline_test_id=identity())
    with pytest.raises(ValueError, match='ACTIVE_SESSION_REQUIRED'):
        await run_personal_installed_owner_session(
            owner=owner, seconds=.1, interval=.05, offline_test_id=identity())
    assert calls == ['SHUTDOWN_FLATTEN']


@pytest.mark.asyncio
async def test_event_creation_failure_marks_existing_owner_unverified(tmp_path, monkeypatch):
    import app.services.personal_installed_stop_owner as module
    runtime, owner, calls, _ = harness(tmp_path)
    def denied(**kwargs):
        raise OSError('synthetic event ACL denied')
    monkeypatch.setattr(module, 'open_personal_installed_python_stop_signal', denied)
    with pytest.raises(OSError, match='synthetic event ACL denied'):
        await run_personal_installed_owner_session(
            owner=owner, seconds=.2, interval=.05, offline_test_id=identity())
    assert calls == [] and runtime.uncertain and runtime.entry_closed.is_set()
    assert runtime.state == 'STOP_INCOMPLETE'
