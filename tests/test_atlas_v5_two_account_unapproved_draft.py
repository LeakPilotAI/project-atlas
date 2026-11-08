"""Selected V5 two-account source-only rebinding regression, never financial activation."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from app.services.paper_financial_replay import digest, validate_manifest
from app.services.quality_dips_autonomous_enrollment import validate_enrollment as qd_enroll
from app.services.perp_operational_contract import validate_enrollment as hl_enroll

ROOT = Path(__file__).resolve().parents[1] / "docs"
HISTORICAL = ROOT / "ATLAS_TWO_ACCOUNT_V4_BASE_FEE_UNAPPROVED_ENROLLMENT_BUNDLE_2026-11-08.json"
CURRENT = ROOT / "ATLAS_TWO_ACCOUNT_V5_BASE_FEE_UNAPPROVED_ENROLLMENT_BUNDLE_2026-11-08.json"
HISTORICAL_SHA = "8379c100d2fe1dc67a11d91d83002694f16925895680786aa0885d6487e9a53b"
CURRENT_SHA = "d4b439d8b7c4ea8d51cd3a003f1cf68cc22f008b500b4c58acdf357af0cf6800"
V5_RELEASE = "247a4f4e1d78594cdb55ef55f185ef37921bf535"
V5_ARTIFACT = "5f5940fdc1e0dbc2cdda7def83b8b138dce3d868655012a34db8e59565832879"
V5_RECEIPT_SHA = "f6c359e3f216e1ef513aba3ce9d5d80ec3cb2bf170fe7aa604640bbc6a474cf8"
V5_HEAD = "cd1c73cd207ab363db53e4ae8713ba381f0f4fba4585729f48c1c6a872b2d66f"
AUTHORITY = ("creation_authorized", "enrollment_accepted", "account_inception_authorized",
             "provider_check_authorized", "paper_start_authorized", "live_order_authorized")
EXPECTED_DIGESTS = {
    "QUALITY_DIPS": "ad07479ae2f57da148b145612c7331322acd5d00e2f7279716a2d414243a376d",
    "HYPERLIQUID": "46023d87dc3dcae69c2340446627a45dccabec38e60ccabbf137f45870703703",
}


def load():
    old, now = HISTORICAL.read_bytes(), CURRENT.read_bytes()
    assert hashlib.sha256(old).hexdigest() == HISTORICAL_SHA
    assert hashlib.sha256(now).hexdigest() == CURRENT_SHA
    return json.loads(old), json.loads(now)


def test_old_v4_is_preserved_and_v5_is_exactly_selected_but_not_authorized():
    old, v5 = load()
    assert old["schema"] == v5["schema"] == "ATLAS_PERSONAL_TWO_ACCOUNT_OFFLINE_DRAFT_BUNDLE_V1"
    assert v5["status"] == "V5_PUBLIC_BASE_PERPS_FEES_REVIEW_ONLY_NOT_ACCEPTED_OR_AUTHORIZED"
    assert (v5["selected_release_commit"], v5["selected_release_artifact_digest"],
            v5["selected_selector_head"], v5["installed_receipt_sha256"]) == (
                V5_RELEASE, V5_ARTIFACT, V5_HEAD, V5_RECEIPT_SHA
            )
    assert all(old[k] is False and v5[k] is False for k in AUTHORITY)
    assert v5["policy_digest"] == old["policy_digest"]
    assert v5["hl_directory_receipt_sha256"] == old["hl_directory_receipt_sha256"]
    assert set(v5["accounts"]) == {"QUALITY_DIPS", "HYPERLIQUID"}
    assert any("provisional" in x.lower() for x in v5["provisional_values"])
    assert any("not permission" in x.lower() for x in v5["provisional_values"])


@pytest.mark.parametrize("lane,validator,currency", [
    ("QUALITY_DIPS", qd_enroll, "USD"), ("HYPERLIQUID", hl_enroll, "USDC")
])
def test_v5_release_manifests_rehashed_and_true_owner_required(lane, validator, currency):
    old, now = load()
    historical, current = old["accounts"][lane], now["accounts"][lane]
    m, n, report = current["parameters"], current["native_enrollment_draft"], current["report_scope_draft"]
    m_old, n_old, report_old = (historical["parameters"], historical["native_enrollment_draft"],
                               historical["report_scope_draft"])
    validate_manifest(m)
    assert m["release"] == n["release_digest"] == V5_ARTIFACT
    assert m["opening_cash"] == "1000" and m["currency"] == currency
    assert m["initial_net_r"] == "0" and m["opened_at"] == m_old["opened_at"]
    assert (m["epoch"], n["epoch"], report["epoch"]) == (m_old["epoch"], n_old["epoch"], report_old["epoch"])
    assert n["inception_digest"] == current["parameters_digest"] == report["policy_digest"] == EXPECTED_DIGESTS[lane]
    assert digest(m) == EXPECTED_DIGESTS[lane]
    assert report["account_id"] == n["account_id"] == report_old["account_id"]
    assert n["policy_digest"] == digest(m["autonomous_policy"] if lane == "QUALITY_DIPS" else m["perp_policy"])
    assert n["policy_digest"] == n_old["policy_digest"]
    assert current["parameters_schema_validated"] is True
    assert current["report_scope_validated_against_manifest"] is True
    assert current["native_financial_inception_published"] is False
    assert current["enrollment_schema_validated"] is False
    assert n["writers"] is None and n["acceptance_id"] is None
    assert current["identity_requirements_pending"] == historical["identity_requirements_pending"]
    assert n["resources"] == n_old["resources"]
    expected_manifest = copy.deepcopy(m_old)
    expected_manifest["release"] = V5_ARTIFACT
    assert m == expected_manifest
    assert {k: v for k, v in n.items() if k not in {"release_digest", "inception_digest"}} == {
        k: v for k, v in n_old.items() if k not in {"release_digest", "inception_digest"}}
    assert {k: v for k, v in report.items() if k != "policy_digest"} == {
        k: v for k, v in report_old.items() if k != "policy_digest"}
    with pytest.raises((TypeError, ValueError)):
        validator(n)


def test_twelve_original_distinct_native_resource_ids_never_silently_migrated():
    old, new = load()
    identities = []
    paths = []
    for lane in ("QUALITY_DIPS", "HYPERLIQUID"):
        n = new["accounts"][lane]["native_enrollment_draft"]
        prev = old["accounts"][lane]["native_enrollment_draft"]
        assert set(n["resources"]) == {"source", "projection", "control", "coordination", "report", "custody"}
        for role, resource in n["resources"].items():
            assert resource == prev["resources"][role]
            assert resource["path"].startswith("D:\\")
            assert n["epoch"] in resource["path"]
            identities.append(tuple(resource["native_id"]))
            paths.append(resource["path"].lower())
    assert len(identities) == len(set(identities)) == 12
    assert len(paths) == len(set(paths)) == 12


def test_hyperliquid_fee_and_unaccepted_market_source_still_conservative():
    old, new = load()
    p = new["accounts"]["HYPERLIQUID"]["parameters"]["perp_policy"]
    assert p == old["accounts"]["HYPERLIQUID"]["parameters"]["perp_policy"]
    assert (p["maker_bps"], p["taker_bps"]) == ("1.5", "4.5")
    assert p["fee_schedule_id"] == "PENDING_E1_VERIFIED_FEE_SCHEDULE"
    assert all(p[k].startswith("PENDING_E1_") for k in ("market_source", "funding_source", "instrument_cut"))
    assert new["accounts"]["HYPERLIQUID"]["native_enrollment_draft"]["epoch"].startswith("hl-paper-20261108-de437abe")
