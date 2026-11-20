"""Small acceptance-only sequencing helpers. No install/financial authority."""

import json
import os
import threading
import time
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit

from scripts.observation_runtime.installed_acceptance_cleanup import socket_cleanup
from scripts.observation_runtime.installed_acceptance_handoff import BrowserWindow
from scripts.observation_runtime.socket_evidence import reconcile


class PreselectionCut:
    """Recheck actual raw observations at dispatch, not cached passing flags."""

    def __init__(
        self, *, address, port, after_ns, packet, monotonic_ns=time.perf_counter_ns
    ):
        self.address, self.port, self.after_ns = address, port, after_ns
        self.packet, self.clock = deepcopy(packet), monotonic_ns
        self.used = False
        self.owner = os.getpid(), threading.get_ident()

    def dispatch(self, action):
        if self.owner != (os.getpid(), threading.get_ident()):
            raise ValueError("EXACT_PRESELECTION_OWNER_REQUIRED")
        if self.used:
            raise ValueError("PRESELECTION_CUT_ALREADY_USED_OR_REFUSED")
        self.used = True  # No repeated effects or revival after a refusal.
        if type(self.packet) is not dict:
            raise ValueError("PRESELECTION_EVIDENCE_MISSING")
        now = self.clock()
        socket = reconcile(
            self.packet.get("observations"),
            address=self.address,
            port=self.port,
            after_ns=self.after_ns,
            now_ns=now,
        )
        process = socket_cleanup(
            self.packet.get("snapshot"),
            address=self.address,
            port=self.port,
            stopped_ns=self.after_ns,
            now_ns=now,
        )
        if not socket["cleanup_clear"] or not process["accepted"]:
            raise ValueError("PRESELECTION_SOCKET_OR_PROCESS_UNRESOLVED")
        # The original strict validators already enforce every query's bounds.
        # Also require the stricter roster cut to follow the complete bundle.
        snapshot = self.packet["snapshot"]
        start = snapshot["started_ticks"] * 10**9 // snapshot["frequency"]
        if start < max(o["finished_ns"] for o in self.packet["observations"]):
            raise ValueError("PRESELECTION_PROCESS_SNAPSHOT_MUST_BE_LAST")
        # Nothing unrelated executes between validation and dispatch.
        return action()


def run_cycle(
    *,
    controller,
    ready,
    expected,
    cycle,
    root,
    domain,
    ready_ns,
    notify,
    diagnose,
    collect,
    final=False,
    monotonic_ns=time.perf_counter_ns,
    sleep=time.sleep,
):
    """READY -> request -> genuine ACK -> diagnostics -> existing Stop/gates.

    The 45 seconds start at the verified READY observation, never at a later
    navigation or diagnostic completion. Native ownership/Stop/next-cycle
    checks stay in the existing AcceptanceController, not in replacements.
    """
    controller.ready(ready["host_id"])
    window = BrowserWindow(
        root=root,
        cycle=cycle,
        ready=ready,
        expected=expected,
        ready_ns=ready_ns,
        domain=domain,
        monotonic_ns=monotonic_ns,
    )
    notify(window.ticket)  # First: no HTTP sweeps or large reports before this.
    ack = window.wait(sleep=sleep)
    diagnostics = diagnose(ready)  # Unrelated work cannot delay ACK processing.
    started_ns = monotonic_ns()
    stopped = controller.stop()
    # Keep the existing ACK-before-audit property even when a later cut refuses.
    # This is an observer receipt, never a new financial publication or replay.
    with (Path(root) / f"cycle-{cycle}-stop-ack.json").open("x") as stream:
        json.dump(
            {
                "domain": domain,
                "cycle": cycle,
                "host_id": ready["host_id"],
                "received_ns": controller.stopped_ns,
                "ack": stopped,
            },
            stream,
        )
    proof = collect(ready, controller.stopped_ns)
    expected_port = urlsplit(ready["url"]).port
    if (
        type(proof) is not dict
        or type(proof.get("port")) is not int
        or proof["port"] != expected_port
    ):
        controller.refused = True
        raise ValueError("CYCLE_CLEANUP_ENDPOINT_SUBSTITUTION")
    process = socket_cleanup(
        proof.get("snapshot"),
        address="127.0.0.1",
        port=proof["port"],
        stopped_ns=controller.stopped_ns,
        now_ns=monotonic_ns(),
    )
    socket = reconcile(
        proof.get("observations"),
        address="127.0.0.1",
        port=proof["port"],
        after_ns=controller.stopped_ns,
        now_ns=monotonic_ns(),
    )
    if not process["accepted"] or not socket["cleanup_clear"]:
        controller.refused = True
        raise ValueError("CYCLE_SOCKET_OR_PROCESS_CLEANUP_UNRESOLVED")
    result = {
        "cycle": cycle,
        "ready": ready,
        "browser": ack,
        "diagnostics": diagnostics,
        "stop": stopped,
        "cleanup": proof,
    }
    if final:
        drained = controller.finish()
        if not drained["accepted"]:
            raise ValueError("FINAL_CONTROLLER_DRAIN_UNRESOLVED")
        result["drain"] = {
            key: value
            for key, value in drained.items()
            if key not in ("stdout", "stderr")
        }
    if monotonic_ns() - started_ns > 8 * 10**9:
        controller.refused = True
        raise ValueError("COMPLETE_STOP_WITH_READBACK_EXCEEDS_EIGHT_SECONDS")
    result["complete_stop_ns"] = monotonic_ns() - started_ns
    if not final:
        controller.next_cycle(
            proof["snapshot"],
            address="127.0.0.1",
            port=proof["port"],
            observations=proof["observations"],
        )
    return result
