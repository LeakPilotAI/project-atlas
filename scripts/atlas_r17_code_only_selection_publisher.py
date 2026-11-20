"""R17 exact native CODE-only selection publisher; one-shot not authorized yet.

Requires exact separately pinned Windows-SID operator decision for selecting a
genuinely installed immutable R17 code release. The selected native R16 must
still be current, 180 seconds of independently qualified two-peer UTC and a
full installed Windows-original-handle verification must pass, and only one
append-only rev16 selector record may be created. No finance/operator issuer,
accounts, providers, startup, desktop shortcuts or orders.
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

from scripts import atlas_r17_selection_handoff as handoff
from scripts import release_selection
from scripts.atlas_r13_low_impact_installer import LowImpactEnvelope, _exact_bytes
from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE as NTP_SOURCE
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    SELECTOR_NATIVE_ID,
)
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    SOURCE as SELECTED_R16_RELEASE,
)
from scripts.release_selection_store import NativeSelectionStore

ROOT = Path("D:/Work/Project Atlas")
APPROVAL = ROOT / "logs/diagnostics/atlas-r17-code-only-selection-one-shot-approval.json"
APPROVAL_SHA256 = "6a88cecfa28b3f1c9e4c5424478fcc4415bf5a71ac66548b08efe9a5b349eda4"  # R17 distinct nonfinancial native selection; no prior operator permission reused.
SCOPE = "SELECT_EXACT_INSTALLED_R17_CODE_ONLY_NO_FINANCIAL_START"
OPERATION = "APPROVE_ONE_R17_NATIVE_CODE_ONLY_SELECTION"
CLOCK_IDENTITY = "atlas-r17-code-only-native-selection"
QUALIFY_SECONDS = 180
QUALIFY_MIN_SAMPLES = 37
QUALIFY_PROOF_FRESH_SECONDS = 120
SELECTOR_PREVIOUS_RECORDS = 15
_QUALIFIED = weakref.WeakKeyDictionary()


def approval_source_digest():
    marker = (
        b"APPROVAL_SHA256 = None  # R17 distinct nonfinancial native selection; "
        b"no prior operator permission reused."
    )
    pattern = (rb"(?m)^APPROVAL_SHA256 = (?:None|\"[0-9a-f]{64}\")  # R17 distinct "
               rb"nonfinancial native selection; no prior operator permission reused\.")
    canonical, hits = re.subn(pattern, marker, Path(__file__).read_bytes())
    if hits != 1:
        raise ValueError("R17_SELECTION_SINGLE_SOURCE_PIN_REQUIRED")
    return hashlib.sha256(canonical).hexdigest()


def inspect():
    state = handoff.inspect()
    return {
        "schema": "ATLAS_R17_CODE_ONLY_SELECTION_PUBLISHER_REVIEW_V1",
        "status": (
            "READY_FOR_SEPARATE_EXACT_NATIVE_SELECTION_DECISION_NOT_APPROVED"
            if state["status"] ==
               "INSTALLED_RECEIPT_PROPOSED_NOT_NATIVE_HANDLE_ACCEPTED"
            else "WAITING_FOR_SEPARATELY_APPROVED_R17_NATIVE_CODE_INSTALL"
        ),
        "selected_predecessor": "R16",
        "selected_native_head": handoff.R16_HEAD,
        "target_source_commit": handoff.SOURCE,
        "proposed_revision": 16,
        "installed_receipt_proposed": (
            state["status"] == "INSTALLED_RECEIPT_PROPOSED_NOT_NATIVE_HANDLE_ACCEPTED"
        ),
        "exact_operator_selection_approval_pinned": False,
        "qualified_clock": False,
        "original_native_installed_handles_accepted": False,
        "new_selection_record_published": False,
        "financial_authority": False,
        "paper_accounts_enrolled": False,
        "paper_start_authorized": False,
        "live_orders_authorized": False,
    }


def validate_operator_decision(record, *, sid, proposal, publisher_source_sha256):
    """Pure exact scope, original native predecessor, source and installed pin."""
    row = proposal.get("proposed_selection_record") if type(proposal) is dict else None
    selected = row.get("selected") if type(row) is dict else None
    if (type(proposal) is not dict or type(record) is not dict
            or type(row) is not dict or type(selected) is not dict
            or type(sid) is not str or not sid.startswith("S-1-")
            or type(publisher_source_sha256) is not str
            or not re.fullmatch("[0-9a-f]{64}",publisher_source_sha256)
            or set(record) != {
                "schema", "operation", "scope", "operator_sid",
                "source_commit", "installed_receipt_sha256",
                "native_selection_revision", "previous_r16_head",
                "previous_r16_record_sha256", "proposed_row_sha256",
                "publisher_source_sha256", "one_shot",
                "selection_allowed", "financial_authority", "provider_access",
                "paper_accounts", "paper_start_authorized",
                "live_orders_authorized",
            }
            or record.get("schema") != "ATLAS_R17_CODE_ONLY_NATIVE_SELECTION_APPROVAL_V1"
            or record.get("operation") != OPERATION
            or record.get("scope") != SCOPE
            or record.get("operator_sid") != sid
            or record.get("source_commit") != handoff.SOURCE
            or record.get("installed_receipt_sha256") != selected.get("receipt_sha256")
            or record.get("native_selection_revision") != 16
            or record.get("previous_r16_head") != handoff.R16_HEAD
            or record.get("previous_r16_record_sha256") != handoff.R16_RECORD_SHA
            or record.get("proposed_row_sha256") !=
               proposal.get("proposed_record_sha256")
            or record.get("publisher_source_sha256") != publisher_source_sha256
            or record.get("one_shot") is not True
            or record.get("selection_allowed") is not True
            or any(record.get(key) is not False for key in (
                "financial_authority", "provider_access", "paper_accounts",
                "paper_start_authorized", "live_orders_authorized",
            ))
            or proposal.get("status") !=
               "INSTALLED_RECEIPT_PROPOSED_NOT_NATIVE_HANDLE_ACCEPTED"):
        raise ValueError("R17_SELECTION_SID_BOUND_ONE_SHOT_DECISION_REQUIRED")
    row = proposal["proposed_selection_record"]
    if (row.get("revision") != 16 or row.get("previous") != handoff.R16_HEAD
            or row.get("action") != "SELECT"
            or release_selection.digest(row) != proposal["proposed_record_sha256"]):
        raise ValueError("R17_SELECTION_INSTALLED_ROW_CHANGED")
    return record


def require_operator_approval(proposal):
    if type(APPROVAL_SHA256) is not str or not re.fullmatch(
            "[0-9a-f]{64}", APPROVAL_SHA256):
        raise ValueError("R17_SELECTION_NEW_PINNED_ONE_SHOT_OPERATOR_APPROVAL_REQUIRED")
    from scripts.volume_inspector.windows_output import current_sid
    raw = _exact_bytes(APPROVAL, APPROVAL_SHA256, max_bytes=4096)
    return validate_operator_decision(
        release_selection.strict(raw), sid=current_sid(), proposal=proposal,
        publisher_source_sha256=approval_source_digest())


def validate_clock(clock):
    from scripts.observation_runtime.atlas_independent_ntp_clock import (
        IndependentNtpClock,
    )
    if type(clock) is not IndependentNtpClock:
        raise ValueError("R17_SELECTION_GENUINE_TWO_PEER_NTP_CLOCK_REQUIRED")
    clock.require_operational(CLOCK_IDENTITY)
    evidence = clock.evidence
    if (type(evidence) is not dict
            or evidence.get("source") != NTP_SOURCE
            or evidence.get("domain") != "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS"
            or evidence.get("financial_authority") is not False
            or type(evidence.get("bound_ms")) is not int
            or not 0 <= evidence["bound_ms"] <= 1000):
        raise ValueError("R17_SELECTION_APPROVED_TWO_PEER_CLOCK_SCOPE_REQUIRED")
    return evidence


def qualify_clock(clock):
    started = time.perf_counter()
    samples = 0
    while True:
        evidence = validate_clock(clock)
        samples += 1
        elapsed = time.perf_counter()-started
        if elapsed >= QUALIFY_SECONDS:
            break
        time.sleep(min(5,QUALIFY_SECONDS-elapsed))
    if samples < QUALIFY_MIN_SAMPLES:
        raise ValueError("R17_SELECTION_FULL_37_CLOCK_SAMPLES_REQUIRED")
    proof = {"elapsed_seconds":elapsed, "samples":samples,
             "bound_ms":evidence["bound_ms"]}
    _QUALIFIED[clock] = {"proof":dict(proof), "identity":CLOCK_IDENTITY,
                         "finished_at":time.perf_counter()}
    return proof


def publish(*, clock, proof):
    proposal = handoff.inspect()
    require_operator_approval(proposal)
    from scripts.observation_runtime.atlas_independent_ntp_clock import (
        IndependentNtpClock,
    )
    if type(clock) is not IndependentNtpClock:
        raise ValueError("R17_SELECTION_CURRENT_PROCESS_NTP_PROOF_REQUIRED")
    qualification = _QUALIFIED.pop(clock,None)
    if (type(qualification) is not dict or type(proof) is not dict
            or qualification.get("identity") != CLOCK_IDENTITY
            or qualification.get("proof") != proof
            or type(proof.get("samples")) is not int
            or proof["samples"] < QUALIFY_MIN_SAMPLES
            or type(proof.get("elapsed_seconds")) not in (int,float)
            or proof["elapsed_seconds"] < QUALIFY_SECONDS
            or type(qualification.get("finished_at")) not in (int,float)
            or not 0 <= time.perf_counter()-qualification["finished_at"]
                    <= QUALIFY_PROOF_FRESH_SECONDS):
        raise ValueError("R17_SELECTION_CURRENT_PROCESS_180S_CLOCK_PROOF_REQUIRED")
    validate_clock(clock)
    row = proposal["proposed_selection_record"]
    if (row.get("revision") != 16
            or row.get("previous") != handoff.R16_HEAD
            or release_selection.digest(row) !=
               proposal["proposed_record_sha256"]):
        raise ValueError("R17_SELECTION_PROPOSED_ROW_DRIFT")
    from scripts.release_selection import NativeInstalledReleaseVerifier
    store = NativeSelectionStore(root=str(handoff.SELECTION_ROOT),
                                 native_root=SELECTOR_NATIVE_ID)
    try:
        with LowImpactEnvelope(check_every=32,pace_every=128) as envelope:  # noqa: SIM117
            with store.locked():
                envelope.tick()
                require_operator_approval(proposal)
                validate_clock(clock)
                previous = store.records()
                if (len(previous) != SELECTOR_PREVIOUS_RECORDS
                        or release_selection.digest(previous[-1]) != handoff.R16_HEAD
                        or previous[-1].get("revision") != 15
                        or previous[-1].get("selected",{}).get("release") !=
                           SELECTED_R16_RELEASE
                        or os.path.lexists(handoff.SELECTION_ROOT/"r0016.pending")
                        or os.path.lexists(handoff.SELECTION_ROOT/"r0016.json")):
                    raise ValueError("R17_SELECTION_REAL_R16_PREDECESSOR_DRIFT")
                with NativeInstalledReleaseVerifier().open(row["selected"]) as installed:
                    if (installed.get("source_commit") != handoff.SOURCE
                            or installed.get("artifact_digest") !=
                               row["selected"]["artifact_digest"]
                            or len(installed.get("files",[])) !=
                               handoff.EXPECTED_TOTAL_FILES
                            or len(installed.get("directories",[])) !=
                               handoff.EXPECTED_TOTAL_DIRECTORIES
                            or any(installed.get(k) is not False for k in (
                                "selected","financial_effects",
                                "provider_connections","operational_acceptance"))):
                        raise ValueError("R17_SELECTION_ORIGINAL_INSTALLED_HANDLES_REFUSED")
                    validate_clock(clock)
                    envelope.tick()
                require_operator_approval(proposal)
                validate_clock(clock)
                raw = handoff.read_small_regular(handoff.RECEIPT,maximum=10*1024*1024)
                journal = handoff.read_small_regular(handoff.JOURNAL,maximum=8192)
                current = handoff.candidate_from_receipt(
                    receipt=release_selection.strict(raw),
                    receipt_bytes=raw,journal_bytes=journal)
                if current != row:
                    raise ValueError("R17_SELECTION_INSTALLED_RECEIPT_DRIFT")
                validate_clock(clock)
                envelope.tick()
                store.publish(row)
                after = store.records()
                if (len(after) != 16 or after[:15] != previous
                        or after[-1] != row
                        or release_selection.digest(after[-1]) !=
                           proposal["proposed_record_sha256"]):
                    raise ValueError("R17_SELECTION_OUTCOME_UNKNOWN_NO_RETRY")
    finally:
        store.close()
    return {
        "status":"R17_NONFINANCIAL_CODE_SELECTED",
        "native_revision":16,
        "source_commit":handoff.SOURCE,
        "native_selected_head":proposal["proposed_record_sha256"],
        "financial_authority":False,
        "paper_accounts":False,
        "provider_access":False,
        "paper_start_authorized":False,
        "live_orders_authorized":False,
    }


def execute():
    proposal = handoff.inspect()
    require_operator_approval(proposal)
    from scripts.observation_runtime.atlas_independent_ntp_clock import (
        IndependentNtpClock,
    )
    clock = IndependentNtpClock(runtime_id=CLOCK_IDENTITY)
    try:
        proof = qualify_clock(clock)
        require_operator_approval(handoff.inspect())
        return publish(clock=clock,proof=proof)
    finally:
        clock.revoke()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--inspect",action="store_true")
    choice.add_argument("--execute-one-shot-code-selection",action="store_true")
    parser.add_argument("--confirm-scope",default=None)
    args = parser.parse_args(argv)
    if args.inspect:
        if args.confirm_scope is not None:
            raise ValueError("R17_SELECTION_INSPECT_AND_EXECUTION_MIXED_REFUSED")
        return inspect()
    if args.confirm_scope != SCOPE:
        raise ValueError("R17_SELECTION_EXACT_ONE_SHOT_SCOPE_REQUIRED")
    require_operator_approval(handoff.inspect())
    return execute()


if __name__ == "__main__":
    print(json.dumps(main(),sort_keys=True))
