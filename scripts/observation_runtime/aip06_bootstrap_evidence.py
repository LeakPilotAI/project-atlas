"""Root-retained bootstrap escrow/object handoff, never a financial ACK."""

import copy

from app.services.paper_financial_replay import digest
from scripts.observation_runtime.aip06_bootstrap_lease import InheritedBootstrapLease
from scripts.observation_runtime.aip06_harness import SCOPE_HASH, need


class BootstrapObjects:
    def __init__(self, *, descriptor, binding, resources, calls, objects, allocations, clock_ns):
        # Reuse exact nonce/parent/shape/time checks; this does not create a
        # second reservation ledger or adopt an unregistered process.
        InheritedBootstrapLease(descriptor,{'nonce':binding.request.nonce,
            'parent':binding.parent,'child':binding.runtime},clock_ns)
        self.descriptor=copy.deepcopy(descriptor);self.binding=binding
        self.resources,self.calls,self.objects,self.allocations,self.clock=resources,calls,objects,allocations,clock_ns
        self.head=digest({k:v for k,v in descriptor.items() if k!='reservation_head'})
        self.sequence=0;self.cut=None;self.live={};self.failed=False
        self.released=False;self.done=set();self.terminal=None

    def accept(self, value):
        try:return self._accept(value)
        except BaseException:
            self.failed=True
            raise

    def _accept(self, value):
        self.binding.verify()
        need(not self.failed and self.objects is not None and type(value) is dict
             and set(value)=={'schema','scope','nonce','owner','parent_owner','sequence','at_ns','descriptor',
                              'slots','parent_reservations_released','financial_ack'}
             and value['schema']=='AIP06_BOOTSTRAP_OBJECT_CUT_V1' and value['scope']==SCOPE_HASH
             and value['nonce']==self.binding.request.nonce and value['owner']==digest(self.binding.runtime)
             and value['parent_owner']==digest(self.binding.parent) and value['descriptor']==self.head
             and type(value['sequence']) is int and value['sequence']==self.sequence+1
             and type(value['at_ns']) is int and 0<=self.clock()-value['at_ns']<=5*10**9
             and value['parent_reservations_released'] is False and value['financial_ack'] is False
             and set(value['slots'])==set(self.descriptor['slots']), 'BOOTSTRAP_OBJECT_CUT_IDENTITY')
        seen=set();current_slots=set()
        for slot,item in value['slots'].items():
            row=self.resources.state['resources'].get(slot)
            need(row=={'owner':value['parent_owner'],'kind':self.descriptor['slots'][slot],'closed':False},
                 'BOOTSTRAP_ROOT_RESERVATION_CHANGED')
            state=item.get('state')
            if state=='RESERVED_NOT_ACQUIRED':
                need(set(item)=={'state'},'BOOTSTRAP_UNUSED_SLOT_NOT_OBJECT_PROOF');continue
            need(type(item.get('key')) is str and item['key'] not in seen
                 and item.get('kind')==row['kind'],'BOOTSTRAP_SLOT_ACQUISITION_CONFLICT')
            seen.add(item['key'])
            if state=='OBSERVER_CAPACITY':
                need(set(item)=={'key','kind','state','completed','active'} and item['active']==0
                     and type(item['completed']) is int and 0<=item['completed']<=4096
                     and item['key'] in {f'observer-envelope:{i}' for i in range(8)},
                     'BOOTSTRAP_OBSERVER_CAPACITY_NOT_QUIESCENT')
            elif state=='CLOSED_LOCAL':
                need(set(item)=={'key','kind','state','native'},'BOOTSTRAP_LOCAL_CLOSE_SCHEMA')
                # Historical local closure is labelled as such, not fabricated
                # current kernel evidence. The full parent escrow remains held
                # until original child exit independently proves reclamation.
            elif state=='RETAINED_NATIVE':
                native=item.get('native')
                need(set(item)=={'key','kind','state','native'} and type(native) is dict
                     and set(native)=={'handle','acquired_ns'} and type(native['handle']) is int
                     and native['handle']>0 and type(native['acquired_ns']) is int
                     and self.descriptor['started_ns']<=native['acquired_ns']<=value['at_ns'],
                     'BOOTSTRAP_EXPLICIT_ACQUISITION_REQUIRED')
                current_slots.add(slot)
                if slot in self.live:
                    need(self.live[slot]['remote']==native['handle'],'BOOTSTRAP_ACQUISITION_REBOUND')
                    local=self.live[slot]['local']
                else:
                    ticket=self.allocations.reserve('bootstrap-object:'+slot,'handle')
                    local=self.calls.duplicate(self.binding.runtime_handle,native['handle'])
                    self.live[slot]={'ticket':ticket,'local':local,'remote':native['handle']}
                observed=self.objects.observe(local)
                need(observed['type']=='Process' and observed['pid']==self.binding.runtime['pid']
                     and observed['created']==self.binding.runtime['created']
                     and self.calls.in_job(local,self.binding.api.job), 'BOOTSTRAP_CURRENT_OBJECT_OWNER_OR_JOB')
                self.live[slot]['identity']=copy.deepcopy(observed)
            else:raise ValueError('BOOTSTRAP_UNSUPPORTED_ACQUISITION_STATE')
        # The pinned bootstrap retains exactly its own process handle plus
        # quiescent observer capacity. An all-capacity cut cannot prove this
        # acquisition, even when every reservation is present.
        need(len(current_slots)==1 and current_slots==set(self.live),
             'BOOTSTRAP_CURRENT_OBJECT_RELEASE_UNPROVED')
        self.sequence=value['sequence'];self.cut=copy.deepcopy(value)
        self.verify()
        return {'scope':SCOPE_HASH,'nonce':value['nonce'],'cut':digest(value),'financial_ack':False}

    def verify(self):
        try:return self._verify()
        except BaseException:
            self.failed=True
            raise

    def _verify(self):
        need(not self.failed and self.cut is not None and 0<=self.clock()-self.cut['at_ns']<=5*10**9,
             'BOOTSTRAP_OBJECT_CUT_MISSING_OR_STALE')
        self.binding.verify()
        for slot,item in self.live.items():
            need(self.objects.observe(item['local'])==item['identity'],'BOOTSTRAP_RETAINED_OBJECT_CHANGED')
            ticket=self.allocations.reserve('bootstrap-continuity:'+slot,'handle')
            current=self.calls.duplicate(self.binding.runtime_handle,item['remote'])
            try:need(self.objects.same(current,item['local']),'BOOTSTRAP_ORIGINAL_HANDLE_REUSED')
            finally:
                self.calls.close(current);need(self.calls.closed(current),'BOOTSTRAP_COMPARISON_NOT_CLOSED')
                self.allocations.release(ticket)
        return set(self.descriptor['slots'])

    def dispose_after_exit(self):
        if self.released:return {'closed':True,'financial_ack':False}
        life=self.calls.lifecycle(self.binding.runtime_handle)
        need(life['pid']==self.binding.runtime['pid'] and life['created']==self.binding.runtime['created']
             and life['exited'] is True and life['exit_code']==0 and self.binding.api.members()==set(),
             'BOOTSTRAP_ORIGINAL_EXIT_BEFORE_RELEASE')
        for slot,item in self.live.items():
            if not item.get('closed'):
                self.calls.close(item['local']);need(self.calls.closed(item['local']),'BOOTSTRAP_RETAINED_CLOSE_INCOMPLETE')
                item['closed']=True
            self.allocations.release(item['ticket'])
        self.live.clear()
        self.terminal=copy.deepcopy(life);self.released=True
        return {'closed':True,'financial_ack':False}

    def release_reservations(self):
        need(not self.failed and self.released and self.terminal is not None and not self.live,
             'BOOTSTRAP_TERMINAL_OBJECT_RELEASE_REQUIRED')
        owner=self.descriptor['parent_owner']
        self.done.update(self.descriptor['slots'])
        self.resources.close_bootstrap(owner,self)
        return {'scope':SCOPE_HASH,'nonce':self.descriptor['nonce'],'closed':True,'financial_ack':False}

    def closed(self, owner, key):
        return self.released and owner==self.descriptor['parent_owner'] and key in self.done
