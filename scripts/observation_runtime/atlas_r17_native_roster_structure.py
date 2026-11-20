"""Pure R17 structural writer-roster shape bound to ORIGINAL live process.

No enrollment/financial acceptance; synthetic IDs intentionally start UNACCEPTED.
Actual caller must verify held original Job/PROCESS and original native roots.
"""
from __future__ import annotations

from copy import deepcopy

from app.services.perp_operational_contract import (
    WRITERS as HL_WRITERS,
)
from app.services.quality_dips_autonomous_enrollment import (
    WRITERS as QD_WRITERS,
)

from scripts.observation_runtime.atlas_independent_ntp_clock import (
    SOURCE as CLOCK_SOURCE,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    ROLES,
)
from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
    validate_selected_two_lane_rosters,
)
from scripts.observation_runtime.personal_r15_owned_job_activation import (
    require_exact_r15_preinception_roots,
)


def verify_unaccepted_selected_rosters(
        *, original, evidence, release_digest, original_image):
    """Only for an already independently verified live original PROCESS/Job."""
    if (type(evidence) is not dict
            or evidence.get("all_twelve_distinct_and_empty") is not True
            or evidence.get("native_root_ids_verified") != 12
            or evidence.get("existing_empty_root_namespaces") != 12
            or type(evidence.get("lanes")) is not dict
            or set(evidence["lanes"]) != {"QUALITY_DIPS", "HYPERLIQUID"}
            or type(original) is not dict
            or type(original_image) is not str
            or original.get("image") != original_image):
        raise ValueError("R17_UNACCEPTED_ROSTER_REAL_PREINCEPTION_REQUIRED")
    process = {"schema": "QD_OP_PROCESS_ID_V1", **original}
    plans = {}
    for lane, writer_roles, resource_schema, enroll_schema in (
        ("QUALITY_DIPS", QD_WRITERS, "QD_AUTO_NATIVE_ROOT_V4",
         "QD_AUTO_NATIVE_ENROLLMENT_V4"),
        ("HYPERLIQUID", HL_WRITERS, "PERP_AUTO_NATIVE_ROOT_V1",
         "PERP_AUTO_NATIVE_ENROLLMENT_V1"),
    ):
        info = evidence["lanes"][lane]
        entries = info["roots"]
        if (type(info) is not dict or type(entries) is not dict
                or set(entries) != set(ROLES)
                or type(info.get("epoch")) is not str):
            raise ValueError("R17_UNACCEPTED_ROSTER_ORIGINAL_ROOT_SCHEMA_REQUIRED")
        resources = {}
        for role in ROLES:
            actual = entries[role]
            if (type(actual) is not dict
                    or actual.get("native_identity_verified") is not True
                    or actual.get("existing_empty_namespace_verified") is not True
                    or type(actual.get("native_id")) is not list
                    or type(actual.get("path")) is not str):
                raise ValueError("R17_UNACCEPTED_ROSTER_ORIGINAL_ROOT_REQUIRED")
            resources[role] = {
                "schema":resource_schema,
                "path":actual["path"],
                "native_id":deepcopy(actual["native_id"]),
            }
        plans[lane] = {
            "schema":enroll_schema,
            "profile":"AUTONOMOUS_PAPER_ONLY_V1",
            "account_id":"UNACCEPTED_R17_STRUCTURAL_"+lane,
            "epoch":info["epoch"],
            "policy_digest":"0"*64,
            "inception_digest":"1"*64,
            "release_digest":release_digest,
            "resources":resources,
            "writers":{role:deepcopy(process) for role in writer_roles},
            "clock_source":CLOCK_SOURCE,
            "acceptance_id":"UNACCEPTED_R17_STRUCTURAL_"+lane,
        }
    qd, hl = plans["QUALITY_DIPS"], plans["HYPERLIQUID"]
    verified, q, h = validate_selected_two_lane_rosters(
        qd, hl, original_process=original,
        release_digest=release_digest, image=original_image,
    )
    roots = require_exact_r15_preinception_roots(q, h, evidence)
    if (len(verified) != 12 or len(set(verified.values())) != 1
            or len(roots) != 12
            or not q["acceptance_id"].startswith("UNACCEPTED_")
            or not h["acceptance_id"].startswith("UNACCEPTED_")):
        raise ValueError("R17_ORIGINAL_UNACCEPTED_ROSTER_PROOF_REFUSED")
    return {
        "schema":"ATLAS_R17_UNACCEPTED_TWELVE_ORIGINAL_PROCESS_ROSTERS_V1",
        "status":"EXACT_ORIGINAL_NATIVE_PROCESS_STRUCTURAL_ROSTER_ONLY",
        "original_process_writer_role_count":len(verified),
        "original_native_root_ids_bound":len(roots),
        "all_enrollments_intentionally_unaccepted":True,
        "financial_writer_enrolled":0,
        "native_account_files_created":0,
        "paper_start_authorized":False,
        "live_trading_authorized":False,
    }
