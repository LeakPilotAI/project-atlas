"""Abort must independently re-observe the original process exit after wait."""
from types import SimpleNamespace

import pytest

from scripts.observation_runtime.aip06_native_session import Session, WindowsSessionPort


@pytest.mark.parametrize('after', [
    {'pid': 20, 'created': 100, 'exited': False},
    {'pid': 21, 'created': 100, 'exited': True},
    {'pid': 20, 'created': 101, 'exited': True},
], ids=['not-exited', 'pid-reused', 'birth-reused'])
def test_abort_refuses_unverified_post_wait_exit(after):
    child = Session(name='case_host', plan={}, permit={}, keys=(),
                    argv=(), options={}, observer=None)
    child.launch_handle = 40
    child.creation_native = {'pid': 20, 'created': 100}
    child.job = 50
    port = object.__new__(WindowsSessionPort)
    port.sessions = [child]
    port.failed = False
    events = []
    snapshots = iter([{'pid': 20, 'created': 100, 'exited': True}, after])
    port.calls = SimpleNamespace(
        lifecycle=lambda handle: next(snapshots),
        wait=lambda handle, deadline: events.append('wait'),
        members=lambda job: events.append('members') or set(),
        close=lambda handle: events.append('close'))
    port.protocol = SimpleNamespace(close=lambda *args, **kwargs: events.append('channel-close'))
    with pytest.raises(ValueError, match='ABORT_ORIGINAL_PROCESS_EXIT_NOT_INDEPENDENTLY_VERIFIED'):
        port.abort(child, deadline_ns=200)
    assert events == ['wait']
    assert child.failed and port.failed and not child.closed
