"""R15 immutable CODE-ONLY native installer, separate one-shot approval required.

This is the exact successor of the approved R14 low-impact installer, NOT an
install/selection entitlement. No default install command, no financial startup,
no real provider, no account creation. A failed partial install is retained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path

from scripts.atlas_r13_low_impact_installer import LowImpactEnvelope, _exact_bytes
from scripts.atlas_r14_low_impact_installer import (
    CHECK_EVERY, PACE_EVERY, PAUSE_SECONDS, MAX_SECONDS,
    NTP_ADMISSION_REFRESH_SECONDS, HOST_ADMISSION_REFRESH_SECONDS,
)
from scripts.install_verified_release import (
    installation_target, installed_readback, write_new_json,
)
from scripts.native_install_candidate import _copy_prepared_code
from scripts.observation_runtime.atlas_r15_code_install_plan_preflight import (
    SOURCE_COMMIT, ARCHIVE_SHA, INVENTORY_SHA, TARGET, RECEIPT,
    ROOT, inspect as inspect_plan, require_new_native_target,
)
from scripts.observation_runtime.atlas_r14_selected_paper_readiness import (
    collect_selected_reference,
)
from scripts.observation_runtime.native_install_host_admission import (
    require_code_install_host_ready,
)

APPROVAL = ROOT / "logs/diagnostics/atlas-r15-code-only-native-install-one-shot-approval.json"
APPROVAL_SHA256 = None  # Cannot become an install grant from chat or old R14 consent.
SCOPE = "INSTALL_EXACT_R15_UNSELECTED_CODE_ONLY_NO_FINANCIAL_START"
OPERATION = "APPROVE_ONE_R15_CODE_ONLY_NATIVE_INSTALL"
CLOCK_IDENTITY = "atlas-r15-code-only-install-" + SOURCE_COMMIT


def validate_operator_decision(record, *, sid):
    required = {
        "schema","decision","scope","source_commit","source_archive_sha256",
        "source_inventory_sha256","target","receipt","dependency_inventory_sha256",
        "selected_r14_head","installer_source_sha256", "operator_sid","one_shot","selection_allowed",
        "financial_authority","provider_access","paper_accounts",
        "startup_authorized","paper_orders_authorized","live_orders_authorized",
    }
    from scripts.observation_runtime.atlas_r15_code_install_plan_preflight import (
        DEPENDENCY_INVENTORY_SHA256, R14_HEAD,
    )
    if (type(record) is not dict or set(record)!=required
            or type(sid) is not str or not sid.startswith("S-1-")
            or record.get("schema")!="ATLAS_R15_CODE_ONLY_NATIVE_INSTALL_APPROVAL_V1"
            or record.get("decision")!=OPERATION
            or record.get("scope")!=SCOPE
            or record.get("source_commit")!=SOURCE_COMMIT
            or record.get("source_archive_sha256")!=ARCHIVE_SHA
            or record.get("source_inventory_sha256")!=INVENTORY_SHA
            or record.get("dependency_inventory_sha256")!=DEPENDENCY_INVENTORY_SHA256
            or record.get("target")!=str(TARGET)
            or record.get("receipt")!=str(RECEIPT)
            or record.get("selected_r14_head")!=R14_HEAD
            or record.get("installer_source_sha256")!=hashlib.sha256(
                Path(__file__).read_bytes()).hexdigest()
            or record.get("operator_sid")!=sid
            or record.get("one_shot") is not True
            or any(record.get(key) is not False for key in (
                "selection_allowed","financial_authority","provider_access",
                "paper_accounts","startup_authorized","paper_orders_authorized",
                "live_orders_authorized"))):
        raise ValueError("R15_EXACT_SID_BOUND_ONE_SHOT_INSTALL_DECISION_REQUIRED")
    return record


def require_separate_consent():
    """Read the exact reviewed, SID-bound one-time approval. Never create it."""
    if type(APPROVAL_SHA256) is not str or not re.fullmatch(r"[0-9a-f]{64}",APPROVAL_SHA256):
        raise ValueError("R15_FRESH_ONE_SHOT_CODE_INSTALL_APPROVAL_NOT_PINNED")
    from scripts.volume_inspector.windows_output import current_sid
    record = json.loads(_exact_bytes(APPROVAL,APPROVAL_SHA256,max_bytes=4096))
    return validate_operator_decision(record,sid=current_sid())


def _r14_unchanged():
    """Native 13-record selection replay is independent of prior R12 head."""
    selected=collect_selected_reference()
    if (selected.get("selected_release")!="7ff9d3dba2eabe110f843c13efac49464805de2a"
            or selected.get("revision")!=13
            or selected.get("financial_authority") is not False):
        raise ValueError("R15_INSTALL_SELECTED_R14_IDENTITY_CHANGED")
    return True


def inspect():
    """No native mutation, OS clock, external NTP, credentials or provider I/O."""
    with LowImpactEnvelope(
        check_every=CHECK_EVERY,pace_every=PACE_EVERY,pause_seconds=PAUSE_SECONDS,
        max_seconds=MAX_SECONDS,
    ) as envelope:
        plan=inspect_plan()
        envelope.tick()
    return {
        "schema":"ATLAS_R15_CODE_ONLY_LOW_IMPACT_INSTALLER_PREVIEW_V1",
        "status":"READY_FOR_SEPARATE_EXACT_INSTALL_APPROVAL_NOT_APPROVED",
        "source_commit":SOURCE_COMMIT,
        "source_archive_sha256":ARCHIVE_SHA,
        "planned_native_files":plan["planned_native_files"],
        "planned_native_bytes":plan["planned_native_bytes"],
        "new_install_target":str(TARGET),
        "operator_approval_pinned":False,
        "idle_priority_required":True,
        "independent_180_second_two_peer_clock_required":True,
        "single_native_copy_and_child_readback_required":True,
        "separate_future_code_selection_required":True,
        "installation_authorized":False,
        "installed":False,
        "selection_authorized":False,
        "provider_access":False,
        "paper_accounts":False,
        "startup_authorized":False,
        "paper_orders_authorized":False,
        "live_orders_authorized":False,
    }


def _admit(*, clock, guard):
    """Both CPU admission and qualified UTC continuity, never Windows time."""
    guard.tick()
    now=guard.monotonic()
    last=getattr(guard,"last_ntp_admission",None)
    if (last is None or now<last
            or now-last >= NTP_ADMISSION_REFRESH_SECONDS
            or guard.checks%CHECK_EVERY == 0):
        clock.require_operational(CLOCK_IDENTITY)
        guard.last_ntp_admission=guard.monotonic()
    host=getattr(guard,"last_host_admission",None)
    if (host is None or now<host
            or now-host >= HOST_ADMISSION_REFRESH_SECONDS):
        require_code_install_host_ready(TARGET.parent)
        _r14_unchanged()
        # Once the create-only intent journal exists, the original empty
        # target preflight MUST NOT be repeated: it would reject our own
        # journal before the native copier creates its first directory.
        # This admission is an active-custody check, not a fresh-install gate.
        guard.last_host_admission=guard.monotonic()
    return True


def final_native_install_ack(receipt):
    """Existing non-R14 native selector contract; emit BEFORE final receipt.

    The installed R15 source zip uses the already-frozen generic verifier,
    which expects the trailing UNSELECTED_CODE_INSTALL_VERIFIED record.
    Produce its SHA from the exact create-only receipt serialization.
    """
    if (type(receipt) is not dict
            or receipt.get('source_commit')!=SOURCE_COMMIT
            or receipt.get('release_path')!=str(TARGET)
            or receipt.get('selected') is not False
            or receipt.get('financial_effects') is not False
            or receipt.get('provider_connections') is not False
            or receipt.get('operational_acceptance') is not False
            or receipt.get('stage')!='D_RUNTIME_LAYOUT_VERIFIED'
            or type(receipt.get('artifact_digest')) is not str):
        raise ValueError('R15_FINAL_NONFINANCIAL_RECEIPT_REQUIRED')
    raw=json.dumps(receipt,sort_keys=True,allow_nan=False).encode()
    return {'stage':'UNSELECTED_CODE_INSTALL_VERIFIED',
            'receipt_sha256':hashlib.sha256(raw).hexdigest()}


def _remaining_timeout(guard):
    guard.tick()
    remaining=guard.max_seconds-(guard.monotonic()-guard.started)
    if remaining<=35:
        raise ValueError("R15_INSTALL_NATIVE_READBACK_DEADLINE_NO_RETRY")
    return min(120,remaining-5)


def install(*, execute_approved=False, clock=None):
    """Single create-only native install, after separately pinned one-shot scope."""
    if execute_approved is not True:
        raise ValueError("R15_EXPLICIT_CODE_ONLY_INSTALL_EXECUTION_REQUIRED")
    require_separate_consent()
    require_code_install_host_ready(TARGET.parent)
    from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock
    if type(clock) is not IndependentNtpClock:
        raise ValueError("R15_GENUINE_INDEPENDENT_NTP_CLOCK_REQUIRED")
    clock.require_operational(CLOCK_IDENTITY)
    # A previous short NTP probe is NOT enough for native financial-code install.
    from scripts.install_version_safe_candidate import _qualify_native_clock_180s
    _qualify_native_clock_180s(clock,CLOCK_IDENTITY)
    require_separate_consent()
    require_code_install_host_ready(TARGET.parent)
    with LowImpactEnvelope(
        check_every=CHECK_EVERY,pace_every=PACE_EVERY,pause_seconds=PAUSE_SECONDS,
        max_seconds=MAX_SECONDS,
    ) as guard:
        review=inspect_plan()
        guard.tick()
        require_separate_consent()
        _r14_unchanged()
        require_new_native_target(TARGET)
        from scripts.atlas_r14_low_impact_installer import (
            DEPENDENCY,DEPENDENCY_RECEIPT_SHA256,DEPENDENCY_INVENTORY_SHA256,
        )
        from scripts.native_install_plan import prepare_install_inputs
        dependency=json.loads(_exact_bytes(
            DEPENDENCY,DEPENDENCY_RECEIPT_SHA256,max_bytes=16*1024*1024))
        prepared=prepare_install_inputs(
            archive=ROOT/"logs/diagnostics/atlas-r15-source-only-20261110-r01/package/atlas-source.zip",
            archive_sha256=ARCHIVE_SHA,source_commit=SOURCE_COMMIT,
            inventory_digest=INVENTORY_SHA,dependency_receipt=dependency,
            dependency_digest=DEPENDENCY_INVENTORY_SHA256,require_tracked=True)
        if (len(prepared["runtime"])!=960
                or len(prepared["dependencies"])!=9566
                or len(prepared["names"])!=review["planned_native_files"]
                or prepared["total"]!=review["planned_native_bytes"]):
            raise ValueError("R15_EXACT_REVIEWED_INSTALL_PLAN_CHANGED")
        guard.tick()
        clock.require_operational(CLOCK_IDENTITY)
        def admission():
            return _admit(clock=clock,guard=guard)
        admission()
        # A create-only intent is the irreversible first step. Any failure
        # afterwards preserves evidence; never retry a partial installation.
        journal=RECEIPT.with_suffix(".pending.jsonl")
        write_new_json(journal,{
            "schema":"ATLAS_R15_UNSELECTED_CODE_INSTALL_INTENT_V1",
            "source_commit":SOURCE_COMMIT,
            "archive_sha256":ARCHIVE_SHA,
            "target":str(TARGET),
            "selection_allowed":False,"financial_authority":False,
            "provider_access":False,"startup_authorized":False,
        })
        def event(row):
            with journal.open("ab") as stream:
                stream.write(b"\n"+json.dumps(row,sort_keys=True).encode())
                stream.flush()
                os.fsync(stream.fileno())
        try:
            copied=_copy_prepared_code(
                destination=TARGET,archive_sha256=ARCHIVE_SHA,
                source_commit=SOURCE_COMMIT,prepared=prepared,
                observer=None,admission=admission)
            admission()
            receipt={
                "schema":"ATLAS_QD_D_RUNTIME_INSTALLATION_V1",
                "stage":"D_RUNTIME_LAYOUT_VERIFIED",
                "release_path":str(TARGET),"source_commit":SOURCE_COMMIT,
                "files":copied["files"],"directories":copied["directories"],
                "archive_sha256":ARCHIVE_SHA,"inventory_sha256":INVENTORY_SHA,
                "selected":False,"financial_effects":False,
                "provider_connections":False,"operational_acceptance":False,
            }
            artifact_digest=hashlib.sha256(json.dumps(
                receipt["files"],sort_keys=True,separators=(",",":")
            ).encode()).hexdigest()
            clock.require_operational(CLOCK_IDENTITY)
            installed=installed_readback(
                TARGET,receipt,artifact_digest,timeout=_remaining_timeout(guard))
            admission()
            clock.require_operational(CLOCK_IDENTITY)
            _r14_unchanged()
            require_separate_consent()
            receipt.update(layout=installed["layout"],artifact_digest=artifact_digest)
            # The existing selected-native R15 source verifier expects this
            # exact terminal ACK. Durable ACK goes BEFORE the final receipt,
            # so a journal failure cannot leave a false installed receipt.
            event(final_native_install_ack(receipt))
            guard.tick()
            clock.require_operational(CLOCK_IDENTITY)
            _r14_unchanged()
            require_separate_consent()
            guard.tick()
            write_new_json(RECEIPT,receipt)
            return receipt
        except BaseException:
            event({"stage":"REFUSED_PRESERVE_PARTIAL_NO_RETRY"})
            raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inspect",action="store_true")
    group.add_argument("--execute-one-shot-code-install",action="store_true")
    parser.add_argument("--confirm-scope",default=None)
    args=parser.parse_args(argv)
    if args.inspect:
        if args.confirm_scope is not None:
            raise ValueError("R15_INSPECT_MIXED_INSTALL_SCOPE_REFUSED")
        return inspect()
    if args.confirm_scope!=SCOPE:
        raise ValueError("R15_EXACT_ONE_SHOT_SCOPE_CONFIRMATION_REQUIRED")
    # Consent is checked BEFORE any NTP clock, source copy or protected writes.
    require_separate_consent()
    from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock
    clock=IndependentNtpClock(runtime_id=CLOCK_IDENTITY)
    try:
        receipt=install(execute_approved=True,clock=clock)
        return {"status":"R15_CODE_INSTALLED_UNSELECTED",
                "source_commit":receipt["source_commit"],
                "artifact_digest":receipt["artifact_digest"],
                "selection_allowed":False,"financial_authority":False,
                "paper_startup_authorized":False}
    finally:
        clock.revoke()


if __name__=="__main__":
    print(json.dumps(main(),sort_keys=True),flush=True)
