"""Actual IEX parser/engine with explicit synthetic publication/operator ports."""
import copy
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from app.investment.alpaca_iex import FEED
from app.investment.quality_dips_candidate_evidence import CandidateEvidenceAdapter
from app.services.paper_financial_replay import strict
from app.services.paper_source_publication import QualityDipsSourcePublication
from app.services.quality_dips_iex_input import IEXPaperQuotes
from app.services.quality_dips_publication_reader import QualityDipsPublicationReader
from test_alpaca_iex import authority, feed, message
from test_quality_dips_autonomous_paper import candidate, quote
from test_quality_dips_autonomous_paper import setup as engine_setup

from scripts.observation_runtime.personal_engine_session import NativePersonalEngineSession
from scripts.observation_runtime.personal_local_authority import NativePersonalOperatorAuthority
from scripts.observation_runtime.personal_market_inputs import NativePersonalMarketInputs


def setup(tmp_path):
    n = engine_setup(tmp_path)
    n.engine.stop()
    n.grant.update(feed_id=FEED, session_id='SYNTHETIC-MARKET-INPUTS')
    n.engine.start(n.grant)
    b = candidate(n)
    packet = {'schema':'QD_SCANNER_PUBLICATION_V1','source_id':'SYNTHETIC-NOT-ENROLLED',
              'revision':1,'observed_at':n.now[0],'bundles':[b],'monitors':{}}
    f, _ = feed()
    clock = lambda: n.now[0]
    f.clock = clock
    f.receive(json.dumps([message(t=datetime.fromtimestamp(clock(),UTC).isoformat().replace('+00:00','Z'))]))
    flags = {'source':True,'data_action':True}
    publication = object.__new__(QualityDipsSourcePublication)
    def read():
        if not flags['source']: raise ValueError('SYNTHETIC_SOURCE_REVOKED')
        return copy.deepcopy(packet)
    publication.read_current = read
    reader = object.__new__(QualityDipsPublicationReader)
    reader.source, reader._verify = publication, lambda: None
    reader.read_request = lambda timeout: {'instrument':b['instrument'],'bundles':packet['bundles'],'observation':None}
    source = IEXPaperQuotes(feed=f, execution_authority=authority(b['instrument'],quote(n,b)['calendar']),
                           session_id=n.grant['session_id'],decision_reader=reader)
    operator = object.__new__(NativePersonalOperatorAuthority)
    operator.clock = clock
    def activation(action):
        if not flags['data_action']: raise ValueError('SYNTHETIC_OPERATOR_REVOKED')
        return {'SYNTHETIC_ACTION':action}
    operator.activation = activation
    session = object.__new__(NativePersonalEngineSession)
    session.operator, session.manifest = operator, n.m
    def session_verify(grant, now):
        if grant != n.grant or not grant['issued_at'] <= now < grant['expires_at']:
            raise ValueError('SYNTHETIC_SESSION_REFUSED')
        return {'SYNTHETIC_SESSION':True}
    session.verify = session_verify
    port = NativePersonalMarketInputs(operator=operator, session=session, source=source)
    return SimpleNamespace(**locals())


def test_current_publication_and_real_iex_packet_bind_existing_candidate(tmp_path):
    s = setup(tmp_path)
    s.port.bind_session(s.n.grant)
    preflight = s.port.preflight()
    assert preflight['symbols'] == ['MSFT']
    adapter = CandidateEvidenceAdapter(ranking_authority=s.port, execution_authority=s.port)
    assert strict(adapter.candidate(s.b, level='L1', now=s.clock()))['ranking']['symbol'] == 'MSFT'
    frame = s.source.next(.01)
    proof = s.port.verify(frame['request'], now=s.clock())
    assert proof['schema'] == 'QD_AUTO_SOURCE_PROOF_V1' and proof['verified']
    assert s.n.ledger.snapshot()['revision'] == 0


def test_verified_no_candidate_observation_is_a_real_no_fill_not_missing_data(tmp_path):
    s = setup(tmp_path)
    s.packet['bundles'] = []
    s.packet['monitors'] = {s.b['instrument']['instrument_id']:{'instrument':s.b['instrument'],
        'symbol':'MSFT','observed_at':s.clock(),'current':{'evidence_quality':'UNAVAILABLE'}}}
    s.port.bind_session(s.n.grant)
    assert s.port.preflight()['symbols'] == ['MSFT']
    s.n.engine.source_authority = s.port
    frame = s.source.next(.01)
    result = s.n.engine.step('no-eligible-entry', **frame['request'])
    assert result['filled'] is False and result['reason'] == 'NO_ELIGIBLE_CANDIDATE'
    state = s.n.ledger.snapshot()
    assert state['cash'] == '1000' and state['revision'] == 0 and state['positions'] == {}


@pytest.mark.parametrize('damage',['unbound','source','permission','foreign-bundle','disconnect','reader','expiry'])
def test_unavailable_or_substituted_evidence_refuses(tmp_path, damage):
    s = setup(tmp_path)
    if damage != 'unbound': s.port.bind_session(s.n.grant)
    bundle = copy.deepcopy(s.b)
    if damage == 'source': s.flags['source']=False
    elif damage == 'permission': s.flags['data_action']=False
    elif damage == 'foreign-bundle': bundle['board'][0]['opportunity_score']=999
    elif damage == 'disconnect': s.f.disconnect()
    elif damage == 'reader': s.source.decision_reader=object()
    elif damage == 'expiry': s.n.now[0]=s.n.grant['expires_at']
    with pytest.raises(ValueError):
        if damage == 'foreign-bundle': s.port.verify_current(bundle, now=s.clock())
        else: s.port.preflight()
    assert s.n.ledger.snapshot()['revision'] == 0


def test_shutdown_requires_issued_fresh_bid_but_not_a_new_fundamental_ranking(tmp_path):
    s = setup(tmp_path)
    s.port.bind_session(s.n.grant)
    evidence = s.source.observe({'instrument':s.b['instrument'],'symbol':'MSFT'}, .1)
    request = {**evidence,'bundles':[],'shutdown_mode':'SHUTDOWN_FLATTEN'}
    s.flags['source']=False
    assert s.port.verify(request, now=s.clock())['verified']
    s.f.disconnect()
    with pytest.raises(ValueError): s.port.verify(request, now=s.clock())


def test_defaults_refuse():
    with pytest.raises(ValueError): NativePersonalMarketInputs()
