"""Pure review checks. No startup, selection, clock capability or financial port."""

import re

from scripts.release_selection import MAX_RECORDS, digest, validate_spec

APPLICATION = "2c039af29dfefd1df77e0caa3db3fdf5ed188118"
SUPPORT = "5b027d7dc0853975ee751c2c83145a9820a95da28041263b3585b56a4312eccc"
READY = "SOURCE_AND_DISPOSABLE_VALIDATED_READY_FOR_SEPARATE_AUTHORIZATION"
ORDER = ["CIM", "NETSTAT", "IP_HELPER", "STRICT_CIM_PROCESS_LAST"]
EVIDENCE_ROOT = r"D:\Work\Project Atlas\logs\diagnostics\qd-final-installed-nonfinancial-acceptance-v4-20261103"
BASELINE_HEAD = "c9bc240c11c148cd6c6f6dda7c6760aa2d2ac9547ee8c44847bf239b6382ffbc"


def selection_baseline(rows, *, domain="WINDOWS_LOCAL"):
    """Independently check already native-read records; never construct a writer.

    Uses the existing canonical digest/spec rules and checks the full chain,
    including historical rollback targets, without manufacturing a clock just
    to review immutable metadata. Native pair/ACL checks belong to the caller.
    """
    if domain not in ("WINDOWS_LOCAL", "DISPOSABLE") or type(rows) is not list:
        raise ValueError("EXACT_SELECTION_HISTORY_REQUIRED")
    if not 0 < len(rows) <= MAX_RECORDS - 2:
        raise ValueError("SELECTION_HISTORY_OR_TWO_RECORD_CAPACITY_REQUIRED")
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
            or row["domain"] != domain
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
            validate_spec(row["selected"], domain)
        if row["action"] == "SELECT":
            if row["selected"] is None or row["restores"] is not None:
                raise ValueError("SELECTION_TARGET_REQUIRED")
        else:
            restore = row["restores"]
            if restore == "BASELINE":
                if index != 2 or row["selected"] is not None:
                    raise ValueError("SELECTION_UNVERIFIED_BASELINE")
            elif (
                type(restore) is not str
                or restore not in known
                or row["selected"] != known[restore]["selected"]
            ):
                raise ValueError("SELECTION_UNVERIFIED_ROLLBACK")
        operations.add(row["operation"])
        previous = digest(row)
        known[previous] = row
    if rows[-1]["selected"] is not None:
        raise ValueError("INDEPENDENT_UNSELECTED_BASELINE_REQUIRED")
    return {"revision": len(rows), "head": previous, "selected": None}


def validate_scope(scope):
    """Review only. An exact scope is still not explicit execution permission."""
    if type(scope) is not dict:
        raise ValueError("EXACT_V4_REVIEW_SCOPE_REQUIRED")
    if any(
        type(scope.get(k)) is not dict
        for k in (
            "application",
            "baseline",
            "selection",
            "clock",
            "cleanup",
            "runtime_isolation",
            "cycle_limits",
        )
    ):
        raise ValueError("COMPLETE_TYPED_REVIEW_SECTIONS_REQUIRED")
    if (
        scope.get("schema") != "QD_FINAL_INSTALLED_NONFINANCIAL_ACCEPTANCE_SCOPE_V4"
        or scope.get("status") != READY
    ):
        raise ValueError("EXACT_V4_REVIEW_SCOPE_REQUIRED")
    if (
        scope.get("application_release") != APPLICATION
        or scope.get("support_id") != SUPPORT
    ):
        raise ValueError("EXACT_FROZEN_APPLICATION_AND_SUPPORT_REQUIRED")
    if (
        scope.get("evidence_root") != EVIDENCE_ROOT
        or scope.get("public_scope_document")
        != "docs/QD_FINAL_INSTALLED_NONFINANCIAL_ACCEPTANCE_SCOPE_V4_2026-11-03.json"
        or scope.get("support_destination") != "D:\\AtlasRuntime\\launchers\\" + SUPPORT
        or scope.get("support_control")
        != "D:\\AtlasRuntime\\support-installations\\" + SUPPORT
        or scope.get("application", {}).get("root")
        != "D:\\AtlasRuntime\\releases\\" + APPLICATION
    ):
        raise ValueError("EXACT_REVIEWED_PATHS_REQUIRED")
    if scope.get("limits") != {
        "seconds": 600,
        "entries": 8192,
        "accounted_bytes": 64 * 1024**2,
    }:
        raise ValueError("UNCHANGED_RESOURCE_LIMITS_REQUIRED")
    baseline = scope.get("baseline", {})
    if (
        type(baseline.get("revision")) is not int
        or not 0 < baseline["revision"] <= MAX_RECORDS - 2
        or baseline.get("selected", "MISSING") is not None
        or baseline.get("freshly_verified") is not True
        or type(baseline.get("head")) is not str
        or not re.fullmatch("[0-9a-f]{64}", baseline["head"])
    ):
        raise ValueError("INDEPENDENT_CURRENT_BASELINE_REQUIRED")
    # This particular reviewed package binds the independently reread r6.
    # A different future baseline requires a new package, never auto-adoption.
    if baseline["revision"] != 6 or baseline["head"] != BASELINE_HEAD:
        raise ValueError("CURRENT_REVIEWED_R6_PIN_REQUIRED")
    selection = scope.get("selection", {})
    if (
        selection.get("root") != r"D:\AtlasRuntime\selection"
        or selection.get("select_revision") != baseline["revision"] + 1
        or selection.get("rollback_revision") != baseline["revision"] + 2
        or selection.get("restores") != baseline["head"]
        or selection.get("final_selected", "MISSING") is not None
        or selection.get("select_only_release") != APPLICATION
    ):
        raise ValueError("EXACT_SELECTION_AND_KNOWN_HEAD_ROLLBACK_REQUIRED")
    clock = scope.get("clock", {})
    if (
        clock.get("maximum_uncertainty_ms") != 1000
        or clock.get("maximum_age_seconds") != 120
        or clock.get("expected_source") != "time.windows.com,0x9"
        or clock.get("required_service_state") != "Running"
        or clock.get("required_startup") != "Auto"
        or clock.get("fresh_at_selection") is not True
        or clock.get("configuration_changes") is not False
    ):
        raise ValueError("FRESH_UNCHANGED_CLOCK_CONTRACT_REQUIRED")
    if scope.get("cleanup", {}).get("reader_order") != ORDER:
        raise ValueError("V4_THREE_READERS_THEN_STRICT_PROCESS_REQUIRED")
    if scope.get("cleanup", {}).get("peer_eof_before_stop") is not True:
        raise ValueError("PEER_EOF_AND_CLIENT_CLOSE_REQUIRED")
    if any(
        scope["cleanup"].get(k) != v
        for k, v in {
            "maximum_cim_age_seconds": 2,
            "maximum_reader_age_seconds": 10,
            "maximum_collection_seconds": 5,
        }.items()
    ):
        raise ValueError("UNCHANGED_SOCKET_FRESHNESS_REQUIRED")
    isolation = scope["runtime_isolation"]
    if set(isolation) != {
        "providers",
        "financial_writers",
        "trading",
        "automatic_atlas_startup",
        "workspace_application_fallback",
    } or any(v is not False for v in isolation.values()):
        raise ValueError("EXACT_NONFINANCIAL_ISOLATION_REQUIRED")
    if scope.get("cycle_limits") != {
        "maximum_cycles": 2,
        "application_seconds": 120,
        "total_attempted_http_requests": 96,
        "readiness_seconds": 180,
        "browser_acknowledgement_seconds": 45,
        "complete_stop_seconds": 8,
    }:
        raise ValueError("UNCHANGED_CYCLE_DEADLINES_REQUIRED")
    if scope.get("approval_status") != "NOT_AUTHORIZED_FRESH_SINGLE_USE_GRANT_REQUIRED":
        raise ValueError("REVIEW_CANNOT_SELF_AUTHORIZE")
    return scope
