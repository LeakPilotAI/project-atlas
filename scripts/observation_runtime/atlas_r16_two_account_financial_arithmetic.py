"""R16 two-lane FS1/FS3 financial arithmetic preview, NO account inception.

The CURRENT selected R16 native revision-15 code and its actual 2 original
unaccepted paper account drafts are bound to exact local policy. The FS1 event
replay and independent financial auditor prove both opening $1000 cash books;
the FS3 daily report builder/auditor checks local trading-day cutoffs.

All computations are in memory with explicitly HYPOTHETICAL source binding,
and no trusted-clock, operator, provider, native writer or startup approval.
This must NEVER be used as an activation or a published native financial cut.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import (
    digest, initial_state, replay_verified_events, validate_manifest,
)
from app.services.paper_daily_report import (
    audit_daily_report, build_daily_report, validate_scope,
)
from app.services.personal_paper_runtime import (
    PROFILE as PERSONAL_PROFILE, validate_policy,
)
from app.services.quality_dips_autonomous_enrollment import (
    WRITERS as QD_WRITERS,
)
from app.services.perp_operational_contract import WRITERS as HL_WRITERS
from scripts.observation_runtime.atlas_r16_two_account_enrollment_handoff import (
    R16_ARTIFACT, R16_HEAD, R16_RECORD_SHA, R16_SOURCE,
    inspect as inspect_handoff,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    ROLES, inspect_two_lane_native_roots,
)

SCHEMA = "ATLAS_R16_TWO_LANE_CURRENT_ACCOUNT_FS1_FS3_ARITHMETIC_NO_INCEPTION_V1"
# Exact R16 source proposal, previously reviewed and pinned; not authority.
DRAFT_DIGEST = "57c3dc502cb5a5e70885bf016364ea1746b47a6f5b2027169d8ee77e066678db"
MANIFEST_DIGESTS = {
    "QUALITY_DIPS": "778380e25decdfd63f913754c160146b0134bcc966864b52a2250d4530769067",
    "HYPERLIQUID": "ce4cd1dc55c5a51ea32e93f17c99ec8adabb1ff5d289a454472a2a8f2faaefbb",
}
POLICY_PATH = Path(__file__).resolve().parents[2] / "docs/ATLAS_PERSONAL_PAPER_RELEASE_POLICY.json"
POLICY_SHA256 = "4d67c4ef2d692719a9195d0d5b3068cb91e352a357425a085f83c96779550ff2"
POLICY_DIGEST = "099e873af77d3db977c39d3af8a679d4b9680b7e894e61f0f83a1ff1a4dbbdb7"


def evaluate(*, proposal, roots, observed_at, personal_policy):
    """Pure fail-closed arithmetic on read-only *actual R16* native bindings."""
    policy = validate_policy(personal_policy)
    if (digest(policy) != POLICY_DIGEST
            or type(observed_at) is not int or observed_at <= 0
            or type(proposal) is not dict
            or digest(proposal) != DRAFT_DIGEST
            or proposal.get("schema") !=
                "ATLAS_R16_TWO_ACCOUNT_PROVISIONAL_NATIVE_DRAFT_REBIND_V1"
            or proposal.get("status") !=
                "R16_TWO_LANE_CURRENT_CODE_PROPOSAL_ONLY_UNACCEPTED"
            or proposal.get("selected_native_revision") != 15
            or proposal.get("selected_native_head") != R16_HEAD
            or proposal.get("selected_native_record_sha256") != R16_RECORD_SHA
            or proposal.get("selected_r16_source_commit") != R16_SOURCE
            or proposal.get("selected_r16_artifact_digest") != R16_ARTIFACT
            or proposal.get("native_original_empty_root_count_verified") != 12
            or proposal.get("actual_financial_writer_roles_enrolled") != 0
            or proposal.get("native_financial_inceptions_published") != 0
            or proposal.get("accepted_financial_operating_gates") != 0
            or proposal.get("financial_paper_start_authorized") is not False
            or proposal.get("live_trading_authorized") is not False
            or proposal.get("provider_requests") != 0
            or proposal.get("filesystem_mutations") != 0
            or set(proposal.get("accounts", {})) != set(MANIFEST_DIGESTS)
            or type(roots) is not dict
            or roots.get("schema") !=
                "ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1"
            or roots.get("native_root_total") != 12
            or roots.get("native_root_ids_verified") != 12
            or roots.get("existing_empty_root_namespaces") != 12
            or roots.get("all_twelve_distinct_and_empty") is not True
            or roots.get("filesystem_writes") != 0
            or roots.get("network_requests") != 0
            or set(roots.get("lanes", {})) != set(MANIFEST_DIGESTS)
            or any(roots.get(k) is not False for k in (
                "operator_account_enrollment_verified", "writer_ownership_verified",
                "native_activation_record_verified", "financial_inception_verified",
                "paper_start_authorized", "live_trading_authorized"))
            or policy.get("profile_id") != PERSONAL_PROFILE):
        raise ValueError("R16_ARITHMETIC_GENUINE_SELECTED_UNACCEPTED_NATIVE_EVIDENCE_REQUIRED")
    accounts, resource_ids, account_ids, epochs = {}, set(), set(), set()
    for lane, pin in MANIFEST_DIGESTS.items():
        item = proposal["accounts"][lane]
        if type(item) is not dict:
            raise ValueError("R16_ARITHMETIC_EXACT_TWO_ACCOUNT_UNACCEPTED_DRAFT_REQUIRED")
        m = item["provisional_r16_parameters"]
        e = item["provisional_r16_enrollment_unaccepted"]
        scope = item["provisional_r16_report_scope_unaccepted"]
        if (type(m) is not dict or type(e) is not dict or type(scope) is not dict
                or item.get("provisional_r16_manifest_digest") != pin
                or digest(m) != pin
                or e.get("inception_digest") != pin
                or e.get("release_digest") != R16_ARTIFACT
                or m.get("release") != R16_ARTIFACT
                or scope.get("policy_digest") != pin
                or item.get("existing_native_roots_original_handles_matched") is not True
                or item.get("fs3_reporting_scope_structurally_valid") is not True
                or item.get("opening_timestamp_historical_not_current") is not True
                or item.get("fee_policy_historical_review_only") is not True
                or item.get("real_writer_roster_present") is not False
                or item.get("accepted_operator_inception") is not False
                or item.get("financial_inception_published") is not False
                or item.get("provider_source_rights_accepted") is not False
                or e.get("writers") is not None
                or e.get("acceptance_id") is not None
                or e.get("account_id") != scope.get("account_id")
                or e.get("epoch") != m.get("epoch")
                or e.get("epoch") != scope.get("epoch")
                or e["account_id"] in account_ids
                or e["epoch"] in epochs
                or type(m.get("opened_at")) is not int
                or observed_at <= m["opened_at"]
                or type(e.get("resources")) is not dict
                or set(e["resources"]) != set(ROLES)
                or set(roots["lanes"][lane].get("roots",{})) != set(ROLES)
                or roots["lanes"][lane].get("epoch") != e["epoch"]
                or m.get("opening_cash") != "1000"
                or m.get("initial_net_r") != "0"
                or m.get("currency") != ("USD" if lane=="QUALITY_DIPS" else "USDC")
                or m.get("timezone") != ("America/New_York" if lane=="QUALITY_DIPS" else "UTC")
                or scope.get("timezone") != m.get("timezone")
                or e.get("profile") != "AUTONOMOUS_PAPER_ONLY_V1"):
            raise ValueError("R16_ARITHMETIC_ACCOUNT_CURRENT_MANIFEST_SCOPE_REFUSED")
        account_ids.add(e["account_id"])
        epochs.add(e["epoch"])
        for role in ROLES:
            expected = roots["lanes"][lane]["roots"][role]
            actual = e["resources"][role]
            if (actual.get("native_id") != expected.get("native_id")
                    or actual.get("path") != expected.get("path")
                    or expected.get("native_identity_verified") is not True
                    or expected.get("existing_empty_namespace_verified") is not True
                    or tuple(actual["native_id"]) in resource_ids):
                raise ValueError("R16_ARITHMETIC_TWELVE_DISTINCT_ORIGINAL_NATIVE_ROOTS_REQUIRED")
            resource_ids.add(tuple(actual["native_id"]))
        validate_manifest(m)
        validate_scope(scope,m)
        per_policy = policy["accounts"][lane]
        if lane=="QUALITY_DIPS":
            if (m["provenance"]!="ACCEPTED_AUTONOMOUS_PAPER_PARAMETERS_V1"
                    or e.get("policy_digest") != digest(m["autonomous_policy"])
                    or m["fees_bps"] != per_policy["fee_bps_per_side"]
                    or m["slippage_bps"] != per_policy["slippage_bps_per_side"]):
                raise ValueError("R16_ARITHMETIC_QD_FINANCIAL_POLICY_FEE_DRIFT")
        elif (m["provenance"]!="ACCEPTED_PERP_PAPER_PARAMETERS_V1"
              or e.get("policy_digest")!=digest(m["perp_policy"])
              or not set(m["perp_policy"]["symbols"])<=set(per_policy["universe"])
              or Decimal(m["perp_policy"]["risk_limit"])>1
              or m["perp_policy"]["max_positions"]>3
              or Decimal(m["perp_policy"]["session_stop"])>Decimal(-3)):
            raise ValueError("R16_ARITHMETIC_HL_FINANCIAL_RISK_POLICY_DRIFT")
        roles=QD_WRITERS if lane=="QUALITY_DIPS" else HL_WRITERS
        if (type(roles) is not tuple or len(roles)!=(5 if lane=="QUALITY_DIPS" else 7)
                or len(set(roles))!=len(roles)):
            raise ValueError("R16_ARITHMETIC_WRITER_ROLE_CONTRACT_DRIFT")
        # Genuine FS1 replay arithmetic and independent event auditor. ZERO
        # events + zero state are not a financial file or operator inception.
        state, head, receipts = replay_verified_events(m, [])
        audit_financial_events(m, [], state)
        if (state!=initial_state(m) or head!=pin or receipts
                or state["cash"]!="1000" or state["positions"]!={}
                or state["revision"]!=0 or Decimal(state["net"])!=0
                or Decimal(state["gross"])!=0 or Decimal(state["costs"])!=0):
            raise ValueError("R16_ARITHMETIC_FS1_UNPUBLISHED_INITIAL_STATE_MISMATCH")
        placeholder = {
            "root":e["resources"]["source"]["native_id"],
            "epoch":m["epoch"],
            "inception":{"non_native_hypothetical_memory_only":True},
            "entries":[],
        }
        day=datetime.fromtimestamp(
            observed_at,ZoneInfo(m["timezone"])).date().isoformat()
        report=build_daily_report(scope,m,placeholder,[],day,observed_at)
        audit_daily_report(report,scope,m,placeholder,[],state)
        if (report["cash"]!={"opening":"1000","closing":"1000"}
                or report["currency"]!=m["currency"]
                or report["account_id"]!=scope["account_id"]
                or report["status"]!="INCOMPLETE"
                or report["startup_authorized"] is not False
                or report["production_authorized"] is not False):
            raise ValueError("R16_ARITHMETIC_FS3_UNPUBLISHED_DAILY_REPORT_MISMATCH")
        accounts[lane]={
            "account_id":e["account_id"],"epoch":m["epoch"],
            "currency":m["currency"],"opening_cash":"1000",
            "manifest_digest_provisional":pin,
            "reporting_timezone":m["timezone"],"observed_reporting_day":day,
            "fs1_empty_replay_and_independent_audit_passed":True,
            "fs3_daily_report_and_independent_audit_passed":True,
            "fs3_unpublished_report_status":"INCOMPLETE",
            "source_head_hypothetical_only":head,
            "historical_opened_at_is_not_current_financial_inception":True,
            "in_memory_initial_cash":"1000","in_memory_initial_positions":0,
            "initial_financial_source_events":0,
            "registered_native_writer_roles":0,
            "required_writer_roles":list(roles),
            "native_fs1_inception_bound":False,
            "native_fs3_report_bound":False,
            "financial_account_inception_accepted":False,
            "operator_activation_accepted":False,
            "paper_order_authorized":False,
        }
    if len(resource_ids)!=12 or len(account_ids)!=2 or len(epochs)!=2:
        raise ValueError("R16_ARITHMETIC_TWO_LANE_CROSS_ACCOUNT_ALIAS_REFUSED")
    return {
        "schema":SCHEMA,
        "status":"R16_SELECTED_TWO_LANE_FS1_FS3_ARITHMETIC_PREVIEW_ONLY",
        "selected_native_revision":15,
        "selected_native_head":R16_HEAD,
        "unaccepted_r16_source_draft_digest":DRAFT_DIGEST,
        "accounts":accounts,
        "opening_cash_kept_separate_in_usd_and_usdc":True,
        "usd_to_usdc_conversion_or_netting_performed":False,
        "required_real_writer_roles_unenrolled":12,
        "historical_inception_timestamps_must_be_replaced":True,
        "unpublished_initial_daily_reports":2,
        "operator_financial_authority_accepted":False,
        "independent_financial_clock_lease_accepted":False,
        "provider_market_rights_accepted":False,
        "native_financial_accounts_incepted":False,
        "paper_start_authorized":False,
        "live_trading_authorized":False,
        "native_financial_account_files_written":0,
        "network_provider_requests":0,
        "paper_orders_created":0,
    }


def inspect(*, observed_at=None):
    # UTC from the ordinary OS is an OFFLINE reporting arithmetic input,
    # NEVER an operational financial clock qualification or trusted lease.
    stamp = (int(datetime.now(UTC).timestamp())
             if observed_at is None else observed_at)
    if (not POLICY_PATH.is_file() or POLICY_PATH.is_symlink()
            or POLICY_PATH.is_junction()
            or hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest() !=
               POLICY_SHA256):
        raise ValueError("R16_ARITHMETIC_ORIGINAL_PERSONAL_POLICY_SHA_CHANGED")
    return evaluate(
        proposal=inspect_handoff(),
        roots=inspect_two_lane_native_roots(),
        observed_at=stamp,
        personal_policy=json.loads(POLICY_PATH.read_text(encoding="utf-8-sig")),
    )


if __name__=="__main__":
    print(json.dumps(inspect(),sort_keys=True,indent=2))
