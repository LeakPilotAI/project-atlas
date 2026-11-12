"""R17 real empty original roots + PURE intentionally UNACCEPTED writer shape."""
from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.observation_runtime import atlas_r17_native_roster_structure as roster
from scripts.observation_runtime import atlas_r17_parked_native_job_probe as owner
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)

ORIGINAL = {
    "pid":17238,
    "creation_filetime":183000000010000000,
    "image":owner.IMAGE,
}


def test_real_original_root_identity_structural_rosters_no_acceptance():
    before = inspect_two_lane_native_roots()
    preserved = deepcopy(before)
    result = roster.verify_unaccepted_selected_rosters(
        original=ORIGINAL, evidence=before,
        release_digest="bb8e0c3835400e515cc3079986be220dbd6f876e36bfd02808289245dada1d00",
        original_image=owner.IMAGE,
    )
    assert result["original_process_writer_role_count"] == 12
    assert result["original_native_root_ids_bound"] == 12
    assert result["all_enrollments_intentionally_unaccepted"] is True
    assert result["financial_writer_enrolled"] == 0
    assert result["native_account_files_created"] == 0
    assert result["paper_start_authorized"] is False
    assert result["live_trading_authorized"] is False
    assert inspect_two_lane_native_roots() == preserved


@pytest.mark.parametrize("damage", [
    "bad_pid", "foreign_image", "wrong_release",
    "one_nonempty_root", "missing_native_root",
    "root_identity_false", "no_root_id", "wrong_image",
    "duplicate_root", "same_epoch", "foreign_root_path",
])
def test_unaccepted_rosters_refuse_untrusted_native_preconditions(damage):
    proof = inspect_two_lane_native_roots()
    original = deepcopy(ORIGINAL)
    artifact = "bb8e0c3835400e515cc3079986be220dbd6f876e36bfd02808289245dada1d00"
    original_image = owner.IMAGE
    if damage == "bad_pid":
        original["pid"] = True
    elif damage == "foreign_image":
        original["image"] = r"D:\Bad\python.exe"
    elif damage == "wrong_release":
        artifact = "FOREIGN_RELEASE"
    elif damage == "one_nonempty_root":
        proof["all_twelve_distinct_and_empty"] = False
    elif damage == "missing_native_root":
        proof["lanes"]["QUALITY_DIPS"]["roots"].pop("source")
    elif damage == "root_identity_false":
        proof["lanes"]["QUALITY_DIPS"]["roots"]["source"]["native_identity_verified"] = False
    elif damage == "no_root_id":
        proof["lanes"]["HYPERLIQUID"]["roots"]["source"].pop("native_id")
    elif damage == "wrong_image":
        original_image = r"D:\Other\python.exe"
    elif damage == "duplicate_root":
        proof["lanes"]["HYPERLIQUID"]["roots"]["source"]["native_id"] = (
            proof["lanes"]["QUALITY_DIPS"]["roots"]["source"]["native_id"]
        )
    elif damage == "same_epoch":
        proof["lanes"]["HYPERLIQUID"]["epoch"] = (
            proof["lanes"]["QUALITY_DIPS"]["epoch"]
        )
    elif damage == "foreign_root_path":
        proof["lanes"]["HYPERLIQUID"]["roots"]["source"]["path"] = r"C:\Foreign"
    with pytest.raises((ValueError, KeyError, TypeError)):
        roster.verify_unaccepted_selected_rosters(
            original=original, evidence=proof,
            release_digest=artifact,
            original_image=original_image,
        )


def test_extra_finance_claim_not_a_publisher_or_issuer():
    assert not hasattr(roster,"publish")
    assert not hasattr(roster,"lease")
    assert not hasattr(roster,"incept")
    assert not hasattr(roster,"place_order")
    with pytest.raises(SystemExit):
        owner.main(["--execute-structural-rosters","--confirm-scope","WRONG"])
    assert owner.ROSTER_RECEIPT != owner.RECEIPT
