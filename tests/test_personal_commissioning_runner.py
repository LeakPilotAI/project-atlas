"""Explicit in-memory driver doubles. No real enrollment or provider activity."""
from contextlib import nullcontext
from threading import Event
from types import SimpleNamespace

import pytest
from app.investment.alpaca_iex import IEXFeed
from app.services.personal_paper_runtime import PersonalEnrolledRuntime
from app.services.quality_dips_iex_input import IEXPaperQuotes
from app.services.quality_dips_publication_reader import QualityDipsPublicationReader

from scripts.observation_runtime.personal_commissioning_runner import PersonalCommissioningRunner
from scripts.observation_runtime.personal_coordination_store import NativePersonalCoordinationImages
from scripts.observation_runtime.personal_local_authority import NativePersonalOperatorAuthority
from scripts.observation_runtime.personal_writer_ownership import NativePersonalWriterOwnership


def setup(*, tick=10, frame=True, start_failure=False):
    now, calls = [1000], []
    auth = object.__new__(NativePersonalOperatorAuthority)
    auth.clock = lambda: now[0]
    def verify(request):
        if not 1000 <= now[0] < 1060: raise ValueError('EXPIRED_SYNTHETIC_GRANT')
        return True
    auth.verify = verify
    images = object.__new__(NativePersonalCoordinationImages)
    images.reserve_stop_capacity = lambda **kw: calls.append(('reserve', kw))
    images.require_operation_capacity = lambda **kw: calls.append(('budget', kw))
    images.begin_reserved_stop = lambda: calls.append('stop-reserve')
    ledger = SimpleNamespace(images=images)
    ownership = object.__new__(NativePersonalWriterOwnership)
    ownership.ledger = ledger
    ownership.lease = lambda *a, **kw: nullcontext()
    r = SimpleNamespace(engine=SimpleNamespace(ledger=ledger, entry_admission_closed=False, dispatch_closed=False,
        _grant=lambda stamp: None), ownership=ownership, stopped=Event(), halted=False,
        _now=lambda: now[0], _proof=lambda *a: None, _catch_up_report=lambda stamp: None,
        enrollment={}, grant={})
    owner = object.__new__(PersonalEnrolledRuntime)
    owner.runtime, owner.installation = r, SimpleNamespace(identity=auth)
    owner.admission = SimpleNamespace(enrollment={})
    cut = {'source': {'entries': []}, 'reports': {'reports': [{}]}}
    owner.financial = SimpleNamespace(cut=lambda: cut)
    def start(grant):
        calls.append('start')
        if start_failure: raise ValueError('START_UNKNOWN')
    owner.start = start
    owner.accept = lambda frame: calls.append(('accept', now[0]))
    owner._action = lambda: nullcontext()
    owner.stop = lambda **kw: calls.append('stop') or {'status': 'FLATTENED'}
    def next_frame(timeout):
        assert timeout == 0.2
        now[0] += tick
        return {'SYNTHETIC': True} if frame else None
    source = object.__new__(IEXPaperQuotes)
    source.next = next_frame
    source.feed = object.__new__(IEXFeed)
    source.decision_reader = object.__new__(QualityDipsPublicationReader)
    source.authority, source.session_id = object(), 'synthetic-once'
    runner = PersonalCommissioningRunner(runtime=owner, source=source)
    grant = {'native_grant': {'issued_at': 1000, 'expires_at': 1060, 'session_id': 'synthetic-once'}}
    return SimpleNamespace(**locals())


def test_defaults_refuse():
    with pytest.raises(ValueError): PersonalCommissioningRunner()


def test_one_shot_dispatch_stops_before_grant_expiry_and_reuses_existing_stop():
    s = setup(tick=2)
    result = s.runner.run(s.grant)
    assert result['completed'] and result['accepted_observations'] == 25
    assert s.now[0] == 1052 and s.calls[-1] == 'stop'
    assert all(call[1] < 1052 for call in s.calls if isinstance(call, tuple) and call[0] == 'accept')
    assert s.r.stopped.is_set() and s.r.engine.entry_admission_closed
    with pytest.raises(ValueError, match='ONCE_ONLY'): s.runner.run(s.grant)


def test_slow_source_crossing_expiry_never_dispatches_or_flattens():
    s = setup(tick=61)
    result = s.runner.run(s.grant)
    assert not result['completed'] and result['shutdown']['status'] == 'SHUTDOWN_INCOMPLETE'
    assert not any(isinstance(c, tuple) and c[0] == 'accept' for c in s.calls)
    assert 'stop' not in s.calls and s.r.engine.dispatch_closed


def test_missing_observations_not_a_successful_zero_trade_pilot():
    s = setup(tick=4, frame=False)
    result = s.runner.run(s.grant)
    assert not result['completed'] and result['reason'] == 'NO_ACCEPTED_CURRENT_OBSERVATIONS'
    assert result['shutdown']['status'] == 'FLATTENED'


def test_unknown_start_never_retries_or_invokes_financial_stop():
    s = setup(start_failure=True)
    result = s.runner.run(s.grant)
    assert result['reason'] == 'START_UNKNOWN' and not result['completed']
    assert s.calls.count('start') == 1 and 'stop' not in s.calls


def test_source_replacement_after_read_refuses_dispatch_and_stop():
    s = setup()
    def changed(timeout):
        s.source.authority = object()
        return {'SYNTHETIC': True}
    s.source.next = changed
    result = s.runner.run(s.grant)
    assert not result['completed'] and 'COMPONENT_CHANGED' in result['reason']
    assert 'stop' not in s.calls
    assert not any(isinstance(c, tuple) and c[0] == 'accept' for c in s.calls)


def test_stop_request_during_source_read_closes_entries_without_parallel_dispatch():
    s = setup()
    def stop_during_read(timeout):
        assert s.runner.request_stop() == 'STOP_REQUESTED'
        assert s.r.engine.entry_admission_closed
        return {'SYNTHETIC': True}
    s.source.next = stop_during_read
    result = s.runner.run(s.grant)
    assert s.calls.count('stop') == 1 and result['accepted_observations'] == 0
    assert not any(isinstance(c, tuple) and c[0] == 'accept' for c in s.calls)


def test_stop_before_start_refuses_without_reservation():
    s = setup()
    s.runner.request_stop()
    with pytest.raises(ValueError, match='ONCE_ONLY'): s.runner.run(s.grant)
    assert not s.calls


@pytest.mark.parametrize('resource,count', [('source',127),('reports',124)])
def test_financial_capacity_refuses_before_session_or_financial_effect(resource,count):
    s = setup()
    s.cut[resource]['entries' if resource == 'source' else 'reports'] = [{}]*count
    result = s.runner.run(s.grant)
    assert not result['completed'] and 'CAPACITY' in result['reason']
    assert 'start' not in s.calls and 'stop' not in s.calls
