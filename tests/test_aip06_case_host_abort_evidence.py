"""Injected owner-handle cleanup failures; never launches native processes."""
from types import SimpleNamespace
import pytest
from tests.test_aip06_case_host_input_owner import setup


def prepare(monkeypatch, failure):
    port, child, _, packet, _ = setup(monkeypatch)
    events = []
    child.launch_handle = object()
    child.creation_native = {'pid': 44, 'created': 55}
    child.job = object()
    child.native = {}
    child.released = set()
    child.closed = False
    port.closed_proofs = set()
    port.protocol.close = lambda original, *, deadline_ns: events.append('channel-close')
    port.calls = SimpleNamespace(
        lifecycle=lambda handle: {'pid': 44, 'created': 55, 'exited': 'wait' in events,
                                  'exit_code': 1 if 'wait' in events else None},
        in_job=lambda handle, job: True,
        terminate_owned_job=lambda job: events.append('terminate'),
        wait=lambda handle, deadline: events.append('wait'),
        members=lambda job: {44} if failure == 'job-not-empty' else set(),
        close=lambda handle: events.append('process-close'),
        closed=lambda handle: failure != 'handle-open',
    )
    def send(*args, **kwargs):
        raise TimeoutError('authenticated INPUT timed out')
    port.protocol.send_case_host_input = send
    return port, child, packet, events


@pytest.mark.parametrize('failure,expected', [
    ('job-not-empty', 'ABORT_JOB_NOT_EMPTY'),
    ('handle-open', 'ABORT_PROCESS_HANDLE_OPEN'),
])
def test_unverified_cleanup_never_reports_closed(monkeypatch, failure, expected):
    port, child, packet, events = prepare(monkeypatch, failure)
    with pytest.raises(TimeoutError, match='authenticated INPUT timed out'):
        port.deliver_case_host_input(child, packet, deadline_ns=200)
    assert expected in port.case_host_input_cleanup_failure
    assert child.failed and port.failed and child.case_host_input_sent
    assert not child.closed
    assert not hasattr(child, 'abort_exit_proof')
    assert events[:2] == ['terminate', 'wait']
    if failure == 'job-not-empty':
        assert 'process-close' not in events
        assert 'channel-close' not in events
    else:
        assert 'channel-close' in events and 'process-close' in events
    with pytest.raises(ValueError):
        port.deliver_case_host_input(child, packet, deadline_ns=200)


def test_verified_native_abort_retains_original_exit_evidence(monkeypatch):
    port, child, _, events = prepare(monkeypatch, failure=None)
    port.abort(child, deadline_ns=200)
    assert child.closed is True
    assert child.abort_exit_proof == {'pid': 44, 'created': 55, 'exited': True,
                                      'exit_code': 1}
    assert events[:2] == ['terminate', 'wait']
    assert events[-1] == 'process-close'


@pytest.mark.parametrize('bad_exit', [None, True, '1'])
def test_abort_refuses_untyped_exit_code_before_handle_closure(monkeypatch, bad_exit):
    port, child, _, events = prepare(monkeypatch, failure=None)
    port.calls.lifecycle = lambda handle: {
        'pid': 44, 'created': 55, 'exited': 'wait' in events,
        'exit_code': bad_exit,
    }
    with pytest.raises(ValueError, match='ABORT_ORIGINAL_PROCESS_EXIT_NOT_INDEPENDENTLY_VERIFIED'):
        port.abort(child, deadline_ns=200)
    assert 'process-close' not in events
    assert 'channel-close' not in events
    assert not child.closed
    assert not hasattr(child, 'abort_exit_proof')
