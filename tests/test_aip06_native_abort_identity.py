"""Abort must never adopt an equal-value foreign Session or close its handles."""
import copy
from types import SimpleNamespace

import pytest

from scripts.observation_runtime.aip06_native_session import Session, WindowsSessionPort


def test_abort_refuses_equal_value_foreign_session_before_side_effects():
    original = Session(name='case_host', plan={}, permit={}, keys=(),
                       argv=(), options={}, observer=None)
    foreign = copy.copy(original)
    assert foreign == original and foreign is not original
    port = object.__new__(WindowsSessionPort)
    port.sessions = [original]
    port.failed = False
    events = []
    port.calls = SimpleNamespace(lifecycle=lambda *args: events.append('lifecycle'))
    port.protocol = SimpleNamespace(close=lambda *args, **kwargs: events.append('close'))
    with pytest.raises(ValueError, match='ORIGINAL_RETAINED_ABORT_SESSION_REQUIRED'):
        port.abort(foreign, deadline_ns=100)
    assert events == []
    assert not port.failed and not foreign.failed and not original.failed
