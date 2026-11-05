"""Predeclared original-handle suspended descendants; no CLI or native loader.

This is the existing descendant registry's staging implementation. Stage and
bootstrap release are NOT guard/financial ACKs. The transport/gateway must bind
this transaction before any child may use it; otherwise creation stays refused.
"""

import copy
import hashlib
import ntpath

from app.services.paper_financial_replay import body, digest
from scripts.observation_runtime.aip06_harness import LIMITS, SCOPE_HASH, need
from scripts.observation_runtime.aip06_ipc import MAX_IPC_NS
from scripts.observation_runtime.launch_ownership import RetainedLaunchBinding


class SuspendedDescendantGraph:
    def __init__(self, registry):
        from scripts.observation_runtime.aip06_job_budget import AggregateJobBudget

        need(
            type(registry.peer) is RetainedLaunchBinding
            and type(registry.aggregate) is AggregateJobBudget,
            "ORIGINAL_PEER_AND_NATIVE_AGGREGATE_REQUIRED",
        )
        self.registry = registry
        self.peer = registry.peer
        self.calls = registry.calls
        self.clock = registry.aggregate.clock
        self.nodes = {}
        self.closed = set()
        self.failed = False

    def _identity(self):
        """Original peer identities inside quarantine, NEVER a roster PASS."""
        p = self.peer
        need(
            not p.refused
            and not p.finished
            and p.runtime_handle is not None
            and p.api.observe(p.parent_handle) == p.parent
            and p.api.observe(p.launch_handle) == p.launch
            and p.api.observe(p.runtime_handle) == p.runtime,
            "STAGING_ORIGINAL_PEER_LIFETIME_LOST",
        )

    def stage(self, proof):
        r = self.registry
        need(
            not self.failed
            and not r.failed
            and type(proof) is dict
            and r.files is not None
            and set(proof)
            == {"nonce", "parent", "launch", "thread", "tid", "image", "job"}
            and proof["nonce"] in r.declarations
            and proof["nonce"] not in self.nodes,
            "EXACT_PREDECLARED_SUSPENDED_TRANSFER",
        )
        self.failed = True
        self._identity()
        request, slot = r.declarations[proof["nonce"]]
        need(
            proof["nonce"] in r.declaration_times
            and 0 <= self.clock() - r.declaration_times[proof["nonce"]] < MAX_IPC_NS,
            "STAGING_PREDECLARATION_EXPIRED",
        )
        need(
            r.aggregate.resources.state["resources"].get(slot)
            == {"owner": digest(self.peer.runtime), "kind": "launch", "closed": False},
            "STAGING_LAUNCH_SLOT_LOST",
        )
        held = r.held.setdefault(proof["nonce"], [])
        local = {}
        # Each duplicate is charged before the native operation. Unknown outcome
        # retains its ticket; a later failure never converts it to a free slot.
        for name in ("parent", "launch", "thread", "image", "job"):
            need(
                type(proof[name]) is int and proof[name] > 0,
                "STAGING_ORIGINAL_HANDLE_REQUIRED",
            )
            ticket = r.allocations.reserve("staged-" + name, "handle")
            h = self.calls.duplicate(self.peer.runtime_handle, proof[name])
            held.append((ticket, h))
            local[name] = h
        need(
            r.objects.same(local["parent"], self.peer.runtime_handle),
            "STAGING_PARENT_KERNEL_OBJECT_MISMATCH",
        )
        native = self.calls.native(local["launch"])
        need(
            not self.calls.lifecycle(local["launch"])["exited"]
            and self.calls.in_job(local["launch"], local["job"])
            and self.calls.in_job(local["launch"], self.peer.api.job)
            and self.calls.in_job(local["launch"], r.aggregate.job),
            "STAGING_INHERITED_JOB_CHAIN_MISMATCH",
        )
        limits = {
            "processes": r.aggregate.limits["processes"],
            "private_bytes": r.aggregate.limits["private_bytes"],
            "child_private_bytes": LIMITS["child_private_bytes"],
            "cpu_ns": r.aggregate.limits["cpu_ns"],
            "kill_on_close": True,
        }
        need(
            self.calls.job_limits(local["job"]) == limits,
            "STAGING_FINITE_LEAF_JOB_REQUIRED",
        )
        thread = r.objects.observe(local["thread"])
        need(
            thread["type"] == "Thread"
            and thread["pid"] == native["pid"]
            and type(proof["tid"]) is int
            and thread["tid"] == proof["tid"] > 0
            and thread["created"] >= native["created"]
            and thread["exited"] is False,
            "STAGING_PRIMARY_THREAD_IDENTITY_MISMATCH",
        )
        api = r.observer_factory(job=local["job"], parent=local["parent"])
        pending = RetainedLaunchBinding(api, request, local["parent"], local["launch"])
        need(
            body(pending.parent) == body(self.peer.runtime)
            and pending.launch["pid"] == native["pid"]
            and pending.launch["created"] == native["created"],
            "STAGING_NATIVE_SOURCE_OR_ANCESTRY_MISMATCH",
        )
        image = r.files.describe(local["image"])
        need(
            image["id"] == list(request.launch_image[1])
            and image["kind"] == "file"
            and image["links"] == 1
            and not image["reparse"]
            and ntpath.normcase(r.files.final_path(local["image"]))
            == request.launch_image[0]
            and hashlib.sha256(r.files.read(local["image"], 32 * 1024**2)).hexdigest()
            == request.launch_image[2],
            "STAGING_RETAINED_LAUNCH_IMAGE_MISMATCH",
        )
        need(
            native["pid"] not in {row["native"]["pid"] for row in self.nodes.values()},
            "STAGING_PID_REUSE_OR_ALIAS",
        )
        # A newly created suspended primary thread must already have count 1.
        # The verifier adds and retains a second fence. No READY is invented.
        self.calls.hold_created_thread(local["thread"])
        self.nodes[proof["nonce"]] = {
            "local": local,
            "native": copy.deepcopy(native),
            "pending": pending,
            "request": request,
            "phase": "SUSPENDED",
            "held": held,
            "remote": copy.deepcopy(proof),
        }
        self._verify()
        # Never assign/adopt a running foreign process into the root. The native
        # inherited-chain proof above precedes this already-created attachment.
        r.aggregate.attach_created(
            handle=local["launch"], job=local["job"], native=native
        )
        need(
            self.clock() - r.declaration_times[proof["nonce"]] < MAX_IPC_NS,
            "STAGING_PREDECLARATION_EXPIRED",
        )
        self.failed = False
        return {
            "schema": "AIP06_SUSPENDED_STAGE_V1",
            "scope": SCOPE_HASH,
            "nonce": proof["nonce"],
            "identity": copy.deepcopy(pending.launch),
            "request": digest(vars(request)),
            "released_to_bootstrap": False,
            "financial_ack": False,
        }

    def verify(self):
        try:
            need(not self.failed, "STAGING_FAILURE_LATCHED")
            return self._verify()
        except BaseException:
            self.failed = True
            raise

    def _verify(self):
        """Compare COMPLETE native Jobs, including every declared descendant."""
        self._identity()
        expected = {self.peer.runtime["pid"]}
        for nonce, row in self.nodes.items():
            if nonce in self.closed:
                continue
            local, native = row["local"], row["native"]
            pending = row["pending"]
            need(
                self.calls.native(local["launch"]) == native
                and not self.calls.lifecycle(local["launch"])["exited"]
                and pending.api.observe(local["parent"]) == pending.parent
                and pending.api.observe(local["launch"]) == pending.launch,
                "STAGING_CURRENT_PROCESS_OR_PARENT_CHANGED",
            )
            # This registry owns direct descendants of this exact peer. A
            # deeper graph requires its own forwarded predeclaration; an extra
            # member is rejected, never subtracted from these observations.
            need(
                self.calls.members(local["job"]) == {native["pid"]},
                "STAGING_LEAF_JOB_HAS_UNDECLARED_DESCENDANT",
            )
            expected.add(native["pid"])
        need(
            self.calls.members(self.peer.api.job) == expected,
            "STAGING_COMPLETE_PARENT_JOB_CONFLICT",
        )
        return {
            "scope": SCOPE_HASH,
            "peer": digest(self.peer.runtime),
            "members": sorted(expected),
            "at_ns": self.clock(),
        }

    def resume_bootstrap(self, nonce):
        try:
            return self._resume_bootstrap(nonce)
        except BaseException:
            self.failed = True
            raise

    def _resume_bootstrap(self, nonce):
        need(
            not self.failed
            and nonce in self.nodes
            and self.nodes[nonce]["phase"] == "SUSPENDED",
            "STAGED_BOOTSTRAP_RELEASE_ONCE_ONLY",
        )
        self.failed = True
        self._verify()
        self.registry.aggregate.observe(commit=False)
        row = self.nodes[nonce]
        need(
            self.clock() - self.registry.declaration_times[nonce] < MAX_IPC_NS,
            "STAGING_BOOTSTRAP_RELEASE_EXPIRED",
        )
        self.calls.resume_staged_thread(row["local"]["thread"])
        row["phase"] = "BOOTSTRAP"
        self._verify()
        self.failed = False
        return {
            "schema": "AIP06_STAGED_BOOTSTRAP_RELEASE_V1",
            "scope": SCOPE_HASH,
            "nonce": nonce,
            "identity": copy.deepcopy(row["native"]),
            "financial_ack": False,
            "guard_release": False,
        }

    def finish(self, nonce, binding):
        need(
            not self.failed and nonce in self.nodes and nonce not in self.closed,
            "STAGED_ORIGINAL_EXIT_REQUIRED",
        )
        row = self.nodes[nonce]
        local = row["local"]
        life = self.calls.lifecycle(local["launch"])
        need(
            binding.finished
            and binding.runtime_handle == local["launch"]
            and life
            == {
                "pid": row["native"]["pid"],
                "created": row["native"]["created"],
                "exited": True,
                "exit_code": 0,
            }
            and not self.calls.members(local["job"])
            and self.registry.objects.observe(local["thread"])["exited"] is True,
            "STAGED_NORMAL_EXIT_OR_THREAD_DRAIN_MISSING",
        )
        self.closed.add(nonce)
        row["phase"] = "EXITED"
        return self.verify()
