"""Finite parent-reserved child startup escrow, never a second shared ledger.

The child cannot create the RPC guard before reading its inherited connection.
Reserve that small startup envelope in the parent's real ledger BEFORE creation.
Every local startup allocation consumes one precharged, non-reusable slot. All
slots remain held by the parent until the original child exits independently.
Neither a local close declaration nor a bootstrap ACK refunds any reservation.
"""

import copy

from app.services.paper_financial_replay import digest
from scripts.observation_runtime.aip06_harness import LIMITS, SCOPE_HASH, need


KINDS = ("handle",) * 120 + ("thread",) * 4 + ("image",) * 4


class ParentBootstrapLease:
    def __init__(self, resources, owner, nonce, clock_ns):
        self.resources, self.owner, self.nonce, self.clock = (
            resources,
            owner,
            nonce,
            clock_ns,
        )
        self.keys, self.done = {}, set()
        self.started = clock_ns()
        self.cleanup = resources.state["mode"] == "STOP" or any(
            r["state"] == "PENDING" for r in resources.state["stops"].values()
        )
        self.expires = min(
            self.started + 30 * 10**9,
            resources.state["started_ns"]
            + LIMITS["seconds" if self.cleanup else "work_seconds"] * 10**9,
        )
        self.prepared = False

    def reserve(self):
        need(
            not self.prepared and self.clock() < self.expires,
            "BOOTSTRAP_LEASE_ONCE_BEFORE_CREATION",
        )
        self.prepared = True
        self.resources.reserve_bootstrap(self.owner,self.nonce,cleanup=self.cleanup)
        for serial, kind in enumerate(KINDS):
            key = f"child-bootstrap:{self.nonce}:{serial:03d}"
            self.keys[key] = kind
        return self.descriptor()

    def descriptor(self):
        need(
            self.prepared and len(self.keys) == len(KINDS),
            "COMPLETE_PARENT_BOOTSTRAP_RESERVATION",
        )
        return {
            "schema": "AIP06_PARENT_BOOTSTRAP_LEASE_V1",
            "scope": SCOPE_HASH,
            "nonce": self.nonce,
            "parent_owner": self.owner,
            "started_ns": self.started,
            "expires_ns": self.expires,
            "slots": copy.deepcopy(self.keys),
            "reservation_head": self.resources.head,
        }

    def release(self, *, calls, child, deadline_ns):
        need(self.clock() < deadline_ns, "BOOTSTRAP_RELEASE_DEADLINE")
        if child.launch_handle is None:
            need(
                not getattr(child, "creation_attempted", False),
                "BOOTSTRAP_CREATION_OUTCOME_UNKNOWN",
            )
        else:
            life = calls.lifecycle(child.launch_handle)
            need(
                child.creation_native is not None
                and life["pid"] == child.creation_native["pid"]
                and life["created"] == child.creation_native["created"]
                and life["exited"] is True,
                "BOOTSTRAP_LEASE_REQUIRES_ORIGINAL_CHILD_EXIT",
            )
        from scripts.observation_runtime.aip06_ipc import RemoteResources
        if type(self.resources) is RemoteResources and child.launch_handle is not None:
            self.resources.release_bootstrap(self.nonce)
            need(all(self.resources.state['resources'][key]['closed'] for key in self.keys),
                 'BOOTSTRAP_ROOT_RELEASE_ACK_INCOMPLETE')
            self.done.update(self.keys)
            return {'closed':True,'scope':SCOPE_HASH,'nonce':self.nonce,'financial_ack':False}
        need(self.clock() < deadline_ns, "BOOTSTRAP_RELEASE_DEADLINE")
        self.done.update(self.keys)
        self.resources.close_bootstrap(self.owner,self)
        return {
            "closed": True,
            "scope": SCOPE_HASH,
            "nonce": self.nonce,
            "financial_ack": False,
        }

    def closed(self, owner, key):
        return owner == self.owner and key in self.done


class InheritedBootstrapLease:
    def __init__(self, descriptor, binding, clock_ns):
        need(
            type(descriptor) is dict
            and set(descriptor)
            == {
                "schema",
                "scope",
                "nonce",
                "parent_owner",
                "started_ns",
                "expires_ns",
                "slots",
                "reservation_head",
            }
            and descriptor["schema"] == "AIP06_PARENT_BOOTSTRAP_LEASE_V1"
            and descriptor["scope"] == SCOPE_HASH
            and descriptor["nonce"] == binding["nonce"]
            and descriptor["parent_owner"] == digest(binding["parent"])
            and type(descriptor["started_ns"]) is int
            and type(descriptor["expires_ns"]) is int
            and descriptor["started_ns"]
            <= clock_ns()
            < descriptor["expires_ns"]
            <= descriptor["started_ns"] + 30 * 10**9,
            "EXACT_FRESH_INHERITED_BOOTSTRAP_LEASE",
        )
        slots = descriptor["slots"]
        need(
            type(slots) is dict
            and len(slots) == len(KINDS)
            and list(slots.values()) == list(KINDS)
            and list(slots)
            == [
                f"child-bootstrap:{binding['nonce']}:{i:03d}" for i in range(len(KINDS))
            ],
            "EXACT_PRECHARGED_BOOTSTRAP_SLOTS",
        )
        self.descriptor, self.clock = copy.deepcopy(descriptor), clock_ns
        self.owner = digest(binding["child"])
        self.available = list(slots)
        self.used, self.done = {}, set()
        self.sealed = False
        self.retained = set()
        self.native = {}
        self.capacities = {}
        self.evidence_sequence = 0

    def bind_native_handle(self, key, handle):
        need(not self.sealed and key in self.used and key not in self.done
             and key not in self.native and key not in self.capacities
             and type(handle) is int and handle > 0, 'BOOTSTRAP_NATIVE_ACQUISITION_BINDING')
        self.native[key] = {'handle':handle,'acquired_ns':self.clock()}

    def register_capacity(self, key, batch):
        need(key in self.used and key not in self.native and key not in self.capacities
             and type(batch) is ObserverBatch and batch.lease is self,
             'BOOTSTRAP_TYPED_OBSERVER_CAPACITY')
        self.capacities[key] = batch

    def evidence(self):
        need(self.sealed, 'BOOTSTRAP_EVIDENCE_AFTER_SEAL_ONLY')
        self.evidence_sequence += 1
        slots = {slot:{'state':'RESERVED_NOT_ACQUIRED'} for slot in self.descriptor['slots']}
        for key, row in self.used.items():
            item = {'key':key,'kind':row['kind']}
            if key in self.done:
                item.update(state='CLOSED_LOCAL',native=self.native.get(key))
            elif key in self.capacities:
                batch=self.capacities[key]
                need(not batch.live,'BOOTSTRAP_OBSERVER_CUT_NOT_QUIESCENT')
                item.update(state='OBSERVER_CAPACITY',completed=batch.serial,active=0)
            else:
                need(key in self.native,'BOOTSTRAP_RETAINED_OBJECT_WITHOUT_ACQUISITION')
                item.update(state='RETAINED_NATIVE',native=self.native[key])
            slots[row['parent_slot']] = item
        from app.services.paper_financial_replay import digest
        return {'schema':'AIP06_BOOTSTRAP_OBJECT_CUT_V1','scope':SCOPE_HASH,
                'nonce':self.descriptor['nonce'],'owner':self.owner,
                'parent_owner':self.descriptor['parent_owner'],'sequence':self.evidence_sequence,
                'at_ns':self.clock(),'descriptor':digest({k:v for k,v in self.descriptor.items() if k!='reservation_head'}),
                'slots':slots,'parent_reservations_released':False,'financial_ack':False}

    @property
    def state(self):
        return {
            "mode": "WORK",
            "stops": {},
            "resources": {
                k: {"owner": self.owner, "kind": v["kind"], "closed": k in self.done}
                for k, v in self.used.items()
            },
        }

    def read(self):
        need(
            not self.sealed and self.clock() < self.descriptor["expires_ns"],
            "BOOTSTRAP_LEASE_SEALED_OR_EXPIRED",
        )
        return {
            "domain": "PARENT_RESERVED_PRE_RPC_ESCROW_NOT_FINANCIAL_AUTHORITY",
            "state": self.state,
        }

    def reserve(self, owner, key, kind, *, entries=0, size=0, cleanup=False):
        self.read()
        need(
            owner == self.owner
            and key not in self.used
            and entries == size == 0
            and not cleanup,
            "BOOTSTRAP_ONLY_PRECHARGED_NATIVE_ALLOCATIONS",
        )
        slots = [s for s in self.available if self.descriptor["slots"][s] == kind]
        need(slots, "BOOTSTRAP_RESERVATION_EXHAUSTED")
        slot = slots[0]
        self.available.remove(slot)
        self.used[key] = {"kind": kind, "parent_slot": slot}

    def close(self, owner, key, *, observer):
        if self.sealed:
            need(
                key in self.retained,
                "ONLY_RETAINED_BOOTSTRAP_CAPABILITY_MAY_CLOSE_AFTER_SEAL",
            )
        else:
            self.read()
        need(
            owner == self.owner
            and key in self.used
            and key not in self.done
            and observer.closed(owner, key) is True,
            "BOOTSTRAP_LOCAL_RELEASE_PROOF",
        )
        self.done.add(key)

    def seal(self, *, retained=()):
        self.read()
        need(
            set(self.used) - self.done == set(retained),
            "BOOTSTRAP_UNRESOLVED_ALLOCATION",
        )
        self.sealed = True
        self.retained = set(retained)
        return {
            "scope": SCOPE_HASH,
            "used": len(self.used),
            "local_closed": len(self.done),
            "parent_reservations_released": False,
            "financial_ack": False,
        }


class ObserverBatch:
    """Prepaid read-only CIM batch; never reserves through its own RPC channel.

    Parent escrow stays live for the entire child lifetime. Eight concurrent
    slots cover one native observer thread and its seven COM references. Local
    lifetimes/counters are never reset and must close before a slot is reused.
    No filesystem effects, process launches, or financial writes use this batch.
    """

    def __init__(self, lease):
        self.lease, self.owner = lease, lease.owner
        self.slots = {}
        for i, kind in enumerate(("thread",) + ("handle",) * 7):
            key = f"observer-envelope:{i}"
            lease.reserve(self.owner, key, kind)
            self.slots[key] = kind
            lease.register_capacity(key,self)
        self.live, self.completed = {}, set()
        self.serial = 0

    @property
    def state(self):
        return {"mode": "WORK", "stops": {}}

    def read(self):
        return {"domain": "PREPAID_READONLY_OBSERVER_BATCH_NOT_FINANCIAL_AUTHORITY"}

    def reserve(self, owner, key, kind, *, entries=0, size=0, cleanup=False):
        need(
            owner == self.owner
            and kind in ("handle", "thread")
            and key not in self.live
            and key not in self.completed
            and entries == size == 0
            and not cleanup,
            "OBSERVER_ONLY_NATIVE_READ_LIFETIME",
        )
        used = {v["slot"] for v in self.live.values()}
        available = [s for s, k in self.slots.items() if k == kind and s not in used]
        need(available and self.serial < 4096, "OBSERVER_BATCH_CAPACITY")
        self.serial += 1
        self.live[key] = {"slot": available[0], "serial": self.serial}

    def close(self, owner, key, *, observer):
        need(
            owner == self.owner
            and key in self.live
            and observer.closed(owner, key) is True,
            "OBSERVER_NATIVE_RELEASE_REQUIRED",
        )
        del self.live[key]
        self.completed.add(key)

    def finish(self):
        need(not self.live, "OBSERVER_BATCH_STILL_ACTIVE")
        for key in self.slots:
            self.lease.close(self.owner, key, observer=self)

    def closed(self, owner, key):
        return owner == self.owner and not self.live and key in self.slots
