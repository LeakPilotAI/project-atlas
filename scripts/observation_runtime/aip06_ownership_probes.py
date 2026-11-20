"""Bounded live supervisor/descendant evidence over original guarded providers.

Inert until collect(). No process discovery/adoption, launch, PID-open or
financial authority. A result dictionary is not a retained probe capability.
"""

import copy
import ntpath
import secrets

from app.services.paper_financial_replay import body, digest
from scripts.observation_runtime.aip06_cleanup_providers import StrictProcessCleanup
from scripts.observation_runtime.aip06_harness import LIMITS, SCOPE_HASH, need
from scripts.observation_runtime.aip06_windows_cim import filetime
from scripts.observation_runtime.aip06_windows_process import (
    NativeProcessObserver,
    bounded_observations,
)


class OwnershipProbes:
    CASES = ("supervisor", "unexpected-child")
    MAX_NS = 5 * 10**9

    def __init__(self, port, tables, output):
        self.port, self.tables, self.output = port, tables, output
        self.failed = False
        self.retained = {}
        self.publications = {}
        self.aggregate = port.aggregate
        self.originals = (
            (port.aggregate.controller_handle, port.aggregate.job)
            if port.aggregate is not None
            else None
        )
        self.accounts = copy.deepcopy(port.controller.profile["accounts"])

    def collect(self, case, *, deadline_ns):
        if type(deadline_ns) is not int:
            self.failed = self.port.failed = self.port.guard.failed = True
            raise ValueError("OWNERSHIP_PROBE_ABSOLUTE_BOUND")
        with bounded_observations(deadline_ns):
            return self._collect(case, deadline_ns=deadline_ns)

    def _collect(self, case, *, deadline_ns):
        p = self.port
        self.enumeration = None
        try:
            need(not self.failed and case in self.CASES, "OWNERSHIP_PROBE_HEALTHY_CASE")
            start = p.clock()
            need(
                type(deadline_ns) is int and start < deadline_ns <= start + self.MAX_NS,
                "OWNERSHIP_PROBE_ABSOLUTE_BOUND",
            )
            p.controller.require_ready()
            p.guard.check()
            a = p.aggregate
            need(
                a is not None
                and a is self.aggregate
                and not a.dormant
                and (a.controller_handle, a.job) == self.originals
                and p.controller.profile["accounts"] == self.accounts,
                "OWNERSHIP_PROBE_ORIGINAL_AGGREGATE",
            )
            a._controller()
            for handle, kind in zip(self.originals, ("handle", "job"), strict=True):
                tickets = [k for k, h in a.held if h == handle]
                need(
                    len(tickets) == 1
                    and p.resources.state["resources"].get(tickets[0])
                    == {"owner": p.guard.owner, "kind": kind, "closed": False}
                    and not p.calls.closed(handle),
                    "OWNERSHIP_PROBE_ORIGINAL_HANDLE_RESERVATION",
                )
            supervisor = p.resources.state["owners"][p.guard.owner]
            need(
                body(supervisor) == body(a.controller)
                and p.resources.state["controller"] == p.guard.owner,
                "OWNERSHIP_PROBE_SUPERVISOR_ACCOUNT_OR_OWNER",
            )

            observer = NativeProcessObserver(
                calls=p.calls, cim=p.cim, images=p.pinned_images, clock_ns=p.clock
            )
            observer.parent = a.controller_handle
            actual = observer.observe(a.controller_handle)
            need(
                body(actual) == body(supervisor), "OWNERSHIP_PROBE_SUPERVISOR_IDENTITY"
            )
            expected = {actual["pid"]: actual}
            claims = p.guard.ownership.verify()
            for name, binding in p.guard.ownership.bindings.items():
                if name in p.guard.ownership.finished:
                    continue
                rows = [binding.launch, binding.runtime]
                if binding.descendant_graph is not None:
                    rows.extend(binding.descendant_graph())
                for row in rows:
                    pid = row["pid"]
                    need(
                        pid not in expected or body(expected[pid]) == body(row),
                        "OWNERSHIP_PROBE_CONFLICTING_BIRTH",
                    )
                    expected[pid] = row
            need(
                {r["pid"] for r in claims} == set(expected) - {actual["pid"]}
                and len(expected) <= LIMITS["processes"],
                "OWNERSHIP_PROBE_COMPLETE_ROSTER",
            )
            for pid, row in expected.items():
                if pid != actual["pid"]:
                    need(
                        row["parent_pid"] in expected
                        and expected[row["parent_pid"]]["created"] <= row["created"],
                        "OWNERSHIP_PROBE_ANCESTRY",
                    )
                    seen, cursor = set(), pid
                    while cursor != actual["pid"]:
                        need(
                            cursor not in seen and cursor in expected,
                            "OWNERSHIP_PROBE_ANCESTRY_CYCLE",
                        )
                        seen.add(cursor)
                        cursor = expected[cursor]["parent_pid"]

            live_before = self._live()
            slots = [
                r for r in live_before.values() if r["kind"] in ("launch", "process")
            ]
            child_owners = {
                digest(row) for pid, row in expected.items() if pid != actual["pid"]
            }
            need(
                all(r["kind"] == "process" for r in slots)
                and len(slots) == len(child_owners)
                and {r["owner"] for r in slots} == child_owners,
                "OWNERSHIP_PROBE_PROCESS_RESERVATION_MISMATCH",
            )
            need(
                all(
                    r["owner"] in {digest(row) for row in expected.values()}
                    for r in live_before.values()
                ),
                "OWNERSHIP_PROBE_RESOURCE_OWNER",
            )
            source_head = p.resources.head
            fields = StrictProcessCleanup.FIELDS
            predicate = " OR ".join(
                f"ProcessId={pid} OR ParentProcessId={pid}" for pid in sorted(expected)
            )
            cut = self.tables.read(
                namespace=r"ROOT\CIMV2",
                query="SELECT "
                + ",".join(fields)
                + " FROM Win32_Process WHERE "
                + predicate,
                fields=fields,
                deadline_ns=deadline_ns,
                maximum=64,
            )
            # Persist attributable diagnostics without exporting an unexpected
            # process's command line, executable path or other private strings.
            self.enumeration = {
                "digest": digest(cut),
                "started_ns": cut.get("started_ns"),
                "finished_ns": cut.get("finished_ns"),
                "complete": cut.get("complete"),
                "identities": [
                    {
                        "pid": r.get("ProcessId"),
                        "parent_pid": r.get("ParentProcessId"),
                        "row_sha256": digest(r),
                    }
                    for r in cut.get("rows", [])
                    if type(r) is dict
                ],
            }
            need(
                cut["complete"] is True
                and cut["error"] is None
                and type(cut["rows"]) is list
                and len(cut["rows"]) <= 64
                and start
                <= cut["started_ns"]
                <= cut["finished_ns"]
                <= p.clock()
                < deadline_ns,
                "OWNERSHIP_PROBE_ENUMERATION_INCOMPLETE_OR_STALE",
            )
            seen = set()
            for row in cut["rows"]:
                need(
                    type(row) is dict and set(row) == set(fields),
                    "OWNERSHIP_PROBE_EXACT_CIM_FIELDS",
                )
                pid = row["ProcessId"]
                need(
                    type(pid) is int and pid not in seen and pid in expected,
                    "OWNERSHIP_PROBE_UNEXPECTED_OR_CONFLICTING_CHILD",
                )
                seen.add(pid)
                want = expected[pid]
                need(
                    row["ParentProcessId"] == want["parent_pid"]
                    and filetime(row["CreationDate"]) // 10 == want["created"] // 10
                    and row["CommandLine"] == want["command_line"]
                    and ntpath.normcase(row["ExecutablePath"])
                    == ntpath.normcase(want["image"]),
                    "OWNERSHIP_PROBE_CIM_ANCESTRY_OR_IDENTITY",
                )
            need(seen == set(expected), "OWNERSHIP_PROBE_MISSING_EXPECTED_PROCESS")
            # Queries can race process exit or a new descendant. Recheck the
            # retained graph, original supervisor and complete native Job last.
            objects = p.protocol.endpoints.ownership_objects(
                p, expected, deadline_ns=deadline_ns
            )
            need(
                p.guard.ownership.verify() == claims and self._live() == live_before,
                "OWNERSHIP_PROBE_RESOURCE_OR_GRAPH_CHANGED",
            )
            need(
                body(observer.observe(a.controller_handle)) == body(supervisor),
                "OWNERSHIP_PROBE_SUPERVISOR_CHANGED",
            )
            usage = a.observe()
            need(
                set(usage["members"]) == set(expected) and p.clock() < deadline_ns,
                "OWNERSHIP_PROBE_JOB_OR_DEADLINE",
            )
            value = {
                "schema": "AIP06_OWNERSHIP_PROBE_V1",
                "scope": SCOPE_HASH,
                "session": p.controller.profile["session"],
                "nonce": secrets.token_hex(16),
                "case": case,
                "domain": "DISPOSABLE",
                "supervisor": actual,
                "descendants": [
                    expected[pid] for pid in sorted(expected) if pid != actual["pid"]
                ],
                "accounts": digest(p.controller.profile["accounts"]),
                "source_head": source_head,
                "head": p.resources.head,
                "started_ns": start,
                "finished_ns": p.clock(),
                "enumeration": digest(cut),
                "objects": objects,
                "usage": usage,
                "native_acceptance": False,
                "financial_ack": False,
            }
            receipt = self.output.append(value)
            need(
                self._live() == live_before
                and p.controller.profile["accounts"] == self.accounts
                and p.clock() < deadline_ns,
                "OWNERSHIP_PROBE_PUBLICATION_LATE_OR_RESOURCE_CHANGED",
            )
            # Native evidence publication itself advances the journal. Keep
            # its post-write cut separately from the observation's own head.
            self.publications[value["nonce"]] = {
                "head": p.resources.head,
                "receipt": copy.deepcopy(receipt),
                "output_head": getattr(self.output, "head", None),
            }
            self.retained[value["nonce"]] = copy.deepcopy(value)
            return copy.deepcopy(value)
        except BaseException as error:
            self.failed = p.failed = p.guard.failed = True
            reason = (
                str(error)
                if type(error) is ValueError
                and str(error).startswith("OWNERSHIP_PROBE_")
                else type(error).__name__
            )
            self.failure = {
                "schema": "AIP06_OWNERSHIP_PROBE_FAILURE_V1",
                "scope": SCOPE_HASH,
                "case": case,
                "at_ns": p.clock(),
                "reason": reason,
                "session": p.controller.profile["session"],
                "enumeration": getattr(self, "enumeration", None),
                "native_acceptance": False,
                "financial_ack": False,
            }
            try:
                self.output.append(self.failure)
            except BaseException:
                # The original refusal remains primary. An output failure is
                # not an ACK and cannot undo the uncertainty latch.
                self.failure["output_failed"] = True
            raise

    def _live(self):
        self.port.resources.read()
        return {
            k: v
            for k, v in self.port.resources.state["resources"].items()
            if not v["closed"]
        }

    def verify(self, value):
        """Freshness/producer continuity only; never a replacement for collect."""
        p = self.port
        try:
            need(
                not self.failed
                and not p.failed
                and not p.guard.failed
                and type(value) is dict
                and self.retained.get(value.get("nonce")) == value
                and value["session"] == p.controller.profile["session"]
                and value["accounts"] == digest(p.controller.profile["accounts"])
                and self.publications[value["nonce"]]["head"]
                == p.resources.read()["head"]
                and self.publications[value["nonce"]]["output_head"]
                == getattr(self.output, "head", None)
                and value["finished_ns"]
                <= p.clock()
                < value["started_ns"] + self.MAX_NS,
                "OWNERSHIP_PROBE_UNRETAINED_CHANGED_STALE_OR_ACCOUNT",
            )
            return copy.deepcopy(value)
        except BaseException:
            self.failed = p.failed = p.guard.failed = True
            raise
