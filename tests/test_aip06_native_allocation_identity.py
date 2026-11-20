"""Native allocation must use the original retained Session object."""
import copy
from types import SimpleNamespace

import pytest

from scripts.observation_runtime.aip06_native_session import WindowsSessionPort, Session


def test_equal_value_foreign_session_cannot_allocate_native_handles():
    original = Session(name='case_host', plan={}, permit={}, keys=('reserved',),
                       argv=(), options={}, observer=None)
    foreign = copy.copy(original)
    assert foreign == original and foreign is not original
    factory = object.__new__(WindowsSessionPort)
    factory.sessions = [original]
    factory.resources = SimpleNamespace(state={'resources': {
        'reserved': {'owner': 'owner', 'kind': 'handle', 'closed': False}}})
    allocations = []
    with pytest.raises(ValueError, match='KNOWN_NATIVE_SESSION'):
        factory.allocate(foreign, ('handle',), lambda: allocations.append('native') or 41)
    assert allocations == []
