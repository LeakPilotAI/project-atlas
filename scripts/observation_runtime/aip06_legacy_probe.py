"""Versioned legacy projection from actual retained guarded sessions.

Pure construction; no launch except run_case behind the existing guard. No
externally supplied dictionary is accepted as an ownership/exit capability.
"""

import copy
import hashlib
import ntpath
import secrets

from app.services.paper_financial_replay import strict
from scripts.observation_runtime.aip06_harness import BASE, SCOPE_HASH, need

CASES = ("direct-worker",)


class LegacyProbeRunner:
    def __init__(self, controller, output):
        self.controller, self.output = controller, output
        self.runs = {}
        self.failed = False

    def run_case(self, case):
        c = self.controller
        c.require_ready()
        g = c.guard
        p = c.process_port
        need(
            not self.failed and case in CASES,
            "LEGACY_CASE_REQUIRES_SUPPORTED_RETAINED_SOURCE",
        )
        target = c.profile["targets"].get("query")
        expected = ntpath.join(
            ntpath.dirname(ntpath.dirname(BASE)),
            "scripts",
            "observation_runtime",
            "aip06_legacy_entry.py",
        )
        need(
            target == expected and target in c.profile["source_pins"],
            "EXACT_GUARDED_LEGACY_SOURCE_REQUIRED",
        )
        c.verify_source(target)
        nonce = secrets.token_hex(16)
        started = c.clock()
        child = None
        argv = [p.executable, "-B", target, "--case", case, "--nonce", nonce]
        request = {
            "schema": "AIP06_PROBE_CLOSE_V1",
            "scope": SCOPE_HASH,
            "case": case,
            "nonce": nonce,
        }
        try:
            child = g.spawn(argv, env={"ATLAS_SYNTHETIC_STOP_NONCE": nonce})
            identity = child.identity()
            bound = g.ownership.bindings["query"]
            claims = bound.verify()
            stdout, stderr = p.communicate(
                child.child, request, timeout=6, maximum_bytes=65536
            )
            need(
                stderr == ""
                and p.returncode(child.child) == 0
                and len(stdout.encode()) <= 65536,
                "PROBE_BOUNDED_NORMAL_RESULT",
            )
            lines = stdout.splitlines()
            need(len(lines) == 1, "EXACT_ONE_PROBE_READY_RECORD")
            ready = strict(lines[0])
            expected_ready = {
                "schema": "AIP06_LEGACY_READY_V1",
                "scope": SCOPE_HASH,
                "case": case,
                "nonce": nonce,
                "pid": identity["pid"],
                "created": identity["created"],
                "image": identity["image"],
                "role": "acceptance_worker",
            }
            need(
                ready == expected_ready, "PROBE_READY_NATIVE_IDENTITY_OR_CASE_MISMATCH"
            )
            # Capture original terminal evidence BEFORE close invalidates handles.
            exit_rows = {
                "parent": bound.api.observe(bound.parent_handle),
                "worker": bound.api.lifecycle(bound.runtime_handle),
                "members": sorted(bound.api.members()),
            }
            child.close()
            need(
                bound.finished
                and child.closed
                and p.resources_closed(child.child, child.keys)
                and p.all_members() == set(),
                "PROBE_ORIGINAL_EXIT_AND_RELEASE_INCOMPLETE",
            )
            value = {
                "case": case,
                "ready": ready,
                "claims": claims,
                "exit": {"normal_exit": True, "job_empty": True},
                "cleanup": {"handles_closed": True, "job_members": []},
                "refusal": None,
                "source": {
                    "schema": "AIP06_RETAINED_PROBE_SOURCE_V1",
                    "scope": SCOPE_HASH,
                    "session": c.profile["session"],
                    "nonce": nonce,
                    "argv": argv,
                    "target_sha256": c.profile["source_pins"][target],
                    "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
                    "started_ns": started,
                    "finished_ns": c.clock(),
                    "exit_rows": exit_rows,
                },
            }
            # The verifier requires this exact in-memory session plus current
            # close evidence; JSON cannot manufacture a retained capability.
            self.runs[nonce] = {
                "value": copy.deepcopy(value),
                "child": child,
                "binding": bound,
                "verified": False,
            }
            self.output.append(
                {"schema": "AIP06_RETAINED_PROBE_RESULT_V1", "value": value}
            )
            self.verify(value)
            return copy.deepcopy(value)
        except BaseException:
            self.failed = True
            if child is not None and not child.closed:
                p.refuse_current_launch()
            raise

    def verify(self, value):
        try:
            return self._verify(value)
        except BaseException:
            self.failed = True
            raise

    def _verify(self, value):
        c = self.controller
        c.require_ready()
        p = c.process_port
        need(
            not self.failed
            and type(value) is dict
            and set(value)
            == {"case", "ready", "claims", "exit", "cleanup", "refusal", "source"},
            "EXACT_RETAINED_PROBE_RESULT_REQUIRED",
        )
        source = value["source"]
        nonce = source.get("nonce")
        run = self.runs.get(nonce)
        need(
            run is not None
            and value == run["value"]
            and source["scope"] == SCOPE_HASH
            and source["session"] == c.profile["session"]
            and source["schema"] == "AIP06_RETAINED_PROBE_SOURCE_V1"
            and value["case"] in CASES
            and 0 <= c.clock() - source["started_ns"] <= 180 * 10**9,
            "PROBE_UNRETAINED_CHANGED_OR_STALE_RESULT",
        )
        child, bound = run["child"], run["binding"]
        row = source["exit_rows"]
        need(
            bound.finished
            and not bound.refused
            and child.closed
            and row["parent"] == bound.parent
            and row["worker"]
            == {
                "pid": bound.runtime["pid"],
                "created": bound.runtime["created"],
                "exited": True,
                "exit_code": 0,
            }
            and row["members"] == []
            and p.resources_closed(child.child, child.keys)
            and p.all_members() == set(),
            "PROBE_RETAINED_TERMINAL_AND_HANDLE_PROOF",
        )
        need(
            value["ready"]["pid"] == bound.runtime["pid"]
            and value["ready"]["created"] == bound.runtime["created"]
            and value["ready"]["nonce"] == nonce
            and value["ready"]["role"] == bound.request.role == "acceptance_worker"
            and value["claims"]
            == [
                {
                    "pid": bound.runtime["pid"],
                    "created": bound.runtime["created"],
                    "image": bound.runtime["image"],
                }
            ],
            "PROBE_CLAIMS_CHANGED",
        )
        run["verified"] = True
        return {"verified": True, "native_acceptance": False, "financial_ack": False}
