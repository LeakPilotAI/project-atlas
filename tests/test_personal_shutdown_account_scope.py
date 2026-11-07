"""Shutdown scope and arithmetic with explicit synthetic authority/price ports."""
import copy
from contextlib import nullcontext
from threading import Event, RLock
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest, number
from app.services.quality_dips_shutdown import flatten_and_stop, read_account
from test_quality_dips_autonomous_paper import candidate, entry, monitor, quote, setup


def system(tmp_path):
    n=setup(tmp_path)
    read={'account_id':'SYNTHETIC-STABLE-ACCOUNT','epoch':n.m['epoch']}
    calls=[]
    def current(account,epoch):
        assert (account,epoch)==(read['account_id'],read['epoch'])
        calls.append((account,epoch))
        state=n.ledger.snapshot()
        return {'state':state,'source_revision':state['revision']}
    reader=SimpleNamespace(enrollment=copy.deepcopy(read),read_committed=current)
    scope={'reader_enrollment':copy.deepcopy(read),'process_identity':{'synthetic':'OWNED'},'writer_roster':['decision']}
    grant={'engine_grant':copy.deepcopy(n.grant)}
    owned={'verified':True,'process_identity':scope['process_identity'],'writer_roster':scope['writer_roster'],
           'resources':read,'unknown_writers':[]}
    ownership=SimpleNamespace(lease=lambda request,now:nullcontext(SimpleNamespace(snapshot=owned,
        check=lambda value,stamp:value==owned)),drain=lambda request,now:{'pending':0,'unknown':False,
        'session_id':grant['engine_grant']['session_id'],'enrollment_digest':digest(scope)})
    done=Event();done.set()
    r=SimpleNamespace(engine=n.engine,reader=reader,enrollment=scope,grant=grant,run_done=done,gate=RLock(),
        stopped=Event(),ownership=ownership,_now=lambda:n.now[0],_admission=lambda now:nullcontext(),
        _publish_report=lambda now:calls.append('SYNTHETIC_REPORT_NOT_NATIVE'),_proof=lambda *a:None,
        _incomplete=lambda:None)
    owner=SimpleNamespace(runtime=r,_action=lambda:nullcontext(),stop=n.engine.stop,failed=False)
    def observe(position,timeout):
        assert timeout==2
        n.now[0]+=1  # A new synthetic quote, not conflicting reuse of the last sequence.
        return {'quotes':[quote(n,candidate(n),bid='120',ask='120.1')],
            'observation':{'symbol':position['symbol'],'instrument':position['instrument'],'observed_at':n.now[0],'current':{}}}
    evidence=SimpleNamespace(observe=observe)
    return SimpleNamespace(**locals())


def test_distinct_account_shutdown_really_flattens_partial_position(tmp_path):
    s=system(tmp_path)
    assert entry(s.n)['filled']
    assert monitor(s.n,candidate(s.n),'partial','110',{'fundamentals_score':60})['filled']
    result=flatten_and_stop(s.owner,s.evidence)
    assert result['status']=='FLATTENED' and result['position_state']=='FLAT',result
    assert result['process_shutdown_allowed'] is True
    state=s.n.ledger.snapshot()
    assert number(state['cash'])==number('1015.9136')
    assert all(number(p['remaining'])==number(p['remaining_entry_costs'])==0 for p in state['positions'].values())
    assert [c for c in s.calls if isinstance(c,tuple)]==[(s.read['account_id'],s.read['epoch'])]*2
    before=copy.deepcopy(state)
    assert flatten_and_stop(s.owner,s.evidence)==result and s.n.ledger.snapshot()==before


@pytest.mark.parametrize('damage',['reader-account','runtime-account','epoch'])
def test_conflicting_shutdown_identity_never_retargets_or_claims_flat(tmp_path,damage):
    s=system(tmp_path)
    assert entry(s.n)['filled']
    before=s.n.ledger.snapshot()
    if damage=='reader-account':s.reader.enrollment['account_id']='FOREIGN'
    elif damage=='runtime-account':s.scope['reader_enrollment']['account_id']='FOREIGN'
    else:s.reader.enrollment['epoch']=s.scope['reader_enrollment']['epoch']='FOREIGN-EPOCH'
    with pytest.raises(ValueError,match='SHUTDOWN_READER_ACCOUNT_BINDING'):read_account(s.r)
    result=flatten_and_stop(s.owner,s.evidence)
    assert result['status']=='SHUTDOWN_INCOMPLETE' and result['position_state']=='UNKNOWN'
    after=s.n.ledger.snapshot()
    assert after==before and any(number(p['remaining'])>0 for p in after['positions'].values())
