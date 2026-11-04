"""Shared accounting for the journal's own nonrecursive native IO.

Writing a journal event to reserve a handle needed to read that same journal
would recurse. These ephemeral lifetimes therefore live on the SharedResources
object, outside its persistent financial/resource event chain. Storage charges
remain in the original journal commit. This never creates a recovered writer.
"""

import threading
from app.services.paper_financial_replay import digest
from scripts.observation_runtime.aip06_harness import LIMITS, SCOPE_HASH, need


class IntrinsicJournalIO:
    def __init__(self, *, owner, clock_ns, started_ns):
        self.owner, self.clock, self.started = owner, clock_ns, started_ns
        self.serial = 0
        self.live = {}
        self.closed_count = 0
        self.failed = False
        self.head = digest(
            {"scope": SCOPE_HASH, "owner": owner, "started_ns": started_ns}
        )
        self.lock = threading.RLock()
        self.bound = None

    def bind(self, resources):
        need(self.bound is None and not self.live, "INTRINSIC_ACCOUNTING_BIND_ONCE")
        self.bound = resources

    def _fresh(self):
        need(
            not self.failed
            and self.started
            <= self.clock()
            <= self.started + LIMITS["seconds"] * 10**9,
            "INTRINSIC_IO_BOUND_OR_UNKNOWN",
        )
        if self.bound is not None:
            state = self.bound.state
            need(
                state["controller"] in (None, self.owner),
                "INTRINSIC_IO_CONTROLLER_CHANGED",
            )
            cleanup = state["mode"] == "STOP" or any(
                r["state"] == "PENDING" for r in state["stops"].values()
            )
            need(
                cleanup
                or self.clock() <= self.started + LIMITS["work_seconds"] * 10**9,
                "INTRINSIC_IO_WORK_CUTOFF",
            )

    def acquire(self, key):
        with self.lock:
            self._fresh()
            need(key not in self.live and len(self.live) < 16, "INTRINSIC_IO_CAPACITY")
            self.serial += 1
            self.live[key] = {"handle": None, "sequence": self.serial}
            self.head = digest([self.head, "RESERVE", key, self.serial])

    def created(self, key, handle):
        with self.lock:
            need(
                key in self.live
                and self.live[key]["handle"] is None
                and type(handle) is int
                and handle > 0,
                "INTRINSIC_IO_ALLOCATION_IDENTITY",
            )
            need(
                handle not in [r["handle"] for r in self.live.values()],
                "INTRINSIC_HANDLE_REUSE",
            )
            self.live[key]["handle"] = handle
            self.head = digest([self.head, "CREATED", key, handle])

    def no_allocation(self, key):
        with self.lock:
            need(
                self.live.get(key, {}).get("handle", "missing") is None,
                "INTRINSIC_NO_HANDLE_PROOF",
            )
            del self.live[key]
            self.closed_count += 1
            self.head = digest([self.head, "NO_ALLOCATION", key])

    def released(self, key, handle, *, observer):
        with self.lock:
            need(
                key in self.live
                and self.live[key]["handle"] == handle
                and observer.closed(handle) is True,
                "INTRINSIC_IO_RELEASE_UNVERIFIED",
            )
            del self.live[key]
            self.closed_count += 1
            self.head = digest([self.head, "CLOSED", key, handle])

    def quiescent(self):
        with self.lock:
            self._fresh()
            need(
                not self.live and self.serial == self.closed_count,
                "INTRINSIC_NATIVE_RESOURCE_LEAK",
            )
            return {
                "scope": SCOPE_HASH,
                "owner": self.owner,
                "reserved": self.serial,
                "closed": self.closed_count,
                "live": 0,
                "head": self.head,
                "durable_financial_authority": False,
            }
