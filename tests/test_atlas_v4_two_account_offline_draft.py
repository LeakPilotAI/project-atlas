"""Historical V4 two-account draft is structurally pinned, never enrollment authority."""

import hashlib
import json
from pathlib import Path

import pytest

from app.services.paper_financial_replay import digest, validate_manifest
from app.services.perp_operational_contract import validate_enrollment as validate_hl
from app.services.quality_dips_autonomous_enrollment import (
    validate_enrollment as validate_qd,
)

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "docs/ATLAS_TWO_ACCOUNT_UNAPPROVED_ENROLLMENT_BUNDLE_2026-11-08.json"
NEW = ROOT / "docs/ATLAS_TWO_ACCOUNT_V4_UNAPPROVED_ENROLLMENT_BUNDLE_2026-11-08.json"
OLD_SHA = "77c0fd0709f1bfbaeb6517ced4fdefac7461ea571a9d90a16cc602774d4b9616"
V4_SHA = "fd40c907ee6f62a1eabff4d347c1ca17c4438c8ddd3e226bc92d69db8290fbd1"
V4_RELEASE = "fc07ba532f9b88a2b6d281a4f5c60ef2b72deaed"
V4_ARTIFACT = "d7724787ef6f459d3a130f915dc7823ccc3de9c3d8337af4b948879e211ee5b5"
V4_HEAD = "fc0d8eccac057b1b23f872a1b01da7cd614a44cfb763fc2594a171da1f1cfd55"
FLAGS = (
    "creation_authorized",
    "account_inception_authorized",
    "paper_start_authorized",
    "enrollment_accepted",
    "live_order_authorized",
    "provider_check_authorized",
)


def _load():
    old_raw, new_raw = OLD.read_bytes(), NEW.read_bytes()
    assert hashlib.sha256(old_raw).hexdigest() == OLD_SHA
    assert hashlib.sha256(new_raw).hexdigest() == V4_SHA
    return json.loads(old_raw), json.loads(new_raw)


def test_v4_draft_pins_exact_selected_code_without_authority():
    old, new = _load()
    assert new["schema"] == old["schema"] == "ATLAS_PERSONAL_TWO_ACCOUNT_OFFLINE_DRAFT_BUNDLE_V1"
    assert new["status"] == "V4_REBIND_REVIEW_ONLY_NOT_ACCEPTED_OR_AUTHORIZED"
    assert new["selected_release_commit"] == V4_RELEASE
    assert new["selected_release_artifact_digest"] == V4_ARTIFACT
    assert new["selected_selector_head"] == V4_HEAD
    assert new["selected_release_artifact_digest"] != old["selected_release_artifact_digest"]
    assert all(new[k] is False for k in FLAGS)
    assert set(new["accounts"]) == {"QUALITY_DIPS", "HYPERLIQUID"}


@pytest.mark.parametrize("lane,validator", [
    ("QUALITY_DIPS", validate_qd), ("HYPERLIQUID", validate_hl)
])
def test_v4_draft_manifest_scope_is_consistent_but_enrollment_refuses(lane, validator):
    old, new = _load()
    account = new["accounts"][lane]
    orig = old["accounts"][lane]
    enrollment, manifest, scope = (
        account["native_enrollment_draft"], account["parameters"], account["report_scope_draft"]
    )
    validate_manifest(manifest)
    assert manifest["opening_cash"] == "1000"
    assert manifest["initial_net_r"] == "0"
    assert manifest["release"] == enrollment["release_digest"] == V4_ARTIFACT
    assert account["parameters_digest"] == enrollment["inception_digest"] == digest(manifest)
    assert scope["policy_digest"] == digest(manifest)
    assert scope["epoch"] == manifest["epoch"] == enrollment["epoch"]
    assert scope["account_id"] == enrollment["account_id"]
    assert enrollment["resources"] == orig["native_enrollment_draft"]["resources"]
    assert manifest["epoch"] == orig["parameters"]["epoch"]
    assert enrollment["writers"] is None and enrollment["acceptance_id"] is None
    assert account["native_financial_inception_published"] is False
    assert account["enrollment_schema_validated"] is False
    with pytest.raises((ValueError, TypeError)):
        validator(enrollment)


def test_v4_account_native_ids_are_distinct_draft_only():
    _, new = _load()
    ids = [
        tuple(root["native_id"])
        for account in new["accounts"].values()
        for root in account["native_enrollment_draft"]["resources"].values()
    ]
    assert len(ids) == len(set(ids)) == 12
    assert all(len(fid) == 3 and all(type(n) is int and n >= 0 for n in fid) for fid in ids)


@pytest.mark.parametrize("lane,folder", [
    ("QUALITY_DIPS", "QualityDips"),
    ("HYPERLIQUID", "Hyperliquid"),
])
def test_v4_rebind_preserves_unaccepted_epoch_roots_without_silent_migration(lane, folder):
    """Existing epoch strings are labels, never V4 authority or a new epoch."""
    old, new = _load()
    initial = old["accounts"][lane]
    current = new["accounts"][lane]
    e = current["native_enrollment_draft"]
    original = initial["native_enrollment_draft"]
    epoch = e["epoch"]
    assert epoch == original["epoch"]
    assert e["resources"] == original["resources"]
    assert current["native_financial_inception_published"] is False
    assert new["account_inception_authorized"] is False
    assert new["enrollment_accepted"] is False
    for role, resource in e["resources"].items():
        base = rf"D:\AtlasCustody\{folder}" if role == "custody" else rf"D:\AtlasPaper\{folder}"
        expected = base + "\\" + epoch + ("" if role == "custody" else "\\" + role)
        assert resource["path"] == expected
    if lane == "HYPERLIQUID":
        assert "de437abe" in epoch  # Historical directory label is not active V4.
        assert V4_RELEASE[:8] not in epoch
        assert e["release_digest"] == V4_ARTIFACT
