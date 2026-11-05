"""Independent remote handle continuity over an original retained process.

The parent duplicates from the verified child creation handle, never a PID.
The child's close declaration is only a request for independent observation.
"""

from app.services.paper_financial_replay import body, digest
from scripts.observation_runtime.aip06_harness import need
from scripts.observation_runtime.launch_ownership import RetainedLaunchBinding


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
        self.binding.verify()

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

    def child_binding(self, *args):
        need(len(args) == 2 and self.descendants is not None, "REMOTE_DESCENDANT_DECLARATION_PROVIDER_REQUIRED")
        wire, proof = args
        self.verify_peer(wire)
        return self.descendants.import_binding(proof)

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
