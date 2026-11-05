"""Versioned anonymous-pipe IPC and parent-owned resource RPC for AIP06.

No sockets, launcher, default transport, financial acknowledgement or authority.
Native endpoints are explicit and injected; neither Windows endpoint is selected
by default. Their cross-process/native qualification is still pending.
Every connection must be bound to original launch/parent/Job handles first.
"""

import copy
import contextlib
import struct
import threading

from app.services.paper_financial_replay import body, digest, strict

from scripts.observation_runtime.aip06_harness import (
    SCOPE_HASH,
    SharedResources,
    integer,
    need,
)

VERSION = "AIP06_PIPE_V1"
MAX_MESSAGE = 1024**2
MAX_IPC_NS = 6 * 10**9
KINDS = frozenset(
    {
        "HELLO",
        "BIND",
        "RELEASE",
        "REQUEST",
        "REPLY",
        "STOP",
        "ACK",
        "DRAIN",
        "OUTPUT",
        "EXIT",
        "FAILURE",
        "INPUT",
    }
)


def encode(value):
    raw = body(value).encode("utf8")
    need(0 < len(raw) <= MAX_MESSAGE, "IPC_MESSAGE_CAPACITY")
    return struct.pack("!I", len(raw)) + raw


class Channel:
    """One ordered private connection; replay or uncertain IO latches refusal."""

    def __init__(self, endpoint, *, binding, clock_ns, account_scope, role):
        need(
            type(binding) is dict
            and set(binding)
            == {"scope", "session", "nonce", "parent", "child", "job", "launch"}
            and binding["scope"] == SCOPE_HASH
            and type(binding["session"]) is str
            and binding["session"]
            and type(binding["nonce"]) is str
            and len(binding["nonce"]) == 32,
            "EXACT_IPC_BINDING",
        )
        need(
            role in ("PARENT", "CHILD")
            and type(account_scope) is dict
            and account_scope
            and set(account_scope) <= {"QUALITY_DIPS", "HYPERLIQUID"}
            and all(
                type(v) is dict and set(v) == {"account_id", "epoch", "currency"}
                for v in account_scope.values()
            ),
            "EXACT_IPC_ACCOUNT_SCOPE",
        )
        for lane, row in account_scope.items():
            need(
                row["currency"] == ("USD" if lane == "QUALITY_DIPS" else "USDC")
                and all(type(v) is str and v for v in row.values()),
                "IPC_CURRENCY_SCOPE",
            )
        self.endpoint, self.binding, self.clock = (
            endpoint,
            strict(body(binding)),
            clock_ns,
        )
        self.accounts, self.role = strict(body(account_scope)), role
        self.sent, self.received, self.failed = 0, 0, False
        self.send_head, self.receive_head = digest(binding), digest(binding)
        self.send_lock, self.receive_lock = threading.RLock(), threading.RLock()

    def deadline(self, deadline_ns):
        now = self.clock()
        need(
            not self.failed
            and integer(now)
            and integer(deadline_ns)
            and now < deadline_ns <= now + MAX_IPC_NS,
            "BOUNDED_IPC_DEADLINE",
        )
        self.endpoint.verify_peer(self.binding)
        return now

    @contextlib.contextmanager
    def operation(self, lock, deadline_ns):
        with lock:
            try:
                started = self.deadline(deadline_ns)
                yield started
            except BaseException:
                self.failed = True
                raise

    def send(self, kind, payload, *, deadline_ns):
        with self.operation(self.send_lock, deadline_ns) as started:
            need(kind in KINDS, "IPC_KIND")
            value = {
                "schema": VERSION,
                "binding": digest(self.binding),
                "accounts": digest(self.accounts),
                "direction": self.role,
                "sequence": self.sent + 1,
                "parent": self.send_head,
                "sent_ns": started,
                "kind": kind,
                "payload": payload,
            }
            raw = encode(value)
            self.endpoint.write_all(raw, deadline_ns=deadline_ns)
            need(started <= self.clock() <= deadline_ns, "IPC_SEND_DEADLINE")
            self.sent += 1
            self.send_head = digest(value)
            return self.send_head

    def receive(self, *, deadline_ns, expected_kind=None):
        with self.operation(self.receive_lock, deadline_ns) as started:
            prefix = self.endpoint.read_exact(4, deadline_ns=deadline_ns)
            need(type(prefix) is bytes and len(prefix) == 4, "IPC_FRAME_HEADER")
            count = struct.unpack("!I", prefix)[0]
            need(0 < count <= MAX_MESSAGE, "IPC_FRAME_CAPACITY")
            raw = self.endpoint.read_exact(count, deadline_ns=deadline_ns)
            need(type(raw) is bytes and len(raw) == count, "IPC_FRAME_TRUNCATED")
            value = strict(raw.decode("utf8"))
            need(
                type(value) is dict
                and set(value)
                == {
                    "schema",
                    "binding",
                    "accounts",
                    "direction",
                    "sequence",
                    "parent",
                    "sent_ns",
                    "kind",
                    "payload",
                }
                and body(value).encode() == raw
                and value["schema"] == VERSION
                and value["binding"] == digest(self.binding)
                and value["accounts"] == digest(self.accounts)
                and value["direction"] != self.role
                and value["direction"] in ("PARENT", "CHILD")
                and type(value["sequence"]) is int
                and value["sequence"] == self.received + 1
                and value["parent"] == self.receive_head
                and integer(value["sent_ns"])
                and 0 <= self.clock() - value["sent_ns"] <= MAX_IPC_NS
                and value["kind"] in KINDS
                and (expected_kind is None or value["kind"] == expected_kind),
                "IPC_IDENTITY_SEQUENCE_OR_FRESHNESS",
            )
            need(started <= self.clock() <= deadline_ns, "IPC_RECEIVE_DEADLINE")
            self.endpoint.verify_peer(self.binding)
            self.received += 1
            self.receive_head = digest(value)
            return value


class Broker:
    """Serialize child effects through the one live parent ledger.

    verifier duplicates/checks only handles from the retained peer process.
    output writes append-only INTENT/RESULT records before replying. Recovery
    never repeats an effect with a missing result, even if the pipe ACK was lost.
    """

    def __init__(self, *, resources, channel, peer_owner, verifier, output, clock_ns):
        need(
            type(resources) is SharedResources
            and peer_owner in resources.state["owners"]
            and resources.state["owners"][peer_owner] == channel.binding["child"],
            "RETAINED_BROKER_PEER",
        )
        self.resources, self.channel, self.owner = resources, channel, peer_owner
        self.verifier, self.output, self.clock = verifier, output, clock_ns
        self.last = 0
        self.unknown = False
        self.history = []
        self.peer_head = resources.head

    def _operation(self, request):
        need(
            type(request) is dict
            and set(request)
            == {"revision", "parent_head", "method", "args", "kwargs", "proof"}
            and type(request["revision"]) is int
            and request["revision"] == self.last + 1
            and request["parent_head"] == self.peer_head
            and type(request["args"]) is list
            and type(request["kwargs"]) is dict,
            "RPC_EXACT_CURRENT_REQUEST",
        )
        method = request["method"]
        args = request["args"]
        kw = request["kwargs"]
        need(
            method
            in {
                "read",
                "reserve",
                "charge_write",
                "close",
                "bind_reserved_process",
                "reserve_stop_request",
                "resolve_stop",
                "bind_native_handle",
                "defer_native_release",
                'declare_effect',
                'declare_descendant',
                'stage_descendant', 'resume_descendant', 'release_descendant', 'verify_descendants',
            },
            "RPC_METHOD_NOT_PERMITTED",
        )
        self.verifier.verify_peer(self.channel.binding)
        if method in ('stage_descendant','resume_descendant','release_descendant','verify_descendants'):
            need(len(args)==2 and args[0]==self.owner and not kw and request['proof'] is None,
                 'RPC_DESCENDANT_OWNER_OR_ARGUMENTS')
            return getattr(self.verifier,method)(self.channel.binding,args[1])
        if method == 'declare_descendant':
            need(len(args) == 3 and args[0] == self.owner and not kw
                 and request['proof'] is None, 'RPC_DESCENDANT_DECLARATION_OWNER')
            return self.verifier.declare_descendant(self.channel.binding,args[1],args[2])
        if method == "read":
            need(not args and not kw and request["proof"] is None, "RPC_READ_ARGUMENTS")
            return self.resources.read()
        if method == "bind_native_handle":
            need(
                len(args) == 3
                and args[0] == self.owner
                and not kw
                and request["proof"] is None,
                "RPC_NATIVE_HANDLE_ARGUMENTS",
            )
            return self.verifier.bind_native_handle(
                self.channel.binding, args[1], args[2]
            )
        if method == 'defer_native_release':
            need(len(args) == 2 and args[0] == self.owner and not kw and request['proof'] is None, 'RPC_DEFERRED_NATIVE_OWNER')
            return self.verifier.defer_native_release(self.channel.binding, args[1])
        if method == 'declare_effect':
            need(len(args) == 5 and args[0] == self.owner and not kw and request['proof'] is None, 'RPC_EFFECT_OWNER')
            return self.verifier.declare_effect(self.channel.binding,*args[1:])
        if method in ("reserve", "charge_write", "close"):
            need(args and args[0] == self.owner, "RPC_FOREIGN_OWNER")
            if method == "close":
                need(len(args) == 2 and not kw, "RPC_CLOSE_ARGUMENTS")
                observer = self.verifier.release_observer(
                    self.channel.binding, args[1], request["proof"]
                )
                return self.resources.close(*args, observer=observer)
            need(request["proof"] is None, "RPC_UNEXPECTED_MUTATION_PROOF")
            result = getattr(self.resources, method)(*args, **kw)
            if method == 'reserve' and hasattr(self.verifier,'note_reservation'):
                self.verifier.note_reservation(*args,**kw)
            return result
        if method == "bind_reserved_process":
            need(
                len(args) == 2 and args[1] == self.owner and not kw,
                "RPC_CHILD_RESERVATION_OWNER",
            )
            binding, handle = self.verifier.child_binding(
                self.channel.binding, request["proof"]
            )
            return self.resources.bind_reserved_process(
                args[0], self.owner, binding, handle
            )
        need(
            len(args) in (1, 2) and not kw and request["proof"] is None,
            "RPC_STOP_ARGUMENTS",
        )
        command = args[0]
        need(
            type(command) is dict and digest(command.get("worker")) == self.owner,
            "RPC_STOP_WORKER",
        )
        return getattr(self.resources, method)(*args)

    def serve_once(self, *, deadline_ns):
        need(not self.unknown, "RPC_RECOVERY_REQUIRED")
        incoming = self.channel.receive(
            deadline_ns=deadline_ns, expected_kind="REQUEST"
        )
        return self.serve_message(incoming, deadline_ns=deadline_ns)

    def serve_message(self, incoming, *, deadline_ns):
        # Only the single receive owner may dispatch a fully verified frame.
        # Rechecking the channel's current receive head prevents callers from
        # injecting a plausible REQUEST dict outside Channel.receive.
        need(
            not self.unknown
            and type(incoming) is dict
            and incoming.get("kind") == "REQUEST"
            and digest(incoming) == self.channel.receive_head,
            "RPC_RECEIVED_FRAME_REQUIRED",
        )
        request = incoming["payload"]
        operation = digest(request)
        self.unknown = True
        self.output.append(
            {
                "schema": "AIP06_RPC_INTENT_V1",
                "peer": self.owner,
                "operation": operation,
                "request": request,
            }
        )
        result = self._operation(request)
        snapshot = self.resources.read()
        record = {
            "schema": "AIP06_RPC_RESULT_V1",
            "peer": self.owner,
            "operation": operation,
            "revision": request["revision"],
            "head": snapshot["head"],
            "result": result,
        }
        self.output.append(record)
        self.history.append((operation, record))
        self.last = request["revision"]
        snapshot = self.resources.read()
        reply = {**record, "head": snapshot["head"], "snapshot": snapshot}
        self.channel.send("REPLY", reply, deadline_ns=deadline_ns)
        self.peer_head = snapshot["head"]
        self.unknown = False
        return reply

    def recover(self, records, *, expected_head):
        need(
            not self.history and self.last == 0 and type(records) is list,
            "RPC_COLD_RECOVERY_ONLY",
        )
        pending = None
        last = 0
        for record in records:
            need(record.get("peer") == self.owner, "RPC_RECOVERY_PEER")
            if record.get("schema") == "AIP06_RPC_INTENT_V1":
                need(
                    pending is None
                    and record["operation"] == digest(record["request"])
                    and record["request"]["revision"] == last + 1,
                    "RPC_RECOVERY_INTENT",
                )
                pending = record
            else:
                need(
                    record.get("schema") == "AIP06_RPC_RESULT_V1"
                    and pending is not None
                    and record["operation"] == pending["operation"]
                    and record["revision"] == last + 1,
                    "RPC_RECOVERY_RESULT",
                )
                last = record["revision"]
                pending = None
        need(self.resources.head == expected_head, "RPC_RECOVERY_HEAD")
        self.last = last
        self.unknown = True  # Inspection/cleanup only; no resumed writes.
        return {
            "pending": pending is not None,
            "revision": last,
            "resumption_authorized": False,
            "head": expected_head,
        }


class RemoteResources(SharedResources):
    """RPC facade, NOT a second SharedResources journal or recovered writer."""

    def __init__(self, channel, *, owner, initial, clock_ns, proofs):
        need(
            owner == digest(channel.binding["child"])
            and initial["scope"] == SCOPE_HASH
            and initial["state"]["owners"].get(owner) == channel.binding["child"],
            "REMOTE_LEDGER_BINDING",
        )
        self.channel, self.owner, self.clock, self.proofs = (
            channel,
            owner,
            clock_ns,
            proofs,
        )
        self.snapshot = copy.deepcopy(initial)
        self.revision = 0
        self.uncertain = False
        self.lock = threading.RLock()
        self._recovered = False
        from scripts.observation_runtime.aip06_windows_pump import Mailbox
        self.mailbox=Mailbox(channel)

    @property
    def state(self):
        return copy.deepcopy(self.snapshot["state"])

    @property
    def head(self):
        return self.snapshot["head"]

    @property
    def recovered(self):
        return False

    def call(self, method, args, kwargs, proof=None):
        with self.lock:
            need(not self.uncertain, "REMOTE_LEDGER_UNKNOWN")
            self.uncertain = True
            request = {
                "revision": self.revision + 1,
                "parent_head": self.head,
                "method": method,
                "args": list(args),
                "kwargs": kwargs,
                "proof": proof,
            }
            end = self.clock() + MAX_IPC_NS
            self.channel.send("REQUEST", request, deadline_ns=end)
            result = self.mailbox.receive('REPLY',deadline_ns=end)['payload']
            need(
                type(result) is dict
                and set(result)
                == {
                    "schema",
                    "peer",
                    "operation",
                    "revision",
                    "head",
                    "result",
                    "snapshot",
                }
                and result["schema"] == "AIP06_RPC_RESULT_V1"
                and result["peer"] == self.owner
                and result["operation"] == digest(request)
                and type(result["revision"]) is int
                and result["revision"] == self.revision + 1
                and result["head"] == result["snapshot"]["head"]
                and result["snapshot"]["scope"] == SCOPE_HASH
                and result["snapshot"]["state"]["controller"]
                == self.state["controller"]
                and result["snapshot"]["state"]["entries"] >= self.state["entries"]
                and result["snapshot"]["state"]["charged_bytes"]
                >= self.state["charged_bytes"],
                "RPC_ACK_IDENTITY_REVISION",
            )
            self.snapshot = copy.deepcopy(result["snapshot"])
            self.revision += 1
            self.uncertain = False
            return copy.deepcopy(result["result"])

    def read(self):
        return self.call("read", (), {})

    def reserve(self, *args, **kwargs):
        return self.call("reserve", args, kwargs)

    def charge_write(self, *args, **kwargs):
        return self.call("charge_write", args, kwargs)

    def bind_native_handle(self, key, handle):
        self.proofs.bind(key, handle)
        return self.call("bind_native_handle", (self.owner, key, handle), {})

    def defer_native_release(self, owner, key):
        need(owner == self.owner, 'REMOTE_DEFER_FOREIGN_OWNER')
        result = self.call('defer_native_release', (owner, key), {})
        need(result == {'key': key, 'owner': owner, 'closed': False, 'release_pending_peer_exit': True, 'financial_ack': False}
             and self.state['resources'][key]['closed'] is False, 'DEFERRED_NATIVE_RELEASE_IS_NOT_CLOSED')
        return result

    def close(self, owner, key, *, observer):
        need(observer.closed(owner, key) is True, "LOCAL_RELEASE_UNVERIFIED")
        if key not in getattr(self.proofs,'handles',{}) and key not in getattr(self.proofs,'effects',{}) and self.state['resources'][key]['kind'] == 'handle':
            return self.defer_native_release(owner,key)
        return self.call(
            "close", (owner, key), {}, self.proofs.release(owner, key, observer)
        )

    def declare_effect(self, key, kind, path, size=None):
        intent = self.call('declare_effect',(self.owner,key,kind,path,size),{})
        need(intent['owner'] == self.owner and intent['key'] == key and intent['path'] == path
             and intent['kind'] == kind and intent['scope'] == SCOPE_HASH, 'REMOTE_EFFECT_ACK_SCOPE')
        self.proofs.effects[key] = digest(intent)
        return intent

    def declare_descendant(self, request, slot):
        from scripts.observation_runtime.launch_ownership import LaunchRequest
        need(type(request) is LaunchRequest, 'EXACT_DESCENDANT_LAUNCH_REQUEST')
        request.validate()
        return self._checked_descendant('declare_descendant',(self.owner,vars(request),slot),lambda result:
            result == {'schema':'AIP06_DESCENDANT_DECLARED_V1','owner':self.owner,
                        'nonce':request.nonce,'slot':slot,'financial_ack':False},
             'DESCENDANT_DECLARATION_ACK_CONFLICT')

    def _checked_descendant(self, method, args, validate, reason):
        with self.lock:
            try:
                result=self.call(method,args,{})
                need(validate(result),reason)
                return result
            except BaseException:
                self.uncertain=True
                raise

    def stage_descendant(self, proof, request, identity):
        return self._checked_descendant('stage_descendant',(self.owner,proof),lambda v:
            type(v) is dict and set(v)=={'schema','scope','nonce','identity','request','released_to_bootstrap','financial_ack'}
            and v['schema']=='AIP06_SUSPENDED_STAGE_V1' and v['scope']==SCOPE_HASH
            and v['nonce']==request.nonce==proof['nonce'] and v['request']==digest(vars(request))
            and all(v['identity'].get(k)==identity[k] for k in ('pid','created','image'))
            and v['released_to_bootstrap'] is False and v['financial_ack'] is False,
            'DESCENDANT_STAGE_RECEIPT_CONFLICT')

    def resume_descendant(self, nonce, identity):
        return self._checked_descendant('resume_descendant',(self.owner,nonce),lambda v:
            v=={'schema':'AIP06_STAGED_BOOTSTRAP_RELEASE_V1','scope':SCOPE_HASH,'nonce':nonce,
                'identity':identity,'financial_ack':False,'guard_release':False},'DESCENDANT_RESUME_RECEIPT_CONFLICT')

    def release_descendant(self, nonce):
        return self._checked_descendant('release_descendant',(self.owner,nonce),lambda v:
            v=={'schema':'AIP06_DESCENDANT_RELEASE_V1','scope':SCOPE_HASH,'nonce':nonce,
                'owner':self.owner,'duplicates_closed':True,'financial_ack':False},'DESCENDANT_RELEASE_RECEIPT_CONFLICT')

    def verify_descendants(self):
        return self._checked_descendant('verify_descendants',(self.owner,None),lambda v:
            type(v) is dict and set(v)=={'scope','peer','members','at_ns','source_head'}
            and v['scope']==SCOPE_HASH and v['peer']==self.channel.binding['child']
            and type(v['at_ns']) is int and 0<=self.clock()-v['at_ns']<=MAX_IPC_NS
            and type(v['members']) is list and len(v['members'])==len(set(v['members']))<=8
            and all(type(p) is int and p>4 for p in v['members'])
            and v['peer']['pid'] in v['members'] and type(v['source_head']) is str and len(v['source_head'])==64
            and set(v['source_head'])<=set('0123456789abcdef'),
            'DESCENDANT_GRAPH_STALE_OR_CONFLICTING')

    def register_owner(self, observed, **kwargs):
        key = digest(observed)
        need(
            key in self.state["owners"]
            and self.state["owners"][key] == strict(body(observed)),
            "REMOTE_OWNER_REQUIRES_RETAINED_REGISTRATION",
        )
        return key

    def bind_reserved_process(self, key, parent_owner, binding, handle, **kwargs):
        need(
            parent_owner == self.owner and not kwargs.get("cleanup", False),
            "REMOTE_LAUNCH_DURING_STOP",
        )
        return self.call(
            "bind_reserved_process",
            (key, parent_owner),
            {},
            self.proofs.child(binding, handle),
        )

    def reserve_stop_request(self, request):
        return self.call("reserve_stop_request", (request,), {})

    def resolve_stop(self, request, status):
        return self.call("resolve_stop", (request, status), {})

    def begin_stop(self):
        raise ValueError("ONLY_PARENT_CAN_BEGIN_GLOBAL_CLEANUP")

    def usage(self, **kwargs):
        raise ValueError("ONLY_PARENT_CAN_ATTEST_AGGREGATE_USAGE")


class StopMessages:
    """Correlate actual worker ACK/drain; never infer them from exit or EOF."""

    def __init__(self, channel, request, *, revision, accounts):
        need(
            type(revision) is int
            and revision >= 0
            and request["scope"] == SCOPE_HASH
            and body(accounts) == body(channel.accounts)
            and body(request["worker"]) == body(channel.binding["child"]),
            "STOP_IPC_BINDING",
        )
        self.channel, self.request, self.revision = (
            channel,
            copy.deepcopy(request),
            revision,
        )
        self.acked, self.drained = False, False

    def acknowledge(self, message):
        need(
            not self.acked
            and type(message) is dict
            and set(message) == {"request", "revision", "accounts"}
            and body(message["request"]) == body(self.request)
            and type(message["revision"]) is int
            and message["revision"] == self.revision
            and body(message["accounts"]) == body(self.channel.accounts),
            "STOP_ACK_MISSING_DUPLICATE_OR_CONFLICT",
        )
        self.acked = True
        return copy.deepcopy(self.request)

    def drain(self, message):
        need(
            self.acked
            and not self.drained
            and type(message) is dict
            and body(message)
            == body(
                {
                    "scope": SCOPE_HASH,
                    "operation_id": self.request["operation_id"],
                    "pending": 0,
                    "unknown": False,
                    "orders": 0,
                }
            ),
            "STOP_DRAIN_INCOMPLETE_OR_DUPLICATE",
        )
        self.drained = True
        return copy.deepcopy(message)
