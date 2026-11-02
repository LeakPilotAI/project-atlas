"""Test-orchestration cleanup only; no launcher, selector or financial authority.

The frozen installed adapter still performs its own native ownership and Stop
verification. This observer must not turn a process exit into socket clearance.
"""

import ipaddress
import json
import math
import re
import subprocess
import time

from scripts.installed_nonfinancial_launcher import read_ready
from scripts.observation_runtime.disposable_host_owner import (
    observe_handle,
    observe_pid,
)


def socket_cleanup(snapshot, *, address, port, stopped_ns, now_ns=None):
    """Assess one fresh, complete CIM observation; never infer a missing PID as 0."""
    result = {
        "accepted": False,
        "reasons": [],
        "matching_rows": [],
        "enumeration_error": None,
    }
    now_ns = time.perf_counter_ns() if now_ns is None else now_ns
    try:
        target = ipaddress.ip_address(address)
        if not target.is_loopback or type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("EXACT_LOOPBACK_ENDPOINT_REQUIRED")
        if type(stopped_ns) is not int or type(now_ns) is not int or stopped_ns <= 0:
            raise ValueError("MONOTONIC_TIMES_REQUIRED")
        required = {
            "schema",
            "protocol",
            "query_port",
            "query_address",
            "started_ticks",
            "finished_ticks",
            "frequency",
            "rows",
            "non_helpers",
            "error",
        }
        if (
            type(snapshot) is not dict
            or not required <= snapshot.keys()
            or snapshot.get("schema") != "QD_SOCKET_CLEANUP_CIM_V1"
            or snapshot.get("protocol") != "TCP"
            or type(snapshot.get("query_port")) is not int
            or snapshot["query_port"] != port
            or ipaddress.ip_address(snapshot.get("query_address")) != target
            or snapshot.get("error") is not None
        ):
            raise ValueError("SOCKET_ENUMERATION_FAILED_OR_INCOMPLETE")
        start, end, frequency = (
            snapshot.get(k) for k in ("started_ticks", "finished_ticks", "frequency")
        )
        if any(type(n) is not int or n <= 0 for n in (start, end, frequency)):
            raise ValueError("SOCKET_ENUMERATION_TIMING_MISSING")
        start_ns, end_ns = start * 10**9 // frequency, end * 10**9 // frequency
        if (
            not stopped_ns <= start_ns <= end_ns <= now_ns
            or now_ns - end_ns > 2 * 10**9
        ):
            raise ValueError("SOCKET_ENUMERATION_STALE_OR_PRESTOP")
        if end_ns - start_ns > 5 * 10**9:
            raise ValueError("SOCKET_ENUMERATION_TOO_SLOW")
        rows = snapshot.get("rows")
        if type(rows) is not list or len(rows) > 1024:
            raise ValueError("SOCKET_ENUMERATION_CAPACITY_OR_TYPE")
        if type(snapshot.get("non_helpers")) is not int or snapshot["non_helpers"] != 0:
            result["reasons"].append("PROCESS_CLEANUP_UNRESOLVED")
        for row in rows:
            if type(row) is not dict or row.get("protocol") != "TCP":
                raise ValueError("SOCKET_ROW_PROTOCOL_MISSING")
            local, remote = (
                ipaddress.ip_address(row["local_address"]),
                ipaddress.ip_address(row["remote_address"]),
            )
            if row.get("family") != local.version or remote.version != local.version:
                raise ValueError("SOCKET_ROW_ADDRESS_FAMILY_MISMATCH")
            if (
                type(row.get("local_port")) is not int
                or row["local_port"] != port
                or type(row.get("remote_port")) is not int
                or not 0 <= row["remote_port"] <= 65535
                or type(row.get("state")) is not int
            ):
                raise ValueError("SOCKET_ROW_ENDPOINT_OR_STATE_MISSING")
            # Include a wildcard/mapped listener that could cover this endpoint.
            # Distinct concrete IPv4/IPv6 endpoints are not silently conflated.
            overlap = local == target or (
                local.version == target.version and local.is_unspecified
            )
            overlap |= (
                local.version == 6
                and target.version == 4
                and (local.is_unspecified or local.ipv4_mapped == target)
            )
            if not overlap:
                continue
            result["matching_rows"].append(dict(row))
            pid = row.get("owner_pid")
            if (
                row.get("owner_present") is not True
                or type(pid) is not int
                or not 0 <= pid <= 0xFFFFFFFF
            ):
                result["reasons"].append("SOCKET_OWNER_UNAVAILABLE")
            if row["state"] == 2:
                result["reasons"].append(
                    "LISTENER_REMAINS_PID_ZERO" if pid == 0 else "LISTENER_REMAINS"
                )
            elif row["state"] not in (1, 11):
                result["reasons"].append("SOCKET_ACTIVE_OR_UNKNOWN_STATE")
        result["accepted"] = not result["reasons"]
    except (ValueError, KeyError, TypeError) as exc:
        result["enumeration_error"] = str(exc)
        result["reasons"].append("SOCKET_ENUMERATION_UNVERIFIED")
    result["reasons"] = list(dict.fromkeys(result["reasons"]))
    return result


class AcceptanceController:
    """Retain exact process ownership and a single Stop attempt per ready cycle.

    This class never starts a process or grants startup permission. Only the
    externally reviewed harness can supply an already-created controller.
    """

    def __init__(self, process, identity):
        if (
            type(identity) is not dict
            or set(identity) != {"pid", "created", "image"}
            or any(
                type(identity[k]) is not int or identity[k] <= 0
                for k in ("pid", "created")
            )
            or type(identity["image"]) is not str
            or not identity["image"]
        ):
            raise ValueError("EXACT_NATIVE_CONTROLLER_IDENTITY_REQUIRED")
        self.process, self.identity = process, dict(identity)
        self.host_id = self.stop_ack = self.stopped_ns = None
        self.stop_attempted = self.refused = self.closed = False
        self.final_result = None
        self._verify(live=True)

    def _verify(self, *, live):
        if self.closed or self.process.pid != self.identity["pid"]:
            raise ValueError("CONTROLLER_IDENTITY_CHANGED_OR_CLOSED")
        if observe_handle(int(self.process._handle)) != self.identity["created"]:
            raise ValueError("CONTROLLER_CREATION_HANDLE_CHANGED")
        if live and (
            self.process.poll() is not None
            or observe_pid(self.process.pid) != self.identity
        ):
            raise ValueError("CONTROLLER_PID_CREATION_OR_IMAGE_CHANGED")

    def ready(self, host_id):
        self._verify(live=True)
        if (
            self.refused
            or self.host_id is not None
            or self.stop_attempted
            or type(host_id) is not str
            or not re.fullmatch("[0-9a-f]{32}", host_id)
        ):
            raise ValueError("CONTROLLER_CYCLE_NOT_ADMITTED")
        self.host_id = host_id

    def stop(self):
        if self.stop_ack is not None:
            return dict(self.stop_ack)  # A later audit failure cannot resend Stop.
        if self.stop_attempted or self.host_id is None:
            raise ValueError("CONTROLLER_STOP_UNKNOWN_NO_RETRY")
        self._verify(live=True)
        self.stop_attempted = True  # Before the first possible pipe effect.
        started = time.perf_counter()
        try:
            self.process.stdin.write(("STOP " + self.host_id + "\n").encode())
            self.process.stdin.flush()
            reply = json.loads(read_ready(self.process, seconds=8))
            elapsed = time.perf_counter() - started
            seconds = reply.get("seconds")
            if (
                set(reply) != {"closed", "financial_actions", "seconds"}
                or reply.get("closed") is not True
                or type(reply.get("financial_actions")) is not int
                or reply["financial_actions"] != 0
                or type(seconds) not in (int, float)
                or not math.isfinite(seconds)
                or not 0 <= seconds <= 8
                or elapsed > 8
            ):
                raise ValueError("CONTROLLER_STOP_ACK_OR_EIGHT_SECOND_BUDGET_REFUSED")
            # Persist accepted state BEFORE any independent socket enumeration.
            self.stop_ack, self.stopped_ns = dict(reply), time.perf_counter_ns()
            self.host_id = None
            return dict(reply)
        except BaseException:
            self.refused = True
            raise

    def next_cycle(self, snapshot, *, address, port):
        if self.refused or self.stop_ack is None or self.stopped_ns is None:
            raise ValueError("SECOND_OPEN_REQUIRES_VERIFIED_STOP_AND_CLEANUP")
        evidence = socket_cleanup(
            snapshot, address=address, port=port, stopped_ns=self.stopped_ns
        )
        if not evidence["accepted"]:
            self.refused = True
            raise ValueError("SECOND_OPEN_SOCKET_OR_PROCESS_CLEANUP_UNRESOLVED")
        self._verify(live=True)
        self.process.stdin.write(b"NEXT\n")
        self.process.stdin.flush()
        self.stop_ack = self.stopped_ns = None
        self.stop_attempted = False
        return evidence

    def finish(self, *, timeout=12):
        """EOF, reap, then close handles. On timeout retain ownership; never kill."""
        if self.closed:
            return self.final_result
        if type(timeout) not in (int, float) or not 0 < timeout <= 12:
            raise ValueError("BOUNDED_CONTROLLER_DRAIN_REQUIRED")
        self._verify(live=False)
        errors = []
        if self.process.stdin is not None:
            try:
                self.process.stdin.close()
            except OSError as exc:
                errors.append(type(exc).__name__)
            finally:
                self.process.stdin = None
        try:
            stdout, stderr = self.process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.refused = True
            # A live child's original handle must remain available to its owner.
            raise ValueError("CONTROLLER_DRAIN_INCOMPLETE_OWNERSHIP_RETAINED") from None
        if type(self.process.returncode) is not int:
            self.refused = True
            raise ValueError("CONTROLLER_EXIT_CODE_UNAVAILABLE_HANDLE_RETAINED")
        self.final_result = {
            "exit_code": self.process.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "pipe_close_errors": errors,
        }
        # returncode is collected while the creation handle is still valid.
        try:
            for stream in (self.process.stdout, self.process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError as exc:
                        errors.append(type(exc).__name__)
        finally:
            self.process._handle.Close()
            self.closed = True
        self.final_result["accepted"] = (
            self.process.returncode == 0 and not stdout and not stderr and not errors
        )
        return self.final_result
