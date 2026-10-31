"""Explicit nonfinancial release selection; no default roots or activation."""

import hashlib
import json
import re
from contextlib import contextmanager
from pathlib import Path

MAX_RECORDS = 128
DOMAINS = {"WINDOWS_LOCAL", "DISPOSABLE"}


def encoded(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def strict(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("SELECTION_DUPLICATE_FIELD")
            result[key] = value
        return result

    return json.loads(
        raw,
        object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(
            ValueError("SELECTION_NONFINITE")
        ),
    )


def validate_spec(value, domain):
    fields = {
        "schema",
        "domain",
        "release",
        "root",
        "receipt",
        "receipt_sha256",
        "artifact_digest",
    }
    if (
        domain not in DOMAINS
        or type(value) is not dict
        or set(value) != fields
        or value["schema"] != "QD_INSTALLED_RELEASE_REFERENCE_V1"
        or value["domain"] != domain
        or not isinstance(value["release"], str)
        or not re.fullmatch("[0-9a-f]{40}", value["release"])
        or any(
            type(value[k]) is not str or not re.fullmatch("[0-9a-f]{64}", value[k])
            for k in ("receipt_sha256", "artifact_digest")
        )
        or any(
            type(value[k]) is not str or not Path(value[k]).is_absolute()
            for k in ("root", "receipt")
        )
    ):
        raise ValueError("EXACT_INSTALLED_RELEASE_REFERENCE_REQUIRED")
    root, receipt = Path(value["root"]), Path(value["receipt"])
    if any(".." in p.parts for p in (root, receipt)):
        raise ValueError("SELECTION_PATH_ALIAS")
    if domain == "WINDOWS_LOCAL":
        if root != Path("D:/AtlasRuntime/releases") / value[
            "release"
        ] or receipt != Path("D:/Work/Project Atlas/logs/diagnostics") / (
            "qd-unselected-release-" + value["release"] + ".json"
        ):
            raise ValueError("SELECTION_FOREIGN_OPERATIONAL_PATH")
    elif any(str(p).casefold().startswith("d:\\atlasruntime") for p in (root, receipt)):
        raise ValueError("FIXTURE_CANNOT_ACCESS_OPERATIONAL_RELEASE")
    return strict(encoded(value))


class NativeInstalledReleaseVerifier:
    domain = "WINDOWS_LOCAL"

    @contextmanager
    def open(self, reference):
        from scripts.build_release_candidate import source_bytes
        from scripts.install_verified_release import installed_readback
        from scripts.observation_runtime.personal_release_identity import (
            NativePersonalReleaseIdentity,
        )

        spec = validate_spec(reference, self.domain)
        path = Path(spec["receipt"])
        raw = source_bytes(path.parent, path.name, maximum_bytes=8 * 1024**2)
        if hashlib.sha256(raw).hexdigest() != spec["receipt_sha256"]:
            raise ValueError("SELECTION_RECEIPT_HASH_MISMATCH")
        receipt = strict(raw)
        if (
            receipt.get("source_commit") != spec["release"]
            or Path(receipt.get("release_path", "")) != Path(spec["root"])
            or receipt.get("artifact_digest") != spec["artifact_digest"]
            or any(
                receipt.get(k) is not False
                for k in (
                    "selected",
                    "financial_effects",
                    "provider_connections",
                    "operational_acceptance",
                )
            )
        ):
            raise ValueError("SELECTION_RECEIPT_BINDING")
        journal = path.with_suffix(".pending.jsonl")
        # Reuse safe ancestor/file admission rather than an unchecked tail open.
        # This local installation journal is not a financial/observation journal.
        journal_bytes = source_bytes(
            journal.parent, journal.name, maximum_bytes=128 * 1024**2
        )
        if not journal_bytes:
            raise ValueError("SELECTION_INSTALL_ACK_REQUIRED")
        ack = strict(journal_bytes.splitlines()[-1])
        if ack != {
            "stage": "UNSELECTED_CODE_INSTALL_VERIFIED",
            "receipt_sha256": spec["receipt_sha256"],
        }:
            raise ValueError("SELECTION_INSTALL_ACK_REQUIRED")
        owner = NativePersonalReleaseIdentity(
            receipt=receipt, artifact_digest=spec["artifact_digest"]
        )
        try:
            installed_readback(
                Path(spec["root"]), receipt, spec["artifact_digest"], timeout=180
            )
            yield receipt
            owner.outputs["."]._verify()
        finally:
            owner.close()


class ReleaseSelector:
    """The published record is both durable receipt and selected-version reference.

    Every reader and updater takes the same resource-bound lock. A staged tail
    without its atomic publication refuses all reads; no retry/repair/adoption.
    """

    def __init__(self, *, store=None, verifier=None, clock=None):
        if store is None or verifier is None or store.domain != verifier.domain:
            raise ValueError("SELECTION_ACCEPTED_DEPENDENCIES_REQUIRED")
        self.domain = store.domain
        if self.domain == "WINDOWS_LOCAL":
            from scripts.observation_runtime.personal_windows_clock import (
                LocalWindowsClock,
            )
            from scripts.release_selection_store import NativeSelectionStore

            if (
                type(store) is not NativeSelectionStore
                or type(verifier) is not NativeInstalledReleaseVerifier
                or type(clock) is not LocalWindowsClock
            ):
                raise ValueError("SELECTION_NATIVE_DEPENDENCIES_REQUIRED")
        elif self.domain != "DISPOSABLE":
            raise ValueError("SELECTION_DOMAIN_REQUIRED")
        self.store, self.verifier, self.clock = store, verifier, clock
        self._ports = store, verifier, clock, self.domain
        self._known = None

    def _history(self):
        if (self.store, self.verifier, self.clock, self.domain) != self._ports:
            raise ValueError("SELECTION_COMPONENT_SUBSTITUTION")
        rows = self.store.records()
        if len(rows) > MAX_RECORDS:
            raise ValueError("SELECTION_CAPACITY")
        previous, operations, known = None, set(), {}
        for index, row in enumerate(rows, 1):
            if (
                type(row) is not dict
                or set(row)
                != {
                    "schema",
                    "domain",
                    "revision",
                    "action",
                    "operation",
                    "previous",
                    "selected",
                    "restores",
                }
                or row["schema"] != "QD_RELEASE_SELECTION_RECEIPT_V1"
                or row["domain"] != self.domain
                or type(row["revision"]) is not int
                or row["revision"] != index
                or row["action"] not in ("SELECT", "ROLLBACK")
                or row["previous"] != previous
                or type(row["operation"]) is not str
                or not re.fullmatch("[0-9a-f]{32}", row["operation"])
                or row["operation"] in operations
            ):
                raise ValueError("SELECTION_CHAIN_OR_DUPLICATE")
            if row["selected"] is not None:
                validate_spec(row["selected"], self.domain)
            if row["action"] == "SELECT":
                if row["selected"] is None or row["restores"] is not None:
                    raise ValueError("SELECTION_TARGET_REQUIRED")
            else:
                restore = row["restores"]
                if restore == "BASELINE":
                    if index != 2 or row["selected"] is not None:
                        raise ValueError("SELECTION_UNVERIFIED_BASELINE")
                elif (
                    restore not in known
                    or row["selected"] != known[restore]["selected"]
                ):
                    raise ValueError("SELECTION_UNVERIFIED_ROLLBACK")
            operations.add(row["operation"])
            previous = digest(row)
            known[previous] = row
        pins = [digest(row) for row in rows]
        if self._known is not None and pins[: len(self._known)] != self._known:
            raise ValueError("SELECTION_OBSERVED_ROLLBACK_OR_REWRITE")
        self._known = pins
        return rows

    @contextmanager
    def lease(self, *, expected_head, expected_release=None):
        """Hold selection and immutable release identity through owned launch/Stop."""
        with self.store.locked():
            rows = self._history()
            if (
                not rows
                or digest(rows[-1]) != expected_head
                or rows[-1]["selected"] is None
            ):
                raise ValueError("SELECTION_CURRENT_HEAD_REQUIRED")
            if (
                expected_release is not None
                and rows[-1]["selected"]["release"] != expected_release
            ):
                raise ValueError("SELECTION_EXACT_RELEASE_REQUIRED")
            with self.verifier.open(rows[-1]["selected"]) as receipt:
                yield strict(encoded(rows[-1])), receipt

    def current(self):
        with self.store.locked():
            rows = self._history()
            if not rows:
                return {"head": None, "selected": None}
            row = rows[-1]
            if row["selected"] is not None:
                with self.verifier.open(row["selected"]):
                    pass
            return {"head": digest(row), "selected": row["selected"]}

    def change(self, grant=None, *, approved=False):
        if approved is not True:
            raise ValueError("EXPLICIT_CODE_SELECTION_AUTHORIZATION_REQUIRED")
        if (
            type(grant) is not dict
            or set(grant)
            != {
                "schema",
                "domain",
                "action",
                "operation",
                "expected_head",
                "target",
                "restores",
            }
            or grant["schema"] != "QD_CODE_SELECTION_AUTHORIZATION_V1"
            or grant["domain"] != self.domain
            or grant["action"] not in ("SELECT", "ROLLBACK")
            or type(grant["operation"]) is not str
            or not re.fullmatch("[0-9a-f]{32}", grant["operation"])
            or grant["expected_head"] is not None
            and (
                type(grant["expected_head"]) is not str
                or not re.fullmatch("[0-9a-f]{64}", grant["expected_head"])
            )
            or grant["restores"] is not None
            and (
                type(grant["restores"]) is not str
                or not re.fullmatch("[0-9a-f]{64}|BASELINE", grant["restores"])
            )
            or len(encoded(grant)) > 65536
        ):
            raise ValueError("EXACT_CODE_SELECTION_GRANT_REQUIRED")
        grant = strict(encoded(grant))
        with self.store.locked():
            rows = self._history()
            head = digest(rows[-1]) if rows else None
            if head != grant["expected_head"] or any(
                r["operation"] == grant["operation"] for r in rows
            ):
                raise ValueError("SELECTION_STALE_HEAD_OR_DUPLICATE")
            if len(rows) >= MAX_RECORDS:
                raise ValueError("SELECTION_CAPACITY_NO_RESET")
            target = grant["target"]
            if grant["action"] == "SELECT":
                validate_spec(target, self.domain)
                if grant["restores"] is not None:
                    raise ValueError("SELECTION_UNEXPECTED_RESTORE")
            else:
                known = {digest(r): r["selected"] for r in rows[:-1]}
                if grant["restores"] == "BASELINE" and len(rows) == 1:
                    restored = None
                elif grant["restores"] in known:
                    restored = known[grant["restores"]]
                else:
                    raise ValueError("SELECTION_ROLLBACK_EVIDENCE_REQUIRED")
                if target != restored:
                    raise ValueError("SELECTION_ROLLBACK_TARGET_MISMATCH")
            if rows and target == rows[-1]["selected"]:
                raise ValueError("SELECTION_NO_CHANGE")
            row = {
                "schema": "QD_RELEASE_SELECTION_RECEIPT_V1",
                "domain": self.domain,
                "revision": len(rows) + 1,
                "action": grant["action"],
                "operation": grant["operation"],
                "previous": head,
                "selected": target,
                "restores": grant["restores"],
            }

            def publish():
                if self.domain == "WINDOWS_LOCAL":
                    self.clock.require_operational(
                        "qd-code-selection-" + grant["operation"]
                    )
                self.store.publish(row)
                if self._history()[-1] != row:
                    raise ValueError("SELECTION_POST_PUBLICATION_UNKNOWN")

            if target is None:
                publish()
            else:
                with self.verifier.open(target):
                    publish()
            return {"head": digest(row), "receipt": strict(encoded(row))}


if __name__ == "__main__":
    raise SystemExit(
        "REFUSED: source-only selector; exact accepted native dependencies and operator grant required."
    )
