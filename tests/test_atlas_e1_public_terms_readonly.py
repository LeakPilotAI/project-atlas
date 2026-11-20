"""Fail-closed tests for public E1 documentation review, not source admission."""
import copy
from pathlib import Path

import pytest

from scripts.observation_runtime import atlas_e1_public_terms_readonly as e1

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def originals():
    return e1.read_originals(ROOT)


@pytest.fixture
def review():
    return e1.proposed_review_snapshot()


def test_original_public_e1_review_is_nonfinancial(originals, review):
    report = e1.audit_review(originals=originals, review=review)
    assert report["status"] == e1.DECISION
    assert report["original_e1_rights_accepted"] == 0
    assert report["original_provider_budgets_accepted"] == 0
    assert report["original_source_connections_activated"] == 0
    assert report["proposed_budgets_only"] is True
    assert report["real_financial_source_authority"] is False
    assert report["paper_start_authorized"] is False
    assert report["live_money_authorized"] is False
    assert review["provider_requests_executed"] == 0


@pytest.mark.parametrize("key", e1.FORBIDDEN_TRUE)
def test_public_review_never_mints_a_financial_or_provider_grant(
        originals, review, key):
    forged = copy.deepcopy(review)
    forged[key] = True
    with pytest.raises(ValueError, match="UNAUTHORIZED_GRANT"):
        e1.audit_review(originals=originals, review=forged)


@pytest.mark.parametrize("key,value", [
    ("provider_requests_executed", 1),
    ("unverified_product_claims_are_operating_permissions", True),
    ("historical_user_method_acknowledgment_only", False),
    ("original_e1_provider_acceptance_count", 1),
    ("zero_monthly_paid_subscription_policy_preserved", False),
])
def test_public_review_rejects_attempts_to_promote_a_reference(
        originals, review, key, value):
    forged = copy.deepcopy(review)
    forged[key] = value
    with pytest.raises(ValueError, match="NO_RUNTIME_OR_RIGHTS_PERMISSION"):
        e1.audit_review(originals=originals, review=forged)


@pytest.mark.parametrize("provider,key,value", [
    ("ALPACA_IEX", "documented_websocket_symbol_limit", 100000),
    ("ALPACA_IEX", "proposed_atlas_shared_max_symbols", 13000),
    ("ALPACA_IEX", "documented_price_usd_per_month", 99),
    ("ALPACA_IEX", "proposed_atlas_shared_max_requests_per_second", 20),
    ("HYPERLIQUID_PUBLIC", "proposed_atlas_shared_max_rest_weight_per_minute", 1201),
    ("HYPERLIQUID_PUBLIC", "proposed_atlas_automatic_retries", 1),
    ("QUALITY_DIPS_RESEARCH_PUBLICATION",
     "proposed_atlas_shared_max_requests_per_second", 11),
    ("QUALITY_DIPS_RESEARCH_PUBLICATION",
     "requires_real_contact_user_agent", False),
])
def test_public_review_refuses_unsanctioned_budget_or_capability_change(
        originals, review, provider, key, value):
    forged = copy.deepcopy(review)
    target = next(x for x in forged["providers"] if x["id"] == provider)
    target[key] = value
    with pytest.raises(ValueError, match="SOURCE_CAPABILITY_OR_PROPOSED_BUDGET_DRIFT"):
        e1.audit_review(originals=originals, review=forged)


@pytest.mark.parametrize("target", sorted(e1.SOURCE_IDS))
def test_deleting_an_original_provider_is_refused(originals, review, target):
    forged = copy.deepcopy(review)
    forged["providers"] = [x for x in forged["providers"] if x["id"] != target]
    with pytest.raises(ValueError, match="THREE_PUBLIC_SOURCES_REQUIRED"):
        e1.audit_review(originals=originals, review=forged)


@pytest.mark.parametrize("file_name,key,value", [
    ("docs/PAPER_E1_PROVIDER_READINESS_MANIFEST_V1_2026-10-26.json",
     "startup_authorized", True),
    ("docs/PAPER_E1_PROVIDER_READINESS_MANIFEST_V1_2026-10-26.json",
     "gate_promotions", 3),
    ("docs/ATLAS_E1_PROVIDER_STATIC_SOURCE_RIGHTS_AUDIT_2026-11-07.json",
     "rights_evidence_count", 1),
    ("docs/ATLAS_E1_PROVIDER_STATIC_SOURCE_RIGHTS_AUDIT_2026-11-07.json",
     "connection_authorized_count", 1),
    ("docs/ATLAS_ZERO_COST_RESEARCH_POLICY_2026-10-29.json",
     "monthly_subscription_budget_usd", 99),
    ("docs/ATLAS_ZERO_COST_RESEARCH_POLICY_2026-10-29.json",
     "yahoo_yfinance_allowed", True),
    ("docs/ATLAS_R22_HL_ONE_HOUR_PAPER_METHOD_REVIEW_2026-11-17.json",
     "native_paper_start_authorized", True),
    ("docs/ATLAS_R22_HL_METHOD_PREFERENCE_ACK_ONLY_2026-11-17.json",
     "windows_local_financial_approval_created", True),
])
def test_original_stage_a_remains_unaccepted_even_when_docs_are_mutated(
        originals, review, file_name, key, value):
    changed = copy.deepcopy(originals)
    changed[file_name][key] = value
    with pytest.raises(ValueError, match="E1_PUBLIC_REVIEW_"):
        e1.audit_review(originals=changed, review=review)


def test_missing_original_document_refuses(originals, review):
    originals.pop(next(iter(originals)))
    with pytest.raises(ValueError, match="ORIGINAL_DOCUMENT_SET_REQUIRED"):
        e1.audit_review(originals=originals, review=review)


def test_one_provider_original_rights_present_not_a_license_grant(
        originals, review):
    changed = copy.deepcopy(originals)
    entry = changed[
        "docs/PAPER_E1_PROVIDER_READINESS_MANIFEST_V1_2026-10-26.json"
    ]["providers"][0]
    entry["rights_evidence"] = {"claimed": "SELF_APPROVED"}
    with pytest.raises(ValueError, match="ORIGINAL_E1_SOURCE_RIGHTS_NOT_ACCEPTED"):
        e1.audit_review(originals=changed, review=review)


def test_repeating_provider_is_refused(originals, review):
    forged = copy.deepcopy(review)
    forged["providers"][2]["id"] = "ALPACA_IEX"
    with pytest.raises(ValueError, match="UNKNOWN_DUPLICATE_OR_INVALID_SOURCE"):
        e1.audit_review(originals=originals, review=forged)


def test_public_reviewer_has_no_network_or_credentials_entrypoint():
    assert "requests" not in vars(e1)
    assert "httpx" not in vars(e1)
    assert "socket" not in vars(e1)
    assert e1.proposed_review_snapshot()["provider_requests_executed"] == 0
