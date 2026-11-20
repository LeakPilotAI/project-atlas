"""Pure disposable continuation routing review; never a writable store adapter.

Consumes independently accepted cuts and retains the existing native limits.
No filesystem paths, provisioning, selector, runtime or default authority.
Operational codecs/current-map enrollment remain a separate boundary.
"""

import re

from app.investment.quality_dips_candidate_evidence import verified
from app.investment.quality_dips_operational_contract import native_id
from app.services.paper_financial_replay import body, digest, strict
from app.services.unified_research_sources import UnifiedResearchSources
from app.services.unified_writer_roster import EXCLUSIONS, ROLES

# Actual canonical-lane resources, not V2's synthetic auxiliary-root layout.
# Decision/coordination and global/session roles share their existing journals.
ROLE_RESOURCES = {role: role for role in ROLES}
ROLE_RESOURCES.update(
    QD_DECISION="QD_COORDINATION",
    PERP_FUNDING="PERP_SOURCE",
    PERP_MARK="PERP_SOURCE",
    SESSION_RESERVATION="GLOBAL_CUSTODY",
)
RESOURCES = frozenset(ROLE_RESOURCES.values())
GLOBAL = {"GLOBAL_CUSTODY"}
RESEARCH = {"QD_RANKING_PUBLICATION", "PERP_MARKET_PUBLICATION"}
IMAGE_RESOURCES = RESEARCH | {"QD_COORDINATION"}
LANES = {"QUALITY_DIPS": "USD", "HYPERLIQUID": "USDC"}
MAX_LOCAL = 128
MAX_SEGMENTS = 2  # Reuse the reviewed native disposable limit, not the offline16.


def _integer(value, low=0, high=256):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("BOUNDED_EXACT_INTEGER_REQUIRED")
    return value


def _digest(value):
    if type(value) is not str or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise ValueError("EXACT_CONTENT_DIGEST_REQUIRED")


def _bounded(value):
    encoded = body(value)
    if len(encoded.encode()) > 1024 * 1024:
        raise ValueError("BOUNDED_ROUTE_REVIEW_REQUIRED")
    return strict(encoded)


def _validate_cut(value, enrollments):
    if (
        type(value) is not dict
        or set(value)
        != {
            "schema",
            "execution_domain",
            "revision",
            "previous",
            "resources",
            "roles",
            "exclusions",
            "boundary",
        }
        or value["schema"] != "ATLAS_DISPOSABLE_RESOURCE_CUT_V1"
        or value["execution_domain"] != "DISPOSABLE"
        or value["roles"] != ROLE_RESOURCES
        or set(value["resources"]) != RESOURCES
        or set(value["exclusions"]) != set(EXCLUSIONS)
        or any(type(x) is not str or not x for x in value["exclusions"].values())
        or type(value["boundary"]) is not dict
        or any(type(x) is not bool for x in value["boundary"].values())
        or value["boundary"]
        != {
            "final": True,
            "flat": True,
            "drained": True,
            "resting": False,
            "unknown": False,
        }
    ):
        raise ValueError("COMPLETE_DISPOSABLE_FINAL_RESOURCE_CUT_REQUIRED")
    _integer(value["revision"], 0, 1)
    if value["revision"] == 0:
        if value["previous"] is not None:
            raise ValueError("ORIGINAL_CUT_PREDECESSOR_CONFLICT")
    else:
        _digest(value["previous"])
    roots = []
    for name, row in value["resources"].items():
        if set(row) != {
            "account",
            "epoch",
            "currency",
            "segments",
            "records",
            "state_digest",
            "revisions",
        }:
            raise ValueError("EXACT_RESOURCE_DESCRIPTOR_REQUIRED")
        lane = (
            "GLOBAL"
            if name in GLOBAL
            else "QUALITY_DIPS"
            if name.startswith("QD_")
            else "HYPERLIQUID"
        )
        account = (
            {k: e["account_id"] for k, e in enrollments.items()}
            if lane == "GLOBAL"
            else enrollments[lane]["account_id"]
        )
        epoch = (
            {k: e["epoch"] for k, e in enrollments.items()}
            if lane == "GLOBAL"
            else enrollments[lane]["epoch"]
        )
        currency = None if lane == "GLOBAL" else LANES[lane]
        if (row["account"], row["epoch"], row["currency"]) != (
            account,
            epoch,
            currency,
        ):
            raise ValueError("RESOURCE_ACCOUNT_EPOCH_OR_CURRENCY_CONFLICT")
        _digest(row["state_digest"])
        if (
            type(row["records"]) is not list
            or len(row["records"]) > MAX_LOCAL * MAX_SEGMENTS
        ):
            raise ValueError("BOUNDED_COMPLETE_RECORD_IDENTITIES_REQUIRED")
        for record in row["records"]:
            _digest(record)
        if len(set(row["records"])) != len(row["records"]):
            raise ValueError("DUPLICATE_RECORD_IDENTITY")
        revisions = row["revisions"]
        if set(revisions) != {"logical", "applied_financial", "input"}:
            raise ValueError("SEPARATE_REVISION_NAMESPACES_REQUIRED")
        if _integer(revisions["logical"]) != len(row["records"]):
            raise ValueError("GLOBAL_RECORD_COUNT_MISMATCH")
        for key in ("applied_financial", "input"):
            if revisions[key] is not None:
                _integer(revisions[key], 0, 2**63 - 1)
        if (name in RESEARCH) != (revisions["input"] is not None):
            raise ValueError("RESEARCH_INPUT_REVISION_NAMESPACE_REQUIRED")
        if name.endswith(("_PROJECTION", "_REPORT")):
            if revisions["applied_financial"] is None:
                raise ValueError("PROJECTION_OR_REPORT_SOURCE_REVISION_REQUIRED")
        elif revisions["applied_financial"] is not None:
            raise ValueError("UNEXPECTED_FINANCIAL_REVISION_ALIAS")
        segments = row["segments"]
        if type(segments) is not list or len(segments) != value["revision"] + 1:
            raise ValueError("EXACT_SEGMENT_LINEAGE_REQUIRED")
        offset = 0
        for index, segment in enumerate(segments):
            if set(segment) != {
                "root",
                "index",
                "base",
                "local",
                "initial_images",
                "previous",
            }:
                raise ValueError("EXACT_SEGMENT_DESCRIPTOR_REQUIRED")
            native_id(segment["root"])
            roots.append(body(segment["root"]))
            if (
                type(segment["index"]) is not int
                or segment["index"] != index
                or type(segment["base"]) is not int
                or segment["base"] != offset
            ):
                raise ValueError("SEGMENT_BASE_OR_INDEX_CONFLICT")
            local = _integer(segment["local"], 0, MAX_LOCAL)
            if type(segment["initial_images"]) is not int or segment[
                "initial_images"
            ] != (1 if name in IMAGE_RESOURCES else 0):
                raise ValueError("SOURCE_IMAGE_INITIAL_SLOT_REQUIRED")
            if local + segment["initial_images"] > MAX_LOCAL:
                raise ValueError("LOCAL_NATIVE_CAPACITY_EXCEEDED")
            expected = None if index == 0 else digest(segments[:index])
            if segment["previous"] != expected:
                raise ValueError("IMMUTABLE_PREDECESSOR_CONFLICT")
            offset += local
        if offset != revisions["logical"]:
            raise ValueError("LOCAL_GLOBAL_REVISION_CONFLICT")
    if len(roots) != len(set(roots)):
        raise ValueError("UNDECLARED_RESOURCE_OR_PREDECESSOR_ALIAS")
    for lane, prefix in (("QUALITY_DIPS", "QD"), ("HYPERLIQUID", "PERP")):
        financial = value["resources"][prefix + "_SOURCE"]["revisions"]["logical"]
        for suffix in ("_PROJECTION", "_REPORT"):
            if (
                value["resources"][prefix + suffix]["revisions"]["applied_financial"]
                != financial
            ):
                raise ValueError("FINAL_PROJECTION_REPORT_PARITY_REQUIRED")


def capacity_review(cut, demand, *, entries_remaining, bytes_remaining):
    """Explicit prospective costs including Stop, never runtime admission.

    Caller must supply all 11 physical resources; aliases are not double-counted.
    Existing runtime-specific position/order/settlement reserve checks still apply.
    """
    if (
        type(demand) is not dict
        or set(demand) != RESOURCES
        or set(cut["resources"]) != RESOURCES
    ):
        raise ValueError("COMPLETE_RESOURCE_CAPACITY_PLAN_REQUIRED")
    _integer(entries_remaining, 0, 2**63 - 1)
    _integer(bytes_remaining, 0, 2**63 - 1)
    totals = {"entries": 0, "bytes": 0}
    remaining = {}
    for name in sorted(RESOURCES):
        row = demand[name]
        if type(row) is not dict or set(row) != {"work", "stop", "entries", "bytes"}:
            raise ValueError("EXPLICIT_WORK_STOP_AND_STORAGE_COST_REQUIRED")
        for key in row:
            _integer(row[key], 1 if key == "stop" else 0, 2**63 - 1)
        # Costs must include both ordinary work and the complete final Stop.
        if (
            row["entries"] < row["work"] + row["stop"]
            or row["bytes"] < row["entries"] * 4096
        ):
            raise ValueError("CONSERVATIVE_ACCOUNTED_STORAGE_REQUIRED")
        segment = cut["resources"][name]["segments"][-1]
        slots = MAX_LOCAL - segment["initial_images"] - segment["local"]
        if row["work"] + row["stop"] > slots:
            raise ValueError("CAPACITY_RESERVED_FOR_STOP_NO_RESET")
        remaining[name] = slots - row["work"] - row["stop"]
        for key in totals:
            totals[key] += row[key]
    if totals["entries"] > entries_remaining or totals["bytes"] > bytes_remaining:
        raise ValueError("TOTAL_RESOURCE_BUDGET_EXCEEDED")
    return {
        "after_reserved_stop": remaining,
        "accounted": totals,
        "operational_admission": False,
    }


def review_disposable_route(
    *,
    research,
    predecessor,
    successor,
    demand,
    entries_remaining,
    bytes_remaining,
    authority,
):
    """Bind a proposed successor to acknowledged current sources without selecting it.

    Native identities and complete non-research cuts must be verified by the
    injected evidence owner. A digest or this review cannot supply that authority.
    """
    if type(research) is not UnifiedResearchSources or authority is None:
        raise ValueError("EXACT_CURRENT_SOURCE_PAIR_AND_REVIEW_AUTHORITY_REQUIRED")
    sources = research.read_current()
    if sources["execution_domain"] != "DISPOSABLE":
        raise ValueError("OPERATIONAL_ROUTING_NOT_AUTHORIZED")
    enrollments = {k: strict(body(v.enrollment)) for k, v in research.sources.items()}
    before, after, costs = map(_bounded, (predecessor, successor, demand))
    _validate_cut(before, enrollments)
    _validate_cut(after, enrollments)
    if (
        before["revision"] != 0
        or after["revision"] != 1
        or after["previous"] != digest(before)
    ):
        raise ValueError("ONE_ACKNOWLEDGED_SUCCESSOR_REVIEW_ONLY")
    for name in RESOURCES:
        old, new = before["resources"][name], after["resources"][name]
        if (
            {k: v for k, v in old.items() if k != "segments"}
            != {k: v for k, v in new.items() if k != "segments"}
            or new["segments"][:-1] != old["segments"]
            or new["segments"][-1]["local"] != 0
        ):
            raise ValueError("CARRY_STATE_RECORD_OR_REVISION_CHANGED")
    for lane, role in (
        ("QUALITY_DIPS", "QD_RANKING_PUBLICATION"),
        ("HYPERLIQUID", "PERP_MARKET_PUBLICATION"),
    ):
        producer = research.sources[lane]
        row = before["resources"][role]
        head = producer.archive.current()
        evidence = producer.archive.read_evidence(head)
        if (
            row["segments"][-1]["root"] != enrollments[lane]["root_id"]
            or row["revisions"]["logical"] != head["revision"]
            or row["state_digest"] != digest(evidence)
            or not row["records"]
            or row["records"][-1] != digest(evidence["packet"])
            or row["revisions"]["input"]
            != evidence["sources"]["current_input"]["input"]["input_revision"]
            or evidence["packet"] != sources["lanes"][lane]["packet"]
        ):
            raise ValueError("CURRENT_RESEARCH_ARCHIVE_CARRY_CONFLICT")
    capacity = capacity_review(
        after,
        costs,
        entries_remaining=entries_remaining,
        bytes_remaining=bytes_remaining,
    )
    context = {
        "before": before,
        "after": after,
        "sources": sources,
        "enrollments": enrollments,
        "capacity": capacity,
        "demand": costs,
        "budget": {
            "entries_remaining": entries_remaining,
            "bytes_remaining": bytes_remaining,
        },
    }
    frozen = body(context)
    now = research.clock()
    receipt = verified(
        authority.verify_boundary(context, now=now),
        digest(context),
        "ATLAS_DISPOSABLE_CONTINUATION_REVIEWED_V1",
    )
    if (
        receipt.get("execution_domain") != "DISPOSABLE"
        or body(context) != frozen
        or research.read_current() != sources
        or type(research.clock()) is not int
        or not 0 <= research.clock() - now <= 1
    ):
        raise ValueError("CONTINUATION_REVIEW_CUT_OR_AUTHORITY_CHANGED")
    return strict(
        body(
            {
                "schema": "ATLAS_CONTINUATION_ROUTING_REVIEW_V1",
                "predecessor": digest(before),
                "successor": digest(after),
                "capacity": capacity,
                "receipt": receipt,
                "operational_admission": False,
                "selection_performed": False,
            }
        )
    )
