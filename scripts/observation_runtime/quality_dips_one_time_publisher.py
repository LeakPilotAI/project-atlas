"""Uninstalled one-time QD_OP genesis publisher; explicit independent trust only.

No issuer/custodian, directory provisioner, loader, API route or startup path.
Native file writes are reachable only through explicitly injected authorities.
"""

import importlib.util
from contextlib import contextmanager
from pathlib import Path

from app.investment.quality_dips_operational_contract import (
    ROLES,
    exact,
    positive,
    process,
)
from app.investment.quality_dips_operational_replay import history, initial, replay
from app.services.paper_financial_replay import body, digest, strict


class PublicationUnknown(ValueError):
    """Reservation may have durable effects. No automatic retry or recovery."""


class NativeGenesisFiles:
    """Existing-only native roots; exclusive immutable file creation, no repair."""

    @contextmanager
    def open(self, enrollment):
        spec = importlib.util.spec_from_file_location(
            "genesis_bound_reader",
            Path(__file__).parents[1]
            / "volume_inspector/operational_financial_read.py",
        )
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        outputs = {}
        try:
            for role in ROLES:
                resource = enrollment["resources"][role]
                out = m.s.w.WindowsOutput(resource["root_path"])
                outputs[role] = out
                if m.s.native.file_identity(out.root_handle) != resource["native_root"]:
                    raise ValueError("GENESIS_RESOURCE_IDENTITY_MISMATCH")
                if list(Path(out.root).iterdir()):
                    raise ValueError("GENESIS_REQUIRES_EMPTY_NO_LEGACY_ADOPTION")
            yield _BoundFiles(m, outputs)
        finally:
            for out in outputs.values():
                out.close()


class _BoundFiles:
    def __init__(self, module, outputs):
        self.module, self.outputs = module, outputs
        self.expected = {role: {} for role in ROLES}

    def write(self, role, name, document):
        out = self.outputs[role]
        bound = out.write_bound(name, body(document).encode())
        pin = {
            "schema": "QD_OP_FILE_BINDING_V1",
            "native_id": bound["id"],
            "sha256": bound["sha256"],
            "record_schema": document["schema"],
        }
        self.expected[role][name] = (pin, strict(body(document)))
        self.verify()
        return pin

    def verify(self):
        for role, out in self.outputs.items():
            out._verify()
            if {p.name for p in Path(out.root).iterdir()} != set(self.expected[role]):
                raise ValueError("GENESIS_NAMESPACE_CHANGED")
            for name, (pin, document) in self.expected[role].items():
                read = self.module.NativeOperationalReadPort._read(
                    out, name, pin, document["schema"]
                )
                if body(read) != body(document):
                    raise ValueError("GENESIS_NATIVE_READBACK_FAILED")


class OneTimePublisher:
    """Custody.reserve must atomically persist single-use PENDING before yield.

    An authenticated transaction supplies snapshot/check, commit, acknowledge,
    mark_unknown. Exclusive reservation, monotonic custody, durable CAS and
    receipts are independent dependencies, never implemented with local hashes.
    """

    def __init__(
        self, *, bootstrap=None, custody=None, ownership=None, observer=None, files=None
    ):
        if any(v is None for v in (bootstrap, custody, ownership, observer, files)):
            raise ValueError("PUBLISHER_ACCEPTED_DEPENDENCIES_REQUIRED")
        if custody is not bootstrap.publication:
            raise ValueError("PUBLISHER_AND_BOOTSTRAP_CUSTODY_MUST_MATCH")
        self.bootstrap, self.custody, self.ownership, self.observer, self.files = (
            bootstrap,
            custody,
            ownership,
            observer,
            files,
        )

    @contextmanager
    def _reservation(self, intent, context, now):
        try:
            with self.custody.reserve(
                strict(body(intent)), strict(body(context)), now
            ) as transaction:
                yield transaction
        except PublicationUnknown:
            raise
        except BaseException as error:
            # Failure entering/exiting an external durable reservation may itself
            # be commit-before-ack. Do not infer UNPUBLISHED or retry it.
            raise PublicationUnknown("GENESIS_RESERVATION_UNKNOWN_NO_REPLAY") from error

    def publish(self):
        b = self.bootstrap
        if self.custody is not b.publication:
            raise ValueError('PUBLISHER_AND_BOOTSTRAP_CUSTODY_MUST_MATCH')
        intent = b.prepare()  # Authenticated UNPUBLISHED only; no financial read/write.
        e = strict(body(b.enrollment))
        now = b.clock()
        positive(now)
        identity = strict(body(self.observer()))
        process(identity)
        context = {
            "schema": "QD_OP_GENESIS_WRITER_V1",
            "intent_digest": digest(intent),
            "process": identity,
        }
        last = now
        with (
            b.issuer.lease(strict(body(intent)), now) as issuer,
            self.ownership.lease(strict(body(context)), now) as owner,
        ):

            def admitted():
                nonlocal last
                current = b.clock()
                if (
                    type(current) is not int
                    or not last <= current <= now + 30
                    or body(self.observer()) != body(identity)
                    or issuer.check(strict(body(intent)), current) is not True
                    or owner.check(strict(body(context)), current) is not True
                ):
                    raise ValueError("GENESIS_ISSUER_CLOCK_OR_WRITER_REFUSED")
                last = current
                return current

            admitted()
            with self._reservation(intent, context, now) as txn:
                try:
                    reservation = strict(body(txn.snapshot))
                    exact(
                        reservation,
                        "QD_OP_GENESIS_PENDING_V1",
                        {
                            "operation_id",
                            "intent_digest",
                            "writer_digest",
                            "state",
                            "pending_durable",
                        },
                    )
                    if (
                        reservation["operation_id"] != intent["operation_id"]
                        or reservation["intent_digest"] != digest(intent)
                        or reservation["writer_digest"] != digest(context)
                        or reservation["state"] != "PENDING"
                        or reservation["pending_durable"] is not True
                    ):
                        raise ValueError("GENESIS_DURABLE_RESERVATION_REQUIRED")

                    def boundary():
                        t = admitted()
                        if txn.check(strict(body(reservation)), t) is not True:
                            raise ValueError("GENESIS_CUSTODY_LOST_OR_ROLLED_BACK")
                        return t

                    boundary()
                    with self.files.open(e) as files:
                        boundary()
                        inception = files.write(
                            "source", "inception.json", e["account"]
                        )
                        source = {
                            "schema": "QD_OP_SOURCE_PIN_V1",
                            "resource_id": e["resources"]["source"]["resource_id"],
                            "native_root": e["resources"]["source"]["native_root"],
                            "revision": 0,
                            "inception": inception,
                            "records": [],
                            "head_digest": inception["sha256"],
                        }
                        state, snapshots = replay(
                            e, {"revision": 0, "source": source}, [], now
                        )
                        if body(state) != body(initial()):
                            raise ValueError("GENESIS_ARITHMETIC_REFUSED")
                        projection = {
                            "schema": "QD_OP_PROJECTION_DOCUMENT_V1",
                            "enrollment_digest": digest(e),
                            "source_pin_digest": digest(source),
                            "revision": 0,
                            "state": state,
                        }
                        cutoff = boundary()
                        report = {
                            "schema": "QD_OP_REPORT_DOCUMENT_V2",
                            "enrollment_digest": digest(e),
                            "source_pin_digest": digest(source),
                            "revision": 0,
                            "status": "INCOMPLETE",
                            "timezone": "America/New_York",
                            "cutoff": cutoff,
                            "history": history(
                                [], snapshots, cutoff, "America/New_York"
                            ),
                        }
                        current = {
                            "schema": "QD_OP_CURRENT_V1",
                            "enrollment_digest": digest(e),
                            "generation": 1,
                            "revision": 0,
                            "acknowledged_revision": 0,
                            "status": "ACKNOWLEDGED",
                            "source": source,
                        }
                        for role, doc in (
                            ("projection", projection),
                            ("report", report),
                        ):
                            boundary()
                            pin = files.write(role, role + ".json", doc)
                            current[role] = {
                                "schema": "QD_OP_"
                                + role.upper()
                                + "_PIN_"
                                + ("V2" if role == "report" else "V1"),
                                "resource_id": e["resources"][role]["resource_id"],
                                "native_root": e["resources"][role]["native_root"],
                                "revision": 0,
                                "source_pin_digest": digest(source),
                                "record": pin,
                            }
                        files.verify()
                        boundary()
                        commit = txn.commit(strict(body(current)), boundary())
                        exact(
                            commit,
                            "QD_OP_GENESIS_COMMIT_V1",
                            {
                                "operation_id",
                                "intent_digest",
                                "current_digest",
                                "state",
                            },
                        )
                        if (
                            commit["operation_id"] != intent["operation_id"]
                            or commit["intent_digest"] != digest(intent)
                            or commit["current_digest"] != digest(current)
                            or commit["state"] != "COMMITTED"
                        ):
                            raise ValueError("GENESIS_COMMIT_RECEIPT_REFUSED")
                        boundary()
                        witness = txn.acknowledge(strict(body(commit)), boundary())
                        files.verify()
                        boundary()
                        ready = (
                            b.verify_publication()
                        )  # Existing independent native/replay/read-service path.
                        if ready["publication_digest"] != digest(witness) or ready[
                            "current_digest"
                        ] != digest(current):
                            raise ValueError("GENESIS_ACK_READBACK_REFUSED")
                        boundary()
                        return ready
                except BaseException as error:
                    try:
                        txn.mark_unknown(type(error).__name__)
                    except BaseException as custody_error:
                        # The original exception remains custody_error.__context__.
                        raise PublicationUnknown(
                            "GENESIS_UNKNOWN_AND_CUSTODY_UPDATE_FAILED"
                        ) from custody_error
                    raise PublicationUnknown(
                        "GENESIS_UNKNOWN_NO_REPLAY_OR_RECOVERY"
                    ) from error


if __name__ == "__main__":
    raise SystemExit(
        "REFUSED: no default issuer, custody, ownership or financial publication authority"
    )
