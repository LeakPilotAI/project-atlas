"""Independent remote handle continuity over an original retained process.

The parent duplicates from the verified child creation handle, never a PID.
The child's close declaration is only a request for independent observation.
"""

from app.services.paper_financial_replay import body, digest, strict
from scripts.observation_runtime.aip06_harness import need
from scripts.observation_runtime.launch_ownership import RetainedLaunchBinding


class _DescendantReleased:
    def __init__(self, peer, owner, key):
        self.peer,self.owner,self.key=peer,owner,key
    def closed(self, owner, key):
        return owner==self.owner and key==self.key and key in self.peer.done


class RemoteHandleProofs:
    def __init__(self, owner):
        self.owner, self.handles = owner, {}
        self.effects = {}

    def bind(self, key, handle):
        need(
            type(handle) is int
            and handle > 0
            and (key not in self.handles or self.handles[key] == handle),
            "REMOTE_ORIGINAL_HANDLE_CONFLICT",
        )
        self.handles[key] = handle
        return {"owner": self.owner, "key": key, "handle": handle}

    def release(self, owner, key, observer):
        if key in self.effects:
            need(owner == self.owner and observer.closed(owner,key) is True, 'REMOTE_LOCAL_EFFECT_INCOMPLETE')
            return {'owner':owner,'key':key,'effect':self.effects[key]}
        need(
            owner == self.owner
            and key in self.handles
            and observer.closed(owner, key) is True,
            "REMOTE_RELEASE_REQUIRES_REGISTERED_ORIGINAL",
        )
        return {"owner": owner, "key": key, "handle": self.handles[key]}

    def child(self, *args):
        need(len(args) == 2 and type(args[0]) is RetainedLaunchBinding, "REMOTE_DESCENDANT_RETAINED_BINDING_REQUIRED")
        binding, handle = args
        binding.verify()
        need(digest(binding.parent) == self.owner and handle == binding.runtime_handle, "REMOTE_DESCENDANT_EXACT_PARENT_AND_HANDLE")
        need(all(type(h) is int and h > 0 for h in (binding.parent_handle, binding.launch_handle,
             binding.runtime_handle, binding.api.job)), 'REMOTE_DESCENDANT_ORIGINAL_NATIVE_HANDLES')
        return {
            "nonce": binding.request.nonce, "parent": binding.parent_handle,
            "launch": binding.launch_handle, "runtime": binding.runtime_handle,
            "job": binding.api.job,
            "ready": {"pid": binding.runtime['pid'], "nonce": binding.request.nonce, "role": binding.request.role},
        }


class RetainedPeerHandles:
    """Keep a charged parent duplicate until the remote close is verified.

    A reused remote integer which is still valid is ambiguous and refuses,
    even if it now refers to a different object. No name/PID-based adoption.
    A failed registration retains its allocated duplicate for owned cleanup.
    """

    def __init__(self, *, binding, resources, calls, files, allocations, allowed_path, objects=None, descendants=None, sid=None, effects_io=None):
        need(type(binding) is RetainedLaunchBinding, "ORIGINAL_RETAINED_PEER_REQUIRED")
        self.binding, self.resources, self.calls = binding, resources, calls
        self.files, self.allocations, self.allowed_path = (
            files,
            allocations,
            allowed_path,
        )
        self.owner = digest(binding.runtime)
        self.live = {}
        self.done = set()
        self.failed = False
        self.objects, self.descendants = objects, descendants
        self.sid = sid
        self.deferred = set()
        self.effects_io, self.effects, self.effect_paths, self.reservations = effects_io, {}, {}, {}

    def verify_peer(self, wire):
        need(
            not self.failed
            and body(wire["child"]) == body(self.binding.runtime)
            and body(wire["parent"]) == body(self.binding.parent),
            "REMOTE_WIRE_NATIVE_PEER_CONFLICT",
        )
        if getattr(self,'attested',None) is not None:
            self.capture_peer(wire)
            rows=self.attested_rows()
            need(self.binding.api.members()=={self.binding.runtime['pid']} | {r['pid'] for r in rows},
                 'FORWARDED_NATIVE_JOB_DISAGREEMENT')
        elif self.descendants is not None and self.descendants.staging is not None and self.descendants.staging.nodes:
            self.descendants.staging.verify()
            self.descendants.aggregate.observe(commit=False)
        else:
            self.binding.verify()

    def attested_rows(self):
        from scripts.observation_runtime.aip06_graph_evidence import validate_graph_evidence
        return validate_graph_evidence(self.attested,{'child':self.binding.runtime,'nonce':self.binding.request.nonce},
                                       self.resources.clock())

    def capture_peer(self, wire):
        """Identity fence for bounded frame capture, NEVER roster admission."""
        need(not self.failed and body(wire['child']) == body(self.binding.runtime)
             and body(wire['parent']) == body(self.binding.parent)
             and not self.binding.refused and not self.binding.finished
             and self.binding.api.observe(self.binding.parent_handle) == self.binding.parent
             and self.binding.api.observe(self.binding.launch_handle) == self.binding.launch
             and self.binding.api.observe(self.binding.runtime_handle) == self.binding.runtime,
             'CAPTURE_ORIGINAL_PEER_IDENTITY_LOST')

    def graph_evidence(self):
        self.verify_peer({'parent':self.binding.parent,'child':self.binding.runtime})
        rows=[] if self.binding.descendant_graph is None else self.binding.descendant_graph()
        return {'schema':'AIP06_RETAINED_GRAPH_V1','scope':self.resources.read()['scope'],
                'peer':self.binding.runtime,'nonce':self.binding.request.nonce,'rows':rows,
                'at_ns':self.resources.clock(),'source_head':self.resources.head}

    def _forwarded_peer(self, wire, nested, *, create=False):
        from types import SimpleNamespace
        from scripts.observation_runtime.aip06_ipc import Broker
        from scripts.observation_runtime.aip06_native_objects import DeclaredDescendants
        self.capture_peer(wire)
        nested=strict(body(nested))
        need(self.descendants is not None,
             'FORWARDED_REGISTERED_CHANNEL_REQUIRED')
        r=self.descendants
        need(type(nested) is dict and nested.get('nonce') in r.bindings,'FORWARDED_UNREGISTERED_DESCENDANT')
        bound,_,_=r.bindings[nested['nonce']]
        need(set(nested)=={'scope','session','nonce','parent','child','job','launch'}
             and nested['job']==r.staging.nodes[nested['nonce']]['remote']['job']
             and body(nested.get('parent'))==body(self.binding.runtime)
             and body(nested.get('child'))==body(bound.runtime)
             and body(nested.get('launch'))==body(bound.launch)
             and nested.get('scope')==wire['scope'] and nested.get('session')==wire['session'],
             'FORWARDED_CHANNEL_ANCESTRY_CONFLICT')
        if not hasattr(self,'forwarded'):
            self.forwarded={}
        if nested['nonce'] not in self.forwarded:
            need(create,'FORWARDED_CHANNEL_NOT_PRE_REGISTERED')
            peer=RetainedPeerHandles(binding=bound,resources=self.resources,calls=self.calls,files=self.files,
                allocations=self.allocations,allowed_path=self.allowed_path,objects=self.objects,
                sid=self.sid,effects_io=self.effects_io)
            peer.descendants=DeclaredDescendants(peer=bound,calls=self.calls,objects=self.objects,
                allocations=self.allocations,observer_factory=r.observer_factory,aggregate=r.aggregate,files=self.files)
            broker=Broker(resources=self.resources,channel=SimpleNamespace(binding=nested),peer_owner=digest(bound.runtime),
                          verifier=peer,output=self.forward_output,clock_ns=self.resources.clock)
            peer.forward_output=self.forward_output
            self.forwarded[nested['nonce']]=(nested,broker)
        else:
            need(not create,'FORWARDED_CHANNEL_ALREADY_REGISTERED')
        original,broker=self.forwarded[nested['nonce']]
        need(body(original)==body(nested) and not broker.unknown,'FORWARDED_CHANNEL_REPLAY_OR_UNKNOWN')
        return broker

    def register_descendant_channel(self, wire, nested):
        self.verify_peer(wire)
        self.pending_registration=self._forwarded_peer(wire,nested,create=True)
        return {'scope':wire['scope'],'nonce':nested['nonce'],'owner':digest(nested['child']),
                'registered':True,'financial_ack':False}

    def forward_operation(self, wire, value):
        """Forward ONLY a registered child's original private-channel request."""
        need(type(value) is dict and set(value)=={'wire','request'}, 'FORWARDED_REQUEST_SCHEMA')
        broker=self._forwarded_peer(wire,value['wire'])
        request=value['request'];broker.unknown=True
        broker.output.append({'schema':'AIP06_FORWARDED_INTENT_V1','peer':broker.owner,'request':request})
        result=broker._operation(request)
        evidence=broker.verifier.graph_evidence()
        broker.output.append({'schema':'AIP06_FORWARDED_RESULT_V1','peer':broker.owner,'operation':digest(request),
                              'result':result,'ownership':evidence})
        broker.last=request['revision'];broker.peer_head=self.resources.head;broker.unknown=False
        broker.pending_forwarded_head=True
        self.verify_peer(wire)
        return {'result':result,'ownership':evidence}

    def finish_forwarded_heads(self, head):
        pending=getattr(self,'pending_registration',None)
        if pending is not None:
            pending.peer_head=head;self.pending_registration=None
        for _,broker in getattr(self,'forwarded',{}).values():
            if getattr(broker,'pending_forwarded_head',False):
                broker.peer_head=head;broker.pending_forwarded_head=False
            broker.verifier.finish_forwarded_heads(head)

    def admit_frame(self, wire, frame):
        self.capture_peer(wire)
        request = frame.get('payload', {})
        from scripts.observation_runtime.aip06_ipc import RemoteResources
        if frame['kind']=='REQUEST' and type(self.resources) is RemoteResources:
            # The sole root ledger admits each forwarded operation. No local
            # resource mutation or descendant adoption is possible here.
            return
        if frame['kind']=='REQUEST' and request.get('method')=='forward_operation':
            need(self.descendants is not None,'FORWARDING_GRAPH_REQUIRED')
            return
        if frame['kind'] == 'REQUEST' and request.get('method') in ('stage_descendant','release_descendant'):
            args = request.get('args')
            nonce = args[1].get('nonce') if type(args) is list and len(args)==2 and type(args[1]) is dict else (args[1] if type(args) is list and len(args)==2 else None)
            need(self.descendants is not None and type(args) is list and len(args) == 2
                 and args[0] == self.owner and nonce in self.descendants.declarations
                 and request.get('kwargs') == {} and request.get('proof') is None,
                 'CAPTURE_REQUIRES_PRIOR_SUSPENDED_DECLARATION')
            if request['method']=='stage_descendant':
                need(nonce not in self.descendants.staging.nodes,'CAPTURE_STAGE_REPLAY')
            else:
                need(nonce in self.descendants.bindings,'CAPTURE_RELEASE_BEFORE_BIND')
            # Only the authenticated stage request may reach Broker. It journals
            # its intent BEFORE duplicating handles or admitting the full graph.
            return
        self.verify_peer(wire)

    def bind_native_handle(self, wire, key, handle):
        self.verify_peer(wire)
        row = self.resources.state["resources"].get(key)
        need(
            type(handle) is int
            and handle > 0
            and row is not None
            and row["owner"] == self.owner
            and not row["closed"],
            "REMOTE_HANDLE_PRIOR_RESERVATION",
        )
        if key in self.live:
            need(self.live[key]["remote"] == handle, "REMOTE_HANDLE_REBIND")
            return
        ticket = self.allocations.reserve("remote-retained:" + key, "handle")
        duplicate = self.calls.duplicate(self.binding.runtime_handle, handle)
        self.live[key] = {
            "remote": handle,
            "local": duplicate,
            "ticket": ticket,
            "verified": False,
        }
        try:
            if self.objects is not None:
                native = self.objects.observe(duplicate)
                expected_type = {'thread': 'Thread', 'job': 'Job', 'pipe': 'Pipe', 'image': 'File',
                                 'file': 'File', 'directory': 'File'}.get(row['kind'])
                need(expected_type is None or native['type'] == expected_type, 'REMOTE_RESERVED_NATIVE_OBJECT_KIND')
                check_ticket = self.allocations.reserve('remote-object-continuity:' + key, 'handle')
                check_handle = self.calls.duplicate(self.binding.runtime_handle, handle)
                try:
                    need(self.objects.same(duplicate, check_handle), "REMOTE_KERNEL_OBJECT_CHANGED_DURING_REGISTRATION")
                finally:
                    self.calls.close(check_handle)
                    need(self.calls.closed(check_handle), 'REMOTE_OBJECT_PROBE_NOT_CLOSED')
                    self.allocations.release(check_ticket)
                if native['type'] == 'File':
                    source = self.allowed_path(native['path'])
                    need(not native['native']['reparse'] and native['native']['links'] == 1, "REMOTE_NATIVE_FILE_IDENTITY")
                    if type(source) is dict:
                        need(native['native']['id'] == list(source['file_id']), 'REMOTE_PINNED_SOURCE_FILE_IDENTITY')
                    if row['kind'] in ('file', 'directory'):
                        need(native['native']['kind'] == row['kind'], 'REMOTE_FILE_DIRECTORY_KIND_CONFLICT')
                elif native['type'] in ('Thread', 'Process'):
                    need(native['pid'] == self.binding.runtime['pid'], "REMOTE_FOREIGN_PROCESS_OR_THREAD")
                elif native['type'] == 'Job':
                    need(set(native['members']) == {self.binding.runtime['pid']} and self.calls.in_job(self.binding.runtime_handle, duplicate), "REMOTE_FOREIGN_JOB")
                elif native['type'] == 'Token':
                    need(type(self.sid) is str and native['sid'] == self.sid and native['token_type'] == 1, 'REMOTE_PRIMARY_TOKEN_IDENTITY')
                else:
                    need(native['type'] in ('Event', 'Mutant', 'Semaphore', 'Timer', 'Pipe'), "REMOTE_OBJECT_UNSUPPORTED")
                self.binding.verify()
                self.live[key].update(verified=True, identity=native)
                return
            native = self.files.describe(duplicate)
            path = self.files.final_path(duplicate)
            self.allowed_path(path)
            need(
                not native["reparse"]
                and native["links"] == 1
                and native["kind"] in ("file", "directory"),
                "REMOTE_NATIVE_FILE_IDENTITY",
            )
            self.binding.verify()
            self.live[key].update(verified=True, identity=native["id"], path=path)
        except BaseException:
            self.failed = True
            raise

    def release_observer(self, wire, key, proof):
        self.verify_peer(wire)
        if key in self.effects:
            intent = self.effects[key]
            need(proof == {'owner':self.owner,'key':key,'effect':digest(intent)}, 'REMOTE_EFFECT_RELEASE_IDENTITY')
            if intent['kind'] != 'capacity':
                parent = self.effects_io.inspect(intent['parent']['path'])
                current = self.effects_io.inspect(intent['path'])
                need(parent == intent['parent'] and current is not None and current['kind'] == intent['kind']
                     and current['parent_id'] == parent['id'] and not current['reparse'] and current['links'] == 1,
                     'REMOTE_EFFECT_NATIVE_READBACK_OR_PARENT_CONFLICT')
                self.effect_paths[intent['path']] = current['id']
            self.done.add(key)
            return self
        item = self.live.get(key)
        need(
            item is not None
            and item["verified"]
            and proof == {"owner": self.owner, "key": key, "handle": item["remote"]},
            "REMOTE_RELEASE_IDENTITY",
        )
        if self.objects is not None and item['identity']['type'] == 'Thread':
            need(self.objects.observe(item['local'])['exited'] is True, 'REMOTE_THREAD_STILL_RUNNING')
        ticket = self.allocations.reserve("remote-close-probe:" + key, "handle")
        try:
            probe = self.calls.duplicate(self.binding.runtime_handle, item["remote"])
        except OSError as exc:
            need(getattr(exc, "winerror", None) == 6, "REMOTE_CLOSE_ENUMERATION_FAILED")
            # The API returned no handle. The transient reservation closes only
            # for ERROR_INVALID_HANDLE from this exact retained peer operation.
            self.allocations.release(ticket)
        else:
            self.calls.close(probe)
            need(self.calls.closed(probe), "REMOTE_PROBE_HANDLE_NOT_CLOSED")
            self.allocations.release(ticket)
            raise ValueError("REMOTE_HANDLE_LIVE_OR_REUSED")
        self.calls.close(item["local"])
        need(self.calls.closed(item["local"]), "PARENT_REMOTE_DUPLICATE_NOT_CLOSED")
        self.allocations.release(item["ticket"])
        del self.live[key]
        self.done.add(key)
        return self

    def closed(self, owner, key):
        return owner == self.owner and key in self.done

    def probe_native_objects(self, *, deadline_ns):
        """Reobserve original duplicates and their creator's exact handles.

        No PID reopen or unknown-object adoption. Temporary comparison handles
        are charged before duplication and credited only after confirmed close.
        """
        try:
            return self._probe_native_objects(deadline_ns=deadline_ns)
        except BaseException:
            self.failed = True
            raise

    def verify_retired_descendant(self, wire, broker):
        """A closed forwarding record is history, only after full finalization.

        Finished/PID absence alone never removes a peer from the inventory.
        The original root registry must prove normal exit, duplicate closure,
        creator manifest release and the committed process-slot finalization.
        """
        r = self.descendants
        nonce = wire['nonce']
        need(r is not None and nonce in r.bindings and nonce in r.finished
             and not r.failed and not broker.unknown, 'RETIRED_DESCENDANT_FINALIZATION_REQUIRED')
        bound, _, slot = r.bindings[nonce]
        need(broker.verifier.binding is bound and bound.finished and not bound.refused
             and body(wire['child']) == body(bound.runtime)
             and not broker.verifier.live
             and self.resources.state['resources'][slot]
             == {'owner':digest(bound.runtime),'kind':'process','closed':True}
             and all(self.calls.closed(h) for _,h in r.held[nonce])
             and all(self.resources.state['resources'][k]['closed'] for k in r.declared_keys[nonce])
             and all(row['closed'] for row in self.resources.state['resources'].values()
                     if row['owner']==digest(bound.runtime)),
             'RETIRED_DESCENDANT_RELEASE_INCOMPLETE')

    def _probe_native_objects(self, *, deadline_ns):
        need(self.resources.clock() < deadline_ns, 'PROBE_NATIVE_OBJECT_TIMEOUT')
        wire = {'parent': self.binding.parent, 'child': self.binding.runtime}
        self.verify_peer(wire)
        need(self.objects is not None and not self.failed,
             'PROBE_NATIVE_OBJECT_PROVIDER_MISSING')
        required = {k for k, r in self.resources.state['resources'].items()
                    if r['owner'] == self.owner and not r['closed']
                    and r['kind'] in ('handle', 'thread', 'pipe', 'job', 'image', 'file', 'directory')}
        for key in required.intersection(self.effects):
            intent = self.effects[key]
            need(self.effects_io is not None and self.resources.clock() < deadline_ns,
                 'PROBE_NATIVE_EFFECT_EVIDENCE_MISSING')
            current = self.effects_io.inspect(intent['path'])
            parent = self.effects_io.inspect(intent['parent']['path'])
            need(parent == intent['parent'] and current is not None
                 and current['parent_id'] == parent['id'] and current['kind'] == intent['kind']
                 and not current['reparse'] and current['links'] == 1,
                 'PROBE_NATIVE_EFFECT_IDENTITY_CHANGED')
        required -= set(self.effects)
        need(required == set(self.live) and not self.deferred,
             'PROBE_NATIVE_OBJECT_EVIDENCE_INCOMPLETE')
        rows = []
        for key, item in sorted(self.live.items()):
            need(item['verified'] is True and self.resources.clock() < deadline_ns,
                 'PROBE_NATIVE_OBJECT_UNVERIFIED_OR_TIMEOUT')
            ticket = self.allocations.reserve('probe-object:' + key, 'handle')
            check = None
            try:
                check = self.calls.duplicate(self.binding.runtime_handle, item['remote'])
                need(self.objects.same(item['local'], check), 'PROBE_NATIVE_OBJECT_REUSED')
                current = self.objects.observe(item['local'])
                original = item['identity']
                need(current['type'] == original['type'], 'PROBE_NATIVE_OBJECT_TYPE_CHANGED')
                if current['type'] in ('Thread', 'Process'):
                    need(all(current[k] == original[k] for k in ('pid', 'created')),
                         'PROBE_NATIVE_OBJECT_BIRTH_CHANGED')
                elif current['type'] == 'File':
                    need(current['native']['id'] == original['native']['id']
                         and current['path'] == original['path']
                         and not current['native']['reparse'] and current['native']['links'] == 1,
                         'PROBE_NATIVE_OBJECT_FILE_CHANGED')
                    self.allowed_path(current['path'])
                elif current['type'] == 'Token':
                    need(current == original, 'PROBE_NATIVE_OBJECT_TOKEN_CHANGED')
                elif current['type'] == 'Job':
                    need(current['limits'] == original['limits'], 'PROBE_NATIVE_OBJECT_JOB_CHANGED')
                    if self.objects.same(item['local'], self.binding.api.job):
                        need(set(current['members']) == set(self.binding.api.members()),
                             'PROBE_NATIVE_OBJECT_JOB_CHANGED')
                    else:
                        r = self.descendants
                        need(r is not None and r.staging is not None,
                             'PROBE_DECLARED_DESCENDANT_JOB_REQUIRED')
                        matches = [row for nonce,row in r.staging.nodes.items()
                                   if nonce not in r.staging.closed
                                   and self.objects.same(item['local'], row['local']['job'])]
                        need(len(matches) == 1, 'PROBE_UNREGISTERED_DESCENDANT_JOB')
                        # The existing graph checks every complete raw subtree
                        # Job; a creator's child Job is not the creator's Job.
                        r.staging.verify()
                rows.append({'owner': self.owner, 'key': key, 'identity': digest(current)})
            finally:
                # A failed duplicate is an unresolved allocation, never a
                # fabricated closed handle or refunded reservation.
                if check is not None:
                    self.calls.close(check)
                    need(self.calls.closed(check), 'PROBE_NATIVE_OBJECT_CLOSE_INCOMPLETE')
                    self.allocations.release(ticket)
        self.verify_peer(wire)
        return rows

    def child_binding(self, *args):
        need(len(args) == 2 and self.descendants is not None, "REMOTE_DESCENDANT_DECLARATION_PROVIDER_REQUIRED")
        wire, proof = args
        self.verify_peer(wire)
        return self.descendants.import_binding(proof)

    def declare_descendant(self, wire, encoded, slot, keys=None):
        from scripts.observation_runtime.launch_ownership import LaunchRequest
        self.verify_peer(wire)
        need(self.descendants is not None and type(encoded) is dict
             and set(encoded) == set(LaunchRequest.__dataclass_fields__),
             'DESCENDANT_DECLARATION_PROVIDER_OR_SCHEMA')
        value = dict(encoded)
        for key in ('launch_image','runtime_image','auxiliary_image'):
            if value[key] is not None:
                image = value[key]
                need(type(image) in (list,tuple) and len(image)==3,
                     'DESCENDANT_DECLARATION_IMAGE')
                value[key] = (image[0],tuple(image[1]),image[2])
        request = LaunchRequest(**value)
        request.validate()
        self.descendants.declare(request,slot=slot,parent_owner=self.owner,resources=self.resources)
        if keys is not None:
            need(type(keys) is list and 0<len(keys)<=64 and len(set(keys))==len(keys)
                 and all(type(k) is str and self.resources.state['resources'].get(k,{}).get('owner')==self.owner
                         and not self.resources.state['resources'][k]['closed'] for k in keys),
                 'DESCENDANT_PRIOR_NATIVE_RESERVATIONS')
            from collections import Counter
            need(Counter(self.resources.state['resources'][k]['kind'] for k in keys)
                 == Counter({'job':1,'handle':1,'image':1,'thread':1,'pipe':8}),
                 'DESCENDANT_EXACT_PHYSICAL_SESSION_RESERVATIONS')
            self.descendants.declared_keys[request.nonce]=tuple(keys)
        return {'schema':'AIP06_DESCENDANT_DECLARED_V1','owner':self.owner,
                'nonce':request.nonce,'slot':slot,'financial_ack':False}

    def stage_descendant(self, wire, proof):
        try:
            return self._stage_descendant(wire,proof)
        except BaseException:
            self.failed=True
            if self.descendants is not None and self.descendants.staging is not None:
                self.descendants.failed=self.descendants.staging.failed=True
            raise

    def _stage_descendant(self, wire, proof):
        self.capture_peer(wire)
        need(self.descendants is not None,'DESCENDANT_STAGE_PROVIDER_REQUIRED')
        need(type(proof) is dict and 'allocations' in proof
             and proof.get('nonce') in self.descendants.declared_keys,
             'DESCENDANT_PHYSICAL_DECLARATION_AND_MANIFEST_REQUIRED')
        native_proof={k:v for k,v in proof.items() if k!='allocations'}
        receipt = self.descendants.stage_suspended(native_proof)
        if 'allocations' in proof:
            self._retain_session_allocations(proof)
        self.verify_peer(wire)
        return receipt

    def _retain_session_allocations(self, proof):
        nonce=proof['nonce'];values=proof['allocations'];r=self.descendants
        need(type(values) is dict and set(values)==set(r.declared_keys.get(nonce,())),
             'DESCENDANT_COMPLETE_DECLARED_NATIVE_MANIFEST')
        need(len({v['handle'] for v in values.values()})==len(values), 'DESCENDANT_NATIVE_HANDLE_ALIAS')
        for key,value in values.items():
            row=self.resources.state['resources'][key]
            need(type(value) is dict and set(value)=={'kind','handle'}
                 and row=={'owner':self.owner,'kind':value['kind'],'closed':False}
                 and key not in self.live and type(value['handle']) is int and value['handle']>0,
                 'DESCENDANT_RESERVED_NATIVE_HANDLE')
            ticket=self.allocations.reserve('descendant-session:'+key,'handle')
            h=self.calls.duplicate(self.binding.runtime_handle,value['handle'])
            self.live[key]={'remote':value['handle'],'local':h,'ticket':ticket,'verified':False}
            actual=self.objects.observe(h)
            expected={'job':'Job','thread':'Thread','image':'File','pipe':'Pipe','handle':'Process'}[value['kind']]
            need(actual['type']==expected,'DESCENDANT_SESSION_OBJECT_KIND')
            if value['kind'] in ('job','thread','image','handle'):
                original={'job':'job','thread':'thread','image':'image','handle':'parent'}[value['kind']]
                need(self.objects.same(h,r.staging.nodes[nonce]['local'][original]),'DESCENDANT_SESSION_ORIGINAL_OBJECT')
            self.live[key].update(verified=True,identity=actual)

    def finalize_descendant(self, wire, value):
        self.verify_peer(wire)
        r=self.descendants
        need(r is not None and type(value) is dict and set(value)=={'owner','slot'}, 'DESCENDANT_FINAL_RELEASE_SCHEMA')
        matches=[n for n,(_,slot) in r.declarations.items() if slot==value['slot']]
        need(len(matches)==1,'DESCENDANT_FINAL_RELEASE_DECLARATION')
        nonce=matches[0]
        need(nonce in r.finished and nonce in r.declared_keys,'DESCENDANT_EXIT_AND_MANIFEST_REQUIRED')
        bound,_,slot=r.bindings[nonce]
        need(value['owner']==digest(bound.runtime) and all(self.calls.closed(h) for _,h in r.held[nonce])
             and all(k in self.done and self.resources.state['resources'][k]['closed']
                     for k in r.declared_keys[nonce])
             and all(row['closed'] for key,row in self.resources.state['resources'].items()
                     if row['owner']==value['owner'] and key!=slot),'DESCENDANT_HANDLES_OR_LEDGER_LEAK')
        if self.resources.state['resources'][slot]['closed']:
            need(slot in self.done,'DESCENDANT_REPEATED_RELEASE_UNVERIFIED')
            self.descendants.aggregate.observe(commit=False)
            return {**value,'closed':True,'financial_ack':False}
        remote=r.staging.nodes[nonce]['remote']['launch']
        ticket=self.allocations.reserve('descendant-final-original-probe','handle')
        try:
            probe=self.calls.duplicate(self.binding.runtime_handle,remote)
        except OSError as exc:
            need(getattr(exc,'winerror',None)==6,'DESCENDANT_FINAL_PROBE_UNKNOWN')
            self.allocations.release(ticket)
        else:
            self.calls.close(probe)
            need(self.calls.closed(probe),'DESCENDANT_FINAL_PROBE_LEAK')
            self.allocations.release(ticket)
            raise ValueError('DESCENDANT_CREATOR_PROCESS_HANDLE_LIVE_OR_REUSED')
        self.done.add(slot)
        self.resources.close(value['owner'],slot,observer=_DescendantReleased(self,value['owner'],slot))
        self.descendants.aggregate.observe()
        return {**value,'closed':True,'financial_ack':False}

    def resume_descendant(self, wire, nonce):
        self.verify_peer(wire)
        need(self.descendants is not None,'DESCENDANT_RESUME_PROVIDER_REQUIRED')
        return self.descendants.resume_staged(nonce)

    def release_descendant(self, wire, nonce):
        self.capture_peer(wire)
        need(self.descendants is not None,'DESCENDANT_RELEASE_PROVIDER_REQUIRED')
        if nonce not in self.descendants.finished:
            deadline=self.resources.clock()+6*10**9
            def dispose(bound,handle):
                forwarded=getattr(self,'forwarded',{}).get(nonce)
                if forwarded is not None:
                    broker=forwarded[1]
                    need(not broker.unknown and broker.verifier.binding is bound
                         and handle==bound.runtime_handle,'DESCENDANT_EXIT_FORWARDING_IDENTITY')
                    broker.verifier.dispose_after_exit(deadline_ns=deadline)
            self.descendants.release(nonce,deadline_ns=deadline,before_close=dispose)
        need(nonce in self.descendants.finished
             and all(self.calls.closed(h) for _,h in self.descendants.held[nonce]),
             'DESCENDANT_RELEASE_INCOMPLETE')
        self.verify_peer(wire)
        return {'schema':'AIP06_DESCENDANT_RELEASE_V1','scope':self.resources.read()['scope'],
                'nonce':nonce,'owner':self.owner,'duplicates_closed':True,'financial_ack':False}

    def verify_descendants(self, wire, unused):
        self.verify_peer(wire)
        need(unused is None and self.descendants is not None and self.descendants.staging is not None,
             'DESCENDANT_GLOBAL_GRAPH_PROVIDER_REQUIRED')
        self.descendants.staging.verify()
        observed=self.descendants.aggregate.observe(commit=False)
        return {'scope':self.resources.read()['scope'],'peer':wire['child'],
                'members':observed['members'],'at_ns':observed['at_ns'],'source_head':self.resources.head}

    def defer_native_release(self, wire, key):
        """COM addresses/failed opens are not independently closable handles.

        Keep their full reservation live until original peer exit. This ACK
        records a deferred declaration, never a release or financial drain ACK.
        Registered kernel handles must use the stronger original-handle proof.
        """
        self.verify_peer(wire)
        row = self.resources.state['resources'].get(key)
        need(row is not None and row == {'owner': self.owner, 'kind': 'handle', 'closed': False}
             and key not in self.live and key not in self.deferred, 'DEFER_ONLY_UNBOUND_NATIVE_LIFETIME')
        self.deferred.add(key)
        return {'key': key, 'owner': self.owner, 'closed': False, 'release_pending_peer_exit': True, 'financial_ack': False}

    def note_reservation(self, owner, key, kind, **kw):
        need(owner == self.owner, 'REMOTE_RESERVATION_OWNER')
        self.reservations[key] = {'kind':kind,**kw}

    def declare_effect(self, wire, key, kind, path, size=None):
        import ntpath
        self.verify_peer(wire)
        row = self.resources.state['resources'].get(key)
        need(self.effects_io is not None and kind in ('file','directory','capacity') and key not in self.effects
             and row == {'owner':self.owner,'kind':'file' if kind == 'capacity' else kind,'closed':False},
             'REMOTE_PRIOR_EFFECT_RESERVATION')
        self.effects_io.allowed(path)
        parent = self.effects_io.inspect(ntpath.dirname(path))
        need(parent is not None and parent['kind'] == 'directory' and not parent['reparse'] and parent['links'] == 1,
             'REMOTE_EFFECT_NATIVE_PARENT')
        before = self.effects_io.inspect(path)
        if kind == 'capacity':
            need(size == 256*1024 and self.reservations.get(key,{}).get('size') == size,
                 'REMOTE_SQLITE_CAPACITY_MUST_ALREADY_BE_CHARGED')
        elif before is not None:
            known = self.effect_paths.get(path, getattr(getattr(self.effects_io,'guard',None),'file_identities',{}).get(path))
            need(known == before['id'] and not before['reparse'] and before['links'] == 1, 'REMOTE_NO_FOREIGN_EFFECT_ADOPTION')
        intent = {'scope':self.resources.read()['scope'],'owner':self.owner,'key':key,'kind':kind,'path':path,
                  'parent':parent,'before':before,'size':size}
        self.effects[key] = intent
        return intent

    def dispose_after_exit(self, *, deadline_ns):
        """Kernel exit releases child handles; never a financial drain ACK."""
        parent = self.binding.api.observe(self.binding.parent_handle)
        life = self.binding.api.lifecycle(self.binding.runtime_handle)
        need(
            parent == self.binding.parent
            and life["pid"] == self.binding.runtime["pid"]
            and life["created"] == self.binding.runtime["created"]
            and life["exited"] is True
            and self.binding.api.members() == set(),
            "REMOTE_RELEASE_REQUIRES_ORIGINAL_PEER_EXIT",
        )
        for key, item in tuple(self.live.items()):
            need(self.resources.clock() < deadline_ns, "REMOTE_RELEASE_DEADLINE")
            self.calls.close(item["local"])
            need(self.calls.closed(item["local"]), "REMOTE_EXIT_DUPLICATE_STILL_OPEN")
            self.allocations.release(item["ticket"])
            del self.live[key]
            self.done.add(key)
            self.resources.close(self.owner, key, observer=self)
        for key in tuple(self.deferred):
            need(self.resources.clock() < deadline_ns, 'DEFERRED_PEER_RELEASE_DEADLINE')
            self.done.add(key)
            self.resources.close(self.owner, key, observer=self)
            self.deferred.remove(key)
        return {
            "peer": self.owner,
            "exit_code": life["exit_code"],
            "release_only": True,
            "financial_ack": False,
        }
