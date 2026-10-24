"""Unenrolled operational read contracts; no issuer, writer or schema relabeling.

Structural validity authenticates nothing. Independent enrollment/current custody
and an accepted native operational-document verifier are mandatory dependencies.
Existing disposable schemas/financial engines remain unchanged.
"""
import ntpath
import re

from app.investment.quality_dips_read_capability import SelectedReadCapability
from app.services.paper_financial_replay import body, digest, number, strict, text

ENROLLMENT = "QD_OP_ENROLLMENT_V1"
ROLES = ("source", "projection", "report")


def exact(value, schema, fields):
    if type(value) is not dict or set(value) != {"schema", *fields} or value.get("schema") != schema:
        raise ValueError("OPERATIONAL_SCHEMA_MISMATCH:" + schema)


def positive(value, zero=False):
    if type(value) is not int or value < (0 if zero else 1):
        raise ValueError("OPERATIONAL_INTEGER_REQUIRED")


def hashed(value):
    if type(value) is not str or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise ValueError("OPERATIONAL_DIGEST_REQUIRED")


def native_id(value):
    if type(value) is not list or len(value) != 3:
        raise ValueError("OPERATIONAL_NATIVE_ID_REQUIRED")
    for part in value:
        positive(part, zero=True)


def binding(value, record_schema):
    exact(value, "QD_OP_FILE_BINDING_V1", {"native_id", "sha256", "record_schema"})
    native_id(value["native_id"])
    hashed(value["sha256"])
    if value["record_schema"] != record_schema:
        raise ValueError("OPERATIONAL_RECORD_VERSION_MISMATCH")


def process(value):
    exact(value, "QD_OP_PROCESS_ID_V1", {"pid", "creation_filetime", "image"})
    positive(value["pid"])
    positive(value["creation_filetime"])
    text(value["image"])


def fresh(value, now):
    for key in ("issued_at", "expires_at"):
        positive(value[key])
    if not value["issued_at"] <= now <= value["expires_at"] <= value["issued_at"] + 30:
        raise ValueError("OPERATIONAL_EVIDENCE_EXPIRED_OR_FUTURE")


def validate_enrollment(e):
    exact(e, ENROLLMENT, {"enrollment_id", "workstation_id", "account", "policy", "resources"})
    text(e["enrollment_id"])
    text(e["workstation_id"])
    a, p = e["account"], e["policy"]
    exact(a, "QD_OP_ACCOUNT_V1", {"account_id", "epoch", "currency", "hypothetical_opening_cash", "policy_digest"})
    text(a["account_id"])
    text(a["epoch"])
    exact(p, "QD_OP_ACCOUNT_POLICY_V1", {"scope", "universe", "max_entry_usd", "max_positions",
                                          "manual_only", "long_only", "scale_in", "overnight", "cost_assumptions"})
    if (a["currency"] != "USD" or a["hypothetical_opening_cash"] != "1000" or a["policy_digest"] != digest(p)
            or p["scope"] != "OPERATIONAL_ACCEPTANCE_REQUIRED"
            or p["universe"] != "ELIGIBLE_QD_RANKED_STOCKS_ETFS" or p["max_entry_usd"] != "100"
            or type(p["max_positions"]) is not int or p["max_positions"] != 1
            or p["manual_only"] is not True or p["long_only"] is not True
            or p["scale_in"] is not False or p["overnight"] is not True
            or p["cost_assumptions"] != "SYNTHETIC_2BPS_FEE_2BPS_SLIPPAGE_PER_SIDE"):
        raise ValueError("OPERATIONAL_ACCOUNT_POLICY_MISMATCH")
    if type(e["resources"]) is not dict or set(e["resources"]) != set(ROLES):
        raise ValueError("OPERATIONAL_RESOURCES_INCOMPLETE")
    ids, roots, paths = set(), set(), set()
    for role, resource in e["resources"].items():
        exact(resource, "QD_OP_RESOURCE_ID_V1", {"resource_id", "role", "root_path", "native_root"})
        text(resource["resource_id"])
        native_id(resource["native_root"])
        path = resource["root_path"]
        if (type(path) is not str or len(path) > 1024 or not re.match(r"^[A-Za-z]:\\", path)
                or any(part in (".", "..") for part in path.split("\\"))
                or any(char in path[2:] for char in (":", "%", "\x00", "/")) or resource["role"] != role):
            raise ValueError("OPERATIONAL_LOCAL_RESOURCE_REQUIRED")
        ids.add(resource["resource_id"])
        roots.add(tuple(resource["native_root"]))
        paths.add(ntpath.normcase(ntpath.normpath(path)))
    if min(len(ids), len(roots), len(paths)) != 3:
        raise ValueError("OPERATIONAL_RESOURCE_ALIAS")
    if any(left != right and right.startswith(left.rstrip("\\") + "\\") for left in paths for right in paths):
        raise ValueError("OPERATIONAL_RESOURCE_OVERLAP")


def validate_bundle(e, bundle, now, observed_process, host_id):
    """Pure validation of untrusted claims, never an acceptance decision."""
    validate_enrollment(e)
    positive(now)
    process(observed_process)
    exact(bundle, "QD_OP_READ_BUNDLE_V1", {"current", "clock", "authority", "session"})
    current = bundle["current"]
    exact(current, "QD_OP_CURRENT_V1", {"enrollment_digest", "generation", "revision", "acknowledged_revision",
                                        "status", "source", "projection", "report"})
    for key in ("generation", "revision", "acknowledged_revision"):
        positive(current[key], zero=key != "generation")
    if (current["enrollment_digest"] != digest(e) or current["status"] != "ACKNOWLEDGED"
            or current["revision"] != current["acknowledged_revision"] or current["revision"] > 128):
        raise ValueError("OPERATIONAL_CURRENT_UNVERIFIED")
    source = current["source"]
    exact(source, "QD_OP_SOURCE_PIN_V1", {"resource_id", "native_root", "revision", "inception", "records", "head_digest"})
    binding(source["inception"], "QD_OP_ACCOUNT_V1")
    if source["inception"]["sha256"] != digest(e["account"]):
        raise ValueError("OPERATIONAL_INCEPTION_MISMATCH")
    if type(source["records"]) is not list or len(source["records"]) != current["revision"]:
        raise ValueError("OPERATIONAL_SOURCE_INCOMPLETE")
    for record in source["records"]:
        binding(record, "QD_OP_FINANCIAL_RECORD_V1")
    record_ids = [source["inception"]["native_id"], *(record["native_id"] for record in source["records"])]
    if len({tuple(ident) for ident in record_ids}) != len(record_ids):
        raise ValueError("OPERATIONAL_DUPLICATE_RECORD_ID")
    head = source["records"][-1] if source["records"] else source["inception"]
    if source["head_digest"] != head["sha256"]:
        raise ValueError("OPERATIONAL_HEAD_MISMATCH")
    for role in ROLES:
        pin, resource = current[role], e["resources"][role]
        native_id(pin["native_root"])
        if role != "source":
            exact(pin, "QD_OP_" + role.upper() + "_PIN_V1", {"resource_id", "native_root", "revision", "source_pin_digest", "record"})
            binding(pin["record"], "QD_OP_" + role.upper() + "_DOCUMENT_V1")
            if pin["source_pin_digest"] != digest(source):
                raise ValueError("OPERATIONAL_SOURCE_PIN_MISMATCH")
        if (pin["resource_id"] != resource["resource_id"] or pin["native_root"] != resource["native_root"]
                or type(pin["revision"]) is not int or pin["revision"] != current["revision"]):
            raise ValueError("OPERATIONAL_PIN_RESOURCE_MISMATCH")
    clock, authority, session = (bundle[key] for key in ("clock", "authority", "session"))
    exact(clock, "QD_OP_CLOCK_V1", {"clock_id", "sequence", "issued_at", "expires_at"})
    text(clock["clock_id"])
    positive(clock["sequence"])
    fresh(clock, now)
    exact(session, "QD_OP_READ_SESSION_V1", {"enrollment_digest", "host_id", "process", "capabilities",
                                             "acceptance_id", "acceptance", "issued_at", "expires_at"})
    text(session["acceptance_id"])
    process(session["process"])
    if (session["enrollment_digest"] != digest(e) or session["host_id"] != host_id
            or re.fullmatch("[a-f0-9]{32}", host_id) is None
            or session["process"] != observed_process or session["capabilities"] != ["READ_ONLY"]
            or session["acceptance"] != "ACCEPTED_READ_ONLY"):
        raise ValueError("OPERATIONAL_SESSION_SCOPE_MISMATCH")
    fresh(session, now)
    exact(authority, "QD_OP_AUTHORITY_V1", {"issuer_id", "custody_id", "enrollment_digest", "current_digest",
                                            "clock_digest", "session_digest", "capabilities", "issued_at", "expires_at"})
    for key in ("issuer_id", "custody_id"):
        text(authority[key])
    if (authority["enrollment_digest"] != digest(e) or authority["current_digest"] != digest(current)
            or authority["clock_digest"] != digest(clock) or authority["session_digest"] != digest(session)
            or authority["capabilities"] != ["READ_ONLY"]):
        raise ValueError("OPERATIONAL_AUTHORITY_SCOPE_MISMATCH")
    fresh(authority, now)


class OperationalReadCapability:
    """Auth custody before resource consumption; no default native OP adapter.

    Custody lease(snapshot,now).check must independently authenticate enrollment,
    current high-water, issuer/clock/session and continuity. resources must expose
    read_operational and verify_operational; the old TEST_PIN reader is not used.
    Native verification/replay remains the accepted adapter's responsibility.
    """
    verify = SelectedReadCapability.verify

    def __init__(self, *, enrollment, authority, clock, port, process_identity, host_id):
        if any(value is None for value in (authority, clock, port)):
            raise ValueError("INDEPENDENT_OPERATIONAL_AUTHORITY_REQUIRED")
        self.enrollment = strict(body(enrollment))
        validate_enrollment(self.enrollment)
        self.authority, self.clock, self.port = authority, clock, port
        self.process, self.host_id = strict(body(process_identity)), host_id
        process(self.process)
        self.account = self.enrollment["account"]

    def read_committed(self, account_id, epoch):
        e = self.enrollment
        if (account_id, epoch) != (self.account["account_id"], self.account["epoch"]):
            raise ValueError("OPERATIONAL_ACCOUNT_MISMATCH")
        now = self.clock()
        positive(now)
        with self.authority.lease(strict(body(e)), now) as lease:
            bundle = strict(body(lease.snapshot))
            if lease.check(strict(body(bundle)), now) is not True:
                raise ValueError("INDEPENDENT_OPERATIONAL_AUTHENTICATION_REQUIRED")
            validate_bundle(e, bundle, now, self.process, self.host_id)
            if not callable(getattr(self.port, "read_operational", None)) or not callable(getattr(self.port, "verify_operational", None)):
                raise TypeError("OPERATIONAL_NATIVE_READ_ADAPTER_REQUIRED")
            current = bundle["current"]
            documents = strict(body(self.port.read_operational(strict(body(e)), strict(body(current)))))
            exact(documents, "QD_OP_DOCUMENTS_V1", {"projection", "report"})
            for role in ("projection", "report"):
                doc = documents[role]
                fields = {"enrollment_digest", "source_pin_digest", "revision", "state" if role == "projection" else "status"}
                exact(doc, "QD_OP_" + role.upper() + "_DOCUMENT_V1", fields)
                if (digest(doc) != current[role]["record"]["sha256"] or doc["enrollment_digest"] != digest(e)
                        or doc["source_pin_digest"] != digest(current["source"])
                        or type(doc["revision"]) is not int or doc["revision"] != current["revision"]):
                    raise ValueError("OPERATIONAL_DOCUMENT_PIN_MISMATCH")
            if self.port.verify_operational(strict(body(e)), strict(body(current)), strict(body(documents))) is not True:
                raise ValueError("OPERATIONAL_NATIVE_VERIFICATION_REQUIRED")
            state, report = documents["projection"]["state"], documents["report"]
            if (type(state.get("revision")) is not int or state["revision"] != current["revision"]
                    or report["status"] not in ("COMPLETE", "INCOMPLETE")
                    or min(number(state[k]) for k in ("cash", "costs")) < 0
                    or number(state["gross"]) - number(state["costs"]) != number(state["net"])
                    or type(state["positions"]) is not dict):
                raise ValueError("OPERATIONAL_SNAPSHOT_INCONSISTENT")
            end = self.clock()
            if type(end) is not int or end < now or lease.check(strict(body(bundle)), end) is not True:
                raise ValueError("OPERATIONAL_CUSTODY_CONTINUITY_LOST")
            validate_bundle(e, bundle, end, self.process, self.host_id)
            checked = self.clock()
            if type(checked) is not int or checked < end:
                raise ValueError("OPERATIONAL_CLOCK_DISCONTINUITY")
            validate_bundle(e, bundle, checked, self.process, self.host_id)
            return {"schema": "QD_COMMITTED_PROJECTION_V1", "account_id": account_id, "epoch": epoch,
                    "status": "ACKNOWLEDGED", "state": state, "observed_at": now,
                    "source_revision": current["revision"], "projection_revision": current["revision"],
                    "source_identity": {"root": current["source"]["native_root"], "pin_digest": digest(current),
                                        "generation": current["generation"]}, "policy_digest": digest(e["policy"]),
                    "report_status": report["status"], "report": report, "selection": None,
                    "inception": {"schema": "QD_SELECTED_INCEPTION_VIEW_V1", "account_id": account_id, "epoch": epoch,
                                  "policy_digest": digest(e["policy"]), "currency": "USD",
                                  "policy_schema": e["policy"]["schema"],
                                  "opening_cash": self.account["hypothetical_opening_cash"]}}
