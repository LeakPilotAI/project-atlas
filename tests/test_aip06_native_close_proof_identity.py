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


@pytest.mark.parametrize('keys', [(), ('resource',), ('resource', 'resource'),
                                  ('resource', 'foreign'), ('resource', 42)])
def test_resource_closure_refuses_incomplete_or_foreign_proof_keys(keys):
    original = Session(name='case_host', plan={}, permit={'slots': ('process',)},
                       keys=('resource',), argv=(), options={}, observer=None)
    original.closed = True
    port = object.__new__(WindowsSessionPort)
    port.sessions = [original]
    with pytest.raises(ValueError, match='EXACT_RETAINED_RESOURCE_CLOSE_PROOF_KEYS_REQUIRED'):
        port.resources_closed(original, keys)


def test_resource_closure_accepts_complete_original_key_set():
    original = Session(name='case_host', plan={}, permit={'slots': ('process',)},
                       keys=('resource',), argv=(), options={}, observer=None)
    original.closed = True
    port = object.__new__(WindowsSessionPort)
    port.sessions = [original]
    port.resources = type('Resources', (), {'state': {'resources': {
        'resource': {'owner': 'owner'}, 'process': {'owner': 'process-owner'}}}})()
    port.closed_proofs = {('owner', 'resource'), ('process-owner', 'process')}
    assert port.resources_closed(original, ('process', 'resource')) is True
