"""Reader verification must reject an equal-value, nonretained Session."""
import copy
from types import SimpleNamespace

import pytest

from scripts.observation_runtime.aip06_fixture_guard import GuardedProcess
from scripts.observation_runtime.aip06_native_session import Session
from scripts.observation_runtime.aip06_scoped_context import ReaderContext


def test_reader_rejects_equal_value_foreign_session_before_other_checks():
    original = Session(name='readonly_reader', plan={}, permit={}, keys=(),
                       argv=(), options={}, observer=None)
    foreign = copy.copy(original)
    assert foreign == original and foreign is not original

    guard = SimpleNamespace(processes=SimpleNamespace(sessions=[original]))
    guarded = object.__new__(GuardedProcess)
    guarded.guard = guard
    guarded.child = foreign
    factory = SimpleNamespace(guard=guard, verify=lambda **kwargs: None)
    context = ReaderContext(SimpleNamespace(factory=factory), None, guarded)

    with pytest.raises(ValueError, match='ORIGINAL_GUARDED_READER_SESSION_REQUIRED'):
        context.verify(deadline_ns=200)
