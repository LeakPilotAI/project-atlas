"""Actual IEX parser, candidate/V5 planner and native writer; synthetic source authority."""
import copy
import json
from types import SimpleNamespace

import pytest
import test_qd_v5_pre_effect_native as native_fixtures
from app.investment.alpaca_iex import FEED
from app.services.paper_financial_replay import body
from app.services.paper_market_observers import IEXMarketObserver
from app.services.quality_dips_iex_input import IEXPaperQuotes
from app.services.quality_dips_unified_planner import QualityDipsUnifiedPlanner
from app.services.quality_dips_unified_writer import EnrolledQualityDipsWriter
from test_alpaca_iex import authority, feed, message
from test_qd_unified_writer_native import FixtureCustodyAuthority
from test_qd_v5_pre_effect_native import capture
from test_quality_dips_autonomous_paper import candidate, quote

system = native_fixtures.system


def components(s):
    grant = copy.deepcopy(s.grant)
    grant['runtime_grant']['engine_grant']['feed_id'] = FEED
    s.runtime.start(grant)
    n = s.x.n
    n.now[0] += 1
    b = candidate(n)
    f, _ = feed()
    f.clock = lambda: n.now[0]
    f.receive(json.dumps([message(bp=99.9, ap=100, t='2026-10-26T14:00:02Z')]))
    observer = IEXMarketObserver(f, calendar=SimpleNamespace(read=lambda now: 'OPEN'), clock=f.clock)
    reader = SimpleNamespace(value={'instrument': b['instrument'], 'bundles': [b], 'observation': None})
    reader.read_request = lambda timeout: copy.deepcopy(reader.value)
    quotes = IEXPaperQuotes(feed=f, execution_authority=authority(b['instrument'], quote(n, b)['calendar']))

    class SourceAuthority(FixtureCustodyAuthority):
        valid = True
        def verify_frame(self, binding, frame, observation, cut):
            return self.valid and observer.verify_observation(observation)
        def verify_planner_components(self, binding, actual):
            return self.valid and actual == {'writer': writer, 'observer': observer, 'quotes': quotes, 'reader': reader}
        def verify_decision_source(self, binding, request, observation, cut):
            return self.valid and body(request) == body(reader.value) and observer.verify_observation(observation)

    a = SourceAuthority(s.runtime)
    writer = EnrolledQualityDipsWriter(runtime=s.runtime, authority=a)
    planner = QualityDipsUnifiedPlanner(writer=writer, observer=observer, quotes=quotes, reader=reader)
    return SimpleNamespace(**locals())


@pytest.mark.asyncio
async def test_source_iex_to_actual_v5_entry_partial_final_and_native_reconciliation(system):
    c = components(system)
    observation = await c.observer.observe()
    before = capture(system)
    p = await c.planner.next_proposal(observation, c.writer._cut())
    assert capture(system) == before and p['command']['quote']['price'] == '100'
    assert p['command']['evidence']['request']['bundles'][0]['publication'] == c.b['publication']
    c.a.reserved = {'state': 'RESERVED', 'binding': 'synthetic-custody-reservation'}
    receipt = c.writer.dispatch(p, c.a.reserved)
    assert receipt['state_digest'] and c.writer._cut()['state']['revision'] == 1
    c.n.now[0] += 1
    c.f.receive(json.dumps([message(bp=110, ap=110.1, t='2026-10-26T14:00:03Z')]))
    c.reader.value = {'instrument': c.b['instrument'], 'bundles': [], 'observation': {
        'symbol': c.b['instrument']['symbol'], 'instrument': c.b['instrument'],
        'observed_at': c.n.now[0], 'current': {'evidence_quality': 'HIGH', 'fundamentals_score': 60}}}
    p = await c.planner.next_proposal(await c.observer.observe(), c.writer._cut())
    assert p['kind'] == 'EXIT' and p['command']['quantity'] == '0.4'
    assert c.writer.dispatch(p, c.a.reserved)['state_digest'] and c.writer._cut()['state']['revision'] == 2
    assert next(iter(c.writer._cut()['state']['positions'].values()))['remaining'] == '0.6'
    c.n.now[0] += 1
    c.f.receive(json.dumps([message(bp=120, ap=120.1, t='2026-10-26T14:00:04Z')]))
    c.reader.value['observation'].update(observed_at=c.n.now[0], current={'classification': 'THESIS_BROKEN'})
    p = await c.planner.next_proposal(await c.observer.observe(), c.writer._cut())
    assert p['kind'] == 'EXIT' and p['command']['quantity'] == '0.6'
    assert c.writer.dispatch(p, c.a.reserved)['state_digest']
    state = c.writer._cut()['state']
    assert state['revision'] == 3 and state['cash'] == '1015.9136'
    assert state['gross'] == '16.0' and state['costs'] == '0.0864'
    assert all(p['remaining'] == '0.0' for p in state['positions'].values())


@pytest.mark.asyncio
async def test_no_signal_does_not_consume_v5_sequence_or_write(system):
    c = components(system)
    c.reader.value = None
    before = capture(system)
    for _ in range(2):
        assert await c.planner.next_proposal(await c.observer.observe(), c.writer._cut()) is None
    assert capture(system) == before and system.runtime.runtime.sequence == 0


@pytest.mark.asyncio
async def test_stopped_planner_does_not_read_another_candidate(system):
    c = components(system)
    o = await c.observer.observe()
    assert system.runtime.stop() == 'STOPPED'
    def forbidden(timeout): raise AssertionError('Candidate read after Stop')
    c.reader.read_request = forbidden
    before = capture(system)
    with pytest.raises(ValueError): await c.planner.next_proposal(o, c.writer._cut())
    assert capture(system) == before


@pytest.mark.asyncio
async def test_actual_hold_decision_is_healthy_and_does_not_consume_sequence(system):
    c = components(system)
    p = await c.planner.next_proposal(await c.observer.observe(), c.writer._cut())
    c.a.reserved = {'state': 'RESERVED', 'binding': 'synthetic-reservation'}
    c.writer.dispatch(p, c.a.reserved)
    c.reader.value = {'instrument': c.b['instrument'], 'bundles': [], 'observation': {
        'symbol': c.b['instrument']['symbol'], 'instrument': c.b['instrument'],
        'observed_at': c.n.now[0], 'current': {}}}
    before = capture(system)
    assert await c.planner.next_proposal(await c.observer.observe(), c.writer._cut()) is None
    assert c.planner.last['reason'] == 'HOLD_EXISTING_POSITION'
    assert capture(system) == before and system.runtime.runtime.sequence == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('damage', ['authority', 'stale-ranking', 'missing-entitlement', 'changed-feed', 'source-head', 'unknown'])
async def test_source_failures_refuse_without_financial_effect(system, damage):
    c = components(system)
    o = await c.observer.observe()
    cut = c.writer._cut()
    if damage == 'authority': c.a.valid = False
    elif damage == 'stale-ranking': c.reader.value['bundles'][0]['publication']['expires_at'] = c.n.now[0]
    elif damage == 'missing-entitlement': c.quotes.authority = None
    elif damage == 'changed-feed': c.f.disconnect()
    elif damage == 'source-head': cut['head'] = 'f' * 64
    else: system.flags['unknown'] = True
    before = capture(system)
    with pytest.raises(ValueError): await c.planner.next_proposal(o, cut)
    assert capture(system) == before and system.x.n.ledger.snapshot()['revision'] == 0
