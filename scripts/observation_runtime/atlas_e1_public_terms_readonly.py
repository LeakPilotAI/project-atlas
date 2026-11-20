"""Original Atlas E1 source-rights public-document review, NEVER an acceptance issuer.

Classifies independently documented product capabilities and unresolved account/
data-use entitlements. It opens no socket, credentials, Windows financial owner,
subscription, account, release selector or trading API.

The official public links are reference *leads*, not a license/contract grant.
Actual E1 acceptance must come from the original independent provider,
financial source and operator authorities, not from this code or its output.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SCHEMA = "ATLAS_E1_PUBLIC_DOCUMENT_CAPABILITY_REVIEW_ONLY_V1"
DECISION = "PUBLIC_PRODUCT_CAPABILITIES_DOCUMENTED_E1_NOT_ACCEPTED"
SOURCE_IDS = frozenset(("ALPACA_IEX", "HYPERLIQUID_PUBLIC",
                        "QUALITY_DIPS_RESEARCH_PUBLICATION"))
SOURCES = {
    "ALPACA_IEX": (
        "https://docs.alpaca.markets/us/docs/about-market-data-api",
        "https://s3.amazonaws.com/files.alpaca.markets/disclosures/library/TermsAndConditions.pdf",
        "https://www.iex.io/resources/trading/fee-schedule",
        "https://www.iex.io/resources/trading/market-data",
    ),
    "HYPERLIQUID_PUBLIC": (
        "https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api",
        "https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits",
        "https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees",
        "https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding",
    ),
    "QUALITY_DIPS_RESEARCH_PUBLICATION": (
        "https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data",
        "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
    ),
}
DOC_PINS = {
    "docs/PAPER_E1_PROVIDER_READINESS_MANIFEST_V1_2026-10-26.json":
        "7df2e4e714e9a4b7f20f3349be97e9a1852b6575363cbe26faeaae26a3e29ba6",
    "docs/ATLAS_E1_PROVIDER_STATIC_SOURCE_RIGHTS_AUDIT_2026-11-07.json":
        "e5bdb784baa5347359ce2d483d606ef80ac28145f04ab67b11438f811934d7d5",
    "docs/ATLAS_ZERO_COST_RESEARCH_POLICY_2026-10-29.json":
        "fa00dfddceed5f98fff9eb4ff2ba57e9c82df33fce38f36e0def64c932c008f4",
    "docs/ATLAS_R22_HL_ONE_HOUR_PAPER_METHOD_REVIEW_2026-11-17.json":
        "2ba230216d88e80990700928c00da59736aa8a195887617c860c00f65a863de9",
    "docs/ATLAS_R22_HL_METHOD_PREFERENCE_ACK_ONLY_2026-11-17.json":
        "cb35187750728ab5b1a69b65f7a0defae53c2a14a3b31fcec3b32c1025d351bd",
}
FORBIDDEN_TRUE = (
    "rights_evidence_accepted", "provider_request_approved",
    "provider_connection_authorized", "provider_budget_authorized",
    "signed_settlement_oracle_accepted", "financial_source_accepted",
    "paper_start_authorized", "account_inceptions_authorized",
    "live_money_authorized", "license_authority_created",
    "windows_local_operator_decision_created",
    "autopaper_or_auto_restart_authorized",
)


def _fail(message: str) -> None:
    raise ValueError("E1_PUBLIC_REVIEW_" + message)


def _must(condition: bool, reason: str) -> None:
    if not condition:
        _fail(reason)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_originals(root: Path) -> dict:
    """Read exact existing tracked original documents, no changes or network."""
    root = Path(root)
    result = {}
    for name, expected in DOC_PINS.items():
        path = root / name
        _must(path.is_file() and not path.is_symlink(),
              "ORIGINAL_PINNED_DOCUMENT_MISSING")
        raw = path.read_bytes()
        _must(_sha(raw) == expected, "ORIGINAL_PINNED_DOCUMENT_DRIFT")
        result[name] = json.loads(raw.decode("utf-8-sig"))
    return result


def proposed_review_snapshot() -> dict:
    """Public docs may inform reviews; never auto-enroll those permissions."""
    return {
        "schema": SCHEMA,
        "status": "UNACCEPTED_DOCUMENTARY_CAPABILITY_INFORMATION_ONLY",
        "observed_date": "2026-11-18",
        "providers": [
            {
                "id": "ALPACA_IEX",
                "official_public_reference_urls": list(SOURCES["ALPACA_IEX"]),
                "documented_product": "ALPACA_TRADING_API_BASIC_IEX_SINGLE_EXCHANGE",
                "documented_price_usd_per_month": 0,
                "documented_websocket_symbol_limit": 30,
                "documented_historical_api_calls_per_minute": 200,
                "proposed_atlas_shared_max_ws_connections": 1,
                "proposed_atlas_shared_max_symbols": 30,
                "proposed_atlas_shared_max_requests_per_second": 2,
                "review_required": [
                    "actual enrolled Basic account plan, credentials, correct IEX feed entitlement",
                    "retail/personal noncommercial and IEX non-display automated research rights",
                    "local display, retention, derivation and provider agreement scope",
                    "exact shared request budget and continuously current real source",
                    "single-exchange IEX is NOT SIP/NBBO/full-market quote or guaranteed trade fill",
                ],
            },
            {
                "id": "HYPERLIQUID_PUBLIC",
                "official_public_reference_urls": list(SOURCES["HYPERLIQUID_PUBLIC"]),
                "documented_product": "HYPERLIQUID_PUBLIC_READONLY_INFO_WS_NOT_ORDERS",
                "documented_rest_aggregate_weight_per_minute": 1200,
                "documented_l2book_weight": 2,
                "documented_default_other_info_weight": 20,
                "documented_max_ws_connections": 10,
                "proposed_atlas_shared_max_ws_connections": 1,
                "proposed_atlas_shared_max_rest_weight_per_minute": 100,
                "proposed_atlas_automatic_retries": 0,
                "review_required": [
                    "actual application-appropriate permitted local automated use and data retention",
                    "complete source rights, account/location applicability and concurrency ownership",
                    "fresh funding future reference or explicitly reviewed conservative flat-first policy",
                    "independent actual fee and settlement-oracle provenance; no account fee tier inferred",
                    "real book/queue/sequence and source recovery; never exchange/orders",
                ],
            },
            {
                "id": "QUALITY_DIPS_RESEARCH_PUBLICATION",
                "official_public_reference_urls":
                    list(SOURCES["QUALITY_DIPS_RESEARCH_PUBLICATION"]),
                "documented_product": "SEC_EDGAR_FREE_PUBLIC_RESEARCH_NOT_A_LIVE_PRICE_SOURCE",
                "documented_sec_fair_access_max_requests_per_second": 10,
                "proposed_atlas_shared_max_requests_per_second": 2,
                "proposed_atlas_automatic_retries": 0,
                "requires_real_contact_user_agent": True,
                "review_required": [
                    "real declared contact User-Agent and accepted fair-access behavior",
                    "upstream per-source data/retention/derived ranking rights and price freshness",
                    "live IEX-only quotation is not SEC companyfacts or derived analyst target",
                    "original permitted QD scoring/source issuer and current reader provenance",
                    "Robinhood/Yahoo/yfinance fallback remains disabled",
                ],
            },
        ],
        "provider_requests_executed": 0,
        "unverified_product_claims_are_operating_permissions": False,
        "historical_user_method_acknowledgment_only": True,
        "original_e1_provider_acceptance_count": 0,
        "zero_monthly_paid_subscription_policy_preserved": True,
        **{key: False for key in FORBIDDEN_TRUE},
    }


def audit_review(*, originals: dict, review: dict) -> dict:
    """Reject missing/forged grants; classify only original Stage A gaps."""
    _must(type(originals) is dict and set(originals) == set(DOC_PINS),
          "ORIGINAL_DOCUMENT_SET_REQUIRED")
    required = ({"schema", "status", "observed_date", "providers",
                 "provider_requests_executed",
                 "unverified_product_claims_are_operating_permissions",
                 "historical_user_method_acknowledgment_only",
                 "original_e1_provider_acceptance_count",
                 "zero_monthly_paid_subscription_policy_preserved"}
                | set(FORBIDDEN_TRUE))
    _must(type(review) is dict and set(review) == required,
          "EXACT_PUBLIC_REVIEW_SCHEMA_REQUIRED")
    _must(review["schema"] == SCHEMA and
          review["status"] ==
          "UNACCEPTED_DOCUMENTARY_CAPABILITY_INFORMATION_ONLY" and
          review["observed_date"] == "2026-11-18",
          "EXACT_REVIEW_ONLY_STATUS_REQUIRED")
    for key in FORBIDDEN_TRUE:
        _must(review[key] is False, "UNAUTHORIZED_GRANT_" + key)
    _must(review["provider_requests_executed"] == 0 and
          review["unverified_product_claims_are_operating_permissions"] is False
          and review["historical_user_method_acknowledgment_only"] is True
          and review["original_e1_provider_acceptance_count"] == 0
          and review["zero_monthly_paid_subscription_policy_preserved"] is True,
          "NO_RUNTIME_OR_RIGHTS_PERMISSION_FROM_PUBLIC_DOCS")
    _must(type(review["providers"]) is list and
          len(review["providers"]) == 3,
          "THREE_PUBLIC_SOURCES_REQUIRED")
    by_id = {}
    expected = proposed_review_snapshot()
    canonical = {row["id"]: row for row in expected["providers"]}
    for row in review["providers"]:
        _must(type(row) is dict and
              type(row.get("id")) is str and row["id"] in SOURCE_IDS and
              row["id"] not in by_id,
              "UNKNOWN_DUPLICATE_OR_INVALID_SOURCE")
        # Explicit full shape, values and budget caps prevent a fake higher
        # allowance or deleted rights-review question being made authoritative.
        _must(row == canonical[row["id"]],
              "SOURCE_CAPABILITY_OR_PROPOSED_BUDGET_DRIFT_" + row["id"])
        by_id[row["id"]] = row
    _must(set(by_id) == SOURCE_IDS,
          "ALL_THREE_PUBLIC_SOURCES_REQUIRED")
    manifest = originals[
        "docs/PAPER_E1_PROVIDER_READINESS_MANIFEST_V1_2026-10-26.json"
    ]
    static = originals[
        "docs/ATLAS_E1_PROVIDER_STATIC_SOURCE_RIGHTS_AUDIT_2026-11-07.json"
    ]
    free = originals[
        "docs/ATLAS_ZERO_COST_RESEARCH_POLICY_2026-10-29.json"
    ]
    method = originals[
        "docs/ATLAS_R22_HL_ONE_HOUR_PAPER_METHOD_REVIEW_2026-11-17.json"
    ]
    acknowledgment = originals[
        "docs/ATLAS_R22_HL_METHOD_PREFERENCE_ACK_ONLY_2026-11-17.json"
    ]
    _must(manifest["schema"] == "ATLAS_E1_PROVIDER_PLANNING_V1" and
          manifest["status"] == "PROPOSED_NOT_ACCEPTED" and
          manifest["runtime_consumable"] is False and
          manifest["startup_authorized"] is False and
          manifest["gate_promotions"] == 0 and
          manifest["operational_action_authorized"] is False,
          "EXISTING_ORIGINAL_E1_REVIEW_ONLY_REQUIRED")
    _must(static["schema"] ==
          "ATLAS_E1_PROVIDER_STATIC_SOURCE_AND_RIGHTS_GAP_V1" and
          static["status"] == "STATIC_SOURCE_AUDIT_NOT_PROVIDER_ACCEPTANCE" and
          static["source_present_count"] == static["source_expected_count"] == 9
          and static["rights_evidence_count"] == 0 and
          static["request_budget_count"] == 0 and
          static["connection_authorized_count"] == 0 and
          static["runtime_consumable"] is False and
          static["startup_authorized"] is False,
          "ORIGINAL_E1_STILL_UNACCEPTED_REQUIRED")
    _must(type(manifest["providers"]) is list and
          len(manifest["providers"]) == 3 and
          type(static["providers"]) is list and
          len(static["providers"]) == 3,
          "ORIGINAL_THREE_PROVIDER_MANIFEST_REQUIRED")
    actual = {}
    for original in manifest["providers"]:
        sid = original.get("id")
        _must(sid in SOURCE_IDS and sid not in actual,
              "E1_ORIGINAL_PROVIDER_IDENTITY_REFUSED")
        matching = next((e for e in static["providers"]
                         if e["id"] == sid), None)
        _must(matching is not None and
              original["status"] == matching["status"] ==
              "UNACCEPTED_NOT_CONNECTED" and
              original["rights_evidence"] is None and
              original["request_budget"] is None and
              original["connection_authorized"] is False and
              original["subscription_activated"] is False and
              original["credentials_enrolled"] is False and
              original["reviewer"] == original["evidence_owner"] ==
              "UNASSIGNED" and
              matching["rights_evidence_present"] is False and
              matching["request_budget_present"] is False and
              matching["connection_authorized"] is False,
              "ORIGINAL_E1_SOURCE_RIGHTS_NOT_ACCEPTED_" + sid)
        actual[sid] = original
    _must(set(actual) == SOURCE_IDS,
          "ORIGINAL_E1_SOURCE_SET_REQUIRED")
    _must(free["monthly_subscription_budget_usd"] == 0 and
          free["paid_subscriptions_allowed"] is False and
          free["deployment"] == "D_ONLY_EXISTING_WINDOWS_ACCOUNT" and
          free["request_ceiling_per_process_per_second"] == 2 and
          free["automatic_retries"] == 0 and
          free["redirects_allowed"] is False and
          free["yahoo_yfinance_allowed"] is False and
          free["paper_startup_authorized_by_this_policy"] is False,
          "ORIGINAL_ZERO_COST_RESEARCH_SOURCE_POLICY_REQUIRED")
    _must(method["native_selected_revision"] == 22 and
          method["operator_method_review_only"] is True and
          method["native_paper_start_authorized"] is False and
          method["native_account_inceptions_authorized"] is False and
          acknowledgment["original_proposal_sha256"] ==
          "2ba230216d88e80990700928c00da59736aa8a195887617c860c00f65a863de9"
          and acknowledgment["original_provider_rights_accepted"] is False
          and acknowledgment["windows_local_financial_approval_created"] is False,
          "ORIGINAL_ONE_HOUR_METHOD_IS_REVIEW_ONLY")
    return {
        "schema": "ATLAS_E1_PUBLIC_SOURCE_RIGHTS_OFFLINE_ASSESSMENT_V1",
        "status": DECISION,
        "documented_public_reference_groups": 3,
        "original_e1_providers": 3,
        "original_e1_source_files_expected": 9,
        "original_e1_rights_accepted": 0,
        "original_provider_budgets_accepted": 0,
        "original_source_connections_activated": 0,
        "proposed_budgets_only": True,
        "actual_account_plan_rights_unverified": True,
        "actual_fee_and_funding_policy_unverified": True,
        "real_financial_source_authority": False,
        "original_financial_accounts_created": False,
        "paper_start_authorized": False,
        "live_money_authorized": False,
    }


def audit_current_checkout(root: Path, review: dict | None = None) -> dict:
    return audit_review(originals=read_originals(root),
                        review=proposed_review_snapshot()
                        if review is None else review)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        raise SystemExit("EXACT_CHECKOUT_PATH_REQUIRED")
    result = audit_current_checkout(Path(sys.argv[1]))
    print(json.dumps(result, sort_keys=True))
