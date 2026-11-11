"""One-shot R16 nonfinancial native CODE selection, locked without approval.

R15 is the genuine currently selected predecessor. The only permitted
operation is to publish one new native revision-15 code selection for the
already installed, original-Windows-handle-verified R16 release. No account
creation, financial writer enrollment, provider, PAPER startup or trading.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import weakref
from pathlib import Path

from scripts import atlas_r16_selection_handoff as handoff
from scripts import release_selection
from scripts.atlas_r13_low_impact_installer import LowImpactEnvelope
from scripts.release_selection_store import NativeSelectionStore
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    SELECTED_HEAD as PREDECESSOR_HEAD,
    SELECTED_SHA as PREDECESSOR_SHA,
    SELECTOR_NATIVE_ID,
)

ROOT = Path("D:/Work/Project Atlas")
APPROVAL = ROOT / "logs/diagnostics/atlas-r16-code-only-selection-one-shot-approval.json"
APPROVAL_SHA256 = None  # R16 separate one-shot operator approval, never install authorization.
CLOCK_IDENTITY = "atlas-r16-code-only-native-selection"
SCOPE = "SELECT_EXACT_INSTALLED_R16_CODE_ONLY_NO_FINANCIAL_START"
OPERATION = "APPROVE_ONE_R16_NATIVE_CODE_SELECTION"
QUALIFY_SECONDS = 180
QUALIFY_MIN_SAMPLES = 37
QUALIFICATION_FRESH_SECONDS = 120
SELECTOR_PREVIOUS_RECORDS = 14
_QUALIFIED = weakref.WeakKeyDictionary()


def approval_source_sha256():
    """Canonical digest excludes only the single one-shot approval-pin value."""
    raw = Path(__file__).read_bytes()
    marker = (
        b"APPROVAL_SHA256 = None  # R16 separate one-shot operator approval, "
        b"never install authorization."
    )
    pattern = (
        rb'(?m)^APPROVAL_SHA256 = (?:None|"[0-9a-f]{64}")  # R16 '
        rb'separate one-shot operator approval, never install authorization\.'
    )
    normalized, matches = re.subn(pattern, marker, raw)
    if matches != 1:
        raise ValueError("R16_SELECTION_SINGLE_SOURCE_PIN_REQUIRED")
    return hashlib.sha256(normalized).hexdigest()


def inspect():
    """Read-only: no clock, provider, native release child or selection write."""
    proposal = handoff.inspect()
    ready = (proposal.get("status") ==
             "NATIVE_INSTALL_RECEIPT_ELIGIBLE_FOR_SEPARATE_HANDLE_AND_OPERATOR_APPROVAL")
    return {
        "schema": "ATLAS_R16_NONFINANCIAL_CODE_SELECTION_PUBLISHER_V1",
        "status": ("PROPOSAL_REVIEW_ONLY_AWAITING_EXACT_SELECTION_APPROVAL"
                   if ready else "WAITING_FOR_SEPARATELY_APPROVED_R16_CODE_ONLY_INSTALL"),
        "predecessor": "R15",
        "selected_predecessor_head": PREDECESSOR_HEAD,
        "native_selection_revision": 15,
        "source_commit": handoff.SOURCE_COMMIT,
        "proposed_head": proposal.get("proposed_row_digest"),
        "proposed_row_available": ready,
        "operator_approval_pinned": False,
        "independent_180_second_two_peer_clock_qualified": False,
        "installed_original_windows_handle_verified": False,
        "native_selection_published": False,
        "financial_authority": False,
        "provider_access": False,
        "paper_accounts_enrolled": False,
        "paper_start_authorized": False,
        "live_orders_authorized": False,
    }


def validate_operator_decision(record, *, sid, proposal):
    """One exact SID-bound selection consent, never broad finance privileges."""
    keys = {
        "schema", "decision", "scope", "operator_sid",
        "source_commit", "predecessor_r15_head",
        "predecessor_r15_record_sha256",
        "native_selection_revision", "proposed_head",
        "installed_receipt_sha256", "operation", "publisher_source_sha256",
        "one_shot", "selection_allowed", "financial_authority",
        "paper_accounts", "provider_access",
        "paper_start_authorized", "live_orders_authorized",
    }
    row = proposal.get("proposed_row") if type(proposal) is dict else None
    head = release_selection.digest(row) if type(row) is dict else None
    if (type(proposal) is not dict or type(row) is not dict
            or type(record) is not dict or set(record) != keys
            or type(sid) is not str or not sid.startswith("S-1-")
            or record.get("schema") != "ATLAS_R16_NATIVE_CODE_SELECTION_APPROVAL_V1"
            or record.get("decision") != OPERATION
            or record.get("scope") != SCOPE
            or record.get("operator_sid") != sid
            or record.get("source_commit") != handoff.SOURCE_COMMIT
            or record.get("predecessor_r15_head") != PREDECESSOR_HEAD
            or record.get("predecessor_r15_record_sha256") != PREDECESSOR_SHA
            or record.get("native_selection_revision") != 15
            or record.get("proposed_head") != proposal.get("proposed_row_digest")
            or record.get("proposed_head") != head
            or record.get("installed_receipt_sha256") != (
                row.get("selected", {}).get("receipt_sha256"))
            or record.get("operation") != row.get("operation")
            or record.get("publisher_source_sha256") != approval_source_sha256()
            or record.get("one_shot") is not True
            or record.get("selection_allowed") is not True
            or any(record.get(k) is not False for k in (
                "financial_authority", "paper_accounts", "provider_access",
                "paper_start_authorized", "live_orders_authorized"))
            or proposal.get("status") !=
                "NATIVE_INSTALL_RECEIPT_ELIGIBLE_FOR_SEPARATE_HANDLE_AND_OPERATOR_APPROVAL"):
        raise ValueError("R16_SELECTION_EXACT_SID_BOUND_ONE_SHOT_DECISION_REQUIRED")
    return record


def require_operator_approval(proposal):
    if (type(APPROVAL_SHA256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", APPROVAL_SHA256)):
        raise ValueError("R16_SELECTION_ONE_SHOT_OPERATOR_APPROVAL_NOT_PINNED")
    from scripts.volume_inspector.windows_output import current_sid
    from scripts.build_release_candidate import source_bytes
    raw = source_bytes(ROOT, APPROVAL.relative_to(ROOT).as_posix(),
                       maximum_bytes=4096)
    if hashlib.sha256(raw).hexdigest() != APPROVAL_SHA256:
        raise ValueError("R16_SELECTION_OPERATOR_APPROVAL_SOURCE_CHANGED")
    record = release_selection.strict(raw)
    return validate_operator_decision(record, sid=current_sid(), proposal=proposal)


def validate_clock(clock):
    from scripts.observation_runtime.atlas_independent_ntp_clock import (
        IndependentNtpClock, SOURCE,
    )
    if type(clock) is not IndependentNtpClock:
        raise ValueError("R16_SELECTION_GENUINE_TWO_PEER_NTP_CLOCK_REQUIRED")
    clock.require_operational(CLOCK_IDENTITY)
    evidence = clock.evidence
    if (type(evidence) is not dict
            or evidence.get("source") != SOURCE
            or evidence.get("domain") != "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS"
            or evidence.get("financial_authority") is not False
            or evidence.get("os_windows_time_service_required") is not False
            or type(evidence.get("bound_ms")) is not int
            or not 0 <= evidence["bound_ms"] <= 1000):
        raise ValueError("R16_SELECTION_TWO_PEER_CLOCK_SCOPE_REFUSED")
    return evidence


def qualify_clock(clock):
    start = time.perf_counter()
    count = 0
    while True:
        evidence = validate_clock(clock)
        count += 1
        elapsed = time.perf_counter() - start
        if elapsed >= QUALIFY_SECONDS:
            break
        time.sleep(min(5, QUALIFY_SECONDS - elapsed))
    if count < QUALIFY_MIN_SAMPLES:
        raise ValueError("R16_SELECTION_37_CLOCK_SAMPLES_REQUIRED")
    proof = {"elapsed_seconds": elapsed, "samples": count,
             "last_bound_ms": evidence["bound_ms"]}
    _QUALIFIED[clock] = {
        "identity": CLOCK_IDENTITY,
        "proof": dict(proof),
        "completed_at": time.perf_counter(),
    }
    return proof


def publish(*, clock, proof):
    """Single create-only native r0015 under original selector Windows mutex."""
    proposal = handoff.inspect()
    require_operator_approval(proposal)
    # Reject weakref-ineligible and synthetic clocks before accessing
    # the process-private qualification map or native selector.
    from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock
    if type(clock) is not IndependentNtpClock:
        raise ValueError("R16_SELECTION_CURRENT_PROCESS_180S_CLOCK_PROOF_REQUIRED")
    qualification = _QUALIFIED.pop(clock, None)
    if (type(proof) is not dict or type(qualification) is not dict
            or qualification.get("identity") != CLOCK_IDENTITY
            or qualification.get("proof") != proof
            or type(proof.get("elapsed_seconds")) not in (int, float)
            or proof["elapsed_seconds"] < QUALIFY_SECONDS
            or type(proof.get("samples")) is not int
            or proof["samples"] < QUALIFY_MIN_SAMPLES
            or type(qualification.get("completed_at")) not in (int, float)
            or not 0 <= time.perf_counter() - qualification["completed_at"]
                    <= QUALIFICATION_FRESH_SECONDS):
        raise ValueError("R16_SELECTION_CURRENT_PROCESS_180S_CLOCK_PROOF_REQUIRED")
    validate_clock(clock)
    row = proposal["proposed_row"]
    if (row.get("revision") != 15
            or row.get("previous") != PREDECESSOR_HEAD
            or release_selection.digest(row) != proposal["proposed_row_digest"]):
        raise ValueError("R16_SELECTION_PROPOSED_NATIVE_ROW_DRIFT")
    from scripts.release_selection import NativeInstalledReleaseVerifier
    store = NativeSelectionStore(root=str(handoff.SELECTION_ROOT),
                                 native_root=SELECTOR_NATIVE_ID)
    try:
        with LowImpactEnvelope(check_every=32, pace_every=128) as guard:
            with store.locked():
                guard.tick()
                require_operator_approval(proposal)
                validate_clock(clock)
                previous = store.records()
                if (len(previous) != SELECTOR_PREVIOUS_RECORDS
                        or release_selection.digest(previous[-1]) != PREDECESSOR_HEAD
                        or previous[-1].get("revision") != 14
                        or previous[-1].get("selected", {}).get("release") !=
                            "2c79a8d846d6b33669008114732ae5896153812a"
                        or os.path.lexists(handoff.SELECTION_ROOT / "r0015.pending")
                        or os.path.lexists(handoff.SELECTION_ROOT / "r0015.json")):
                    raise ValueError("R16_SELECTION_GENUINE_R15_NATIVE_PREDECESSOR_CHANGED")
                # All actual installed R16 Windows file handles, ACLs, hashes,
                # namespace and receipt must be reopened and verified here.
                with NativeInstalledReleaseVerifier().open(row["selected"]) as receipt:
                    if (receipt.get("source_commit") != handoff.SOURCE_COMMIT
                            or receipt.get("artifact_digest") !=
                               row["selected"]["artifact_digest"]
                            or len(receipt.get("files", [])) != 10549
                            or len(receipt.get("directories", [])) != 912
                            or any(receipt.get(k) is not False for k in (
                                "selected", "financial_effects",
                                "provider_connections", "operational_acceptance"))):
                        raise ValueError("R16_SELECTION_NATIVE_INSTALLED_ORIGINAL_HANDLE_REFUSED")
                    validate_clock(clock)
                    guard.tick()
                # Never call handoff.inspect while the selector mutex is held:
                # that would reacquire the same native selection lock.
                require_operator_approval(proposal)
                validate_clock(clock)
                final_raw = handoff._strict_small(handoff.RECEIPT,
                                                  max_bytes=10*1024*1024)
                final_journal = handoff._strict_small(handoff.JOURNAL,
                                                      max_bytes=8192)
                refreshed = handoff.candidate_from_receipt(
                    receipt=release_selection.strict(final_raw),
                    receipt_bytes=final_raw, journal_bytes=final_journal)
                if refreshed != row:
                    raise ValueError("R16_SELECTION_NATIVE_INSTALL_RECEIPT_DRIFT")
                validate_clock(clock)
                guard.tick()
                store.publish(row)
                after = store.records()
                if (len(after) != 15 or after[:14] != previous
                        or after[-1] != row
                        or release_selection.digest(after[-1]) !=
                           proposal["proposed_row_digest"]):
                    raise ValueError("R16_SELECTION_OUTCOME_UNKNOWN_PRESERVE_NO_RETRY")
    finally:
        store.close()
    return {
        "status": "R16_NONFINANCIAL_CODE_SELECTED",
        "revision": 15,
        "source_commit": handoff.SOURCE_COMMIT,
        "selected_native_head": proposal["proposed_row_digest"],
        "financial_authority": False,
        "paper_accounts": False,
        "provider_access": False,
        "paper_start_authorized": False,
        "live_orders_authorized": False,
    }


def execute():
    proposal = handoff.inspect()
    require_operator_approval(proposal)
    from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock
    clock = IndependentNtpClock(runtime_id=CLOCK_IDENTITY)
    try:
        proof = qualify_clock(clock)
        require_operator_approval(handoff.inspect())
        return publish(clock=clock, proof=proof)
    finally:
        clock.revoke()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--inspect", action="store_true")
    choice.add_argument("--execute-one-shot-code-selection", action="store_true")
    parser.add_argument("--confirm-scope", default=None)
    args = parser.parse_args(argv)
    if args.inspect:
        if args.confirm_scope is not None:
            raise ValueError("R16_SELECTION_INSPECT_EXECUTION_MIXED_REFUSED")
        return inspect()
    if args.confirm_scope != SCOPE:
        raise ValueError("R16_SELECTION_EXACT_NONFINANCIAL_CODE_SCOPE_REQUIRED")
    require_operator_approval(handoff.inspect())
    return execute()


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True), flush=True)
