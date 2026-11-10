"""R15 nonfinancial native selection publisher, permanently locked by default.

Selected R14 remains authoritative until a distinct SID-bound exact one-shot
approval is pinned AFTER R15's native installer has independently completed.
Source-only inspect never starts a child, acquires NTP or writes selection.
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

from scripts.atlas_r13_low_impact_installer import LowImpactEnvelope
from scripts import release_selection
from scripts.release_selection_store import NativeSelectionStore
from scripts import atlas_r15_selection_handoff as handoff

ROOT = Path("D:/Work/Project Atlas")
APPROVAL = ROOT / "logs/diagnostics/atlas-r15-code-only-selection-one-shot-approval.json"
APPROVAL_SHA256 = "cac8da532607edf0760de1bacd3b10191653bbf26352c82c43543fe1f52233d6"  # Separate future operator review, not user chat inference.
CLOCK_IDENTITY = "atlas-r15-code-only-native-selection"
SCOPE = "SELECT_EXACT_INSTALLED_R15_CODE_ONLY_NO_FINANCIAL_START"
OPERATION = "APPROVE_ONE_R15_NATIVE_CODE_SELECTION"
QUALIFY_SECONDS = 180
QUALIFY_MIN_SAMPLES = 37
QUALIFICATION_FRESH_SECONDS = 120
_QUALIFIED = weakref.WeakKeyDictionary()


def approval_source_sha256():
    """Bind all publisher source bytes except its single one-shot pin.

    Normalize only the exact beginning-of-line assignment, so inserting the
    approved SHA does not invalidate the source digest in its approval record.
    All other mutations change the digest and refuse the one-shot approval.
    """
    raw=Path(__file__).read_bytes()
    pattern=(rb'(?m)^APPROVAL_SHA256 = (?:None|"[0-9a-f]{64}")  # Separate '
             rb'future operator review, not user chat inference\.')
    marker=(b'APPROVAL_SHA256 = None  # Separate future operator review, '
            b'not user chat inference.')
    normalized,count=re.subn(pattern,marker,raw)
    if count!=1:
        raise ValueError("R15_SELECTION_SINGLE_SOURCE_APPROVAL_PIN_REQUIRED")
    return hashlib.sha256(normalized).hexdigest()


def inspect():
    """No NTP or provider call, no installed child execution or native writes."""
    preview=handoff.inspect()
    ready=preview.get("status")==(
        "SOURCE_ONLY_CANDIDATE_REQUIRES_NATIVE_HANDLE_VERIFIER_AND_ONE_SHOT_SELECTION_APPROVAL")
    return {
        "schema":"ATLAS_R15_NONFINANCIAL_CODE_SELECTION_PUBLISHER_V1",
        "status":(
            "PROPOSAL_REVIEW_ONLY_AWAITING_EXACT_APPROVAL" if ready
            else "WAITING_FOR_SEPARATELY_AUTHORIZED_R15_CODE_ONLY_INSTALL"),
        "native_selected_predecessor":"R14",
        "target_revision":14,
        "source_commit":handoff.SOURCE_COMMIT,
        "proposed_head":preview.get("proposed_row_digest"),
        "proposed_row_available":ready,
        "native_installed_child_readback_completed":False,
        "independent_two_peer_180s_clock_qualified":False,
        "exact_one_shot_operator_approval_pinned":False,
        "native_selection_published":False,
        "native_installation_performed":False,
        "financial_authority":False,
        "paper_accounts_enrolled":False,
        "provider_access":False,
        "paper_start_authorized":False,
        "live_orders_authorized":False,
    }


def validate_operator_decision(record, *, sid, proposal):
    """Pure exact record check; no broad operator privileges or auto approval."""
    keys={
        "schema","decision","scope","operator_sid",
        "source_commit","predecessor_r14_head","native_selection_revision",
        "proposed_head","installed_receipt_sha256","operation",
        "publisher_source_sha256","one_shot",
        "selection_allowed","financial_authority","paper_accounts",
        "provider_access","paper_start_authorized","live_orders_authorized",
    }
    publisher_sha=approval_source_sha256()
    row=proposal.get("proposed_row") if type(proposal) is dict else None
    actual_head=release_selection.digest(row) if type(row) is dict else None
    if (type(proposal) is not dict or type(row) is not dict
            or type(record) is not dict or set(record)!=keys
            or type(sid) is not str or not sid.startswith("S-1-")
            or record.get("schema")!="ATLAS_R15_NATIVE_CODE_SELECTION_APPROVAL_V1"
            or record.get("decision")!=OPERATION
            or record.get("scope")!=SCOPE
            or record.get("operator_sid")!=sid
            or record.get("source_commit")!=handoff.SOURCE_COMMIT
            or record.get("predecessor_r14_head")!=handoff.R14_HEAD
            or record.get("native_selection_revision")!=14
            or record.get("proposed_head")!=proposal.get("proposed_row_digest")
            or record.get("proposed_head")!=actual_head
            or record.get("installed_receipt_sha256")!=(
                row.get("selected",{}).get("receipt_sha256")
                if type(row) is dict else None)
            or record.get("operation")!=row.get("operation")
            or record.get("publisher_source_sha256")!=publisher_sha
            or record.get("one_shot") is not True
            or record.get("selection_allowed") is not True
            or any(record.get(key) is not False for key in (
                "financial_authority","paper_accounts","provider_access",
                "paper_start_authorized","live_orders_authorized"))
            or proposal.get("status")!=(
                "SOURCE_ONLY_CANDIDATE_REQUIRES_NATIVE_HANDLE_VERIFIER_AND_ONE_SHOT_SELECTION_APPROVAL")):
        raise ValueError("R15_SELECTION_EXACT_SID_BOUND_ONE_SHOT_OPERATOR_DECISION_REQUIRED")
    return record


def require_operator_approval(proposal):
    if (type(APPROVAL_SHA256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}",APPROVAL_SHA256)):
        raise ValueError("R15_SELECTION_SEPARATE_ONE_SHOT_OPERATOR_APPROVAL_NOT_PINNED")
    from scripts.volume_inspector.windows_output import current_sid
    from scripts.build_release_candidate import source_bytes
    raw=source_bytes(ROOT,str(APPROVAL.relative_to(ROOT)).replace("\\","/"),
                     maximum_bytes=4096)
    if hashlib.sha256(raw).hexdigest()!=APPROVAL_SHA256:
        raise ValueError("R15_SELECTION_APPROVAL_SOURCE_CHANGED")
    record=release_selection.strict(raw)
    return validate_operator_decision(record,sid=current_sid(),proposal=proposal)


def validate_clock(clock):
    from scripts.observation_runtime.atlas_independent_ntp_clock import (
        IndependentNtpClock,SOURCE,
    )
    if type(clock) is not IndependentNtpClock:
        raise ValueError("R15_SELECTION_REAL_INDEPENDENT_TWO_PEER_NTP_REQUIRED")
    clock.require_operational(CLOCK_IDENTITY)
    evidence=clock.evidence
    if (type(evidence) is not dict
            or evidence.get("source")!=SOURCE
            or evidence.get("domain")!="TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS"
            or evidence.get("financial_authority") is not False
            or evidence.get("os_windows_time_service_required") is not False
            or type(evidence.get("bound_ms")) is not int
            or not 0<=evidence["bound_ms"]<=1000):
        raise ValueError("R15_SELECTION_INDEPENDENT_NTP_SCOPE_REFUSED")
    return evidence


def qualify_clock(clock):
    start=time.perf_counter()
    count=0
    while True:
        record=validate_clock(clock)
        count+=1
        elapsed=time.perf_counter()-start
        if elapsed>=QUALIFY_SECONDS:
            break
        time.sleep(min(5,QUALIFY_SECONDS-elapsed))
    if count<QUALIFY_MIN_SAMPLES:
        raise ValueError("R15_SELECTION_37_INDEPENDENT_CLOCK_SAMPLES_REQUIRED")
    proof={"elapsed_seconds":elapsed,"samples":count,
           "last_bound_ms":record["bound_ms"]}
    _QUALIFIED[clock]={
        "identity":CLOCK_IDENTITY,"proof":dict(proof),
        "completed_at":time.perf_counter(),
    }
    return proof


def publish(*, clock, proof):
    """One exact native SELECT, after full original-handle readback and approval."""
    proposal=handoff.inspect()
    require_operator_approval(proposal)
    qualification=_QUALIFIED.pop(clock,None)
    if (type(proof) is not dict or type(qualification) is not dict
            or qualification.get("identity")!=CLOCK_IDENTITY
            or qualification.get("proof")!=proof
            or type(proof.get("elapsed_seconds")) not in (int,float)
            or proof["elapsed_seconds"]<QUALIFY_SECONDS
            or type(proof.get("samples")) is not int
            or proof["samples"]<QUALIFY_MIN_SAMPLES
            or type(qualification.get("completed_at")) not in (int,float)
            or not 0<=time.perf_counter()-qualification["completed_at"]
                    <=QUALIFICATION_FRESH_SECONDS):
        raise ValueError("R15_SELECTION_CURRENT_PROCESS_CLOCK_QUALIFICATION_REQUIRED")
    validate_clock(clock)
    row=proposal["proposed_row"]
    if (row.get("revision")!=14 or row.get("previous")!=handoff.R14_HEAD
            or release_selection.digest(row)!=proposal["proposed_row_digest"]):
        raise ValueError("R15_SELECTION_EXACT_PROPOSED_ROW_CHANGED")
    from scripts.release_selection import NativeInstalledReleaseVerifier
    store=NativeSelectionStore(
        root=str(handoff.SELECTION_ROOT),native_root=[4004218753,65536,1532785])
    try:
        with LowImpactEnvelope(check_every=32,pace_every=128) as guard:
            with store.locked():
                guard.tick()
                require_operator_approval(proposal)
                validate_clock(clock)
                previous=store.records()
                if (len(previous)!=13
                        or release_selection.digest(previous[-1])!=handoff.R14_HEAD
                        or previous[-1].get("selected",{}).get("release")!=(
                            "7ff9d3dba2eabe110f843c13efac49464805de2a")
                        or os.path.lexists(handoff.SELECTION_ROOT/"r0014.pending")
                        or os.path.lexists(handoff.SELECTION_ROOT/"r0014.json")):
                    raise ValueError("R15_SELECTION_REAL_NATIVE_PREDECESSOR_CHANGED")
                # The original native release verifier, not an inferred fixture.
                # Its exit closes/rechecks original Windows file handles.
                with NativeInstalledReleaseVerifier().open(row["selected"]) as receipt:
                    if (receipt.get("source_commit")!=handoff.SOURCE_COMMIT
                            or receipt.get("artifact_digest")!=row["selected"]["artifact_digest"]
                            or any(receipt.get(k) is not False for k in (
                                "selected","financial_effects","provider_connections",
                                "operational_acceptance"))):
                        raise ValueError("R15_SELECTION_NATIVE_INSTALLED_CODE_PROOF_REQUIRED")
                    validate_clock(clock)
                    guard.tick()
                # Recompute exact proposal AFTER the installed handle closes,
                # before the one irreversible publication.
                validate_clock(clock)
                require_operator_approval(proposal)
                # While the native selection mutex is held, never call
                # handoff.inspect(): it would acquire the same native mutex.
                # Reopen only the installed receipt + journal under their
                # independent source-file checks, without recursive locking.
                final_raw=handoff._strict_small(
                    handoff.RECEIPT,max_bytes=10*1024*1024)
                final_journal=handoff._strict_small(
                    handoff.JOURNAL,max_bytes=8192)
                refreshed=handoff.candidate_from_receipt(
                    receipt=release_selection.strict(final_raw),
                    receipt_bytes=final_raw,journal_bytes=final_journal)
                if refreshed!=row:
                    raise ValueError("R15_SELECTION_NATIVE_RECEIPT_CHANGED_BEFORE_PUBLISH")
                store.publish(row)
                # Selection ACK only after native 14-row replay under same lock.
                after=store.records()
                if (len(after)!=14 or after[:13]!=previous or after[-1]!=row
                        or release_selection.digest(after[-1])!=proposal["proposed_row_digest"]):
                    raise ValueError("R15_SELECTION_POST_PUBLICATION_OUTCOME_UNKNOWN_NO_RETRY")
    finally:
        store.close()
    return {
        "status":"R15_NONFINANCIAL_CODE_SELECTED",
        "revision":14,
        "source_commit":handoff.SOURCE_COMMIT,
        "selected_native_head":proposal["proposed_row_digest"],
        "financial_authority":False,
        "paper_accounts":False,
        "provider_access":False,
        "paper_start_authorized":False,
        "live_orders_authorized":False,
    }


def execute():
    proposal=handoff.inspect()
    require_operator_approval(proposal)
    from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock
    clock=IndependentNtpClock(runtime_id=CLOCK_IDENTITY)
    try:
        proof=qualify_clock(clock)
        require_operator_approval(handoff.inspect())
        return publish(clock=clock,proof=proof)
    finally:
        clock.revoke()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect",action="store_true")
    mode.add_argument("--execute-one-shot-code-selection",action="store_true")
    parser.add_argument("--confirm-scope",default=None)
    args=parser.parse_args(argv)
    if args.inspect:
        if args.confirm_scope is not None:
            raise ValueError("R15_SELECTION_INSPECT_EXECUTE_SCOPE_MIXED_REFUSED")
        return inspect()
    if args.confirm_scope!=SCOPE:
        raise ValueError("R15_SELECTION_EXACT_CODE_ONLY_SCOPE_REQUIRED")
    # No NTP acquisition or native child before operator consent.
    require_operator_approval(handoff.inspect())
    return execute()


if __name__=="__main__":
    print(json.dumps(main(),sort_keys=True),flush=True)
