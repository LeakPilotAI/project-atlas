"""Resource closure evidence must refer to the original retained Session."""
import copy

import pytest

from scripts.observation_runtime.aip06_native_session import Session, WindowsSessionPort


def test_foreign_equal_value_session_cannot_claim_resources_closed():
    original = Session(name='case_host', plan={}, permit={}, keys=(),
                       argv=(), options={}, observer=None)
    original.closed = True
    foreign = copy.copy(original)
    assert foreign == original and foreign is not original
    port = object.__new__(WindowsSessionPort)
    port.sessions = [original]
    with pytest.raises(ValueError, match='ORIGINAL_RETAINED_RESOURCE_CLOSE_PROOF_REQUIRED'):
        port.resources_closed(foreign, ())
    assert port.resources_closed(original, ()) is True
