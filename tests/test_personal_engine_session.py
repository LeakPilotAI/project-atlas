import copy

import pytest
from app.investment.alpaca_iex import FEED
from app.services.paper_financial_replay import digest
from test_personal_local_authority_memory import authority
from test_personal_paper_inception_memory import system

from scripts.observation_runtime.personal_engine_session import NativePersonalEngineSession
from scripts.observation_runtime.personal_local_authority import NativePersonalOperatorAuthority


def setup(monkeypatch):
    a, s = authority(monkeypatch), system('QUALITY_DIPS')
    a.now[0] = s.m['opened_at']+1
    a.value.update(accounts={'QUALITY_DIPS': digest(s.n)}, issued_at=a.now[0], expires_at=a.now[0]+100)
    operator = NativePersonalOperatorAuthority(policy=a.port.policy, enrollment=s.n, reader=a.reader,
                                               clock=a.clock, runtime_id='SYNTHETIC')
    port = NativePersonalEngineSession(operator=operator, manifest=s.m, calendar_id='SYNTHETIC-CALENDAR')
    g = {'schema':'QD_AUTO_ENGINE_SESSION_V5','session_id':a.value['activation_id'],
         'epoch':s.m['epoch'],'issued_at':a.now[0],'expires_at':a.now[0]+60,
         'capabilities':['AUTO_ENTRY','AUTO_EXIT'],'feed_id':FEED,'calendar_id':'SYNTHETIC-CALENDAR'}
    s.ledger.db.close()
    return a, operator, port, g


def test_native_operator_binds_existing_engine_grant_without_market_authority(monkeypatch):
    a, operator, port, g = setup(monkeypatch)
    original = copy.deepcopy(a.value)
    proof = port.verify(g, now=a.now[0])
    assert proof['schema'] == 'QD_AUTO_SESSION_PROOF_V1' and proof['binding'] == digest(g)
    assert proof['verified'] is True and proof['market_evidence_verified'] is False
    assert a.value == original
    operator.revoke()
    with pytest.raises(ValueError): port.verify(g, now=a.now[0])


@pytest.mark.parametrize('damage',['fixture','feed','calendar','epoch','duration','expiry','operator','manifest'])
def test_engine_session_refuses_foreign_or_expired_scope(monkeypatch, damage):
    a, _operator, port, g = setup(monkeypatch)
    if damage == 'fixture': g['schema']='QD_AUTO_SESSION_FIXTURE_V1'
    elif damage == 'feed': g['feed_id']='OTHER'
    elif damage == 'calendar': g['calendar_id']='OTHER'
    elif damage == 'epoch': g['epoch']='OTHER'
    elif damage == 'duration': g['expires_at']+=1
    elif damage == 'expiry': a.now[0]=g['expires_at']
    elif damage == 'operator': a.sid[0]='OTHER'
    else: port.manifest['opening_cash']='2000'
    with pytest.raises(ValueError): port.verify(g, now=a.now[0])


def test_defaults_refuse():
    with pytest.raises(ValueError): NativePersonalEngineSession()
