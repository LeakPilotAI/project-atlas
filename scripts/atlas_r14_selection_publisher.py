"""R14 one-time nonfinancial native CODE selection publisher, disabled by default.

This is NOT release-selection approval. One exact, separate Windows-SID-bound
operator consent is required to call the irreversible native publish path.
Preview cannot select, create a clock, run a native child, or access providers.
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

from scripts import atlas_r14_selection_proposal as proposal
from scripts import release_selection as selection

ROOT = Path(__file__).resolve().parents[1]
REVIEW = proposal.REVIEW
REVIEW_SHA256 = "80517992c14db43de2b0484695434d05cd2e1bf10134282f5824161486860ea4"
PROPOSAL_SOURCE = ROOT / "scripts/atlas_r14_selection_proposal.py"
PROPOSAL_SOURCE_SHA256 = "0900cfcdfdfbaa387bb61b72daebb3d75ecdc947661e30a25e43d76bf5f73ddd"
SELECTOR_SHA256 = proposal.SELECTOR_SHA256
NATIVE_STORE_SHA256 = proposal.SELECTOR_STORE_SHA256
EXPECTED_HEAD = "3fd8e1972b559a5de90627a303fc663b11928f8b43e84621a6796e9f3dbe9383"
OPERATION = "884883becd7c9aac0e3c89f50df30415"
CLOCK_PROFILE = selection.R14_NTP_SELECTION_PROFILE
SCOPE = "SELECT_EXACT_R14_NONFINANCIAL_CODE_RELEASE_ONLY_NO_STARTUP"
DECISION = "APPROVE_ONE_R14_CODE_ONLY_NATIVE_SELECTION"
APPROVAL = ROOT / "logs/diagnostics/atlas-r14-code-only-selection-approval.json"
APPROVAL_PIN = "1dd666e9079cb737e12a8d983b2a2f918496a462bae329431511174720a39242"  # Operator-approved exact ONE-SHOT R14 code-only selection; revoke immediately after attempted execution.
QUALIFY_SECONDS = 180
QUALIFY_MIN_SAMPLES = 37
QUALIFICATION_FRESH_SECONDS = 120
# Qualification is bound to the actual freshly-owned clock instance, not a
# caller-supplied duration or a serializable proof dictionary.
_qualifications = weakref.WeakKeyDictionary()


def refuse_if(condition, reason):
    if condition:
        raise ValueError(reason)


def strict_file(path, expected, maximum):
    return selection.strict(proposal.checked(path, expected, maximum))


def pinned_review():
    """Review frozen read-only candidate; never open native selected runtime."""
    refuse_if(hashlib.sha256(PROPOSAL_SOURCE.read_bytes()).hexdigest()
              != PROPOSAL_SOURCE_SHA256,
              "R14_PUBLISHER_PROPOSAL_SOURCE_CHANGED")
    review = strict_file(REVIEW, REVIEW_SHA256, 8192)
    row = review.get("row")
    required = {
        "schema","status","previous_release","previous_revision",
        "previous_head","previous_selection_envelope_sha256",
        "native_selection_root","native_selection_root_identity",
        "predecessor_records_verified","r14_installed_receipt_sha256",
        "r14_installed_artifact_digest","selection_source_sha256",
        "selection_store_source_sha256","clock_profile",
        "fresh_180s_independent_two_peer_clock_required",
        "clock_qualification_performed",
        "native_installed_child_readback_required_before_publication",
        "native_installed_child_readback_performed","row","proposed_head",
        "r14_selected","operator_approval_present","selection_authorized",
        "selection_mutation_performed","financial_authority","paper_accounts",
        "providers","paper_start","simulated_orders","live_orders",
        "automatic_startup",
    }
    refuse_if(type(review) is not dict or set(review) != required
              or review["schema"] != "ATLAS_R14_NONFINANCIAL_CODE_SELECTION_PROPOSAL_V1"
              or review["status"] != "READ_ONLY_PROPOSAL_NOT_OPERATOR_PERMISSION"
              or review["previous_release"] != proposal.R12_RELEASE
              or review["previous_revision"] != 12
              or review["previous_head"] != proposal.R12_HEAD
              or review["previous_selection_envelope_sha256"]
                 != proposal.R12_ENVELOPE_SHA256
              or review["native_selection_root"] != str(proposal.SEL)
              or review["native_selection_root_identity"] != proposal.NATIVE_ID
              or review["predecessor_records_verified"] != 12
              or review["r14_installed_receipt_sha256"]
                 != selection.R14_RECEIPT_SHA256
              or review["r14_installed_artifact_digest"]
                 != selection.R14_ARTIFACT_DIGEST
              or review["selection_source_sha256"] != SELECTOR_SHA256
              or review["selection_store_source_sha256"] != NATIVE_STORE_SHA256
              or review["clock_profile"] != CLOCK_PROFILE
              or review["fresh_180s_independent_two_peer_clock_required"] is not True
              or review["native_installed_child_readback_required_before_publication"] is not True
              or type(row) is not dict
              or row.get("revision") != 13
              or row.get("action") != "SELECT"
              or row.get("operation") != OPERATION
              or row.get("previous") != proposal.R12_HEAD
              or row.get("selected") != proposal.exact_r14_reference()
              or row.get("restores") is not None
              or review["proposed_head"] != EXPECTED_HEAD
              or selection.digest(row) != EXPECTED_HEAD,
              "R14_PUBLISHER_EXACT_FROZEN_NONFINANCIAL_REVIEW_REQUIRED")
    for name in (
        "clock_qualification_performed","native_installed_child_readback_performed",
        "r14_selected","operator_approval_present","selection_authorized",
        "selection_mutation_performed","financial_authority","paper_accounts",
        "providers","paper_start","simulated_orders","live_orders",
        "automatic_startup",
    ):
        refuse_if(review.get(name) is not False,
                  "R14_PUBLISHER_SOURCE_REVIEW_SCOPE_EXPANSION_REFUSED")
    proposal.checked(proposal.SELECTOR, SELECTOR_SHA256, 64*1024)
    proposal.checked(proposal.SELECTOR_STORE, NATIVE_STORE_SHA256, 64*1024)
    return review


def inspect():
    """No provider/clock/native-file reads or release publication."""
    refuse_if(os.path.lexists(APPROVAL) or APPROVAL_PIN is not None,
              "R14_PUBLISHER_INSPECT_SEPARATE_APPROVAL_PRESENT")
    review = pinned_review()
    actual = proposal.read_only_proposal()
    refuse_if(actual != review, "R14_PUBLISHER_NATIVE_PROPOSAL_CHANGED")
    return {
        "schema":"ATLAS_R14_CODE_ONLY_SELECTION_PUBLISHER_PREVIEW_V1",
        "status":"READY_FOR_SEPARATE_SELECTION_OPERATOR_REVIEW_NOT_APPROVED",
        "previous_release":proposal.R12_RELEASE,
        "proposed_release":selection.R14_CODE_RELEASE,
        "previous_head":proposal.R12_HEAD,
        "proposed_head":EXPECTED_HEAD,
        "operation":OPERATION,
        "proposed_revision":13,
        "review_sha256":REVIEW_SHA256,
        "clock_profile":CLOCK_PROFILE,
        "independent_ntp_180s_required":True,
        "operator_approval_pinned":False,
        "selection_authorized":False,
        "r14_selected":False,
        "financial_authority":False,
        "paper_accounts":False,
        "providers":False,
        "paper_start":False,
        "orders":False,
        "live_orders":False,
        "automatic_startup":False,
    }


def validate_operator_decision(data, *, sid):
    """No general consent/auto-approval: exact single use, R14 only."""
    fields = {
        "schema","decision","scope","operator_sid","one_shot",
        "review_sha256","proposal_source_sha256","selected_r12_head",
        "selected_r12_envelope_sha256","native_selection_root",
        "native_selection_root_identity","operation","proposed_head",
        "r14_release","r14_receipt_sha256","r14_artifact_digest",
        "selection_source_sha256","selection_store_source_sha256",
        "clock_profile","selection_allowed","financial_authority",
        "paper_accounts","providers","paper_start",
        "simulated_orders","live_orders","automatic_startup",
    }
    refuse_if(type(data) is not dict or set(data) != fields
              or type(sid) is not str or not sid.startswith("S-1-")
              or data.get("schema") != "ATLAS_R14_NATIVE_CODE_SELECTION_APPROVAL_V1"
              or data.get("decision") != DECISION
              or data.get("scope") != SCOPE
              or data.get("operator_sid") != sid
              or data.get("one_shot") is not True
              or data.get("review_sha256") != REVIEW_SHA256
              or data.get("proposal_source_sha256") != PROPOSAL_SOURCE_SHA256
              or data.get("selected_r12_head") != proposal.R12_HEAD
              or data.get("selected_r12_envelope_sha256")
                 != proposal.R12_ENVELOPE_SHA256
              or data.get("native_selection_root") != str(proposal.SEL)
              or data.get("native_selection_root_identity") != proposal.NATIVE_ID
              or data.get("operation") != OPERATION
              or data.get("proposed_head") != EXPECTED_HEAD
              or data.get("r14_release") != selection.R14_CODE_RELEASE
              or data.get("r14_receipt_sha256") != selection.R14_RECEIPT_SHA256
              or data.get("r14_artifact_digest") != selection.R14_ARTIFACT_DIGEST
              or data.get("selection_source_sha256") != SELECTOR_SHA256
              or data.get("selection_store_source_sha256") != NATIVE_STORE_SHA256
              or data.get("clock_profile") != CLOCK_PROFILE
              or data.get("selection_allowed") is not True
              or any(data.get(k) is not False for k in (
                  "financial_authority","paper_accounts","providers","paper_start",
                  "simulated_orders","live_orders","automatic_startup")),
              "R14_PUBLISHER_EXACT_ONE_SHOT_NONFINANCIAL_OPERATOR_SCOPE_REQUIRED")
    return data


def require_approved_operator():
    if type(APPROVAL_PIN) is not str or not re.fullmatch("[0-9a-f]{64}",APPROVAL_PIN):
        raise ValueError("R14_PUBLISHER_FRESH_ONE_SHOT_OPERATOR_APPROVAL_NOT_PINNED")
    from scripts.volume_inspector.windows_output import current_sid
    data = strict_file(APPROVAL, APPROVAL_PIN, 4096)
    return validate_operator_decision(data,sid=current_sid())


def validate_clock(clock, identity):
    from scripts.observation_runtime.atlas_independent_ntp_clock import (
        IndependentNtpClock, SOURCE,
    )
    refuse_if(type(clock) is not IndependentNtpClock,
              "R14_PUBLISHER_REAL_INDEPENDENT_TWO_PEER_CLOCK_REQUIRED")
    clock.require_operational(identity)
    evidence=clock.evidence
    refuse_if(type(evidence) is not dict
              or evidence.get("source") != SOURCE
              or evidence.get("domain") != "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS"
              or evidence.get("financial_authority") is not False
              or evidence.get("os_windows_time_service_required") is not False
              or type(evidence.get("bound_ms")) is not int
              or not 0 <= evidence["bound_ms"] <= 1000,
              "R14_PUBLISHER_INDEPENDENT_NTP_EVIDENCE_REFUSED")
    return evidence


def qualify_clock(clock, identity):
    start=time.perf_counter()
    samples=0
    while True:
        evidence=validate_clock(clock, identity)
        samples+=1
        elapsed=time.perf_counter()-start
        if elapsed >= QUALIFY_SECONDS:
            break
        time.sleep(min(5,QUALIFY_SECONDS-elapsed))
    refuse_if(samples < QUALIFY_MIN_SAMPLES,
              "R14_PUBLISHER_37_CLOCK_SAMPLES_REQUIRED")
    proof={"elapsed_seconds":elapsed,"samples":samples,
           "last_bound_ms":evidence["bound_ms"]}
    _qualifications[clock]={
        "identity":identity,"proof":dict(proof),
        "completed_at":time.perf_counter(),
    }
    return proof


def publish_with_native_lock(*, clock, identity, proof):
    """One nonfinancial native revision-13 publication; no default consent."""
    require_approved_operator()  # FIRST, before native selector or clock checks.
    try:
        evidence=_qualifications.pop(clock,None)
    except TypeError:
        # A non-weakrefable forged clock is never a qualified live lease.
        evidence=None
    refuse_if(type(proof) is not dict
              or type(evidence) is not dict
              or evidence.get("identity") != identity
              or evidence.get("proof") != proof
              or type(proof.get("elapsed_seconds")) not in (int,float)
              or proof["elapsed_seconds"] < QUALIFY_SECONDS
              or type(proof.get("samples")) is not int
              or proof["samples"] < QUALIFY_MIN_SAMPLES
              or type(evidence.get("completed_at")) not in (int,float)
              or not 0 <= time.perf_counter()-evidence["completed_at"]
                        <= QUALIFICATION_FRESH_SECONDS,
              "R14_PUBLISHER_FRESH_IN_PROCESS_NTP_QUALIFICATION_REQUIRED")
    validate_clock(clock,identity)
    review=pinned_review()
    from scripts.release_selection import NativeInstalledReleaseVerifier
    from scripts.release_selection_store import NativeSelectionStore
    from scripts.atlas_r13_low_impact_installer import LowImpactEnvelope
    store=NativeSelectionStore(root=str(proposal.SEL),
                               native_root=list(proposal.NATIVE_ID))
    try:
        with LowImpactEnvelope(check_every=32, pace_every=128) as guard:
            with store.locked():
                require_approved_operator()
                guard.tick()
                validate_clock(clock,identity)
                records_before=store.records()
                operations=proposal.chain(records_before)
                refuse_if(OPERATION in operations,
                          "R14_PUBLISHER_DUPLICATE_NATIVE_OPERATION")
                proposal.checked(proposal.SEL/"r0012.json",
                                 proposal.R12_ENVELOPE_SHA256, 65536)
                refuse_if(os.path.lexists(proposal.SEL/"r0013.pending")
                          or os.path.lexists(proposal.SEL/"r0013.json"),
                          "R14_PUBLISHER_INTERRUPTED_OR_SELECTED_R13_TAIL")
                target=selection.validate_spec(review["row"]["selected"],"WINDOWS_LOCAL")
                # Full installed-child readback and native handle identity
                # verification happen here, only after separate consent.
                with NativeInstalledReleaseVerifier().open(target) as receipt:
                    refuse_if(receipt.get("source_commit") != selection.R14_CODE_RELEASE
                              or receipt.get("artifact_digest")
                                 != selection.R14_ARTIFACT_DIGEST
                              or any(receipt.get(k) is not False for k in (
                                  "selected","financial_effects",
                                  "provider_connections","operational_acceptance")),
                              "R14_PUBLISHER_INSTALLED_NONFINANCIAL_RECEIPT_REFUSED")
                    guard.tick()
                    validate_clock(clock, identity)
                # The verifier's root-identity final check and original-handle
                # close run ON EXIT. They must both succeed before publication.
                guard.tick()
                validate_clock(clock, identity)
                require_approved_operator()
                refuse_if(selection.digest(review["row"]) != EXPECTED_HEAD,
                          "R14_PUBLISHER_PROPOSED_NATIVE_HEAD_CHANGED")
                # ONLY irreversible operation, under held native mutex.
                store.publish(review["row"])
                # The real native publisher has already proved the new pair
                # through original Windows handles; independently replay the
                # whole append-only chain under the SAME lock before claiming
                # a selected release. Failure means outcome UNKNOWN, no retry.
                after=store.records()
                refuse_if(len(after) != 13 or after[:12] != records_before
                          or after[-1] != review["row"]
                          or selection.digest(after[-1]) != EXPECTED_HEAD,
                          "R14_PUBLISHER_POST_PUBLICATION_OUTCOME_UNKNOWN")
            # Publication was checked without releasing the native mutex.
            # A close/release error is still a non-acknowledged outcome; never
            # rerun the one-shot decision or overwrite staged native evidence.
    finally:
        store.close()
    return {
        "status":"R14_NONFINANCIAL_CODE_SELECTED",
        "previous_release":proposal.R12_RELEASE,
        "selected_release":selection.R14_CODE_RELEASE,
        "new_head":EXPECTED_HEAD,
        "operation":OPERATION,
        "revision":13,
        "financial_authority":False,
        "paper_accounts":False,
        "providers":False,
        "paper_start":False,
        "orders":False,
        "live_orders":False,
        "automatic_startup":False,
    }


def execute():
    # No clocks, native writes or installed-child readback before fresh consent.
    require_approved_operator()
    pinned_review()
    identity="atlas-r14-code-only-"+OPERATION
    from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock
    clock=IndependentNtpClock(runtime_id=identity)
    try:
        proof=qualify_clock(clock,identity)
        require_approved_operator()
        return publish_with_native_lock(clock=clock, identity=identity, proof=proof)
    finally:
        clock.revoke()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inspect",action="store_true")
    group.add_argument("--execute-one-shot-code-selection",action="store_true")
    parser.add_argument("--confirm-scope",default=None)
    args=parser.parse_args(argv)
    if args.inspect:
        refuse_if(args.confirm_scope is not None,
                  "R14_PUBLISHER_INSPECT_MIXED_SCOPE_REFUSED")
        return inspect()
    refuse_if(args.confirm_scope != SCOPE,
              "R14_PUBLISHER_EXACT_CONFIRMATION_REQUIRED")
    return execute()


if __name__=="__main__":
    print(json.dumps(main(),sort_keys=True),flush=True)
