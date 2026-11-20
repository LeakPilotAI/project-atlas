"""Hyperliquid's public base fees are a draft assumption, never authority.

These tests guard historical proposal preservation and exact V4 financial
hash bindings. No sockets, financial writers, activation, or provider budget.
"""
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.paper_financial_replay import digest, validate_manifest
from app.services.perp_operational_contract import validate_enrollment as validate_hl
from app.services.quality_dips_autonomous_enrollment import (
    validate_enrollment as validate_qd,
)

ROOT = Path(__file__).resolve().parents[1] / "docs"
OLD = ROOT / "ATLAS_TWO_ACCOUNT_V4_UNAPPROVED_ENROLLMENT_BUNDLE_2026-11-08.json"
NEW = ROOT / "ATLAS_TWO_ACCOUNT_V4_BASE_FEE_UNAPPROVED_ENROLLMENT_BUNDLE_2026-11-08.json"
OLD_SHA = "fd40c907ee6f62a1eabff4d347c1ca17c4438c8ddd3e226bc92d69db8290fbd1"
NEW_SHA = "8379c100d2fe1dc67a11d91d83002694f16925895680786aa0885d6487e9a53b"
ARTIFACT = "d7724787ef6f459d3a130f915dc7823ccc3de9c3d8337af4b948879e211ee5b5"
AUTHORITY_FLAGS = ("creation_authorized", "enrollment_accepted",
                   "account_inception_authorized", "provider_check_authorized",
                   "paper_start_authorized", "live_order_authorized")


def _load():
    old_raw, new_raw = OLD.read_bytes(), NEW.read_bytes()
    assert hashlib.sha256(old_raw).hexdigest() == OLD_SHA
    assert hashlib.sha256(new_raw).hexdigest() == NEW_SHA
    return json.loads(old_raw), json.loads(new_raw)


def test_base_fee_review_is_unapproved_and_preserves_original():
    old, new = _load()
    assert new["schema"] == old["schema"] == "ATLAS_PERSONAL_TWO_ACCOUNT_OFFLINE_DRAFT_BUNDLE_V1"
    assert new["status"] == "V4_PUBLIC_BASE_PERPS_FEES_REVIEW_ONLY_NOT_ACCEPTED_OR_AUTHORIZED"
    assert new["selected_release_artifact_digest"] == old["selected_release_artifact_digest"] == ARTIFACT
    assert new["selected_release_commit"] == old["selected_release_commit"]
    assert new["selected_selector_head"] == old["selected_selector_head"]
    assert all(old[k] is False and new[k] is False for k in AUTHORITY_FLAGS)
    assert new["accounts"]["QUALITY_DIPS"] == old["accounts"]["QUALITY_DIPS"]
    assert set(new["accounts"]) == {"QUALITY_DIPS", "HYPERLIQUID"}


@pytest.mark.parametrize("lane,validator", [("QUALITY_DIPS", validate_qd), ("HYPERLIQUID", validate_hl)])
def test_base_fee_enrollment_remains_unaccepted_and_digests_bound(lane, validator):
    old, new = _load()
    account = new["accounts"][lane]
    e, m, scope = (account["native_enrollment_draft"], account["parameters"],
                   account["report_scope_draft"])
    validate_manifest(m)
    assert m["release"] == e["release_digest"] == ARTIFACT
    assert m["opening_cash"] == "1000" and m["initial_net_r"] == "0"
    assert m["epoch"] == e["epoch"] == scope["epoch"]
    assert e["inception_digest"] == account["parameters_digest"] == digest(m)
    assert scope["policy_digest"] == digest(m)
    assert scope["account_id"] == e["account_id"]
    assert e["resources"] == old["accounts"][lane]["native_enrollment_draft"]["resources"]
    assert e["writers"] is None and e["acceptance_id"] is None
    assert account["native_financial_inception_published"] is False
    assert account["enrollment_schema_validated"] is False
    with pytest.raises((ValueError, TypeError)):
        validator(e)


def test_perp_base_fees_and_cost_accounting_and_pending_e1():
    old, new = _load()
    old_hl = old["accounts"]["HYPERLIQUID"]
    proposed = new["accounts"]["HYPERLIQUID"]
    original = old_hl["parameters"]["perp_policy"]
    p = proposed["parameters"]["perp_policy"]
    assert (original["maker_bps"], original["taker_bps"]) == ("1", "2")
    assert (p["maker_bps"], p["taker_bps"]) == ("1.5", "4.5")
    assert proposed["native_enrollment_draft"]["policy_digest"] == digest(p)
    assert original.keys() == p.keys()
    assert all(p[k] == original[k] for k in p.keys() - {"maker_bps", "taker_bps"})
    assert p["fee_schedule_id"] == "PENDING_E1_VERIFIED_FEE_SCHEDULE"
    assert all(p[k].startswith("PENDING_E1") for k in ("market_source", "funding_source", "instrument_cut"))
    assert Decimal(p["maker_bps"]) >= Decimal(original["maker_bps"])
    assert Decimal(p["taker_bps"]) >= Decimal(original["taker_bps"])
    total_notional = Decimal("200")
    old_taker_cost = total_notional * Decimal(original["taker_bps"]) / 10000
    proposed_taker_cost = total_notional * Decimal(p["taker_bps"]) / 10000
    assert (old_taker_cost, proposed_taker_cost) == (Decimal("0.04"), Decimal("0.09"))
    assert proposed_taker_cost > old_taker_cost
