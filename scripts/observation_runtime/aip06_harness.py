"""Inert AIP-06 disposable harness contracts; no launcher or financial authority.

Ports supply retained native observations in a separately approved future run.
Offline ports prove logic only. No default filesystem, process, Job or transport
port is provided, and this module never imports a runtime or executes a command.
"""

import copy
import ntpath
from decimal import Decimal
from threading import RLock
from types import MappingProxyType

from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import (
    body,
    digest,
    replay_verified_events,
    strict,
)

from scripts.observation_runtime.launch_ownership import (
    RetainedLaunchBinding,
    identity,
)
from scripts.observation_runtime.native_fixture_budget import reserve_budget

BASE = r"D:\Work\Project Atlas\logs\diagnostics"
NAMES = {
    "E": "aip06-native-v1-20261104",
    "P": "perp-order-custody-aip06-v1-20261104",
    "Q": "qd-auto-runtime-aip06-v1-20261104",
    "F": "qd-fs3-report-projection-aip06-v1-20261104",
    "N": "qd-personal-pipeline-aip06-v1-20261104",
    "T": "qd-owned-stop-timing-aip06-v1-20261104",
    "L": "qd-v5-launch-ownership-aip06-v1-20261104",
    **{f"S{i}": "qd-personal-pipeline-owned-" + str(i) * 32 for i in (1, 2, 3)},
}
ROOTS = MappingProxyType({key: BASE + "\\" + value for key, value in NAMES.items()})
LIMITS = MappingProxyType(
    {
        "seconds": 600,
        "work_seconds": 540,
        "entries": 8192,
        "bytes": 256 * 1024**2,
        "stop_entries": 512,
        "stop_bytes": 32 * 1024**2,
        "processes": 8,
        "private_bytes": 512 * 1024**2,
        "child_private_bytes": 256 * 1024**2,
        "cpu_ns": 120 * 10**9,
    }
)
SCOPE = {
    "schema": "AIP06_DISPOSABLE_HARNESS_V1",
    "roots": dict(ROOTS),
    "limits": dict(LIMITS),
    "execution_domain": "DISPOSABLE",
    "native_authority": False,
}
SCOPE_HASH = digest(SCOPE)


class HarnessRefused(ValueError):
    pass


def need(condition, reason):
    if not condition:
        raise HarnessRefused(reason)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def copied(value):
    return copy.deepcopy(value)


def path_for(alias, *parts):
    """Exact Windows lexical boundary, independent of the test host's OS."""
    need(type(alias) is str and alias in ROOTS, "DECLARED_ROOT_REQUIRED")
    for part in parts:
        need(
            type(part) is str
            and part not in ("", ".", "..")
            and not part.endswith((".", " "))
            and not any(c in part for c in '\\/:\x00*?<>|"')
            and part.split(".")[0].upper()
            not in {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10)),
            },
            "SINGLE_SAFE_COMPONENT_REQUIRED",
        )
    return ntpath.join(ROOTS[alias], *parts)


class FixturePaths:
    """Native metadata/handle observations come from an explicit port, not JSON.

    port.chain returns drive-to-parent records under retained directory handles;
    port.inspect returns a root record, or None only after a successful query.
    The port must raise on inaccessible/unknown observations. No create/delete
    method exists here. Root publication must use create-new and bind afterward.
    """

    def __init__(self, port):
        need(port is not None, "FILESYSTEM_OBSERVER_REQUIRED")
        self.port, self.bound, self.slots = port, {}, set()

    def _record(self, row, path):
        need(
            type(row) is dict
            and set(row) == {"path", "id", "parent_id", "kind", "reparse", "links"}
            and row["path"] == path
            and row["kind"] == "directory"
            and row["reparse"] is False
            and type(row["links"]) is int
            and row["links"] == 1
            and type(row["id"]) is list
            and len(row["id"]) == 3
            and all(integer(n) for n in row["id"]),
            "NATIVE_DIRECTORY_IDENTITY_REQUIRED",
        )

    def parent(self):
        expected, value = [], "D:\\"
        expected.append(value)
        for component in BASE[3:].split("\\"):
            value = ntpath.join(value, component)
            expected.append(value)
        rows = self.port.chain(BASE)
        need(
            type(rows) is list and len(rows) == len(expected),
            "COMPLETE_ANCESTRY_REQUIRED",
        )
        for index, (row, path) in enumerate(zip(rows, expected, strict=True)):
            self._record(row, path)
            if index:
                need(
                    row["parent_id"] == rows[index - 1]["id"],
                    "DIRECTORY_ANCESTRY_CHANGED",
                )
        need(
            len({tuple(r["id"]) for r in rows}) == len(rows), "DIRECTORY_ALIAS_REFUSED"
        )
        return rows

    def prepare(self, alias):
        path = path_for(alias)
        parents = self.parent()
        need(
            alias not in self.bound and self.port.inspect(path) is None,
            "NO_FIXTURE_ADOPTION",
        )
        return {"alias": alias, "path": path, "parent": copied(parents)}

    def bind_created(self, intent):
        need(
            type(intent) is dict and set(intent) == {"alias", "path", "parent"},
            "ROOT_INTENT_REQUIRED",
        )
        alias = intent["alias"]
        need(
            intent["path"] == path_for(alias) and alias not in self.bound,
            "CREATE_NEW_ROOT_REQUIRED",
        )
        need(self.parent() == intent["parent"], "PARENT_CHANGED_DURING_CREATION")
        row = self.port.inspect(intent["path"])
        self._record(row, intent["path"])
        need(
            row["parent_id"] == intent["parent"][-1]["id"]
            and row["id"] not in [r["id"] for r in self.bound.values()],
            "ROOT_IDENTITY_CONFLICT",
        )
        self.bound[alias] = copied(row)
        return copied(row)

    def verify(self, alias, *parts, existing_id=None):
        path = path_for(alias, *parts)
        self.parent()
        need(
            alias in self.bound
            and self.port.inspect(ROOTS[alias]) == self.bound[alias],
            "ROOT_REPLACED",
        )
        parent = self.bound[alias]
        for index, _ in enumerate(parts[:-1]):
            row = self.port.inspect(path_for(alias, *parts[: index + 1]))
            self._record(row, path_for(alias, *parts[: index + 1]))
            need(row["parent_id"] == parent["id"], "DESCENDANT_PARENT_CONFLICT")
            parent = row
        if parts:
            leaf = self.port.inspect(path)
            if leaf is None:
                need(existing_id is None, "MISSING_BOUND_RESOURCE")
            else:
                need(
                    type(leaf) is dict
                    and set(leaf)
                    == {"path", "id", "parent_id", "kind", "reparse", "links"}
                    and leaf["path"] == path
                    and leaf["parent_id"] == parent["id"]
                    and leaf["id"] == existing_id
                    and existing_id is not None
                    and type(leaf["id"]) is list
                    and len(leaf["id"]) == 3
                    and all(integer(n) for n in leaf["id"])
                    and leaf["kind"] in ("file", "directory")
                    and leaf["reparse"] is False
                    and type(leaf["links"]) is int
                    and leaf["links"] == 1,
                    "FOREIGN_OR_LINKED_RESOURCE",
                )
        return path  # Caller retains native parent handles across the effect.

    def stop_slot(self, sample):
        need(
            type(sample) is int and sample in (1, 2, 3) and sample not in self.slots,
            "FIXED_STOP_SLOT_ONCE_ONLY",
        )
        alias = f"S{sample}"
        intent = self.prepare(alias)
        self.slots.add(sample)  # Failure never silently recycles an attempted slot.
        return intent


class SharedResources:
    """One lock + append/readback journal for all parent/child allocations.

    Journal port append(before_head,event) must CAS/flush and read returns the
    entire immutable chain. There is no default port or old-grant adoption.
    Charges precede effects and never refund after failure/release/deletion.
    Whole matching history rollback needs an independently held expected head.
    """

    def __init__(self, journal, *, clock_ns, expected_head=None):
        need(
            journal is not None and callable(clock_ns),
            "EXPLICIT_JOURNAL_AND_CLOCK_REQUIRED",
        )
        self.journal, self.clock = journal, clock_ns
        self.lock, self.uncertain = RLock(), False
        rows = journal.read()
        need(
            type(rows) is list and len(rows) <= LIMITS["entries"],
            "BOUNDED_JOURNAL_REQUIRED",
        )
        need(not rows or expected_head is not None, "RECOVERY_EXPECTED_HEAD_REQUIRED")
        self._recovered = bool(rows)
        self._rows = []
        self._state = {
            "owners": {},
            "resources": {},
            "stops": {},
            "controller": None,
            "entries": 0,
            "charged_bytes": 0,
            "started_ns": None,
            "last_ns": None,
            "cpu_ns": 0,
            "memory": {},
            "mode": "WORK",
        }
        for row in rows:
            self._apply(row)
        if expected_head is not None:
            need(self.head == expected_head, "JOURNAL_ROLLBACK_OR_CONFLICT")
        self._fresh()

    @property
    def state(self):
        return copied(self._state)

    @property
    def recovered(self):
        return self._recovered

    @property
    def head(self):
        return digest(self._rows[-1]) if self._rows else SCOPE_HASH

    def _fresh(self, *, stop=False):
        need(not self.uncertain, "JOURNAL_UNKNOWN")
        now = self.clock()
        need(integer(now), "MONOTONIC_INTEGER_REQUIRED")
        if self._state["last_ns"] is not None:
            need(now >= self._state["last_ns"], "CLOCK_ROLLBACK")
            limit = (
                LIMITS["seconds"]
                if stop or self._state["mode"] == "STOP"
                else LIMITS["work_seconds"]
            )
            need(now - self._state["started_ns"] <= limit * 10**9, "HARNESS_DEADLINE")
        return now

    def _apply(self, row):
        need(
            type(row) is dict
            and set(row) == {"scope", "sequence", "parent", "at_ns", "state"}
            and row["scope"] == SCOPE_HASH
            and type(row["sequence"]) is int
            and row["sequence"] == len(self._rows) + 1
            and row["parent"] == self.head,
            "JOURNAL_CHAIN_CONFLICT",
        )
        state = row["state"]
        need(
            type(state) is dict
            and set(state) == set(self._state)
            and integer(row["at_ns"])
            and state["last_ns"] == row["at_ns"]
            and integer(state["started_ns"])
            and state["started_ns"] <= row["at_ns"]
            and state["mode"] in ("WORK", "STOP")
            and integer(state["entries"])
            and integer(state["charged_bytes"])
            and state["entries"] >= self._state["entries"]
            and state["charged_bytes"] >= self._state["charged_bytes"]
            and state["entries"] <= LIMITS["entries"]
            and state["charged_bytes"] <= LIMITS["bytes"]
            and integer(state["cpu_ns"])
            and self._state["cpu_ns"] <= state["cpu_ns"] <= LIMITS["cpu_ns"],
            "JOURNAL_STATE_INVALID",
        )
        if self._rows:
            need(
                state["started_ns"] == self._state["started_ns"]
                and state["controller"] == self._state["controller"]
                and row["at_ns"] >= self._state["last_ns"]
                and not (self._state["mode"] == "STOP" and state["mode"] != "STOP")
                and set(self._state["owners"]) <= set(state["owners"])
                and set(self._state["resources"]) <= set(state["resources"])
                and set(self._state["stops"]) <= set(state["stops"]),
                "JOURNAL_REGRESSION",
            )
            for key, value in self._state["owners"].items():
                need(state["owners"][key] == value, "OWNER_REBOUND")
            for key, value in self._state["resources"].items():
                candidate = state["resources"][key]
                adopted = (
                    value["kind"] == "launch"
                    and candidate["kind"] == "process"
                    and not value["closed"]
                    and not candidate["closed"]
                )
                need(
                    (
                        adopted
                        or candidate["owner"] == value["owner"]
                        and candidate["kind"] == value["kind"]
                    )
                    and not (value["closed"] and candidate != value),
                    "RESOURCE_REBOUND_OR_REOPENED",
                )
            for key, value in self._state["stops"].items():
                candidate = state["stops"][key]
                need(
                    candidate["request"] == value["request"]
                    and not (value["state"] == "FAILED" and candidate != value)
                    and not (
                        value["state"] == "CLOSED" and candidate["state"] == "PENDING"
                    ),
                    "STOP_REPLAY_OR_RESET",
                )
        need(
            type(state["owners"]) is dict
            and type(state["resources"]) is dict
            and type(state["memory"]) is dict,
            "JOURNAL_MAPS_REQUIRED",
        )
        need(state["controller"] in state["owners"], "CONTROLLER_REQUIRED")
        need(
            type(state["stops"]) is dict
            and all(
                type(k) is str
                and k
                and type(v) is dict
                and set(v) == {"request", "state"}
                and type(v["request"]) is str
                and len(v["request"]) == 64
                and v["state"] in ("PENDING", "CLOSED", "FAILED")
                for k, v in state["stops"].items()
            ),
            "STOP_HISTORY_REQUIRED",
        )
        for key, value in state["owners"].items():
            need(type(key) is str and key == digest(value), "OWNER_IDENTITY_REQUIRED")
            need(type(value.get("file_id")) is list, "SERIALIZED_IMAGE_ID_REQUIRED")
            identity({**value, "file_id": tuple(value["file_id"])})
        for key, value in state["resources"].items():
            need(
                type(key) is str
                and key
                and type(value) is dict
                and set(value) == {"owner", "kind", "closed"}
                and value["owner"] in state["owners"]
                and type(value["closed"]) is bool
                and value["kind"]
                in (
                    "file",
                    "directory",
                    "process",
                    "launch",
                    "pipe",
                    "handle",
                    "job",
                    "thread",
                    "image",
                ),
                "RESOURCE_OWNER_REQUIRED",
            )
        need(
            1
            + sum(
                not r["closed"] and r["kind"] in ("process", "launch")
                for r in state["resources"].values()
            )
            <= LIMITS["processes"],
            "PROCESS_LIMIT",
        )
        need(
            set(state["memory"]) <= set(state["owners"])
            and all(
                integer(n)
                and n
                <= (
                    LIMITS["private_bytes"]
                    if k == state["controller"]
                    else LIMITS["child_private_bytes"]
                )
                for k, n in state["memory"].items()
            )
            and sum(state["memory"].values()) <= LIMITS["private_bytes"],
            "MEMORY_LIMIT",
        )
        self._state = copied(state)
        self._rows.append(copied(row))

    def _commit(self, state, *, cleanup=False):
        now = self._fresh(stop=cleanup or state["mode"] == "STOP")
        state["started_ns"] = (
            now if state["started_ns"] is None else state["started_ns"]
        )
        state["last_ns"] = now
        # The journal itself consumes a create-new record and its allocated
        # space. Charge conservatively before its append, including metadata.
        work = state["mode"] == "WORK" and not cleanup
        encoded_bound = len(body(state).encode()) + 4096
        state.update(
            reserve_budget(
                {k: state[k] for k in ("entries", "charged_bytes")},
                entries=1,
                size=encoded_bound,
                unit=4096,
                max_entries=LIMITS["entries"] - (LIMITS["stop_entries"] if work else 0),
                max_bytes=LIMITS["bytes"] - (LIMITS["stop_bytes"] if work else 0),
            )
        )
        event = {
            "scope": SCOPE_HASH,
            "sequence": len(self._rows) + 1,
            "parent": self.head,
            "at_ns": now,
            "state": copied(state),
        }
        # Validate before writing; restore state even if validation refuses.
        old, rows = self._state, self._rows
        self._state, self._rows = copied(old), copied(rows)
        try:
            self._apply(event)
        finally:
            self._state, self._rows = old, rows
        self.uncertain = True  # Lost append/ACK cannot authorize another effect.
        self.journal.append(self.head, copied(event))
        need(
            self.journal.read() == [*self._rows, event],
            "DURABLE_RESERVATION_READBACK_REQUIRED",
        )
        need(
            self.journal.receipt()
            == {"head": digest(event), "owner": state["controller"], "closed": True},
            "JOURNAL_HANDLE_RELEASE_UNVERIFIED",
        )
        self._apply(event)
        self.uncertain = False
        return self.head

    def register_owner(self, observed, *, controller=False, cleanup=False):
        identity(observed)
        need(
            set(observed)
            == {
                "pid",
                "created",
                "image",
                "file_id",
                "sha256",
                "command_line",
                "parent_pid",
            }
            and integer(observed["parent_pid"], 5)
            and type(observed["command_line"]) is str
            and 0 < len(observed["command_line"]) < 32767,
            "EXACT_PROCESS_OBSERVATION_REQUIRED",
        )
        observed = strict(body(observed))
        with self.lock:
            need(
                not self.recovered or cleanup is True,
                "RECOVERY_IS_READ_OR_CLEANUP_ONLY",
            )
            self._fresh(stop=cleanup)
            need(self._state["mode"] == "WORK" or cleanup is True, "CLEANUP_ONLY")
            key = digest(observed)
            need(
                not any(
                    r["pid"] == observed["pid"] and r != observed
                    for r in self._state["owners"].values()
                ),
                "PID_REUSE_OR_OWNER_CONFLICT",
            )
            if key in self._state["owners"]:
                return key
            state = copied(self._state)
            state["owners"][key] = copied(observed)
            if state["controller"] is None:
                need(controller is True, "CONTROLLER_MUST_BIND_FIRST")
                state["controller"] = key
            else:
                need(controller is False, "ONE_CONTROLLER_ONLY")
            self._commit(state, cleanup=cleanup)
            return key

    def reserve(self, owner, key, kind, *, entries=0, size=0, unit=4096, cleanup=False):
        with self.lock:
            need(
                not self.recovered or cleanup is True,
                "RECOVERY_IS_READ_OR_CLEANUP_ONLY",
            )
            self._fresh(stop=cleanup)
            need(
                not cleanup
                or self._state["mode"] == "STOP"
                or any(v["state"] == "PENDING" for v in self._state["stops"].values()),
                "NO_UNSCOPED_CLEANUP_RESERVATION",
            )
            need(self._state["mode"] == "WORK" or cleanup is True, "CLEANUP_ONLY")
            need(
                owner in self._state["owners"]
                and type(key) is str
                and 0 < len(key) <= 256
                and key not in self._state["resources"],
                "UNIQUE_DECLARED_RESOURCE_REQUIRED",
            )
            state = copied(self._state)
            if kind in ("file", "directory"):
                work = state["mode"] == "WORK" and not cleanup
                charged = reserve_budget(
                    {k: state[k] for k in ("entries", "charged_bytes")},
                    entries=entries,
                    size=size,
                    unit=unit,
                    max_entries=LIMITS["entries"]
                    - (LIMITS["stop_entries"] if work else 0),
                    max_bytes=LIMITS["bytes"] - (LIMITS["stop_bytes"] if work else 0),
                )
                state.update(charged)
            else:
                need(
                    type(entries) is int
                    and entries == 0
                    and type(size) is int
                    and size == 0,
                    "NONFILE_CHARGE_CONFLICT",
                )
            state["resources"][key] = {"owner": owner, "kind": kind, "closed": False}
            return self._commit(state, cleanup=cleanup)

    def charge_write(self, owner, key, *, size, unit=4096, cleanup=False):
        with self.lock:
            need(
                not self.recovered or cleanup is True,
                "RECOVERY_IS_READ_OR_CLEANUP_ONLY",
            )
            need(
                not cleanup
                or self._state["mode"] == "STOP"
                or any(v["state"] == "PENDING" for v in self._state["stops"].values()),
                "NO_UNSCOPED_CLEANUP_WRITE",
            )
            need(self._state["mode"] == "WORK" or cleanup is True, "CLEANUP_ONLY")
            need(
                key in self._state["resources"]
                and self._state["resources"][key]
                == {"owner": owner, "kind": "file", "closed": False},
                "BOUND_OPEN_FILE_REQUIRED",
            )
            state = copied(self._state)
            work = state["mode"] == "WORK" and not cleanup
            state.update(
                reserve_budget(
                    {k: state[k] for k in ("entries", "charged_bytes")},
                    entries=0,
                    size=size,
                    unit=unit,
                    max_entries=LIMITS["entries"]
                    - (LIMITS["stop_entries"] if work else 0),
                    max_bytes=LIMITS["bytes"] - (LIMITS["stop_bytes"] if work else 0),
                )
            )
            return self._commit(state, cleanup=cleanup)

    def bind_reserved_process(
        self, key, parent_owner, binding, handle, *, cleanup=False
    ):
        need(
            type(binding) is RetainedLaunchBinding,
            "RETAINED_LAUNCH_CAPABILITY_REQUIRED",
        )
        binding.verify()
        observed = binding.api.observe(handle)
        need(
            observed in (binding.launch, binding.runtime),
            "EXACT_LAUNCHED_PROCESS_REQUIRED",
        )
        child = self.register_owner(observed, cleanup=cleanup)
        with self.lock:
            need(
                self._state["resources"].get(key)
                == {"owner": parent_owner, "kind": "launch", "closed": False},
                "PRIOR_LAUNCH_RESERVATION_REQUIRED",
            )
            state = copied(self._state)
            state["resources"][key] = {
                "owner": child,
                "kind": "process",
                "closed": False,
            }
            return self._commit(state, cleanup=cleanup)

    def begin_stop(self):
        with self.lock:
            state = copied(self._state)
            state["mode"] = "STOP"
            return self._commit(state, cleanup=True)

    def reserve_stop_request(self, request):
        with self.lock:
            need(not self.recovered, "RECOVERY_CANNOT_RESUME_STOP_SESSION")
            self._fresh()
            need(
                type(request) is dict
                and set(request) == {"scope", "nonce", "worker", "operation_id"}
                and request["scope"] == SCOPE_HASH
                and type(request["nonce"]) is str
                and len(request["nonce"]) == 32
                and all(c in "0123456789abcdef" for c in request["nonce"])
                and type(request["operation_id"]) is str
                and 0 < len(request["operation_id"]) <= 256,
                "EXACT_STOP_REQUEST_REQUIRED",
            )
            worker = digest(request["worker"])
            need(
                worker in self._state["owners"]
                and worker != self._state["controller"]
                and any(
                    r == {"owner": worker, "kind": "process", "closed": False}
                    for r in self._state["resources"].values()
                ),
                "DECLARED_ACTIVE_STOP_WORKER_REQUIRED",
            )
            key = request["operation_id"]
            need(
                self._state["mode"] == "WORK"
                and key not in self._state["stops"]
                and all(v["state"] == "CLOSED" for v in self._state["stops"].values()),
                "STOP_ONCE_ONLY_OR_PRIOR_UNRESOLVED",
            )
            state = copied(self._state)
            state["stops"][key] = {"request": digest(request), "state": "PENDING"}
            return self._commit(state)

    def resolve_stop(self, request, status):
        with self.lock:
            key = request["operation_id"]
            need(
                status in ("CLOSED", "FAILED")
                and key in self._state["stops"]
                and self._state["stops"][key]["request"] == digest(request)
                and self._state["stops"][key]["state"] != "FAILED",
                "STOP_RESOLUTION_CONFLICT",
            )
            state = copied(self._state)
            state["stops"][key]["state"] = status
            return self._commit(state, cleanup=True)

    def close(self, owner, key, *, observer):
        with self.lock:
            self._fresh(stop=True)
            need(
                key in self._state["resources"]
                and self._state["resources"][key]["owner"] == owner,
                "RESOURCE_OWNERSHIP_CONFLICT",
            )
            if self._state["resources"][key]["closed"]:
                need(observer.closed(owner, key) is True, "REPEATED_CLEANUP_CONFLICT")
                return self.head
            need(observer.closed(owner, key) is True, "INDEPENDENT_RELEASE_REQUIRED")
            state = copied(self._state)
            state["resources"][key]["closed"] = True
            return self._commit(state, cleanup=True)

    def usage(self, *, memory, cpu_ns):
        with self.lock:
            active = {self._state["controller"]} | {
                r["owner"]
                for r in self._state["resources"].values()
                if r["kind"] == "process" and not r["closed"]
            }
            need(
                type(memory) is dict and set(memory) == active,
                "COMPLETE_PARENT_CHILD_USAGE_REQUIRED",
            )
            state = copied(self._state)
            state.update(memory=copied(memory), cpu_ns=cpu_ns)
            return self._commit(state, cleanup=True)

    def read(self):
        with self.lock:
            self._fresh(stop=True)
            need(self.journal.read() == self._rows, "EXTERNAL_JOURNAL_CHANGE")
            return {
                "head": self.head,
                "state": copied(self._state),
                "scope": SCOPE_HASH,
            }


class WorkerOwnership:
    """Existing strict retained binding for the actual worker, not a PID list.

    Each binding observes its exact per-launch Job. The independent all_members
    query must equal the union across all declared Jobs; no filtered allowlist.
    """

    def __init__(self, resources, *, all_members):
        need(callable(all_members), "COMPLETE_JOB_OBSERVER_REQUIRED")
        self.resources, self.all_members = resources, all_members
        self.bindings, self.finished = {}, set()
        self.prepared = {}
        self.refused = False

    def prepare(self, name, request, *, parent_owner=None):
        """Reserve process slots BEFORE a native launcher may create/resume it.

        The returned plan is not a startup authority. Future ports also reserve
        each concrete Job/pipe/image/thread handle before its own allocation.
        """
        request.validate()
        need(
            not self.refused
            and name
            in ("financial_worker", "readonly_reader", "race_one", "race_two", "query")
            and name not in self.prepared
            and request.role == "acceptance_worker"
            and request.auxiliary_image is None,
            "DECLARED_PRELAUNCH_REQUIRED",
        )
        parent_owner = parent_owner or self.resources.state["controller"]
        cleanup = self.resources.state["mode"] == "STOP" or any(
            v["state"] == "PENDING" for v in self.resources.state["stops"].values()
        )
        need(
            not cleanup or name in ("readonly_reader", "query"),
            "NO_FINANCIAL_LAUNCH_DURING_CLEANUP",
        )
        slots = [name + ":" + request.nonce + ":launch"]
        if request.topology == "one_redirector":
            slots.append(name + ":" + request.nonce + ":runtime")
        self.prepared[name] = {
            "request": digest(vars(request)),
            "parent": parent_owner,
            "slots": slots,
        }
        try:
            for key in slots:
                self.resources.reserve(parent_owner, key, "launch", cleanup=cleanup)
        except BaseException:
            self.refused = True
            raise
        return copied(self.prepared[name])

    def bind(
        self, name, *, api, request, parent_handle, launch_handle, runtime_handle, ready
    ):
        try:
            return self._bind(
                name,
                api=api,
                request=request,
                parent_handle=parent_handle,
                launch_handle=launch_handle,
                runtime_handle=runtime_handle,
                ready=ready,
            )
        except BaseException:
            self.refused = True
            raise

    def _bind(
        self, name, *, api, request, parent_handle, launch_handle, runtime_handle, ready
    ):
        need(
            not self.refused
            and name
            in ("financial_worker", "readonly_reader", "race_one", "race_two", "query")
            and name not in self.bindings,
            "DECLARED_LAUNCH_ONCE_ONLY",
        )
        need(
            request.role == "acceptance_worker" and request.auxiliary_image is None,
            "EXACT_AIP06_WORKER_ROLE_REQUIRED",
        )
        need(
            name in self.prepared
            and self.prepared[name]["request"] == digest(vars(request)),
            "PRELAUNCH_RESERVATION_REQUIRED",
        )
        permit = self.prepared[name]
        cleanup = self.resources.state["mode"] == "STOP" or any(
            v["state"] == "PENDING" for v in self.resources.state["stops"].values()
        )
        need(
            not cleanup or name in ("readonly_reader", "query"),
            "NO_FINANCIAL_LAUNCH_DURING_CLEANUP",
        )
        bound = RetainedLaunchBinding(api, request, parent_handle, launch_handle)
        need(
            digest(bound.parent) == permit["parent"],
            "RETAINED_PARENT_RESERVATION_MISMATCH",
        )
        rows = bound.bind_runtime(runtime_handle, ready)
        current = {
            r["pid"]
            for key, old in self.bindings.items()
            if key not in self.finished
            for r in old.verify()
        }
        need(not current.intersection(r["pid"] for r in rows), "PROCESS_ADOPTED_TWICE")
        need(
            self.all_members() == current | {r["pid"] for r in rows},
            "GLOBAL_JOB_ROSTER_CONFLICT",
        )
        self.bindings[name] = bound
        handles = (
            [launch_handle]
            if request.topology == "direct"
            else [launch_handle, runtime_handle]
        )
        for key, handle in zip(permit["slots"], handles, strict=True):
            self.resources.bind_reserved_process(
                key, permit["parent"], bound, handle, cleanup=cleanup
            )
        return copied(rows)

    def verify(self):
        try:
            return self._verify()
        except BaseException:
            self.refused = True
            raise

    def _verify(self):
        need(not self.refused, "OWNERSHIP_REFUSAL_LATCHED")
        rows = []
        for name, bound in self.bindings.items():
            if name not in self.finished:
                rows.extend(bound.verify())
        need(
            self.all_members() == {r["pid"] for r in rows},
            "UNEXPECTED_OR_ORPHAN_PROCESS",
        )
        self.resources.read()
        return copied(rows)

    def exit(self, name):
        try:
            return self._exit(name)
        except BaseException:
            self.refused = True
            raise

    def _exit(self, name):
        need(
            name in self.bindings and name not in self.finished,
            "BOUND_LIFETIME_REQUIRED",
        )
        result = self.bindings[name].verify_exit()
        self.finished.add(name)
        self.verify()
        return result  # Handles still retained; caller must close/account them.


class ReservedFixtureEffects:
    """Connect path/identity and durable reservation before an injected effect.

    No default creator/writer. Future native ports must expose only these
    attributed mutations, including their temp/receipt/cache/output writes.
    An exception retains the charge and unresolved resource; never retry/adopt.
    """

    def __init__(self, resources, paths):
        self.resources, self.paths = resources, paths

    def create_root(self, alias, owner, *, creator, cleanup=False):
        intent = self.paths.prepare(alias)
        self.resources.reserve(
            owner, "root:" + alias, "directory", entries=1, cleanup=cleanup
        )
        creator(copied(intent))
        return self.paths.bind_created(intent)

    def create_file(self, alias, parts, owner, key, *, data, writer, cleanup=False):
        need(
            type(parts) is tuple and parts and type(data) is bytes,
            "EXPLICIT_IMMUTABLE_FILE_WRITE_REQUIRED",
        )
        path = self.paths.verify(alias, *parts)
        self.resources.reserve(
            owner, key, "file", entries=1, size=len(data), cleanup=cleanup
        )
        native_id = writer(path, data)  # Native port uses retained parent + create-new.
        self.paths.verify(alias, *parts, existing_id=native_id)
        return {
            "path": path,
            "native_id": copied(native_id),
            "reservation_head": self.resources.head,
        }


def bounded_line(port, *, deadline_ns, clock_ns, maximum_bytes=1024**2):
    """Explicit timeout/size on every pipe read; late/missing results refuse.

    The native port must implement a cancellable deadline; a future independent
    owned controller/Job remains required to contain a broken blocking port.
    """
    now = clock_ns()
    need(
        integer(now)
        and integer(deadline_ns)
        and deadline_ns > now
        and integer(maximum_bytes, 1)
        and maximum_bytes <= 1024**2,
        "BOUNDED_READ_REQUIRED",
    )
    data = port.read_line(timeout=(deadline_ns - now) / 10**9, limit=maximum_bytes)
    finished = clock_ns()
    need(
        integer(finished)
        and now <= finished <= deadline_ns
        and type(data) is bytes
        and 0 < len(data) <= maximum_bytes
        and data.endswith(b"\n")
        and b"\x00" not in data,
        "PIPE_RESULT_MISSING_OVERSIZED_OR_LATE",
    )
    return data


class StopVerification:
    """Whole-window, monotonic, fail-latched Stop/readback verification.

    Native ports must supply fresh retained-handle observations in a later run.
    No collection, process close, native ACK or runtime Stop is executed here.
    All accepted synthetic tests remain labelled OFFLINE; no native PASS method.
    """

    def __init__(
        self, resources, ownership, *, clock_ns, financial_reader, expected_accounts
    ):
        need(
            callable(clock_ns) and financial_reader is not None,
            "EXPLICIT_STOP_PORTS_REQUIRED",
        )
        self.resources, self.ownership = resources, ownership
        self.clock, self.reader = clock_ns, financial_reader
        need(
            type(expected_accounts) is dict
            and set(expected_accounts) == {"QUALITY_DIPS", "HYPERLIQUID"},
            "PINNED_ACCOUNT_SCOPE_REQUIRED",
        )
        self.accounts = copied(expected_accounts)
        self.request, self.started, self.failure, self.result = None, None, None, None

    def begin(self, *, nonce, worker, operation_id):
        need(
            self.failure is None
            and self.request is None
            and type(nonce) is str
            and len(nonce) == 32
            and all(c in "0123456789abcdef" for c in nonce)
            and type(operation_id) is str
            and operation_id,
            "ONE_EXACT_STOP_REQUEST_REQUIRED",
        )
        self.ownership.verify()
        need(
            "financial_worker" in self.ownership.bindings
            and "financial_worker" not in self.ownership.finished
            and self.resources.read()["state"]["mode"] == "WORK",
            "LIVE_ONCE_ONLY_FINANCIAL_WORKER_REQUIRED",
        )
        bound = self.ownership.bindings["financial_worker"]
        need(worker == bound.runtime, "STOP_WORKER_IDENTITY_CONFLICT")
        self.started = self.clock()  # Before Stop reservation/command/report/IPC.
        need(integer(self.started), "MONOTONIC_INTEGER_REQUIRED")
        self.request = {
            "scope": SCOPE_HASH,
            "nonce": nonce,
            "worker": strict(body(worker)),
            "operation_id": operation_id,
        }
        self.resources.reserve_stop_request(self.request)
        return copied(self.request)

    def finish(
        self, *, acknowledgement, drain, socket_cut, process_cut, release_observer
    ):
        need(
            self.request is not None and self.failure is None and self.result is None,
            "ACTIVE_STOP_REQUIRED",
        )
        try:
            need(
                body(acknowledgement) == body(self.request),
                "STOP_ACK_IDENTITY_MISMATCH",
            )
            need(
                type(drain) is dict
                and body(drain)
                == body(
                    {
                        "scope": SCOPE_HASH,
                        "operation_id": self.request["operation_id"],
                        "pending": 0,
                        "unknown": False,
                        "orders": 0,
                    }
                ),
                "COMPLETE_DRAIN_REQUIRED",
            )
            need(
                self.ownership.finished == set(self.ownership.bindings),
                "CHILD_EXIT_UNRESOLVED",
            )
            self.ownership.verify()
            need(
                "readonly_reader" in self.ownership.finished
                and self.reader.observer_identity
                == self.ownership.bindings["readonly_reader"].runtime
                and digest(self.reader.observer_identity)
                != digest(self.request["worker"]),
                "SEPARATE_RETAINED_READER_REQUIRED",
            )
            financial = self.reader.read_committed(copied(self.request))
            need(
                type(financial) is dict
                and set(financial)
                == {
                    "accounts",
                    "acknowledgements",
                    "before_hashes",
                    "after_hashes",
                    "writer_rebind_refused",
                }
                and financial["before_hashes"]
                and financial["before_hashes"] == financial["after_hashes"]
                and financial["writer_rebind_refused"] is True,
                "INDEPENDENT_READONLY_REOPEN_REQUIRED",
            )
            need(
                type(financial["before_hashes"]) is dict
                and all(
                    type(k) is str
                    and type(v) is str
                    and len(v) == 64
                    and all(c in "0123456789abcdef" for c in v)
                    for k, v in financial["before_hashes"].items()
                ),
                "EXACT_REOPEN_HASH_INVENTORY_REQUIRED",
            )
            accounts = financial["accounts"]
            need(
                type(accounts) is dict
                and set(accounts) == {"QUALITY_DIPS", "HYPERLIQUID"},
                "TWO_SEPARATE_ACCOUNTS_REQUIRED",
            )
            cuts = {}
            for lane, currency in (("QUALITY_DIPS", "USD"), ("HYPERLIQUID", "USDC")):
                row = accounts[lane]
                need(
                    self.accounts[lane]
                    == {k: row[k] for k in ("account_id", "manifest", "native_source")},
                    "FINANCIAL_ACCOUNT_SCOPE_SUBSTITUTION",
                )
                need(
                    set(row)
                    == {
                        "account_id",
                        "manifest",
                        "events",
                        "snapshot",
                        "native_source",
                        "source_head",
                    }
                    and type(row["account_id"]) is str
                    and row["account_id"]
                    and row["manifest"]["currency"] == currency,
                    "ACCOUNT_CURRENCY_CONFLICT",
                )
                state, head, _ = replay_verified_events(row["manifest"], row["events"])
                audit_financial_events(row["manifest"], row["events"], row["snapshot"])
                need(
                    head == row["source_head"]
                    and type(row["native_source"]) is list
                    and len(row["native_source"]) == 3
                    and all(integer(v) for v in row["native_source"])
                    and not any(
                        Decimal(p["remaining"]) != 0
                        for p in state["positions"].values()
                    )
                    and Decimal(state.get("reserved_margin", "0")) == 0,
                    "FINAL_NATIVE_FINANCIAL_CUT_REQUIRED",
                )
                cuts[lane] = {
                    "account_id": row["account_id"],
                    "epoch": row["manifest"]["epoch"],
                    "currency": currency,
                    "revision": state["revision"],
                    "head": head,
                    "state_digest": digest(state),
                    "native_source": copied(row["native_source"]),
                }
            need(
                cuts["QUALITY_DIPS"]["account_id"] != cuts["HYPERLIQUID"]["account_id"]
                and cuts["QUALITY_DIPS"]["epoch"] != cuts["HYPERLIQUID"]["epoch"]
                and cuts["QUALITY_DIPS"]["native_source"]
                != cuts["HYPERLIQUID"]["native_source"],
                "ACCOUNT_ALIAS",
            )
            expected = {
                lane: {"source": cut, "projection": cut, "report": cut, "global": cut}
                for lane, cut in cuts.items()
            }
            need(
                body(financial["acknowledgements"]) == body(expected),
                "ACK_CHAIN_READBACK_CONFLICT",
            )
            need(
                type(socket_cut) is dict
                and set(socket_cut) == {"scope", "at_ns", "readers"}
                and socket_cut["scope"] == SCOPE_HASH
                and integer(socket_cut["at_ns"])
                and socket_cut["at_ns"] >= self.started
                and type(socket_cut["readers"]) is dict
                and set(socket_cut["readers"]) == {"CIM", "IP_HELPER", "NETSTAT"}
                and all(
                    type(r) is dict
                    and set(r)
                    == {
                        "complete",
                        "owned_endpoints",
                        "unknown",
                        "started_ns",
                        "finished_ns",
                    }
                    and r["complete"] is True
                    and r["owned_endpoints"] == []
                    and r["unknown"] is False
                    and integer(r["started_ns"])
                    and integer(r["finished_ns"])
                    and self.started
                    <= r["started_ns"]
                    <= r["finished_ns"]
                    <= socket_cut["at_ns"]
                    for r in socket_cut["readers"].values()
                ),
                "THREE_READER_COMPLETE_CLEANUP_REQUIRED",
            )
            need(
                type(process_cut) is dict
                and set(process_cut)
                == {"scope", "started_ns", "at_ns", "survivors", "unknown"}
                and process_cut["scope"] == SCOPE_HASH
                and integer(process_cut["at_ns"])
                and integer(process_cut["started_ns"])
                and socket_cut["at_ns"]
                <= process_cut["started_ns"]
                <= process_cut["at_ns"]
                and process_cut["survivors"] == []
                and process_cut["unknown"] is False,
                "FRESH_STRICT_PROCESS_CUT_REQUIRED",
            )
            snapshot = self.resources.read()
            need(
                set(snapshot["state"]["memory"]) == {snapshot["state"]["controller"]},
                "FINAL_PARENT_CHILD_USAGE_REQUIRED",
            )
            for key, resource in snapshot["state"]["resources"].items():
                need(
                    resource["closed"]
                    and release_observer.closed(resource["owner"], key) is True,
                    "OWNED_RESOURCE_LEAK_OR_UNVERIFIED_RELEASE",
                )
            self.resources.resolve_stop(self.request, "CLOSED")
            snapshot = self.resources.read()
            done = self.clock()
            need(
                integer(done)
                and self.started <= process_cut["at_ns"] <= done
                and done - socket_cut["at_ns"] <= 2 * 10**9
                and all(
                    done - r["started_ns"] <= 2 * 10**9
                    for r in socket_cut["readers"].values()
                )
                and done - self.started <= 8 * 10**9,
                "COMPLETE_STOP_EIGHT_SECONDS_REQUIRED",
            )
            self.result = {
                "schema": "AIP06_SOURCE_STOP_VERIFICATION_V1",
                "scope": SCOPE_HASH,
                "elapsed_ns": done - self.started,
                "cuts": cuts,
                "resources_head": snapshot["head"],
                "source_contract_passed": True,
                "native_acceptance": False,
                "startup_authorized": False,
            }
            return copied(self.result)
        except BaseException as exc:
            self.failure = type(exc).__name__  # No raw sensitive port errors.
            try:
                self.resources.resolve_stop(self.request, "FAILED")
            except BaseException:  # noqa: BLE001 - retain UNKNOWN on interrupted failure recording.
                self.resources.uncertain = True
            raise
