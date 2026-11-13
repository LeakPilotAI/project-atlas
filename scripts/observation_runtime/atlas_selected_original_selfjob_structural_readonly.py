"""Isolated selected-native original Job/5+7 writer-structure preflight (READ ONLY).

This is NOT financial enrollment. It NEVER creates operator acceptance, account
journals, provider sessions, money, trading grants or persistent financial files.
The two ephemeral in-memory synthetic enrollment digests are intentionally
unaccepted and may not be reused to open an account.

Must run as a separate selected native Windows Python process with both installed
source roots on PYTHONPATH. Job self-containment would terminate its own process
if the last Job handle were closed while running; never embed in an app shell.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import sys
import time
from pathlib import Path

SCHEMA = "ATLAS_SELECTED_ORIGINAL_SELF_JOB_PREINCEPTION_READONLY_V1"


def _synthetic_structural_enrollment(
    lane, writer_roles, schema, selected_digest, root_record, original_identity,
):
    """Validate real root/role shapes with explicitly UNACCEPTED synthetic policy."""
    from app.services.perp_operational_contract import (
        validate_enrollment as validate_hl,
    )
    from app.services.quality_dips_autonomous_enrollment import (
        validate_enrollment as validate_qd,
    )

    short = "QD" if lane == "QUALITY_DIPS" else "HL"
    root_schema = (
        "QD_AUTO_NATIVE_ROOT_V4"
        if lane == "QUALITY_DIPS" else "PERP_AUTO_NATIVE_ROOT_V1"
    )
    data = {
        "schema": schema,
        "profile": "AUTONOMOUS_PAPER_ONLY_V1",
        "account_id": f"UNENROLLED_STRUCTURAL_{short}",
        "epoch": root_record["epoch"],
        "policy_digest": hashlib.sha256(
            ("SYNTHETIC_UNENROLLED_POLICY_" + short).encode()
        ).hexdigest(),
        "inception_digest": hashlib.sha256(
            ("SYNTHETIC_UNENROLLED_INCEPTION_" + short).encode()
        ).hexdigest(),
        "release_digest": selected_digest,
        "resources": {
            role: {
                "schema": root_schema,
                "path": entry["path"],
                "native_id": entry["native_id"],
            } for role, entry in root_record["roots"].items()
        },
        "writers": {
            role: {"schema": "QD_OP_PROCESS_ID_V1", **original_identity}
            for role in writer_roles
        },
        "clock_source": "VERSION_SAFE_INDEPENDENT_NTP_OPERATOR_CLOCK_V1",
        "acceptance_id": f"UNACCEPTED_STRUCTURAL_{short}",
    }
    return validate_qd(data) if lane == "QUALITY_DIPS" else validate_hl(data)


def _selected_original_job_clock(*, owner, release, release_digest, verify_refresh=False):
    """Two actual original public NTP peers under this retained native Job.

    No persistent clock grant, caller-replaceable network ports, time changes,
    provider trading calls or native financial file publication.
    """
    from scripts.observation_runtime.personal_version_safe_release_clock import (
        NativeVersionSafePaperOperatorClock,
        require_version_safe_release_digest,
    )

    expected = (
        release / "scripts/observation_runtime/personal_version_safe_release_clock.py"
    ).resolve()
    if (Path(inspect.getfile(NativeVersionSafePaperOperatorClock)).resolve() != expected
            or owner.verify_still_running() is not True):
        raise ValueError("ISOLATED_SELECTED_NATIVE_CLOCK_AND_JOB_REQUIRED")
    if type(verify_refresh) is not bool:
        raise ValueError("ISOLATED_EXPLICIT_REFRESH_BOUND_REQUIRED")
    runtime_id = "atlas-original-self-job-two-peer-source-only"
    clock = None
    try:
        clock = NativeVersionSafePaperOperatorClock(runtime_id=runtime_id)
        if (clock.require_operational(runtime_id) is not clock
                or require_version_safe_release_digest(
                    clock=clock, runtime_id=runtime_id,
                    release_digest=release_digest,
                ) is not True):
            raise ValueError("ISOLATED_ORIGINAL_NTP_RELEASE_BINDING_REFUSED")
        refresh_start = clock._clock._last_refresh
        first = clock.runtime_sample()
        if clock.verify_runtime_sample(first) is not True:
            raise ValueError("ISOLATED_FIRST_RUNTIME_UTC_REFUSED")
        time.sleep(0.25)
        second = clock.runtime_sample()
        if (clock.verify_runtime_sample(second) is not True
                or owner.verify_still_running() is not True
                or clock.require_operational(runtime_id) is not clock):
            raise ValueError("ISOLATED_NTP_CLOCK_OR_ORIGINAL_JOB_CHANGED")
        refresh_verified = False
        if verify_refresh:
            # Provider clock uses fixed 45s NTP refresh. This holds no active
            # orders, uses one sleeping child and fails closed if either NTP
            # peer or the original in-process native Job disappears.
            time.sleep(46)
            updated = clock.runtime_sample()
            if (clock.verify_runtime_sample(updated) is not True
                    or clock._clock._last_refresh <= refresh_start
                    or owner.verify_still_running() is not True
                    or clock.require_operational(runtime_id) is not clock):
                raise ValueError("ISOLATED_ONE_ORIGINAL_NTP_REFRESH_REFUSED")
            refresh_verified = True
        evidence = clock._clock.evidence
        if (evidence.get("domain") != "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS"
                or evidence.get("financial_authority") is not False
                or type(evidence.get("bound_ms")) is not int
                or not 0 <= evidence["bound_ms"] <= 1000
                or type(evidence.get("peer_difference_ms")) is not int
                or not 0 <= evidence["peer_difference_ms"] <= 250):
            raise ValueError("ISOLATED_TWO_PEER_NTP_PROOF_REFUSED")
        return {
            "two_peer_runtime_utc_verified": True,
            "utc_uncertainty_bound_ms": evidence["bound_ms"],
            "ntp_peer_difference_ms": evidence["peer_difference_ms"],
            "two_native_clock_samples_verified": True,
            "one_real_ntp_refresh_verified": refresh_verified,
            "continuous_financial_clock_lease_accepted": False,
        }
    finally:
        if clock is not None:
            clock.revoke()


def run_isolated_readonly(*, check_independent_ntp=False, verify_ntp_refresh=False):
    if type(check_independent_ntp) is not bool:
        raise ValueError("ISOLATED_EXPLICIT_NTP_CHECK_BOOLEAN_REQUIRED")
    if (type(verify_ntp_refresh) is not bool
            or verify_ntp_refresh and not check_independent_ntp):
        raise ValueError("ISOLATED_EXPLICIT_NTP_REFRESH_REQUIRES_NTP_CHECK")
    from app.services.perp_operational_contract import WRITERS as HL_WRITERS
    from app.services.quality_dips_autonomous_enrollment import WRITERS as QD_WRITERS

    from scripts.observation_runtime.personal_existing_native_resource_evidence import (
        inspect_two_lane_native_roots,
    )
    from scripts.observation_runtime.personal_native_original_self_job import (
        create_original_self_job,
    )
    from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
        RetainedSelectedNativeOwnerPreflight,
    )
    from scripts.observation_runtime.personal_version_safe_release_clock import (
        SELECTOR_NATIVE,
        admit_version_safe_clock_source,
    )
    from scripts.observation_runtime.quality_dips_read_service import observe_self
    from scripts.release_selection_store import NativeSelectionStore

    release = Path(sys.executable).resolve().parent.parent
    release_parent = Path("D:/AtlasRuntime/releases").resolve()
    expected = (
        release / "scripts/observation_runtime/personal_native_selected_owned_job_preflight.py"
    ).resolve()
    if (
        release.parent != release_parent
        or not release.name.isalnum()
        or len(release.name) != 40
        or Path(inspect.getfile(RetainedSelectedNativeOwnerPreflight)).resolve() != expected
    ):
        raise ValueError("ISOLATED_SELECTED_NATIVE_CODE_AND_IMAGE_REQUIRED")

    store = NativeSelectionStore(
        root=r"D:\AtlasRuntime\selection", native_root=list(SELECTOR_NATIVE)
    )
    try:
        with store.locked():
            _, spec = admit_version_safe_clock_source(
                source_file=(
                    release
                    / "scripts/observation_runtime/personal_version_safe_release_clock.py"
                ),
                records=store.records(),
            )
    finally:
        store.close()
    if spec["release"] != release.name:
        raise ValueError("ISOLATED_CURRENT_SELECTED_RELEASE_REQUIRED")

    roots = inspect_two_lane_native_roots()
    if (
        roots["all_twelve_distinct_and_empty"] is not True
        or roots["native_root_total"] != 12
        or roots["native_root_ids_verified"] != 12
        or roots["existing_empty_root_namespaces"] != 12
    ):
        raise ValueError("ISOLATED_UNWRITTEN_TWELVE_NATIVE_ROOTS_REQUIRED")

    original = create_original_self_job()
    identity = observe_self()
    if original.verify() is not True:
        raise ValueError("ISOLATED_NATIVE_SELF_JOB_FAILED")
    qd = _synthetic_structural_enrollment(
        "QUALITY_DIPS", QD_WRITERS, "QD_AUTO_NATIVE_ENROLLMENT_V4",
        spec["artifact_digest"], roots["lanes"]["QUALITY_DIPS"], identity,
    )
    hl = _synthetic_structural_enrollment(
        "HYPERLIQUID", HL_WRITERS, "PERP_AUTO_NATIVE_ENROLLMENT_V1",
        spec["artifact_digest"], roots["lanes"]["HYPERLIQUID"], identity,
    )
    owner = original.selected_two_account_owner(
        qd=qd, perp=hl, release_digest=spec["artifact_digest"]
    )
    if (
        type(owner) is not RetainedSelectedNativeOwnerPreflight
        or owner._phase != "PREINCEPTION"
        or owner._identity != identity
        or owner.verify_still_running() is not True
        or owner.require_exact_roster(qd=qd, perp=hl) is not True
    ):
        raise ValueError("ISOLATED_IN_PROCESS_SELECTED_WRITER_OWNER_NOT_PROVEN")

    clock_evidence = (
        _selected_original_job_clock(
            owner=owner, release=release,
            release_digest=spec["artifact_digest"],
            verify_refresh=verify_ntp_refresh,
        ) if check_independent_ntp else {
            "two_peer_runtime_utc_verified": False,
            "two_native_clock_samples_verified": False,
            "one_real_ntp_refresh_verified": False,
            "continuous_financial_clock_lease_accepted": False,
        }
    )

    return {
        "schema": SCHEMA,
        **clock_evidence,
        "status": "ORIGINAL_NATIVE_PREINCEPTION_STRUCTURAL_PASS_ONLY",
        "selected_code_release": spec["release"],
        "original_self_job_and_process_verified": True,
        "native_root_count": 12,
        "verified_original_writer_roles": {
            "QUALITY_DIPS": len(QD_WRITERS),
            "HYPERLIQUID": len(HL_WRITERS),
        },
        "selected_image_and_artifact_verified": True,
        "financial_native_files_written": False,
        "operator_enrollment_accepted": False,
        "operator_activation_verified": False,
        "quality_dips_operational_source_issuer_accepted": False,
        "financial_account_inception_verified": False,
        "paper_startup_authorized": False,
        "live_trading_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-isolated-readonly", action="store_true")
    parser.add_argument("--check-independent-ntp", action="store_true")
    parser.add_argument("--verify-ntp-refresh", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute_isolated_readonly:
        parser.error("Explicit isolated native source-only preflight flag required")
    try:
        print(json.dumps(run_isolated_readonly(
            check_independent_ntp=args.check_independent_ntp,
            verify_ntp_refresh=args.verify_ntp_refresh,
        ), sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, RuntimeError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "ORIGINAL_NATIVE_PREINCEPTION_STRUCTURAL_REFUSED",
            "financial_native_files_written": False,
            "paper_startup_authorized": False,
            "live_trading_authorized": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
