"""Original-handle bounded Windows netstat command. Inert until execute.

No synthetic READY/financial ACK: the unmodified system command is identified
while suspended and its original process capability is retained through exit.
"""

import copy
import hashlib
import ntpath
import secrets
from subprocess import list2cmdline

from scripts.observation_runtime.aip06_harness import LIMITS, SCOPE_HASH, need
from scripts.observation_runtime.aip06_windows_process import (
    NativeProcessObserver,
    SuspendedLaunchFailure,
)

NETSTAT = r"C:\Windows\System32\netstat.exe"
ARGS = (NETSTAT, "-ano", "-p", "TCP")


class CommandLifetime:
    """Nonfinancial original command capability, never a bootstrap receipt."""

    def __init__(self, observer, parent, process, argv):
        self.api, self.parent_handle, self.runtime_handle = observer, parent, process
        self.parent = observer.observe(parent)
        self.runtime = observer.observe(process)
        self.command = tuple(argv)
        need(
            self.runtime["command_line"] == list2cmdline(argv)
            and ntpath.normcase(self.runtime["image"]) == ntpath.normcase(argv[0])
            and self.runtime["parent_pid"] == self.parent["pid"]
            and self.runtime["created"] >= self.parent["created"],
            "QUERY_COMMAND_OR_PARENT_MISMATCH",
        )
        self.finished = False
        self.verify()

    def verify(self):
        need(
            not self.finished
            and self.api.observe(self.parent_handle) == self.parent
            and self.api.observe(self.runtime_handle) == self.runtime
            and self.api.members() == {self.runtime["pid"]},
            "QUERY_ORIGINAL_IDENTITY_OR_JOB_CHANGED",
        )
        return copy.deepcopy(self.runtime)

    def exit(self):
        need(
            not self.finished and self.api.observe(self.parent_handle) == self.parent,
            "QUERY_ORIGINAL_PARENT_LOST",
        )
        life = self.api.lifecycle(self.runtime_handle)
        need(
            life
            == {
                "pid": self.runtime["pid"],
                "created": self.runtime["created"],
                "exited": True,
                "exit_code": 0,
            }
            and self.api.members() == set(),
            "QUERY_NORMAL_EXIT_AND_EMPTY_JOB_REQUIRED",
        )
        self.finished = True
        return copy.deepcopy(life)


class NativeQueryExecutor:
    """Serial, prospectively charged system command under the controller root.

    Only the exact four netstat arguments are accepted. No shell, environment
    discovery, fallback executable, PID reopen or unretained timeout kill.
    """

    def __init__(self, port, *, pipes, output):
        self.port, self.calls, self.files = port, port.calls, port.files
        self.clock, self.pipes, self.output = port.clock, pipes, output
        self.active = None
        self.records = []
        self.failed = False
        self.done = set()

    def execute(self, argv, *, timeout, maximum_bytes=65536):
        p = self.port
        r = p.resources
        owner = p.guard.owner
        need(
            not self.failed
            and self.active is None
            and tuple(argv) == ARGS
            and type(timeout) in (int, float)
            and 0 < timeout <= 6
            and type(maximum_bytes) is int
            and 0 < maximum_bytes <= 65536,
            "EXACT_BOUNDED_NETSTAT_QUERY_REQUIRED",
        )
        p.guard.check()
        need(
            p.aggregate is not None
            and not p.aggregate.dormant
            and p.all_members() == set(),
            "QUERY_REQUIRES_DRAINED_FINANCIAL_JOBS",
        )
        pin = p.pinned_images.get(ntpath.normcase(NETSTAT))
        need(
            type(pin) is dict and set(pin) == {"sha256", "file_id"},
            "PINNED_NATIVE_NETSTAT_IMAGE_REQUIRED",
        )
        start = self.clock()
        deadline = min(
            start + int(timeout * 10**9),
            r.state["started_ns"] + LIMITS["seconds"] * 10**9,
        )
        state = {
            "nonce": secrets.token_hex(16),
            "held": [],
            "launch": None,
            "thread": None,
            "job": None,
            "native": None,
            "capability": None,
            "created": False,
            "closed": False,
            "at_ns": start,
            "creation_attempted": False,
            "creation_absent": False,
            "buffers": [bytearray(), bytearray()],
            "oversize_observed": None,
            "reservations": [],
        }
        self.active = state

        def reserve(kind, label):
            key = p.allocations_port.reserve(
                "query:" + state["nonce"] + ":" + label, kind
            )
            state["reservations"].append(key)
            return key

        def alloc(kind, label, operation):
            key = reserve(kind, label)
            try:
                h = operation()
            except BaseException:
                # No returned handle: retain the uncertain prospective slot.
                raise
            state["held"].append((key, h))
            return h

        cleanup = r.state["mode"] == "STOP" or any(
            v["state"] == "PENDING" for v in r.state["stops"].values()
        )
        slot = None
        capacity = "query-output:" + state["nonce"]
        capacity_reserved = False
        result = None
        failure = None
        job = None
        try:
            slot = reserve("launch", "process")
            r.reserve(owner, capacity, "file", size=maximum_bytes, cleanup=cleanup)
            capacity_reserved = True
            image = alloc("image", "image", lambda: self.files.open_image(NETSTAT))
            meta = self.files.describe(image)
            need(
                meta["id"] == list(pin["file_id"])
                and not meta["reparse"]
                and meta["links"] == 1
                and ntpath.normcase(self.files.final_path(image))
                == ntpath.normcase(NETSTAT)
                and hashlib.sha256(self.files.read(image, 32 * 1024**2)).hexdigest()
                == pin["sha256"],
                "QUERY_NATIVE_IMAGE_MISMATCH",
            )
            parent = alloc(
                "handle",
                "parent",
                lambda: self.calls.duplicate(
                    self.calls.current(), self.calls.current()
                ),
            )
            limits = {
                k: LIMITS[k]
                for k in ("processes", "private_bytes", "child_private_bytes", "cpu_ns")
            }
            limits["kill_on_close"] = True
            job = state["job"] = alloc(
                "job",
                "job",
                lambda: self.calls.create_job(
                    "Local\\Atlas-AIP06-Query-" + state["nonce"], limits
                ),
            )
            need(
                self.calls.job_limits(job) == limits
                and self.calls.members(job) == set(),
                "QUERY_CREATE_NEW_JOB_REQUIRED",
            )
            pairs = []
            for i in range(3):
                tickets = [reserve("pipe", str(i) + str(n)) for n in range(2)]
                pair = self.calls.pipe()
                need(len(pair) == 2 and pair[0] != pair[1], "QUERY_DISTINCT_PIPE_ENDS")
                state["held"].extend(zip(tickets, pair, strict=True))
                pairs.append(pair)
            stdin, stdout, stderr = pairs
            # The process and primary thread prospective slots exist first.
            thread_key = reserve("thread", "primary")
            try:
                state["creation_attempted"] = True
                created = self.calls.create_suspended(
                    executable=NETSTAT,
                    argv=list(ARGS),
                    environment={},
                    cwd=ntpath.dirname(NETSTAT),
                    inherit_handles=[stdin[0], stdout[1], stderr[1]],
                    stdin=stdin[0],
                    stdout=stdout[1],
                    stderr=stderr[1],
                )
            except SuspendedLaunchFailure as exc:
                if exc.created is not None:
                    state["launch"], state["thread"], _, _ = exc.created
                    state["native"] = self.calls.native(state["launch"])
                    state["held"].append((thread_key, state["thread"]))
                else:
                    state["creation_absent"] = True
                    p.allocations_port.release(thread_key)
                raise
            state["launch"], state["thread"], pid, tid = created
            state["created"] = True
            state["held"].append((thread_key, state["thread"]))
            state["native"] = native = self.calls.native(state["launch"])
            need(
                native["pid"] == pid and type(tid) is int and tid > 0,
                "QUERY_CREATION_HANDLE_CONFLICT",
            )
            p.aggregate.attach_created(handle=state["launch"], job=job, native=native)
            self.calls.assign(job, state["launch"])
            need(
                self.calls.in_job(state["launch"], job)
                and self.calls.members(job) == {pid},
                "QUERY_ASSIGNMENT_FAILED",
            )

            class DeadlineCim:
                def process(self, pid, *, deadline_ns):
                    return p.cim.process(pid, deadline_ns=min(deadline_ns, deadline))

            observer = NativeProcessObserver(
                calls=self.calls,
                cim=DeadlineCim(),
                images=p.pinned_images,
                clock_ns=self.clock,
            )
            observer.job, observer.parent = job, parent
            capability = state["capability"] = CommandLifetime(
                observer, parent, state["launch"], ARGS
            )
            p.aggregate.bind_query(capability, handle=state["launch"], job=job)

            # Parent copies of child pipe ends close before reading EOF.
            def close(h):
                key = next(k for k, v in state["held"] if v == h)
                self.calls.close(h)
                need(self.calls.closed(h), "QUERY_HANDLE_CLOSE_FAILED")
                p.allocations_port.release(key)
                state["held"].remove((key, h))

            for h in (stdin[0], stdin[1], stdout[1], stderr[1]):
                close(h)
            need(self.clock() < deadline, "QUERY_DEADLINE_BEFORE_RESUME")
            self.calls.resume(state["thread"])
            buffers = state["buffers"]
            eof = [False, False]
            while True:
                need(self.clock() < deadline, "QUERY_TIMEOUT")
                for i, h in enumerate((stdout[0], stderr[0])):
                    if eof[i]:
                        continue
                    try:
                        available = self.pipes.available(h)
                    except OSError as exc:
                        need(
                            getattr(exc, "winerror", None) == 109,
                            "QUERY_PIPE_ENUMERATION_FAILURE",
                        )
                        eof[i] = True
                        continue
                    need(type(available) is int and available >= 0, "QUERY_PIPE_COUNT")
                    if available:
                        if sum(map(len, buffers)) + available > maximum_bytes:
                            state["oversize_observed"] = available
                        need(
                            sum(map(len, buffers)) + available <= maximum_bytes,
                            "QUERY_OUTPUT_CAPACITY",
                        )
                        block = self.pipes.read(h, min(available, 32768))
                        need(
                            type(block) is bytes
                            and 0 < len(block) <= min(available, 32768),
                            "QUERY_READ_COUNT",
                        )
                        buffers[i].extend(block)
                life = self.calls.lifecycle(state["launch"])
                need(
                    life["pid"] == native["pid"]
                    and life["created"] == native["created"],
                    "QUERY_PROCESS_BIRTH_CHANGED",
                )
                p.aggregate.observe()
                if not life["exited"]:
                    capability.verify()
                if life["exited"] and all(eof):
                    break
                self.pipes.pause()
            exited = capability.exit()
            p.aggregate.exited(capability, handle=state["launch"])
            result = {
                "exit_code": exited["exit_code"],
                "stdout": buffers[0].decode("ascii"),
                "stderr": buffers[1].decode("ascii"),
                "identity": copy.deepcopy(capability.runtime),
                "closed": False,
            }
        except BaseException as exc:
            self.failed = True
            failure = exc
        finally:
            # Failure is never a successful query, including a later clean exit.
            cleanup_failure = None
            try:
                end = min(
                    self.clock() + 8 * 10**9,
                    r.state["started_ns"] + LIMITS["seconds"] * 10**9,
                )
                if state["launch"] is not None:
                    life = self.calls.lifecycle(state["launch"])
                    need(
                        state["native"] is not None
                        and life["pid"] == state["native"]["pid"]
                        and life["created"] == state["native"]["created"],
                        "QUERY_ABORT_ORIGINAL_BIRTH_REQUIRED",
                    )
                    members = set() if job is None else self.calls.members(job)
                    if members:
                        # Emergency containment is confined to this create-new,
                        # retained query Job, including an unexpected member.
                        # It is failure cleanup, never adoption or successful exit.
                        self.calls.terminate_owned_job(job)
                    elif not life["exited"]:
                        self.calls.terminate_created(state["launch"], state["native"])
                    if not life["exited"]:
                        self.calls.wait(state["launch"], end)
                    while job is not None and self.calls.members(job):
                        need(self.clock() < end, "QUERY_ABORT_JOB_DRAIN_DEADLINE")
                        self.pipes.pause()
                    need(
                        self.calls.lifecycle(state["launch"])["exited"]
                        and (job is None or not self.calls.members(job)),
                        "QUERY_ABORT_EXIT_OR_JOB_INCOMPLETE",
                    )
                    state["terminal_life"] = self.calls.lifecycle(state["launch"])
                    if (
                        failure is not None
                        and state["native"]["pid"] in p.aggregate.rows
                    ):
                        # Preserve original terminal usage on failure; no fake ACK or
                        # successful financial release is emitted.
                        p.aggregate.retire_failed_query(
                            state["launch"], state["native"]
                        )
                for key, h in reversed(tuple(state["held"])):
                    need(self.clock() < end, "QUERY_CLEANUP_DEADLINE")
                    self.calls.close(h)
                    need(self.calls.closed(h), "QUERY_RETAINED_HANDLE_STILL_OPEN")
                    p.allocations_port.release(key)
                    state["held"].remove((key, h))
                if state["launch"] is not None:
                    self.calls.close(state["launch"])
                    need(
                        self.calls.closed(state["launch"]),
                        "QUERY_PROCESS_HANDLE_STILL_OPEN",
                    )
                    p.allocations_port.release(slot)
                elif slot is not None and (
                    not state["creation_attempted"] or state["creation_absent"]
                ):
                    p.allocations_port.release(slot)
                state["closed"] = (
                    not state["held"]
                    and (state["launch"] is None or self.calls.closed(state["launch"]))
                    and all(
                        r.state["resources"][key]["closed"]
                        for key in state["reservations"]
                    )
                )
                if failure is None and self.clock() >= deadline:
                    failure = ValueError("QUERY_CLEANUP_EXCEEDED_ORIGINAL_DEADLINE")
                    self.failed = True
            except BaseException as exc:
                cleanup_failure = exc
                self.failed = True
                state["closed"] = False
                if failure is None:
                    failure = exc
            record = {
                "schema": "AIP06_NATIVE_COMMAND_V1",
                "scope": SCOPE_HASH,
                "session": p.controller.profile["session"],
                "nonce": state["nonce"],
                "argv": list(ARGS),
                "started_ns": start,
                "finished_ns": self.clock(),
                "identity": None
                if state["capability"] is None
                else state["capability"].runtime,
                "stdout_sha256": None
                if result is None
                else hashlib.sha256(result["stdout"].encode()).hexdigest(),
                "stderr_sha256": None
                if result is None
                else hashlib.sha256(result["stderr"].encode()).hexdigest(),
                "partial_stdout_hex": bytes(state["buffers"][0]).hex(),
                "partial_stderr_hex": bytes(state["buffers"][1]).hex(),
                "oversize_observed_bytes": state["oversize_observed"],
                "exit_code": None if result is None else result["exit_code"],
                "terminal_exit_code": state.get("terminal_life", {}).get("exit_code"),
                "closed": state["closed"],
                "failure": None
                if failure is None
                else type(failure).__name__ + ":" + str(failure),
                "cleanup_failure": None
                if cleanup_failure is None
                else type(cleanup_failure).__name__ + ":" + str(cleanup_failure),
                "unresolved_tickets": [
                    key
                    for key in state["reservations"]
                    if not r.state["resources"][key]["closed"]
                ],
                "financial_ack": False,
            }
            self.output.append(record)
            self.records.append(copy.deepcopy(record))
            # Buffer storage is logically reserved, never a kernel close proof.
            if capacity_reserved:
                self.done.add(capacity)
                r.close(owner, capacity, observer=self)
            if state["closed"]:
                self.active = None
        if failure is not None:
            raise failure
        need(
            result is not None and state["closed"] and self.clock() < deadline,
            "QUERY_COMPLETE_WITHIN_DEADLINE_REQUIRED",
        )
        result["closed"] = True
        return result

    def closed(self, owner, key):
        return owner == self.port.guard.owner and key in getattr(self, "done", set())
