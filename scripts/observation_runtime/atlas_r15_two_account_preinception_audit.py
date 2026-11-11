"""Actual R15 two-lane initial financial *arithmetic* audit; no account inception.

Runs the existing FS1 replay and independently implemented financial event and
FS3 daily-report auditors on the original unapproved R15 account proposals.
All calculations are in memory with an explicit NON-NATIVE placeholder source
binding. This can uncover a pre-inception schema/calendar mismatch but cannot
create or certify a native financial epoch, report, writer, source or account.
"""
import json
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import (
    digest, initial_state, replay_verified_events, validate_manifest,
)
from app.services.paper_daily_report import (
    audit_daily_report, build_daily_report, validate_scope,
)
from scripts.observation_runtime.atlas_r15_two_account_enrollment_handoff import (
    inspect as inspect_handoff,
)
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    ARTIFACT, SELECTED_HEAD,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    ROLES, inspect_two_lane_native_roots,
)

SCHEMA = "ATLAS_R15_TWO_LANE_FINANCIAL_ARITHMETIC_BEFORE_INCEPTION_V1"


def evaluate(*, proposal, roots, observed_at):
    if (type(observed_at) is not int or observed_at <= 0
            or type(proposal) is not dict
            or proposal.get("schema") !=
                "ATLAS_R15_TWO_ACCOUNT_UNAPPROVED_REBIND_HANDOFF_V1"
            or proposal.get("status") !=
                "TWO_LANE_R15_STRUCTURAL_REBIND_ONLY_NEVER_ACCEPTED"
            or proposal.get("selected_r15_artifact_digest") != ARTIFACT
            or proposal.get("selected_native_head") != SELECTED_HEAD
            or proposal.get("account_enrollment_accepted") is not False
            or proposal.get("both_financial_inceptions_published") is not False
            or proposal.get("native_operator_activation_present") is not False
            or proposal.get("paper_start_authorized") is not False
            or proposal.get("live_trading_authorized") is not False
            or type(roots) is not dict
            or roots.get("schema") !=
                "ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1"
            or roots.get("native_root_total") != 12
            or roots.get("native_root_ids_verified") != 12
            or roots.get("existing_empty_root_namespaces") != 12
            or roots.get("all_twelve_distinct_and_empty") is not True
            or set(proposal.get("accounts",{})) != {"QUALITY_DIPS","HYPERLIQUID"}
            or set(roots.get("lanes",{})) != {"QUALITY_DIPS","HYPERLIQUID"}):
        raise ValueError("R15_PREINCEPTION_EXACT_UNAPPROVED_NATIVE_EVIDENCE_REQUIRED")
    accounts = {}
    ids = set()
    epochs = set()
    keys = set()
    for lane in ("QUALITY_DIPS","HYPERLIQUID"):
        item = proposal["accounts"][lane]
        m = item["provisional_r15_parameters"]
        scope = item["provisional_report_scope_unaccepted"]
        enrollment = item["provisional_r15_native_enrollment_unaccepted"]
        if (type(item) is not dict
                or item.get("real_enrollment_accepted") is not False
                or item.get("financial_inception_published") is not False
                or item.get("writer_process_observed_and_leased") is not False
                or item.get("account_fee_entitlement_verified") is not False
                or item.get("provisional_fs3_calendar_validated_without_publication") is not True
                or type(m) is not dict or type(scope) is not dict
                or type(enrollment) is not dict or m.get("release") != ARTIFACT
                or enrollment.get("release_digest") != ARTIFACT
                or enrollment.get("writers") is not None
                or enrollment.get("acceptance_id") is not None
                or enrollment.get("epoch") != m.get("epoch")
                or enrollment.get("inception_digest") != digest(m)
                or item.get("provisional_inception_digest") != digest(m)
                or scope.get("policy_digest") != digest(m)
                or scope.get("epoch") != m.get("epoch")
                or item.get("provisional_fs3_reporting_timezone") != m.get("timezone")
                or m.get("opening_cash") != "1000"
                or type(m.get("opened_at")) is not int
                or m["opened_at"] <= 0
                or observed_at <= m["opened_at"]
                or scope.get("account_id") != enrollment.get("account_id")
                or scope["account_id"] in ids
                or m["epoch"] in epochs
                or type(enrollment.get("resources")) is not dict
                or set(enrollment["resources"]) != set(ROLES)
                or set(roots["lanes"][lane]["roots"]) != set(ROLES)):
            raise ValueError("R15_PREINCEPTION_CURRENT_ACCOUNT_SCOPE_OR_PENDING_AUTHORITY_REFUSED")
        ids.add(scope["account_id"])
        epochs.add(m["epoch"])
        for role in ROLES:
            native = enrollment["resources"][role]
            attested = roots["lanes"][lane]["roots"][role]
            if (type(native) is not dict
                    or native.get("native_id") != attested.get("native_id")
                    or native.get("path") != attested.get("path")
                    or attested.get("native_identity_verified") is not True
                    or attested.get("existing_empty_namespace_verified") is not True
                    or tuple(native["native_id"]) in keys):
                raise ValueError("R15_PREINCEPTION_NATIVE_PATH_AND_FILE_ID_REFUSED")
            keys.add(tuple(native["native_id"]))
        validate_manifest(m)
        validate_scope(scope,m)
        if ((lane=="QUALITY_DIPS" and (
                m.get("schema")!="PAPER_EPOCH_AUTONOMOUS_QD_V1"
                or m.get("currency")!="USD"
                or m.get("timezone")!="America/New_York"
                or item.get("historical_draft_reporting_timezone")!="America/Chicago"))
                or (lane=="HYPERLIQUID" and (
                    m.get("schema")!="PAPER_EPOCH_PERP_OPERATIONAL_V1"
                    or m.get("currency")!="USDC"
                    or m.get("timezone")!="UTC"
                    or item.get("historical_draft_reporting_timezone")!="UTC"))):
            raise ValueError("R15_PREINCEPTION_FINANCIAL_CURRENCY_OR_CALENDAR_REFUSED")
        # Unpublished, in-memory initial-state preview only. The dummy
        # inception binding below is intentionally NOT native authenticated.
        state, head, receipts = replay_verified_events(m,[])
        audit_financial_events(m,[],state)
        if (state != initial_state(m) or head != digest(m) or receipts
                or state["cash"]!="1000"
                or state["positions"]!={}
                or state["revision"]!=0
                or Decimal(state["net"])!=0
                or Decimal(state["costs"])!=0
                or Decimal(state["gross"])!=0):
            raise ValueError("R15_PREINCEPTION_FS1_INITIAL_LEDGER_MISMATCH")
        pin = {
            "root": enrollment["resources"]["source"]["native_id"],
            "epoch": m["epoch"],
            "inception": {"hypothetical_memory_only_not_native_bound": True},
            "entries": [],
        }
        day = datetime.fromtimestamp(
            observed_at, ZoneInfo(m["timezone"])).date().isoformat()
        report = build_daily_report(scope,m,pin,[],day,observed_at)
        audit_daily_report(report,scope,m,pin,[],state)
        if (report["cash"] != {"opening":"1000","closing":"1000"}
                or report["currency"] != m["currency"]
                or report["account_id"] != scope["account_id"]
                or report["status"] != "INCOMPLETE"
                or report["startup_authorized"] is not False
                or report["production_authorized"] is not False):
            raise ValueError("R15_PREINCEPTION_FS3_INITIAL_REPORT_MISMATCH")
        accounts[lane] = {
            "account_id":scope["account_id"],"epoch":m["epoch"],
            "currency":m["currency"],"opening_cash":"1000",
            "opened_at_is_historical_not_authorized":True,
            "report_calendar":m["timezone"],"observed_report_day":day,
            "fs1_empty_initial_state_audited":True,
            "fs3_unpublished_initial_daily_report_arithmetic_audited":True,
            "unpublished_report_status":report["status"],
            "opening_source_head_hypothetical_only":head,
            "inception_manifest_digest_provisional":digest(m),
            "initial_cash_state":"1000","initial_open_positions":0,
            "source_events":0,"report_is_native_bound":False,
            "native_initial_financial_ledger_accepted":False,
            "financial_account_inception_published":False,
            "real_writer_enrollment":False,
            "paper_order_authorized":False,
        }
    if len(keys)!=12 or len(ids)!=2 or len(epochs)!=2:
        raise ValueError("R15_PREINCEPTION_CROSS_ACCOUNT_RESOURCE_ISOLATION_REFUSED")
    return {
        "schema":SCHEMA,
        "status":"TWO_LANE_PREINCEPTION_FS1_FS3_ARITHMETIC_VERIFIED_ONLY",
        "accounts":accounts,
        "separate_simulated_usd_and_usdc_balances":True,
        "cash_netting_or_exchange_conversion_performed":False,
        "hypothetical_unpublished_report_count":2,
        "unapproved_historical_inception_timestamps_must_be_replaced":True,
        "operator_activation_accepted":False,
        "current_provider_rights_accepted":False,
        "writer_enrollment_accepted":False,
        "native_financial_accounts_incepted":False,
        "financial_ledger_publication_authorized":False,
        "paper_start_authorized":False,
        "real_money_trading_authorized":False,
        "native_account_file_writes":0,
        "external_provider_requests":0,
        "paper_orders_created":0,
    }


def inspect(*, observed_at=None):
    now=int(datetime.now(UTC).timestamp()) if observed_at is None else observed_at
    return evaluate(proposal=inspect_handoff(),
                    roots=inspect_two_lane_native_roots(),
                    observed_at=now)


if __name__=="__main__":
    print(json.dumps(inspect(),sort_keys=True,indent=2))
