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
# ONLY these fixed source-only codes may cross the credential/provider boundary.
# Untrusted provider exception text, URLs, credentials or HTTP payloads NEVER do.
IEX_PUBLIC_REFUSALS = frozenset((
    "IEX_NATIVE_INSTALLED_SELECTED_PORTS_REQUIRED",
    "IEX_NATIVE_BOUND_DATA_ONLY_CREDENTIAL_FILE_REQUIRED",
    "IEX_NATIVE_ORIGINAL_DATA_CREDENTIALS_REQUIRED",
    "IEX_NATIVE_ORIGINAL_JOB_CLOCK_OR_SELECTED_RELEASE_REQUIRED",
    "IEX_NATIVE_ORIGINAL_JOB_REVOKED_BEFORE_GET",
    "IEX_NATIVE_POST_GET_UTC_JOB_REVOKED",
    "IEX_NATIVE_ORIGINAL_JOB_CHANGED_AT_END",
    "IEX_NATIVE_HTTP_AUTH_OR_ENTITLEMENT_REFUSED",
    "IEX_NATIVE_NETWORK_OR_TLS_UNAVAILABLE",
    "IEX_NATIVE_HTTP_STATUS_REDIRECT_OR_TYPE_REFUSED",
    "IEX_NATIVE_HTTP_RESPONSE_BOUNDS_REFUSED",
    "IEX_NATIVE_JSON_NOT_ACCEPTED",
    "IEX_NATIVE_EXACT_QUOTE_ENVELOPE_REQUIRED",
    "IEX_NATIVE_IEX_EXCHANGE_AND_SHARES_REQUIRED",
    "IEX_NATIVE_SHARE_SIZES_MALFORMED",
    "IEX_NATIVE_QUOTE_EXCHANGE_NOT_IEX",
    "IEX_NATIVE_POSITIVE_SIDE_EXCHANGE_NOT_IEX",
    "IEX_NATIVE_DECIMAL_PRICE_REQUIRED",
    "IEX_NATIVE_NONNEGATIVE_FINITE_PRICE_REQUIRED",
    "IEX_NATIVE_CROSSED_QUOTE_REFUSED",
    "IEX_NATIVE_PROVIDER_UTC_TIMESTAMP_REQUIRED",
    "IEX_NATIVE_DUPLICATE_PROVIDER_FIELD",
    "IEX_NATIVE_NONFINITE_NUMBER",
    "IEX_TRADING_MUST_BE_DISABLED",
    "IEX_ONLY_FEED_REQUIRED",
    "IEX_CREDENTIALS_MISSING_OR_INVALID",
    "IEX_CONFIGURATION_UNAVAILABLE",
    "IEX_CONFIG_DUPLICATE",
))


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


def _selected_original_job_clock(*, owner, release, release_digest,
                                 verify_refresh=False, check_alpaca_iex_rest=False):
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
    if type(verify_refresh) is not bool or type(check_alpaca_iex_rest) is not bool:
        raise ValueError("ISOLATED_EXPLICIT_BOUND_SOURCE_MODE_REQUIRED")
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
        iex_result = None
        if check_alpaca_iex_rest:
            # This newly authored *diagnostic* is uninstalled workspace code.
            # Load it by exact path as READ-ONLY research, never as a selected
            # native financial source/issuer or a member of installed R20.
            from importlib.util import module_from_spec, spec_from_file_location

            file = Path(
                "D:/Work/Project Atlas/scripts/observation_runtime/"
                "atlas_r20_native_iex_latest_readonly.py"
            )
            if (not file.is_file() or file.is_symlink() or file.is_junction()):
                raise ValueError("ISOLATED_IEX_DIAGNOSTIC_EXACT_WORKSPACE_FILE_REQUIRED")
            module_spec = spec_from_file_location("atlas_r20_data_only_iex", file)
            if module_spec is None or module_spec.loader is None:
                raise ValueError("ISOLATED_IEX_SOURCE_ONLY_MODULE_NOT_LOADABLE")
            module = module_from_spec(module_spec)
            module_spec.loader.exec_module(module)
            iex_result = module.audit_owned_iex(
                owner=owner, clock=clock, runtime_id=runtime_id,
                release_digest=release_digest,
            )
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
            "alpaca_iex_rest_source_only": iex_result,
            "continuous_financial_clock_lease_accepted": False,
        }
    finally:
        if clock is not None:
            clock.revoke()


def run_isolated_readonly(*, check_independent_ntp=False, verify_ntp_refresh=False,
                          check_alpaca_iex_rest=False):
    if type(check_independent_ntp) is not bool:
        raise ValueError("ISOLATED_EXPLICIT_NTP_CHECK_BOOLEAN_REQUIRED")
    if (type(verify_ntp_refresh) is not bool
            or verify_ntp_refresh and not check_independent_ntp):
        raise ValueError("ISOLATED_EXPLICIT_NTP_REFRESH_REQUIRES_NTP_CHECK")
    if (type(check_alpaca_iex_rest) is not bool
            or check_alpaca_iex_rest and not check_independent_ntp):
        raise ValueError("ISOLATED_IEX_REQUIRES_ORIGINAL_JOB_NTP_CHECK")
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
            check_alpaca_iex_rest=check_alpaca_iex_rest,
        ) if check_independent_ntp else {
            "two_peer_runtime_utc_verified": False,
            "two_native_clock_samples_verified": False,
            "one_real_ntp_refresh_verified": False,
            "alpaca_iex_rest_source_only": None,
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
    parser.add_argument("--check-alpaca-iex-rest", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute_isolated_readonly:
        parser.error("Explicit isolated native source-only preflight flag required")
    try:
        print(json.dumps(run_isolated_readonly(
            check_independent_ntp=args.check_independent_ntp,
            verify_ntp_refresh=args.verify_ntp_refresh,
            check_alpaca_iex_rest=args.check_alpaca_iex_rest,
        ), sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
        safe = (
            str(exc) if isinstance(exc, ValueError)
            and str(exc) in IEX_PUBLIC_REFUSALS
            else "ORIGINAL_NATIVE_BOUNDARY_OR_SOURCE_REFUSED"
        )
        print(json.dumps({
            "schema": SCHEMA,
            "status": "ORIGINAL_NATIVE_PREINCEPTION_STRUCTURAL_REFUSED",
            "sanitized_reason": safe,
            "financial_native_files_written": False,
            "paper_startup_authorized": False,
            "live_trading_authorized": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
