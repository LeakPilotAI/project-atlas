"""Pure cut checks only:no native constructors,files,ACLs or fixture roots."""
import copy

import pytest
from app.services.paper_financial_replay import digest

from scripts.volume_inspector.native_continuation_fixture import (
    NativeContinuationUnknown,
    NativeSwitchFixture,
    validate_switch_cut,
)


def evidence():
    binding=lambda n:{'id':[1,2,n],'sha256':str(n)*64}
    selection={k:binding(n) for n,k in enumerate(('intent','record','commit','ack'),1)}
    pin={'schema':'NATIVE_SWITCH_FIXTURE_PIN_V1','root':[1,2,3],'scope':binding(5),'selection':selection}
    current={k:{'segments':[{'root':[1,2,i+10],'projection':None}]} for i,k in enumerate(sorted(NativeSwitchFixture.ROLES))}
    cuts={k:{'state':{'revision':2,'cash':'1000'},'pin':v} for k,v in current.items()}
    before={k:digest(['previous',k]) for k in current}
    values={'intent':{'schema':'NATIVE_SWITCH_FIXTURE_INTENT_V1','before':before},
        'record':{'schema':'NATIVE_SWITCH_FIXTURE_RECORD_V1','intent':selection['intent'],'before':before,
            'selected':{k:digest(v) for k,v in current.items()},'state_digests':{k:digest(v['state']) for k,v in cuts.items()},
            'roots':{k:[{'source':s['root'],'projection':s['projection']} for s in v['segments']] for k,v in current.items()}},
        'commit':{'schema':'NATIVE_SWITCH_FIXTURE_COMMIT_V1','record':selection['record'],'intent':selection['intent']},
        'ack':{'schema':'NATIVE_SWITCH_FIXTURE_ACK_V1','commit':selection['commit']}}
    return pin,values,current,cuts,{'status':'ACKNOWLEDGED','catalog':digest(pin)}


def test_complete_cut_is_pure_and_nonmutating():
    args=evidence();before=copy.deepcopy(args)
    assert validate_switch_cut(*args) is True
    assert args==before


@pytest.mark.parametrize('part',['pin','intent','record','commit','ack','status'])
def test_wrong_versions_or_status_refuse(part):
    pin,values,current,cuts,status=evidence()
    if part=='pin':pin['schema']='OPERATIONAL'
    elif part=='status':status['status']='PENDING'
    else:values[part]['schema']='FOREIGN'
    with pytest.raises(NativeContinuationUnknown):validate_switch_cut(pin,values,current,cuts,status)


@pytest.mark.parametrize('damage',['old-ack','missing-ack','partial-selection','root-substitution','projection-substitution','state-change','partial-cut','source-advance','foreign-before','extra-role','missing-role','wrong-commit','wrong-ack','wrong-intent','missing-values','missing-state-digest'])
def test_partial_conflicting_or_replayed_cut_refuses(damage):
    pin,values,current,cuts,status=evidence();role='QD_SOURCE';r=values['record']
    if damage=='old-ack':status['catalog']=digest('OLD-CATALOG')
    elif damage=='missing-ack':status=None
    elif damage=='partial-selection':r['selected'].pop(role)
    elif damage=='root-substitution':current[role]['segments'][0]['root']=[99,99,99]
    elif damage=='projection-substitution':r['roots'][role][0]['projection']={'root':[99,99,99]}
    elif damage=='state-change':cuts[role]['state']['cash']='2000'
    elif damage=='partial-cut':cuts.pop(role)
    elif damage=='source-advance':cuts[role]['pin']={'segments':[]}
    elif damage=='foreign-before':r['before']={}
    elif damage=='extra-role':current['FOREIGN']={}
    elif damage=='missing-role':current.pop(role)
    elif damage=='wrong-commit':values['commit']['record']={}
    elif damage=='wrong-ack':values['ack']['commit']={}
    elif damage=='wrong-intent':r['intent']={}
    elif damage=='missing-values':values.pop('ack')
    else:r['state_digests'].pop(role)
    with pytest.raises(NativeContinuationUnknown):validate_switch_cut(pin,values,current,cuts,status)
