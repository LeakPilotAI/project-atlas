"""Runtime proof dispatch with explicit synthetic native/source dependency doubles."""
import copy

import pytest
from app.services.paper_financial_replay import digest
from app.services.quality_dips_iex_input import IEXPaperQuotes
from test_personal_engine_session import setup as session_setup

from scripts.observation_runtime.personal_local_authority import NativePersonalRuntimeAuthority
from scripts.observation_runtime.personal_runtime_current import PersonalRuntimeCurrent
from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock
from scripts.observation_runtime.personal_writer_ownership import NativePersonalWriterOwnership


def setup(monkeypatch):
    a, operator, session, grant = session_setup(monkeypatch)
    enrollment = {'schema': 'QD_AUTO_LOCAL_RUNTIME_V3', 'scope': 'LOCAL_ENROLLED'}
    custody = object.__new__(PersonalRuntimeCurrent)
    custody.clock = a.clock
    current = {'SYNTHETIC_CURRENT': 'ACKNOWLEDGED'}
    custody.current = lambda request, now: copy.deepcopy(current)
    owner = object.__new__(NativePersonalWriterOwnership)
    owner.authority = operator
    owner._context = lambda request: None
    drain = {'pending': 0, 'unknown': False, 'SYNTHETIC': True}
    owner.drain = lambda request, now: copy.deepcopy(drain)
    source = object.__new__(IEXPaperQuotes)
    frame = {'session_id': grant['session_id'], 'SYNTHETIC_OBSERVATION': True}
    source.verify_observation = lambda candidate, now: candidate == frame
    sample = {'SYNTHETIC_CLOCK': True}
    monkeypatch.setattr(LocalWindowsClock, 'verify_runtime_sample', lambda self, value: value == sample)
    port = NativePersonalRuntimeAuthority(operator=operator, engine_session=session, custody=custody,
                                          ownership=owner, source=source, enrollment=enrollment)
    request = {'enrollment': enrollment, 'grant': {'schema': 'QD_AUTO_LOCAL_SESSION_V3',
                'enrollment_digest': digest(enrollment), 'engine_grant': grant}}
    return a, port, request, current, drain, frame, sample


def test_existing_runtime_proof_shapes_require_distinct_evidence(monkeypatch):
    a, port, session, current, drain, frame, sample = setup(monkeypatch)
    cases = [('CLOCK', {'enrollment_digest': digest(port.enrollment), 'sample': sample}),
             ('SESSION', session), ('CURRENT', current), ('DRAIN', drain), ('OBSERVATION', frame)]
    for kind, request in cases:
        result = port.verify(kind, request, now=a.now[0])
        assert result == {'schema': 'QD_AUTO_LOCAL_AUTHORITY_V3', 'kind': kind, 'verified': True,
                          'binding': digest(request), 'scope': 'LOCAL_ENROLLED', 'issuer_id': 'PERSONAL_LOCAL_OPERATOR'}


@pytest.mark.parametrize('kind', ['CLOCK', 'SESSION', 'CURRENT', 'DRAIN', 'OBSERVATION', 'UNSUPPORTED'])
def test_unverified_proofs_never_become_authority(monkeypatch, kind):
    a, port, session, current, drain, frame, _sample = setup(monkeypatch)
    port.verify('SESSION', session, now=a.now[0])
    request = {'CLOCK': {'enrollment_digest': digest(port.enrollment), 'sample': {}},
               'SESSION': {**session, 'enrollment': {}}, 'CURRENT': {**current, 'foreign': True},
               'DRAIN': {**drain, 'pending': 1}, 'OBSERVATION': {**frame, 'foreign': True},
               'UNSUPPORTED': {}}[kind]
    with pytest.raises(ValueError): port.verify(kind, request, now=a.now[0])


def test_session_required_revocation_and_component_substitution(monkeypatch):
    a, port, session, current, _drain, _frame, _sample = setup(monkeypatch)
    with pytest.raises(ValueError, match='SESSION_MISSING'): port.verify('CURRENT', current, now=a.now[0])
    port.verify('SESSION', session, now=a.now[0])
    port.operator.revoke()
    with pytest.raises(ValueError): port.verify('CURRENT', current, now=a.now[0])
    port.source = object()
    with pytest.raises(ValueError, match='CHANGED'): port.verify('CURRENT', current, now=a.now[0])


def test_default_refusal():
    with pytest.raises(ValueError): NativePersonalRuntimeAuthority()
