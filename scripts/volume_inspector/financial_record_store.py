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
DEFAULT_RECORD_VERSIONS = {"pin": "FS2_TEST_PIN_V1", "record": "FS2_RECORD_V1",
    "intent": "FS2_INTENT_V1", "commit": "FS2_COMMIT_V1", "ack": "FS2_ACK_V1",
    "projection_ack": "FS3_ACK_V1"}


def record_version(store, phase):
    # Constructor-free existing readers retain the original codec by default.
    return getattr(store, "record_versions", DEFAULT_RECORD_VERSIONS)[phase]



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
        if manifest['schema'] == 'PAPER_EPOCH_PERP_OPERATIONAL_V1':
            raise Refused('Operational perpetual inception requires separate publication authority')
        with w.WindowsOutput.create_root(root) as output:
            binding = output.write_bound("inception.json", encoded(manifest))
            s.read_bound(output, "inception.json", binding)
            return {"schema": "FS2_TEST_PIN_V1", "root": native.file_identity(output.root_handle),
                    "inception": binding, "epoch": manifest["epoch"], "entries": []}

    def __init__(self, root, trust, *, projection=None):
        if trust is None:
            raise Refused("Injected current-pin authority required")
        self.trust, self.poisoned, self.mutex = trust, False, None
        self.projection = projection
        self.output = w.WindowsOutput(root)
        try:
            pin = trust.current()
            require_identity(pin["root"])
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
                or pin["schema"] != record_version(self, "pin") or type(pin["entries"]) is not list
                or len(pin["entries"]) > MAX_OPERATIONS
                or native.file_identity(self.output.root_handle) != pin["root"]):
            raise Refused("Malformed or substituted pin")
        require_identity(pin["root"])
        manifest = self._read("inception.json", pin["inception"])
        validate_manifest(manifest)
        if record_version(self, 'pin') == 'FS2_TEST_PIN_V1' and manifest['schema'] == 'PAPER_EPOCH_PERP_OPERATIONAL_V1':
            raise Refused('Operational perpetual parameters cannot use test pins')
        if manifest["epoch"] != pin["epoch"]:
            raise Refused("Wrong inception")
        rows, projections = [], []
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
                "record": {"schema": record_version(self, "record"), "revision": revision, "previous": previous, "event": row},
                "intent": {"schema": record_version(self, "intent"), "revision": revision, "previous": previous,
                           "record_digest": digest(record)},
                "commit": {"schema": record_version(self, "commit"), "revision": revision, "previous": previous,
                           "intent": entry["intent"], "record": entry["record"]},
                "ack": {"schema": record_version(self, "ack"), "revision": revision, "commit": entry["commit"]},
            }
            receipt = strict(row["receipt"])
            if receipt.get("projection_required") is True:
                ack = values["ack"]
                if self.projection is None or set(ack) != {"schema", "revision", "commit", "projection"}:
                    raise Refused("Required projection verifier/acknowledgement unavailable")
                context = projection_context(receipt, entry["record"], entry["commit"])
                self.projection.verify(context, ack["projection"])
                projections.append(ack["projection"])
                expected_values["ack"] = {"schema": record_version(self, "projection_ack"), "revision": revision,
                                          "commit": entry["commit"], "projection": ack["projection"]}
            if any(body(values[k]) != body(v) for k, v in expected_values.items()):
                raise Refused("Contradictory publication lineage")
            rows.append(row)
            previous = {"revision": revision, "record": entry["record"], "event_digest": row["digest"]}
        # Enumeration supplies no authority: any extra name causes refusal. All
        # trusted payload reads above are relative to retained native handles.
        actual = {p.name for p in islice(Path(self.output.root).iterdir(), MAX_OPERATIONS * 4 + 3)}
        if actual != expected:
            raise Refused("Incomplete, newer or unexpected namespace evidence")
        if self.projection is not None:
            self.projection.verify_inventory(projections)
        state, head, operations = replay_verified_events(manifest, rows)
        audit = audit_financial_events(manifest, rows, state)
        return pin, manifest, rows, state, head, operations, audit

    def snapshot(self):
        with self.guard():
            _, _, _, state, head, _, audit = self._load()
            return {"schema": "FS2_ACKNOWLEDGED_VIEW_V1", "state": state, "head": head, "audit": audit,
                    "status": "ACKNOWLEDGED", "valuation": None, "startup_authorized": False}

    def verified_cut(self):
        """Existing-only native read, including the pinned manifest and root."""
        if record_version(self, "pin") != "FS2_TEST_PIN_V1":
            raise Refused("OPERATIONAL_SOURCE_INSPECTION_NOT_ENROLLED")
        pin, manifest, _, state, head, operations, audit = self._inspect_existing()
        return copy.deepcopy({"manifest": manifest, "root": pin["root"], "state": state,
                              "head": head, "audit": audit, "pin_schema": pin["schema"],
                              "acknowledged_operations": {key: digest(value[0]) for key, value in operations.items()}})

    def export_continuation_fixture(self, *, expected_pin):
        """Read-only FS1 rows for an independently pinned DISPOSABLE cut.

        Never use snapshot()/guard() here: those may acquire a writer mutex or
        publish a refusal latch. Operational codecs must use a separately
        reviewed admission-aware export; inherited calls explicitly refuse.
        """
        if record_version(self, 'pin') != 'FS2_TEST_PIN_V1':
            raise Refused('NATIVE_CONTINUATION_OPERATIONAL_EXPORT_NOT_AUTHORIZED')
        if body(self.trust.current()) != body(expected_pin):
            raise Refused('CONTINUATION_EXPECTED_SOURCE_CUT_CHANGED')
        pin, manifest, rows, state, head, operations, audit = self._inspect_existing()
        if (pin.get('schema') != 'FS2_TEST_PIN_V1' or body(pin) != body(expected_pin)
                or manifest.get('schema') not in ('PAPER_EPOCH_FIXTURE_V1',
                    'PAPER_EPOCH_AUTONOMOUS_QD_V1','PAPER_EPOCH_PERP_FIXTURE_V2')
                or not 0 <= len(rows) <= MAX_OPERATIONS or len(pin['entries']) != len(rows)
                or type(state['revision']) is not int or state['revision'] != len(rows)
                or len(operations) != len(rows) or type(audit['source_revision']) is not int
                or audit['source_revision'] != len(rows) or pin['epoch'] != manifest['epoch']
                or body(self.trust.current()) != body(expected_pin)):
            raise Refused('CONTINUATION_COMPLETE_ACKNOWLEDGED_FIXTURE_CUT_REQUIRED')
        return copy.deepcopy({'schema':'FS2_CONTINUATION_FIXTURE_EXPORT_V1',
            'execution_domain':'DISPOSABLE','source_pin':pin,'manifest':manifest,'rows':rows,
            'state':state,'head':head,'audit':audit,'remaining_operations':MAX_OPERATIONS-len(rows),
            'startup_authorized':False})

    def remaining_operations(self):
        """Authenticated existing-only capacity read; no reset or writer mutex."""
        return MAX_OPERATIONS-self.verified_cut()['state']['revision']

    def _inspect_existing(self):
        # Never acquire the writer mutex here: observing an abandoned mutex can
        # consume its evidence, and writer.guard() may publish a failure latch.
        # Immutable handle reads plus a stable accepted pin give a snapshot;
        # exclusive financial admission still belongs to the external custody.
        if self.poisoned or not self.mutex:
            raise Refused("Uncertain or closed source inspection")
        pinned = body(self.trust.current())
        result = self._load()
        if body(result[0]) != pinned or body(self.trust.current()) != pinned:
            raise Refused("Source custody changed during inspection")
        return result

    def preview(self, command):
        """Pure FS1 proposal over an acknowledged cut; never publishes/repairs."""
        if record_version(self, "pin") != "FS2_TEST_PIN_V1":
            raise Refused("OPERATIONAL_SOURCE_INSPECTION_NOT_ENROLLED")
        pin, manifest, _, state, head, operations, _ = self._inspect_existing()
        if command.get("operation_id") in operations:
            raise Refused("Preview cannot adopt or replay an existing operation")
        candidate, receipt = apply_event(manifest, state, command)
        return copy.deepcopy({"manifest": manifest, "root": pin["root"], "head": head,
                              "before": state, "after": candidate, "receipt": receipt})

    def operation_receipt(self, operation_id, payload_digest):
        """Read an already acknowledged receipt without invoking a writer."""
        if record_version(self, "pin") != "FS2_TEST_PIN_V1":
            raise Refused("OPERATIONAL_SOURCE_INSPECTION_NOT_ENROLLED")
        operations = self._inspect_existing()[5]
        original = operations.get(operation_id)
        if original is None or digest(original[0]) != payload_digest:
            raise Refused("Missing or conflicting acknowledged operation")
        return copy.deepcopy(original[1])

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
            next_state, receipt = apply_event(manifest, state, command)
            receipt["projection_required"] = projection_required
            row = event_stream_record(receipt["source_revision"], ident, body(command), head,
                                      digest([head, command, receipt]), body(receipt))
            revision = len(rows) + 1
            previous = {"revision": len(rows),
                        "record": pin["entries"][-1]["record"] if rows else pin["inception"],
                        "event_digest": head}
            record = {"schema": record_version(self, "record"), "revision": revision, "previous": previous, "event": row}
            intent = {"schema": record_version(self, "intent"), "revision": revision, "previous": previous,
                      "record_digest": digest(record)}
            bindings = {}
            def publish(phase, value):
                binding = self.output.write_bound(name(revision, phase), encoded(value))
                self._read(name(revision, phase), binding)
                bindings[phase] = binding
            try:
                publish("intent", intent)
                publish("record", record)
                publish("commit", {"schema": record_version(self, "commit"), "revision": revision,
                                   "previous": previous, "intent": bindings["intent"], "record": bindings["record"]})
                if projection_required and self.projection is None:
                    self.poisoned = True
                    return {"schema": "FS2_UNACKNOWLEDGED_V1", "status": "UNKNOWN",
                            "committed_receipt": receipt, "fully_acknowledged": False,
                            "startup_authorized": False}
                ack = {"schema": record_version(self, "ack"), "revision": revision, "commit": bindings["commit"]}
                if projection_required:
                    context = projection_context(receipt, bindings["record"], bindings["commit"])
                    proof = self.projection.publish(context, next_state)
                    self.projection.verify(context, proof)
                    ack = {"schema": record_version(self, "projection_ack"), "revision": revision,
                           "commit": bindings["commit"], "projection": proof}
                publish("ack", ack)
                next_pin = copy.deepcopy(pin)
                next_pin["entries"].append(bindings)
                self.trust.advance(pin, next_pin)
                self._load()
                return receipt
            except BaseException:
                self.poisoned = True
                self._latch()
                raise



def projection_context(receipt, record, commit):
    return {"schema": "FS3_PROJECTION_CONTEXT_V1", "epoch": receipt["epoch"],
            "operation_id": receipt["operation_id"], "source_revision": receipt["source_revision"],
            "state_digest": receipt["state_digest"], "record": record, "commit": commit}



def require_identity(value):
    if type(value) is not list or len(value) != 3 or any(type(i) is not int or i < 0 for i in value):
        raise Refused("Exact integer native identity required before coordinator selection")
