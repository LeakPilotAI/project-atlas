"""Offline fail-closed case-host INPUT cleanup using retained owner handles."""
import pytest
from tests.test_aip06_case_host_input_owner import setup


def test_failed_send_aborts_original_child_and_preserves_error(monkeypatch):
    port, child, _, packet, _ = setup(monkeypatch)
    aborted = []
    port.abort = lambda original, *, deadline_ns: aborted.append((original, deadline_ns))
    def failed_send(*args, **kwargs):
        raise TimeoutError('original channel timeout')
    port.protocol.send_case_host_input = failed_send
    with pytest.raises(TimeoutError, match='original channel timeout'):
        port.deliver_case_host_input(child, packet, deadline_ns=200)
    assert aborted == [(child, 200)]
    assert child.failed and port.failed and child.case_host_input_sent


def test_cleanup_failure_retains_original_send_error_and_failure_record(monkeypatch):
    port, child, _, packet, _ = setup(monkeypatch)
    def failed_send(*args, **kwargs):
        raise OSError('original INPUT broken')
    def failed_abort(original, *, deadline_ns):
        assert original is child and deadline_ns == 200
        raise RuntimeError('retained handle not closed')
    port.protocol.send_case_host_input = failed_send
    port.abort = failed_abort
    with pytest.raises(OSError, match='original INPUT broken'):
        port.deliver_case_host_input(child, packet, deadline_ns=200)
    assert port.case_host_input_cleanup_failure == 'retained handle not closed'
    assert child.failed and port.failed
    with pytest.raises(ValueError):
        port.deliver_case_host_input(child, packet, deadline_ns=200)
