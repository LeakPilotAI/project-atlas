"""Pure policy/identity checks; no storage enrollment or operational startup."""
import json
from pathlib import Path

import pytest
from app.services.paper_exit_history import stop_command, validate_stop
from app.services.unified_portfolio_custody import portfolio_transition


def test_intermitent_policy_has_no_always_on_or_startup_authority():
    p=json.loads((Path(__file__).resolve().parents[1]/'docs/ATLAS_DESKTOP_SESSION_POLICY_V1.json').read_text())
    assert p['schema']=='ATLAS_DESKTOP_SESSION_POLICY_V1'
    assert p['operating_model']=='INTERMITTENT_USER_STARTED_DESKTOP_SESSIONS'
    assert p['paper_execution']=='AUTONOMOUS_WITHIN_EXPLICITLY_STARTED_SESSION' and p['per_trade_confirmation_required'] is False
    for key in ('always_on_required','automatic_restart_allowed','restart_resets_capacity','startup_authorization_granted','live_money_implementation_allowed'):
        assert p[key] is False
    assert p['deployment_drive']=='D:' and p['governance_decisions_changed']==0

@pytest.mark.parametrize('field,value',[('schema','OTHER'),('session_id','other'),('command_id','caller'),('reason','STRATEGY_EXIT'),('requested_at',-1)])
def test_stop_context_substitution_refused(field,value):
    g={'session_id':'one'};s=stop_command(g,'USER_SHUTDOWN',1);s[field]=value
    with pytest.raises(ValueError):validate_stop(s,g)


def test_new_session_preserves_old_operations_and_cumulative_capacity():
    from app.services.paper_financial_replay import digest
    grant={'session_id':'second'}
    old={'last_clock':1,'session':'old','entry_closed':True,'finalized':{'retained':'final'},
        'sessions':['old'],'operations':{'historic':{'state':'ACKNOWLEDGED','receipt':'original'}},
        'revision':10,'stop_context':{'historic':'stop'}}
    new=portfolio_transition({}, {}, old, {'kind':'SESSION','at':2,'order_id':'session',
        'payload':{'grant_digest':digest(grant),'session_id':'second'}})
    assert new['revision']==11 and new['operations']==old['operations'] and old['finalized']=={'retained':'final'}
    assert new['sessions']==['old',digest(grant)] and 'stop_context' not in new
    assert 128-new['revision']<128-old['revision']
