"""Guarded financial Stop transport/readback assembly. No native execution.

Readback is checked again by the existing StopVerification financial replay and
audit. This module never invents an ACK from an exit, EOF or boolean drain flag.
"""

import copy
import hashlib
import ntpath

from app.services.paper_financial_replay import body, digest
from scripts.observation_runtime.aip06_harness import LIMITS, SCOPE_HASH, need
from scripts.observation_runtime.aip06_ipc import MAX_IPC_NS, StopMessages


def native_hashes(guard, root):
    """Bounded read-only inventory under an already native-bound fixture root."""
    guard.locate(root)
    result = {}
    queue = [root]
    while queue:
        path = queue.pop()
        info = guard.io.inspect(path)
        need(
            info is not None and not info["reparse"] and info["links"] == 1,
            "READBACK_NATIVE_NAMESPACE",
        )
        if info["kind"] == "directory":
            names = guard.io.names(path, maximum=LIMITS["entries"])
            need(
                type(names) is list and len(names) == len(set(names)),
                "READBACK_COMPLETE_NAMES",
            )
            for leaf in names:
                need(
                    type(leaf) is str
                    and ntpath.basename(leaf) == leaf
                    and leaf not in (".", ".."),
                    "READBACK_NATIVE_LEAF",
                )
                child = ntpath.join(path, leaf)
                guard.locate(child)
                queue.append(child)
        else:
            raw = guard.io.read_bytes(path, maximum_bytes=32 * 1024**2)
            result[path] = hashlib.sha256(raw).hexdigest()
        need(
            len(queue) + len(result) <= LIMITS["entries"], "READBACK_INVENTORY_CAPACITY"
        )
    need(result, "READBACK_NOT_EMPTY")
    return result


def personal_financial_reply(
    *,
    guard,
    root,
    native,
    manifest,
    native_reader,
    selected_reader,
    current,
    clock,
    writer_rebind_refused,
):
    """Derive exact cuts only from the original full personal custody checks.

    current._capture invokes original source/projection/report/global custody,
    acknowledged publication, pending/UNKNOWN refusal and native identity checks.
    Stage cuts below are a projection of that verified readback, not synthetic
    delivery or a declaration accepted in place of a source operation.
    """
    before = native_hashes(guard, root)
    cut, _, publication = current._capture(clock())
    raw = native_reader.read_committed()
    selected = selected_reader.read_committed(native["account_id"], native["epoch"])
    proof = selected_reader.verify(
        selected, account_id=native["account_id"], epoch=native["epoch"], now=clock()
    )
    need(
        type(proof) is dict and proof.get("verified") is True,
        "READONLY_SELECTED_PROOF_REQUIRED",
    )
    need(
        raw["schema"] == "QD_AUTO_OP_READ_V1"
        and raw["manifest"] == manifest
        and raw["state"] == selected["state"]
        and raw["source_pin"] == cut["source"]
        and digest(raw["state"]) == cut["state_digest"]
        and len(raw["rows"]) == cut["source_revision"]
        and publication["status"] == "ACKNOWLEDGED"
        and writer_rebind_refused is True,
        "INDEPENDENT_FINANCIAL_CUT_INCOMPLETE",
    )
    account = {
        "account_id": native["account_id"],
        "manifest": manifest,
        "events": raw["rows"],
        "snapshot": raw["state"],
        "native_source": native["resources"]["source"]["native_id"],
        "source_head": raw["head"],
    }
    summary = {
        "account_id": native["account_id"],
        "epoch": manifest["epoch"],
        "currency": manifest["currency"],
        "revision": raw["state"]["revision"],
        "head": raw["head"],
        "state_digest": digest(raw["state"]),
        "native_source": account["native_source"],
    }
    need(
        summary["revision"] == cut["source_revision"] and summary["currency"] == "USD",
        "PERSONAL_FINANCIAL_REVISION",
    )
    again, _, again_publication = current._capture(clock())
    after = native_hashes(guard, root)
    need(
        before == after and again == cut and again_publication == publication,
        "READONLY_REOPEN_CHANGED_FINANCIAL_SOURCE",
    )
    return {
        "accounts": {"QUALITY_DIPS": account},
        "acknowledgements": {
            "QUALITY_DIPS": {
                stage: copy.deepcopy(summary)
                for stage in ("source", "projection", "report", "global")
            }
        },
        "before_hashes": before,
        "after_hashes": after,
        "writer_rebind_refused": True,
    }


class RetainedFinancialReply:
    def __init__(self):
        self.observer_identity = None
        self.reply = None
        self.request = None

    def bind(self, reader, request, payload):
        identity = reader.identity()
        need(
            self.reply is None
            and type(payload) is dict
            and set(payload) == {"request", "financial"}
            and body(payload["request"]) == body(request),
            "COLD_READER_REQUEST_BINDING",
        )
        need(
            type(payload["financial"]) is dict
            and set(payload["financial"])
            == {
                "accounts",
                "acknowledgements",
                "before_hashes",
                "after_hashes",
                "writer_rebind_refused",
            },
            "COLD_READER_FINANCIAL_RESPONSE_INCOMPLETE",
        )
        self.observer_identity = identity
        self.request = copy.deepcopy(request)
        self.reply = copy.deepcopy(payload["financial"])

    def read_committed(self, request):
        need(
            self.reply is not None and body(request) == body(self.request),
            "NO_MATCHED_RETAINED_FINANCIAL_REPLY",
        )
        return copy.deepcopy(self.reply)


class GuardedStopCollector:
    """Drive the same guard/roster/Stop verifier; all observation ports explicit."""

    def __init__(self, *, clock_ns, output, sockets, processes, close_io):
        self.clock, self.output, self.sockets, self.processes, self.close_io = (
            clock_ns,
            output,
            sockets,
            processes,
            close_io,
        )
        self.pending = {}
        self.failed = False

    def send(self, child, request, *, revision):
        need(
            not self.failed and digest(request) not in self.pending,
            "STOP_SEND_ONCE_ONLY",
        )
        child.identity()  # Independently live retained worker/Job, not PID alone.
        wire = child.child.channel
        correlation = StopMessages(
            wire, request, revision=revision, accounts=wire.accounts
        )
        self.pending[digest(request)] = correlation
        wire.send(
            "STOP",
            {"request": request, "revision": revision, "accounts": wire.accounts},
            deadline_ns=self.clock() + MAX_IPC_NS,
        )

    def collect(self, child, guard, request, **options):
        try:
            return self._collect(child, guard, request, **options)
        except BaseException as exc:
            self.failed = True
            guard.failed = True
            if guard.stop is not None:
                guard.stop.failure = type(exc).__name__
            try:
                guard.resources.resolve_stop(request, "FAILED")
            except BaseException:
                guard.resources.uncertain = True
            guard.processes.refuse_current_launch()
            raise

    def _collect(
        self,
        child,
        guard,
        request,
        *,
        deadline_ns,
        reader_argv,
        reader_options,
        reader_input,
        reader,
    ):
        need(
            guard.stop is not None
            and self.clock() < deadline_ns
            and deadline_ns == guard.stop.started + 8 * 10**9
            and digest(request) in self.pending
            and not self.failed,
            "ORIGINAL_STOP_DEADLINE_REQUIRED",
        )
        self.failed = True
        correlation = self.pending[digest(request)]
        wire = child.child.channel
        end = lambda: min(deadline_ns, self.clock() + MAX_IPC_NS)
        ack = wire.receive(deadline_ns=end(), expected_kind="ACK")["payload"]
        acknowledgement = correlation.acknowledge(ack)
        drain = correlation.drain(
            wire.receive(deadline_ns=end(), expected_kind="DRAIN")["payload"]
        )
        # communicate must retain actual process exit and private transport
        # closure; GuardedProcess.close independently verifies normal exit/Job.
        child.communicate(timeout=max(0.001, (deadline_ns - self.clock()) / 10**9))
        need(self.clock() < deadline_ns, "NO_NEW_READER_AFTER_STOP_DEADLINE")
        value = reader_input() if callable(reader_input) else reader_input
        need(self.clock() < deadline_ns, "NO_NEW_READER_AFTER_STOP_INPUT_DEADLINE")
        cold = guard.spawn(reader_argv, **reader_options)
        response = guard.processes.exchange_reader(cold, value, deadline_ns=deadline_ns)
        reader.bind(cold, request, response)
        guard.processes.ack_reader(cold, request, response["financial"])
        cold.communicate(timeout=max(0.001, (deadline_ns - self.clock()) / 10**9))
        self.close_io()
        socket_cut = self.sockets.collect(
            deadline_ns=deadline_ns, started_ns=guard.stop.started
        )
        process_cut = self.processes.collect(
            after_ns=socket_cut["at_ns"], deadline_ns=deadline_ns
        )
        need(self.clock() <= deadline_ns, "COMPLETE_STOP_EIGHT_SECONDS_REQUIRED")
        evidence = {
            "acknowledgement": acknowledgement,
            "drain": drain,
            "socket_cut": socket_cut,
            "process_cut": process_cut,
            "release_observer": guard.processes,
        }
        self.output.append(
            {
                "schema": "AIP06_STOP_COLLECTION_V1",
                "scope": SCOPE_HASH,
                "request": request,
                "acknowledgement": acknowledgement,
                "drain": drain,
                "socket_cut": socket_cut,
                "process_cut": process_cut,
                "reader": reader.observer_identity,
                "native_acceptance": False,
            }
        )
        need(self.clock() <= deadline_ns, "STOP_OUTPUT_DEADLINE")
        self.failed = False
        return evidence


class ChildStopEndpoint:
    """Only the worker's verified received Stop can enable an ACK/drain."""

    def __init__(self, guard, channel):
        self.guard, self.channel = guard, channel
        self.command = None
        self.revision = None

    def receive(self, *, deadline_ns):
        need(self.command is None, "CHILD_STOP_ONCE_ONLY")
        value = self.channel.receive(deadline_ns=deadline_ns, expected_kind="STOP")[
            "payload"
        ]
        need(
            type(value) is dict
            and set(value) == {"request", "revision", "accounts"}
            and body(value["accounts"]) == body(self.channel.accounts)
            and type(value["revision"]) is int,
            "CHILD_STOP_SCOPE_REVISION",
        )
        self.guard.check()
        owner = self.guard.resources.state["owners"][self.guard.owner]
        command = value["request"]
        self.guard.verify_received_stop(
            command,
            self.channel.binding["nonce"],
            {
                "pid": owner["pid"],
                "creation_filetime": owner["created"],
                "image": owner["image"],
            },
        )
        self.command, self.revision = command, value["revision"]
        self.channel.send("ACK", value, deadline_ns=deadline_ns)
        return body(command).encode() + b"\n"

    def drained(self, drain, *, deadline_ns):
        need(
            self.command is not None
            and drain
            == {
                "scope": SCOPE_HASH,
                "operation_id": self.command["operation_id"],
                "pending": 0,
                "unknown": False,
                "orders": 0,
            },
            "CHILD_ACTUAL_DRAIN_REQUIRED",
        )
        self.channel.send("DRAIN", drain, deadline_ns=deadline_ns)
