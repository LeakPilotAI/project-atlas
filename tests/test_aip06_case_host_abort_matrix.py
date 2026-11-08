"""Additional injected abort failures preserve original INPUT errors."""
from types import SimpleNamespace
import pytest
from tests.test_aip06_case_host_abort_evidence import prepare


@pytest.mark.parametrize('failure,expected', [
    ('identity-changed', 'ABORT_ORIGINAL_PROCESS_BIRTH_MISMATCH'),
    ('termination-refused', 'injected owned Job termination refused'),
    ('channel-close-refused', 'injected channel close refused'),
])
def test_abort_failures_keep_original_error_and_unresolved_child(monkeypatch, failure, expected):
    port, child, packet, events = prepare(monkeypatch, failure)
    if failure == 'identity-changed':
        port.calls.lifecycle = lambda handle: {'pid': 44, 'created': 999, 'exited': False}
    elif failure == 'termination-refused':
        def refuse(job):
            events.append('terminate')
            raise OSError('injected owned Job termination refused')
        port.calls.terminate_owned_job = refuse
    else:
        def refuse_channel(original, *, deadline_ns):
            events.append('channel-close')
            raise OSError('injected channel close refused')
        port.protocol.close = refuse_channel
    with pytest.raises(TimeoutError, match='authenticated INPUT timed out'):
        port.deliver_case_host_input(child, packet, deadline_ns=200)
    assert expected in port.case_host_input_cleanup_failure
    assert child.failed and port.failed and child.case_host_input_sent
    assert not child.closed
    assert 'process-close' not in events
    if failure == 'identity-changed':
        assert 'terminate' not in events
    if failure == 'termination-refused':
        assert 'wait' not in events
    if failure == 'channel-close-refused':
        assert events[:3] == ['terminate', 'wait', 'channel-close']
    with pytest.raises(ValueError):
        port.deliver_case_host_input(child, packet, deadline_ns=200)
