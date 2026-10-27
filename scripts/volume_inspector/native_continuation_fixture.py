"""Authorized disposable native segment codec. NEVER operational dispatch.

Uses original WindowsOutput/read_bound,FS1/audit,FS3 projections and injected
fixture custody. No operational schemas,paths,issuers,account startup or providers.
"""
import importlib.util
from itertools import islice
from pathlib import Path

from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import (
    apply_event,
    body,
    digest,
    event_stream_record,
    number,
    replay_verified_events,
    strict,
)

spec=importlib.util.spec_from_file_location('native_continuation_fs3',Path(__file__).with_name('financial_reporting.py'))
fs3=importlib.util.module_from_spec(spec);spec.loader.exec_module(fs3)
f=fs3.f
MAX_LOCAL=128
MAX_SEGMENTS=2


class NativeContinuationUnknown(ValueError):pass


class BoundedOutput:
    def __init__(self,output,budget):self.inner,self.budget=output,budget
    def __getattr__(self,key):return getattr(self.inner,key)
    def write_bound(self,name,data):return self.budget.native_write(self.inner,name,data)


class NativeSegmentFixture:
    def __init__(self,*,base,budget,custody,authority,scope,derive,projection=False):
        self.base=Path(base);self.budget=budget;self.custody=custody;self.authority=authority
        self.scope=strict(body(scope));self.derive=derive;self.projected=projection
        self.outputs={};self.projections={}
        if (not self.base.is_relative_to(budget.root) or scope.get('domain')!='NATIVE_CONTINUATION_DISPOSABLE_V1'
                or authority.verify_scope(scope,str(self.base)) is not True):
            raise ValueError('EXPLICIT_DISPOSABLE_NATIVE_SCOPE_REQUIRED')

    def _output(self,path):
        path=str(path)
        if path not in self.outputs:self.outputs[path]=BoundedOutput(f.w.WindowsOutput(path),self.budget)
        return self.outputs[path]

    def _read(self,out,name,binding):
        raw,_=f.s.read_bound(out,name,binding)
        value=strict(raw.decode())
        if body(value).encode()!=raw:raise NativeContinuationUnknown('NONCANONICAL_NATIVE_BYTES')
        return value

    def _new_root(self,path):
        self.budget.directory(path,native_factory=f.w.WindowsOutput.create_root)
        return self._output(path)

    def _projection(self,path):
        path=str(path)
        if path not in self.projections:
            target=fs3.ProjectionTarget(path,f.native.file_identity(self._output(path).root_handle))
            target.output=BoundedOutput(target.output,self.budget)
            self.projections[path]=target
        return self.projections[path]

    def create(self):
        with self.custody.lease():
            if self.custody.current() is not None:raise NativeContinuationUnknown('NO_ADOPTION_OR_SECOND_SCOPE')
            if self.authority.verify_scope(self.scope,str(self.base)) is not True:raise ValueError('SCOPE_REVOKED')
            self.budget.directory(self.base)
            segment=self._prepare(0,None,[],None)
            self.custody.advance(None,{'schema':'NATIVE_SEGMENT_FIXTURE_PIN_V1','scope':digest(self.scope),'segments':[segment]})
        return self.read()

    def _prepare(self,index,pin,payloads,terminal):
        path=self.base/f'segment-{index}'
        out=self._new_root(path)
        initial=self.derive(payloads)
        scope={'schema':'NATIVE_SEGMENT_FIXTURE_SCOPE_V1','index':index,'original_scope':self.scope,
               'previous_pin':digest(pin) if pin else None,'base_revision':len(payloads),
               'base_state_digest':digest(initial),'terminal':terminal}
        binding=out.write_bound('scope.json',f.encoded(scope))
        projection=None
        if self.projected:
            pp=self.base/f'projection-{index}'
            self._new_root(pp);projection={'path':str(pp),'root':f.native.file_identity(self._output(pp).root_handle)}
        return {'path':str(path),'root':f.native.file_identity(out.root_handle),'scope':binding,
                'entries':[],'projection':projection}

    def _load(self):
        self.budget.check();pin=strict(body(self.custody.current()))
        if (type(pin) is not dict or set(pin)!={'schema','scope','segments'}
                or pin['schema']!='NATIVE_SEGMENT_FIXTURE_PIN_V1' or pin['scope']!=digest(self.scope)
                or not 1<=len(pin['segments'])<=MAX_SEGMENTS or self.custody.verify(pin) is not True
                or self.authority.verify_read(self.scope,pin) is not True):
            raise NativeContinuationUnknown('CURRENT_CUSTODY_UNVERIFIED')
        payloads=[];native_head=digest(self.scope);physical=[];all_proofs=[];expected_dirs=set()
        for index,segment in enumerate(pin['segments']):
            if (segment['path']!=str(self.base/f'segment-{index}') or len(segment['entries'])>MAX_LOCAL):
                raise NativeContinuationUnknown('SEGMENT_MAPPING_OR_CAPACITY')
            expected_dirs.add(f'segment-{index}')
            out=self._output(segment['path'])
            if f.native.file_identity(out.root_handle)!=segment['root']:raise NativeContinuationUnknown('FOREIGN_ROOT')
            prefix=strict(body(pin));prefix['segments']=prefix['segments'][:index]
            # Predecessor current pin included exactly its terminal selected map.
            scope=self._read(out,'scope.json',segment['scope'])
            before=self.derive(payloads)
            if (scope!={'schema':'NATIVE_SEGMENT_FIXTURE_SCOPE_V1','index':index,'original_scope':self.scope,
                        'previous_pin':digest(prefix) if index else None,'base_revision':len(payloads),
                        'base_state_digest':digest(before),'terminal':native_head if index else None}):
                raise NativeContinuationUnknown('CARRY_STATE_OR_PREDECESSOR_CONFLICT')
            names={'scope.json'};proofs=[]
            if segment['projection']:
                expected_dirs.add(f'projection-{index}')
                target=self._projection(segment['projection']['path'])
                if f.native.file_identity(target.output.root_handle)!=segment['projection']['root']:
                    raise NativeContinuationUnknown('PROJECTION_ROOT_CHANGED')
            for local,entry in enumerate(segment['entries'],1):
                values={}
                for stage in ('intent','record','commit','ack'):
                    name=f'{local:04d}-{stage}.json';names.add(name);values[stage]=self._read(out,name,entry[stage])
                record=values['record']
                if self.scope.get('kind')=='FINANCIAL':
                    command=strict(record['payload']['command'])
                    ns,receipt=apply_event(self.scope['manifest'],before['state'],command)
                    receipt['projection_required']=strict(record['payload']['receipt'])['projection_required']
                    expected_row=event_stream_record(ns['revision'],command['operation_id'],body(command),before['financial_head'],
                        digest([before['financial_head'],command,receipt]),body(receipt))
                    if record['payload']!=expected_row:raise NativeContinuationUnknown('FINANCIAL_ROW_RECEIPT_OR_DUPLICATE')
                    after={'state':ns,'financial_head':expected_row['digest']}
                else:after=self.derive(payloads+[record['payload']])
                if (record!={'schema':'NATIVE_SEGMENT_FIXTURE_RECORD_V1','local_revision':local,
                        'global_revision':len(payloads)+1,'parent':native_head,'payload':record['payload'],
                        'state_digest':digest(after)}
                        or values['intent']!={'schema':'NATIVE_SEGMENT_FIXTURE_INTENT_V1','record_digest':digest(record)}
                        or values['commit']!={'schema':'NATIVE_SEGMENT_FIXTURE_COMMIT_V1','intent':entry['intent'],'record':entry['record']}):
                    raise NativeContinuationUnknown('GLOBAL_LOCAL_REVISION_OR_COMMIT_CONFLICT')
                ack=values['ack'];expected={'schema':'NATIVE_SEGMENT_FIXTURE_ACK_V1','commit':entry['commit']}
                if self.projected:
                    receipt=strict(record['payload']['receipt'])
                    context=f.projection_context(receipt,entry['record'],entry['commit'])
                    self._projection(segment['projection']['path']).verify(context,ack['projection'])
                    proofs.append(ack['projection']);expected['projection']=ack['projection']
                if ack!=expected:raise NativeContinuationUnknown('ACK_MISMATCH')
                payloads.append(record['payload']);native_head=digest(record);physical.append(entry['record']);before=after
            if {p.name for p in islice(Path(out.root).iterdir(),MAX_LOCAL*4+2)}!=names:
                raise NativeContinuationUnknown('UNPINNED_SOURCE_TAIL')
            if segment['projection']:self._projection(segment['projection']['path']).verify_inventory(proofs)
            all_proofs.extend(proofs)
        if {p.name for p in self.base.iterdir()}!=expected_dirs or self.custody.current()!=pin or self.custody.verify(pin) is not True:
            raise NativeContinuationUnknown('UNSELECTED_ROOT_OR_CURRENTNESS_CHANGED')
        return pin,payloads,self.derive(payloads),native_head,physical,all_proofs

    def read(self):
        pin,rows,state,head,physical,_=self._load()
        return {'schema':'NATIVE_CONTINUATION_FIXTURE_VIEW_V1','scope':self.scope,'pin':pin,'rows':rows,
                'state':state,'head':head,'physical_records':physical,'global_revision':len(rows),
                'local_revision':len(pin['segments'][-1]['entries']),'remaining_slots':MAX_LOCAL-len(pin['segments'][-1]['entries']),
                'startup_authorized':False}

    def append(self,payload,*,fault=lambda phase:None):
        payload=strict(body(payload))
        with self.custody.lease():
            pin,rows,_state,head,_,_=self._load()
            if self.authority.verify_append(self.scope,pin,payload) is not True:raise ValueError('RESERVATION_REQUIRED')
            key=digest(payload)
            if any(digest(row)==key for row in rows):return self.read()
            segment=pin['segments'][-1];local=len(segment['entries'])+1
            if local>MAX_LOCAL:raise ValueError('LOCAL128_NO_IMPLICIT_ROLLOVER')
            after=self.derive(rows+[payload])
            record={'schema':'NATIVE_SEGMENT_FIXTURE_RECORD_V1','local_revision':local,'global_revision':len(rows)+1,
                    'parent':head,'payload':payload,'state_digest':digest(after)}
            out=self._output(segment['path']);entry={}
            def write(stage,value):
                entry[stage]=out.write_bound(f'{local:04d}-{stage}.json',f.encoded(value));fault(stage)
            fault('before_intent')
            write('intent',{'schema':'NATIVE_SEGMENT_FIXTURE_INTENT_V1','record_digest':digest(record)})
            write('record',record)
            write('commit',{'schema':'NATIVE_SEGMENT_FIXTURE_COMMIT_V1','intent':entry['intent'],'record':entry['record']})
            ack={'schema':'NATIVE_SEGMENT_FIXTURE_ACK_V1','commit':entry['commit']}
            if self.projected:
                receipt=strict(payload['receipt']);context=f.projection_context(receipt,entry['record'],entry['commit'])
                ack['projection']=self._projection(segment['projection']['path']).publish(context,after['state'])
                fault('projection')
            write('ack',ack)
            new=strict(body(pin));new['segments'][-1]['entries'].append(entry)
            self.custody.advance(pin,new);fault('current_ack')
            return self.read()

    def rollover(self,*,fault=lambda phase:None):
        with self.custody.lease():
            pin,rows,state,head,_,_=self._load()
            if len(pin['segments'])>=MAX_SEGMENTS:raise ValueError('TWO_SEGMENTS_ONLY')
            if self.authority.verify_rollover(self.scope,pin,state) is not True:raise ValueError('FINAL_DRAIN_REQUIRED')
            if self.projected and any(number(p['remaining'])>0 for p in state['state']['positions'].values()):
                raise ValueError('OPEN_POSITION_CANNOT_ROLL')
            fault('before_prepare')
            successor=self._prepare(1,pin,rows,head);fault('prepared')
            new=strict(body(pin));new['segments'].append(successor)
            self.custody.advance(pin,new);fault('selected')
            return self.read()

    def close(self):
        for target in self.projections.values():target.close()
        for output in self.outputs.values():output.close()


def financial_derive(manifest,rows):
    state,head,_=replay_verified_events(manifest,rows)
    audit_financial_events(manifest,rows,state)
    return {'state':state,'financial_head':head}


class NativeSwitchFixture:
    """All-role fixture selection barrier;separate physical writes are NOT atomic."""
    ROLES=frozenset({'QD_SOURCE','PERP_SOURCE','QD_REPORT','PERP_REPORT','PERP_ORDERS','GLOBAL'})
    def __init__(self,*,base,budget,custody,status,authority,journals):
        from contextlib import ExitStack
        self.ExitStack=ExitStack
        self.base=Path(base);self.budget=budget;self.custody=custody;self.status=status;self.authority=authority
        self.journals=journals
        if set(journals)!=self.ROLES or not self.base.is_relative_to(budget.root):
            raise ValueError('COMPLETE_FIXTURE_SWITCH_ROSTER_REQUIRED')
        if self.custody.current() is None:
            if self.base.exists():raise ValueError('NO_CATALOG_ADOPTION')
            budget.directory(self.base,native_factory=f.w.WindowsOutput.create_root)
            self.out=BoundedOutput(f.w.WindowsOutput(str(self.base)),budget)
            scope={'schema':'NATIVE_SWITCH_FIXTURE_SCOPE_V1','roles':{k:digest(v.scope) for k,v in journals.items()}}
            bound=self.out.write_bound('scope.json',f.encoded(scope))
            self.custody.advance(None,{'schema':'NATIVE_SWITCH_FIXTURE_PIN_V1',
                'root':f.native.file_identity(self.out.root_handle),'scope':bound,'selection':None})
        else:
            self.out=BoundedOutput(f.w.WindowsOutput(str(self.base)),budget)
            if f.native.file_identity(self.out.root_handle)!=custody.current()['root']:raise ValueError('CATALOG_ROOT_CHANGED')

    def switch(self,*,fault=lambda phase:None):
        with self.ExitStack() as stack:
            stack.enter_context(self.custody.lease())
            for name in sorted(self.journals):stack.enter_context(self.journals[name].custody.lease())
            if self.custody.current()['selection'] is not None:return self.inspect()
            cuts={k:v.read() for k,v in self.journals.items()}
            if (any(len(v['pin']['segments'])>=2 for v in cuts.values())
                    or self.authority.verify_switch(cuts) is not True):raise ValueError('ALL_ROLE_FINAL_DRAIN_REQUIRED')
            for lane in ('QD_SOURCE','PERP_SOURCE'):
                if any(number(p['remaining'])>0 for p in cuts[lane]['state']['state']['positions'].values()):
                    raise ValueError('OPEN_FINANCIAL_POSITION')
            for report_role,source_role in (('QD_REPORT','QD_SOURCE'),('PERP_REPORT','PERP_SOURCE')):
                reports=cuts[report_role]['state']['reports']
                if not reports or reports[-1]['rows']!=cuts[source_role]['rows']:
                    raise ValueError('REPORT_SOURCE_CUT_MISMATCH')
            if any(row['state'] in ('RESERVED','FILL_PENDING') for row in cuts['PERP_ORDERS']['state']['orders'].values()):
                raise ValueError('RESTING_ORDER_BLOCKS_SWITCH')
            if cuts['GLOBAL']['state'].get('finalized') is None:raise ValueError('GLOBAL_FINAL_REQUIRED')
            self.status.pending();fault('reserved')
            intent={'schema':'NATIVE_SWITCH_FIXTURE_INTENT_V1','before':{k:digest(v['pin']) for k,v in cuts.items()}}
            ib=self.out.write_bound('intent.json',f.encoded(intent));fault('intent')
            selected={}
            for name,journal in self.journals.items():
                current=cuts[name]
                new=strict(body(current['pin']))
                new['segments'].append(journal._prepare(1,current['pin'],current['rows'],current['head']))
                selected[name]=new;fault('prepared:'+name)
            record={'schema':'NATIVE_SWITCH_FIXTURE_RECORD_V1','intent':ib,
                'before':intent['before'],'selected':{k:digest(v) for k,v in selected.items()},
                'state_digests':{k:digest(v['state']) for k,v in cuts.items()},
                'roots':{k:[{'source':s['root'],'projection':s['projection']} for s in v['segments']] for k,v in selected.items()}}
            rb=self.out.write_bound('record.json',f.encoded(record));fault('record')
            cb=self.out.write_bound('commit.json',f.encoded({'schema':'NATIVE_SWITCH_FIXTURE_COMMIT_V1','record':rb,'intent':ib}));fault('commit')
            for name,journal in self.journals.items():
                journal.custody.advance(cuts[name]['pin'],selected[name]);fault('selected:'+name)
            if any(j.custody.current()!=selected[k] for k,j in self.journals.items()):
                raise NativeContinuationUnknown('PARTIAL_SELECTED_CATALOG')
            ab=self.out.write_bound('ack.json',f.encoded({'schema':'NATIVE_SWITCH_FIXTURE_ACK_V1','commit':cb}));fault('ack')
            pin=self.custody.current();new={**pin,'selection':{'intent':ib,'record':rb,'commit':cb,'ack':ab}}
            self.custody.advance(pin,new);fault('catalog')
            self.status.acknowledge(digest(new));fault('admitted')
            return self.inspect()

    def inspect(self):
        if not self.status.acknowledged():return {'status':'UNKNOWN','startup_authorized':False}
        pin=self.custody.current();selection=pin['selection']
        if selection is None:raise NativeContinuationUnknown('NO_ACKNOWLEDGED_SELECTION')
        values={stage:strict(f.s.read_bound(self.out,stage+'.json',selection[stage])[0].decode()) for stage in selection}
        r=values['record'];c=values['commit'];a=values['ack'];i=values['intent']
        if (r['intent']!=selection['intent'] or r['before']!=i['before']
                or c!={'schema':'NATIVE_SWITCH_FIXTURE_COMMIT_V1','record':selection['record'],'intent':selection['intent']}
                or a!={'schema':'NATIVE_SWITCH_FIXTURE_ACK_V1','commit':selection['commit']}
                or any(digest(j.custody.current())!=r['selected'][k] for k,j in self.journals.items())
                or self.custody.verify(pin) is not True):
            raise NativeContinuationUnknown('CATALOG_CURRENTNESS_OR_ACK_CONFLICT')
        cuts={k:v.read() for k,v in self.journals.items()}
        if any(digest(v['state'])!=r['state_digests'][k] for k,v in cuts.items()):
            # Selection receipt proves the switch cut,not later financial activity.
            raise NativeContinuationUnknown('CATALOG_SOURCE_ADVANCED_AFTER_SWITCH')
        return {'status':'ACKNOWLEDGED','cuts':cuts,'startup_authorized':False}

    def close(self):self.out.close()
