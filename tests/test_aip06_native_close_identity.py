"""Native handle closure requires the original retained session."""
import copy
from types import SimpleNamespace

import pytest

from scripts.observation_runtime.aip06_native_session import Session, WindowsSessionPort


@pytest.mark.parametrize('keys', [None, 'process-slot', ['process-slot', 'process-slot'], [None]])
def test_close_owned_handles_refuses_malformed_resource_keys_before_cleanup(keys):
    original = Session(name='case_host', plan={}, permit={'slots': ('process-slot',)}, keys=(),
                       argv=(), options={}, observer=None)
    original.binding = SimpleNamespace(finished=True)
    port = object.__new__(WindowsSessionPort)
    port.sessions = [original]
    calls = []
    port.calls = SimpleNamespace(members=lambda *args: calls.append('members'),
                                 close=lambda *args: calls.append('close'))
    port.protocol = SimpleNamespace(close=lambda *args, **kwargs: calls.append('protocol'))
    with pytest.raises(ValueError, match='UNIQUE_TYPED_CLOSE_RESOURCE_KEYS_REQUIRED'):
        port.close_owned_handles(original, keys)
    assert calls == [] and not original.closed


def test_close_owned_handles_refuses_missing_retained_native_handle_before_cleanup():
    original = Session(name='case_host', plan={}, permit={'slots': ()}, keys=('native-key',),
                       argv=(), options={}, observer=None)
    original.binding = SimpleNamespace(finished=True)
    port = object.__new__(WindowsSessionPort)
    port.sessions = [original]
    calls = []
    port.calls = SimpleNamespace(members=lambda *args: calls.append('members'),
                                 close=lambda *args: calls.append('close'))
    port.protocol = SimpleNamespace(close=lambda *args, **kwargs: calls.append('protocol'))
    with pytest.raises(ValueError, match='RETAINED_NATIVE_HANDLE_BEFORE_CLEANUP'):
        port.close_owned_handles(original, ())
    assert calls == [] and not original.closed


def test_close_owned_handles_refuses_missing_process_slot_before_cleanup_side_effects():
    original = Session(name='case_host', plan={}, permit={'slots': ('process-slot',)}, keys=(),
                       argv=(), options={}, observer=None)
    original.binding = SimpleNamespace(finished=True)
    port = object.__new__(WindowsSessionPort)
    port.sessions = [original]
    calls = []
    port.calls = SimpleNamespace(members=lambda *args: calls.append('members'),
                                 close=lambda *args: calls.append('close'))
    port.protocol = SimpleNamespace(close=lambda *args, **kwargs: calls.append('protocol'))
    with pytest.raises(ValueError, match='EXACT_RETAINED_PROCESS_SLOT'):
        port.close_owned_handles(original, ())
    assert calls == [] and not original.closed


def test_close_owned_handles_refuses_equal_value_foreign_session_without_side_effects():
    original = Session(name='case_host', plan={}, permit={'slots': ()}, keys=(),
                       argv=(), options={}, observer=None)
    original.binding = SimpleNamespace(finished=True)
    foreign = copy.copy(original)
    assert foreign == original and foreign is not original
    port = object.__new__(WindowsSessionPort)
    port.sessions = [original]
    calls = []
    port.calls = SimpleNamespace(members=lambda *args: calls.append('members'),
                                 close=lambda *args: calls.append('close'))
    port.protocol = SimpleNamespace(close=lambda *args, **kwargs: calls.append('protocol'))
    with pytest.raises(ValueError, match='ORIGINAL_RETAINED_CLOSE_SESSION_REQUIRED'):
        port.close_owned_handles(foreign, ())
    assert calls == []
    assert not original.closed and not foreign.closed


@pytest.mark.parametrize('keys', [('process-slot', 'foreign'), ('process-slot', 'native-key', 'foreign')])
def test_close_owned_handles_rejects_extra_resource_keys_before_side_effects(keys):
    original = Session(name='case_host', plan={}, permit={'slots': ('process-slot',)},
                       keys=('native-key',), argv=(), options={}, observer=None)
    original.native = {'native-key': {'handle': 5}}
    original.binding = SimpleNamespace(finished=True)
    port = object.__new__(WindowsSessionPort)
    port.sessions = [original]
    calls = []
    port.calls = SimpleNamespace(members=lambda *args: calls.append('members'),
                                 close=lambda *args: calls.append('close'))
    port.protocol = SimpleNamespace(close=lambda *args, **kw: calls.append('protocol'))
    with pytest.raises(ValueError, match='EXACT_RETAINED_CLOSE_RESOURCE_SET_REQUIRED'):
        port.close_owned_handles(original, keys)
    assert calls == []
