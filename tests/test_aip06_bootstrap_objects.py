"""Offline escrow/challenge refusals; no native backend or child launcher."""

import copy
from types import SimpleNamespace

import pytest

from scripts.observation_runtime.aip06_bootstrap_evidence import BootstrapObjects
from scripts.observation_runtime.aip06_bootstrap_lease import InheritedBootstrapLease, ObserverBatch, ParentBootstrapLease
from scripts.observation_runtime.aip06_unexpected_probe import candidate_refusal
from aip06_joined_fixture import Joined
from test_aip06_descendant_closure import bind, exit_child
from test_aip06_physical_path import _dmtf


def acquired():
    j=Joined();binding=bind(j.z);x=j.x
    lease=InheritedBootstrapLease(j.box['lease'].descriptor(),
        {'nonce':j.f.request.nonce,'parent':binding.parent,'child':binding.runtime},lambda:x.now[0])
    batch=ObserverBatch(lease)
    handle=x.calls.allocate('process',j.f.pid)
    lease.reserve(lease.owner,'startup-self','handle');lease.bind_native_handle('startup-self',handle)
    lease.seal(retained=('startup-self',*batch.slots))
    cap=BootstrapObjects(descriptor=lease.descriptor,binding=binding,resources=x.ledger,calls=x.calls,
        objects=j.f.objects_port,allocations=x.alloc,clock_ns=lambda:x.now[0])
    return SimpleNamespace(j=j,x=x,binding=binding,lease=lease,cap=cap,handle=handle)


@pytest.mark.parametrize('damage',['nonce','parent','owner','descriptor','sequence','stale','future',
                                  'missing-slot','missing-native','missing-acquisition','wrong-acquired-time','wrong-object','wrong-job','active-capacity'])
def test_incomplete_acquired_object_cut_latches_refusal_without_credit(damage):
    t=acquired();value=t.lease.evidence();before=copy.deepcopy(t.x.ledger.state['resources'])
    native=next(v for v in value['slots'].values() if v['state']=='RETAINED_NATIVE')
    if damage in ('nonce','parent','owner','descriptor'):
        key='parent_owner' if damage=='parent' else damage
        value[key]='0'*len(value[key])
    elif damage=='sequence':value['sequence']=2
    elif damage=='stale':value['at_ns']-=6*10**9
    elif damage=='future':value['at_ns']+=1
    elif damage=='missing-slot':value['slots'].pop(next(iter(value['slots'])))
    elif damage=='missing-native':native.pop('native')
    elif damage=='missing-acquisition':native.clear();native['state']='RESERVED_NOT_ACQUIRED'
    elif damage=='wrong-acquired-time':native['native']['acquired_ns']=value['at_ns']+1
    elif damage=='wrong-object':native['native']['handle']=t.j.f.parent
    elif damage=='wrong-job':t.x.calls.jobs[t.j.f.job]['members'].clear()
    else:next(v for v in value['slots'].values() if v['state']=='OBSERVER_CAPACITY')['active']=1
    with pytest.raises((ValueError,KeyError)):t.cap.accept(value)
    assert t.cap.failed
    with pytest.raises(ValueError):t.cap.verify()
    assert all(not t.x.ledger.state['resources'][k]['closed'] for k in t.lease.descriptor['slots'])
    assert all(t.x.ledger.state['resources'][k]==v for k,v in before.items())


def test_retained_continuity_rejects_original_handle_reuse():
    t=acquired();t.cap.accept(t.lease.evidence())
    t.x.calls.handles[t.handle]=('process',t.j.f.peer.runtime['pid'])
    with pytest.raises(ValueError,match='HANDLE_REUSED'):t.cap.verify()
    assert not t.cap.released


def test_replay_and_premature_release_never_refund_escrow():
    t=acquired();cut=t.lease.evidence();t.cap.accept(cut)
    with pytest.raises(ValueError):t.cap.release_reservations()
    with pytest.raises(ValueError):t.cap.dispose_after_exit()
    with pytest.raises(ValueError):t.cap.accept(cut)
    assert t.cap.failed and not t.cap.released


def test_original_exit_close_and_atomic_release_are_idempotent():
    t=acquired();t.cap.accept(t.lease.evidence());exit_child(t.j.z)
    t.cap.dispose_after_exit();t.cap.release_reservations();head=t.x.ledger.head
    t.cap.dispose_after_exit();t.cap.release_reservations()
    assert t.x.ledger.head==head and not t.cap.live
    assert all(t.x.ledger.state['resources'][k]['closed'] for k in t.lease.descriptor['slots'])


def test_failed_native_close_cannot_report_release():
    t=acquired();t.cap.accept(t.lease.evidence());exit_child(t.j.z)
    local=next(iter(t.cap.live.values()))['local'];close=t.x.calls.close
    def fail(handle):
        if handle==local:raise OSError('injected close failure')
        close(handle)
    t.x.calls.close=fail
    with pytest.raises(OSError):t.cap.dispose_after_exit()
    with pytest.raises(ValueError):t.cap.release_reservations()
    assert not t.cap.released and t.cap.live


def test_escrow_reservation_collision_is_atomic_and_owner_scoped():
    t=acquired();head=t.x.ledger.head
    with pytest.raises(ValueError):t.x.ledger.reserve_bootstrap(t.j.f.owner,t.j.f.request.nonce)
    assert t.x.ledger.head==head
    with pytest.raises(ValueError):t.x.ledger.reserve_bootstrap('foreign','f'*32)
    with pytest.raises(ValueError):t.x.ledger.close_bootstrap(t.j.f.owner,SimpleNamespace(closed=lambda *a:True))
    assert t.x.ledger.head==head


def test_interrupted_escrow_journal_cannot_reuse_a_previous_receipt():
    t=acquired();head=t.x.ledger.head
    def fail(*a):raise OSError('injected interrupted durable reservation')
    t.x.ledger.journal.append=fail
    pending=ParentBootstrapLease(t.x.ledger,t.j.f.owner,'e'*32,lambda:t.x.now[0])
    with pytest.raises(OSError):pending.reserve()
    assert t.x.ledger.uncertain and t.x.ledger.head==head
    with pytest.raises(ValueError):t.x.ledger.reserve_bootstrap(t.j.f.owner,'f'*32)


def test_prospective_group_validation_does_not_alias_or_rewrite_durable_history():
    t=acquired();ledger=t.x.ledger;before=copy.deepcopy(ledger._rows)
    ledger.reserve_bootstrap(t.j.f.owner,'e'*32)
    assert ledger._rows[:-1]==before and ledger.journal.read()==ledger._rows
    before=copy.deepcopy(ledger._rows);head=ledger.head
    bad=copy.deepcopy(ledger.state);bad['owners'].pop(t.j.f.owner)
    with pytest.raises(ValueError):ledger._commit(bad)
    assert ledger.head==head and ledger._rows==before and ledger.journal.read()==before
    # The journal owns a separate JSON copy. A conflicting rewrite cannot be
    # hidden by aliasing the validator's retained history to that mutable port.
    ledger.journal.rows[-1]['state']['cpu_ns']+=1
    with pytest.raises(ValueError,match='EXTERNAL_JOURNAL_CHANGE'):ledger.read()
    assert ledger._rows==before


@pytest.mark.parametrize('damage',['missing','incomplete','stale','parent','birth','command','image','duplicate','job','native-image'])
def test_unexpected_challenge_requires_independent_complete_ownership(damage):
    t=acquired();x=t.x;f=t.j.f
    def read(**kw):
        rows=[x.calls.rows[f.peer.runtime['pid']],x.calls.rows[f.pid]]
        rows=[{'ProcessId':r['pid'],'ParentProcessId':r['parent_pid'],'CreationDate':_dmtf(r['created']),
               'ExecutablePath':r['image'],'CommandLine':r['command_line']} for r in rows]
        result={'complete':True,'error':None,'rows':rows,'started_ns':x.now[0],'finished_ns':x.now[0]}
        if damage=='missing':result['rows']=rows[:1]
        elif damage=='incomplete':result['complete']=False
        elif damage=='stale':result.update(started_ns=x.now[0]-1,finished_ns=x.now[0]-1)
        elif damage=='duplicate':result['rows']=[rows[0],rows[0]]
        elif damage=='parent':rows[1]['ParentProcessId']=999
        elif damage=='birth':rows[1]['CreationDate']=_dmtf(x.calls.rows[f.pid]['created']+100)
        elif damage=='command':rows[1]['CommandLine']='unapproved'
        elif damage=='image':rows[1]['ExecutablePath']=r'D:\wrong.exe'
        return result
    if damage=='job':x.calls.jobs[f.peer.api.job]['members'].add(999)
    if damage=='native-image':x.files.describe=lambda h:{'reparse':True}
    with pytest.raises((ValueError,KeyError)):
        candidate_refusal(binding=f.peer,auxiliary=t.binding,tables=SimpleNamespace(read=read),calls=x.calls,
            files=x.files,child=SimpleNamespace(image_handle=f.source),clock_ns=lambda:x.now[0],deadline_ns=x.now[0]+5*10**9)
    assert not t.binding.finished and not x.ledger.state['resources'][f.slot]['closed']
