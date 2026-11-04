"""Bounded IPC serving and genuine child input/output. No external delivery."""

import contextlib
import ntpath
import json
import threading

from app.services.paper_financial_replay import body, digest, strict
from scripts.observation_runtime.aip06_harness import need
from scripts.observation_runtime.aip06_ipc import MAX_IPC_NS
from scripts.observation_runtime.aip06_stop import ChildStopEndpoint


class ParentFrames:
    """Service shared-ledger RPCs while awaiting actual child evidence.

    There is one receive owner, no polling worker and no swallowed ACK. A
    surprising non-output/non-request frame fails closed instead of becoming a
    fabricated expected event. OUTPUT is durably recorded before it is returned.
    """

    def __init__(self, channel, *, broker, output):
        self.channel, self.broker, self.output = channel, broker, output
        self.lock = threading.RLock()
        self.failed = False
        self.saved_outputs = []
        self.output_bytes = 0

    @property
    def binding(self):
        return self.channel.binding

    @property
    def accounts(self):
        return self.channel.accounts

    def send(self, *args, **kw):
        return self.channel.send(*args, **kw)

    def receive(self, *, deadline_ns, expected_kind=None):
        with self.lock:
            need(not self.failed, "PARENT_FRAME_SERVICER_FAILED")
            try:
                while True:
                    end = min(deadline_ns, self.channel.clock() + MAX_IPC_NS)
                    item = self.channel.receive(deadline_ns=end)
                    if item["kind"] == "REQUEST":
                        need(
                            self.broker is not None, "CHILD_RPC_BEFORE_RETAINED_BINDING"
                        )
                        self.broker.serve_message(item, deadline_ns=end)
                        continue
                    if item["kind"] == "OUTPUT":
                        self.output_bytes += len(body(item["payload"]).encode())
                        need(
                            self.output_bytes <= 1024**2
                            and len(self.saved_outputs) < 128,
                            "PARENT_OUTPUT_CAPACITY",
                        )
                        self.output.append(
                            {
                                "schema": "AIP06_CHILD_FRAME_V1",
                                "binding": digest(self.binding),
                                "sequence": item["sequence"],
                                "sent_ns": item["sent_ns"],
                                "payload": item["payload"],
                            }
                        )
                        self.saved_outputs.append(item)
                        if expected_kind not in (None, "OUTPUT"):
                            continue
                    need(
                        expected_kind is None or item["kind"] == expected_kind,
                        "UNEXPECTED_SESSION_FRAME",
                    )
                    return item
            except BaseException:
                self.failed = True
                raise


class MailboxChannel:
    def __init__(self, resources):
        self.resources = resources

    @property
    def binding(self):
        return self.resources.channel.binding

    @property
    def accounts(self):
        return self.resources.channel.accounts

    def send(self, *args, **kw):
        return self.resources.channel.send(*args, **kw)

    def receive(self, *, deadline_ns, expected_kind):
        return self.resources.mailbox.receive(expected_kind, deadline_ns=deadline_ns)


class ChildSessionIO:
    """Installs bounded streams and reads only authenticated private frames."""

    def __init__(self, guard, *, clock_ns):
        self.guard, self.clock = guard, clock_ns
        self.channel = MailboxChannel(guard.resources)
        self.stop = ChildStopEndpoint(guard, self.channel)
        self.stdout = ChildText(self, "stdout")
        self.stderr = ChildText(self, "stderr")
        self.sequence = 0
        self.reader_acked = False

    def read_line(self, *, deadline_ns, maximum_bytes):
        raw = self.stop.receive(deadline_ns=deadline_ns)
        need(len(raw) <= maximum_bytes, "CHILD_STOP_INPUT_CAPACITY")
        return raw

    def read_input(self, *, timeout, maximum_bytes):
        value = self.channel.receive(
            deadline_ns=self.clock() + min(int(timeout * 10**9), MAX_IPC_NS),
            expected_kind="INPUT",
        )["payload"]
        raw = body(value).encode()
        need(0 < len(raw) <= maximum_bytes, "CHILD_INPUT_CAPACITY")
        return raw

    def emit_output(self, value):
        self.guard.check()
        self.sequence += 1
        self.channel.send("OUTPUT", value, deadline_ns=self.clock() + MAX_IPC_NS)

    def financial_readback(self, value):
        owner = self.channel.binding["child"]
        process = value.get("process", {}) if type(value) is dict else {}
        need(
            self.stop.command is not None
            and process.get("pid") == owner["pid"]
            and process.get("creation_filetime") == owner["created"]
            and ntpath.normcase(process.get("image", ""))
            == ntpath.normcase(owner["image"]),
            "ACTUAL_WORKER_READBACK_IDENTITY",
        )
        self.guard.check()
        # Called only after the pinned original pipeline's complete Stop,
        # acknowledged native readback, zero-pending and flat-position checks.
        self.stop.drained(
            {
                "scope": self.stop.command["scope"],
                "operation_id": self.stop.command["operation_id"],
                "pending": 0,
                "unknown": False,
                "orders": 0,
            },
            deadline_ns=self.clock() + MAX_IPC_NS,
        )

    def wait_readonly_ack(self, response):
        need(not self.reader_acked, "READONLY_RECEIPT_ONCE_ONLY")
        need(
            type(response) is dict and set(response) == {"request", "financial"},
            "READONLY_RESPONSE_REQUIRED",
        )
        received = self.channel.receive(
            deadline_ns=self.clock() + MAX_IPC_NS, expected_kind="ACK"
        )["payload"]
        need(
            received
            == {
                "schema": "AIP06_READER_RECEIVED_V1",
                "request": digest(response["request"]),
                "financial": digest(response["financial"]),
                "reader": self.guard.owner,
                "financial_verified": False,
            },
            "READER_RECEIPT_IDENTITY_CONFLICT",
        )
        self.reader_acked = True

    @contextlib.contextmanager
    def output_context(self):
        with (
            contextlib.redirect_stdout(self.stdout),
            contextlib.redirect_stderr(self.stderr),
        ):
            try:
                yield
            finally:
                self.stdout.flush()
                self.stderr.flush()


class ChildText:
    encoding = "utf-8"
    errors = "strict"

    def __init__(self, port, stream):
        self.port, self.stream = port, stream
        self.buffer = ""
        self.total = 0
        self.failed = False

    def write(self, text):
        need(type(text) is str and not self.failed, "CHILD_TEXT_REQUIRED")
        raw = text.encode()
        need(self.total + len(raw) <= 1024**2, "CHILD_STREAM_CAPACITY")
        self.total += len(raw)
        self.buffer += text
        need(len(self.buffer.encode()) <= 1024**2, "CHILD_LINE_CAPACITY")
        while "\n" in self.buffer:
            line, rest = self.buffer.split("\n", 1)
            self.failed = True
            self._emit(line)
            self.buffer = rest
            self.failed = False
        return len(text)

    def _emit(self, line):
        try:
            value = strict(line)
        except (ValueError, json.JSONDecodeError):
            value = None
        self.port.emit_output(
            {
                "schema": "AIP06_CHILD_OUTPUT_V1",
                "owner": self.port.guard.owner,
                "stream": self.stream,
                "text": line,
                "value": value,
            }
        )

    def flush(self):
        need(not self.failed, "CHILD_TEXT_DELIVERY_UNKNOWN")
        if self.buffer:
            self.failed = True
            self._emit(self.buffer)
            self.buffer = ""
            self.failed = False

    def isatty(self):
        return False

    def fileno(self):
        raise ValueError("NO_RAW_CHILD_OUTPUT_DESCRIPTOR")
