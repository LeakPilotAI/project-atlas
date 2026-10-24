"""Disposable FS2 immutable financial records. No operational trust or routing.

Trust is explicitly injected and must retain a current pin across restart. Local
hashes and ACLs do not establish independent rollback authority. No recovery API
adopts uncertain tails; retained unacknowledged commits require separate review.
"""
import copy
import importlib.util
from contextlib import contextmanager
from itertools import islice
from pathlib import Path

from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import (
    apply_event,
    body,
    digest,
    event_stream_record,
    replay_verified_events,
    strict,
    validate_manifest,
)

_spec = importlib.util.spec_from_file_location("financial_snapshot_primitives", Path(__file__).with_name("snapshot_store.py"))
s = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s)
w, native, Refused = s.w, s.native, s.Refused
MAX_OPERATIONS = 128


def encoded(value):
    return body(value).encode("utf-8")


def name(revision, phase):
    return f"{revision:04d}-{phase}.json"


class FinancialRecordStore:
    """Bounded test-only protocol; injected pin custody is NOT supplied here.

    trust.current() -> pin, trust.check_clock(timestamp), trust.advance(old,new)
    must fail on unavailable authority or stale compare-and-swap. They are test
    dependencies, never proof of accepted issuer, trusted time or durable custody.
    """
    @staticmethod
    def provision_disposable(root, manifest):
        validate_manifest(manifest)
        with w.WindowsOutput.create_root(root) as output:
            binding = output.write_bound("inception.json", encoded(manifest))
            s.read_bound(output, "inception.json", binding)
            return {"schema": "FS2_TEST_PIN_V1", "root": native.file_identity(output.root_handle),
                    "inception": binding, "epoch": manifest["epoch"], "entries": []}

    def __init__(self, root, trust):
        if trust is None:
            raise Refused("Injected current-pin authority required")
        self.trust, self.poisoned, self.mutex = trust, False, None
        self.output = w.WindowsOutput(root)
        try:
            pin = trust.current()
            if native.file_identity(self.output.root_handle) != pin["root"]:
                raise Refused("Pinned root mismatch")
            self.coordinator = native.Registry.__new__(native.Registry)
            self.coordinator.output, self.coordinator.root_id = self.output, pin["root"]
            self.coordinator._create_mutex()
            self.mutex = self.coordinator.mutex
            self.snapshot()
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.mutex:
            w.close_handle(self.mutex)
            self.mutex = None
        self.output.close()

    @contextmanager
    def guard(self):
        if self.poisoned or not self.mutex:
            raise Refused("Uncertain or closed store")
        result = self.coordinator.wait(self.mutex, 500)
        if result not in (0, 128):
            raise Refused("Bounded writer exclusion unavailable")
        try:
            if result == 128:
                self.poisoned = True
                self._latch()
                raise Refused("Abandoned writer; no recovery authority")
            yield
        finally:
            w.check(self.coordinator.release(self.mutex))

    def _read(self, leaf, binding):
        if (type(binding) is not dict or set(binding) != {"id", "sha256"}
                or type(binding["id"]) is not list or len(binding["id"]) != 3
                or any(type(i) is not int or i < 0 for i in binding["id"])
                or type(binding["sha256"]) is not str or len(binding["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in binding["sha256"])):
            raise Refused("Malformed identity commitment before read")
        raw, _ = s.read_bound(self.output, leaf, binding)
        value = strict(raw.decode("utf-8"))
        if encoded(value) != raw:
            raise Refused("Noncanonical evidence")
        return value

    def _load(self):
        pin = copy.deepcopy(self.trust.current())
        if (type(pin) is not dict or set(pin) != {"schema", "root", "inception", "epoch", "entries"}
                or pin["schema"] != "FS2_TEST_PIN_V1" or type(pin["entries"]) is not list
                or len(pin["entries"]) > MAX_OPERATIONS
                or native.file_identity(self.output.root_handle) != pin["root"]):
            raise Refused("Malformed or substituted pin")
        manifest = self._read("inception.json", pin["inception"])
        validate_manifest(manifest)
        if manifest["epoch"] != pin["epoch"]:
            raise Refused("Wrong inception")
        rows = []
        previous = {"revision": 0, "record": pin["inception"], "event_digest": digest(manifest)}
        expected = {"inception.json"}
        for revision, entry in enumerate(pin["entries"], 1):
            if type(entry) is not dict or set(entry) != {"intent", "record", "commit", "ack"}:
                raise Refused("Incomplete operation pin")
            values = {}
            for phase in ("intent", "record", "commit", "ack"):
                leaf = name(revision, phase)
                expected.add(leaf)
                values[phase] = self._read(leaf, entry[phase])
            record = values["record"]
            if any(type(value) is not dict or type(value.get("revision")) is not int for value in values.values()):
                raise Refused("Contradictory typed publication revision")
            row = record.get("event")
            expected_values = {
                "record": {"schema": "FS2_RECORD_V1", "revision": revision, "previous": previous, "event": row},
                "intent": {"schema": "FS2_INTENT_V1", "revision": revision, "previous": previous,
                           "record_digest": digest(record)},
                "commit": {"schema": "FS2_COMMIT_V1", "revision": revision, "previous": previous,
                           "intent": entry["intent"], "record": entry["record"]},
                "ack": {"schema": "FS2_ACK_V1", "revision": revision, "commit": entry["commit"]},
            }
            if any(body(values[k]) != body(v) for k, v in expected_values.items()):
                raise Refused("Contradictory publication lineage")
            rows.append(row)
            previous = {"revision": revision, "record": entry["record"], "event_digest": row["digest"]}
        # Enumeration supplies no authority: any extra name causes refusal. All
        # trusted payload reads above are relative to retained native handles.
        actual = {p.name for p in islice(Path(self.output.root).iterdir(), MAX_OPERATIONS * 4 + 3)}
        if actual != expected:
            raise Refused("Incomplete, newer or unexpected namespace evidence")
        state, head, operations = replay_verified_events(manifest, rows)
        audit = audit_financial_events(manifest, rows, state)
        return pin, manifest, rows, state, head, operations, audit

    def snapshot(self):
        with self.guard():
            _, _, _, state, head, _, audit = self._load()
            return {"schema": "FS2_ACKNOWLEDGED_VIEW_V1", "state": state, "head": head, "audit": audit,
                    "status": "ACKNOWLEDGED", "valuation": None, "startup_authorized": False}

    def _latch(self):
        try:
            self.output.write_bound("recovery-required.json", encoded({"reason": "PUBLICATION_FAILED"}))
        except (OSError, ValueError):
            # Storage failure cannot promise a newly durable failure marker.
            pass

    def execute(self, command, *, projection_required=False):
        if type(projection_required) is not bool:
            raise Refused("Exact projection requirement needed")
        with self.guard():
            pin, manifest, rows, state, head, operations, _ = self._load()
            self.trust.check_clock(command["timestamp"])
            ident = command["operation_id"]
            if ident in operations:
                original, receipt = operations[ident]
                if body(original) != body(command) or receipt["projection_required"] != projection_required:
                    raise Refused("Conflicting duplicate operation")
                return copy.deepcopy(receipt)
            if len(rows) >= MAX_OPERATIONS:
                raise Refused("Capacity exhausted; no rotation or overwrite")
            _, receipt = apply_event(manifest, state, command)
            receipt["projection_required"] = projection_required
            row = event_stream_record(receipt["source_revision"], ident, body(command), head,
                                      digest([head, command, receipt]), body(receipt))
            revision = len(rows) + 1
            previous = {"revision": len(rows),
                        "record": pin["entries"][-1]["record"] if rows else pin["inception"],
                        "event_digest": head}
            record = {"schema": "FS2_RECORD_V1", "revision": revision, "previous": previous, "event": row}
            intent = {"schema": "FS2_INTENT_V1", "revision": revision, "previous": previous,
                      "record_digest": digest(record)}
            bindings = {}
            def publish(phase, value):
                binding = self.output.write_bound(name(revision, phase), encoded(value))
                self._read(name(revision, phase), binding)
                bindings[phase] = binding
            try:
                publish("intent", intent)
                publish("record", record)
                publish("commit", {"schema": "FS2_COMMIT_V1", "revision": revision,
                                   "previous": previous, "intent": bindings["intent"], "record": bindings["record"]})
                if projection_required:
                    self.poisoned = True
                    return {"schema": "FS2_UNACKNOWLEDGED_V1", "status": "UNKNOWN",
                            "committed_receipt": receipt, "fully_acknowledged": False,
                            "startup_authorized": False}
                publish("ack", {"schema": "FS2_ACK_V1", "revision": revision, "commit": bindings["commit"]})
                next_pin = copy.deepcopy(pin)
                next_pin["entries"].append(bindings)
                self.trust.advance(pin, next_pin)
                self._load()
                return receipt
            except BaseException:
                self.poisoned = True
                self._latch()
                raise
