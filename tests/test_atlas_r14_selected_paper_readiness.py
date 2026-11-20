"""Selected R14 financial PAPER readiness: pure refusal + native read-only tests.

Never launches service/PAPER session, connects providers, signals Stop, or
replays the 263MB native readback done during release commissioning.
"""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import release_selection
from scripts.observation_runtime import atlas_r14_selected_paper_readiness as r14


@pytest.fixture(scope="module")
def read_only_snapshot():
    return r14.inspect()


def test_real_r14_native_code_selected_revision13_identity(read_only_snapshot):
    out = read_only_snapshot
    native = out["selected_code_identity"]
    assert native["selected_release"] == release_selection.R14_CODE_RELEASE
    assert native["revision"] == 13
    assert native["native_selection_head"] == r14.R14_HEAD
    assert native["native_selection_record_verified"] is True
    assert native["financial_authority"] is False
    assert native["native_r13_envelope_sha256"] == r14.R13_SHA
    assert native["native_installed_receipt_sha256"] == r14.R14_SHA
    assert hashlib.sha256((r14.SELECTION_ROOT/"r0013.json").read_bytes()).hexdigest() == r14.R13_SHA
    assert hashlib.sha256((r14.SELECTION_ROOT/"r0012.json").read_bytes()).hexdigest() == r14.R12_SHA


def test_actual_r14_desktop_start_stop_remain_blocked(read_only_snapshot):
    out = read_only_snapshot
    assert out["lifecycle"]["workspace_desktop"] == {
        "desktop_start":"BLOCKED_LEGACY",
        "desktop_stop":"BLOCKED_LEGACY",
    }
    selected = out["lifecycle"]["selected_runtime_script_checks"]
    assert selected["Atlas-Launch.ps1"] == "BLOCKED_LEGACY"
    assert selected["Atlas-Stop.ps1"] == "BLOCKED_LEGACY"
    assert selected["Atlas-Paper-Stop-Request.ps1"] == "SOURCE_ONLY_STOP_SIGNAL_NOT_FLATNESS_RECEIPT"


def test_all_nine_formal_operating_gates_still_reject_activation(read_only_snapshot):
    out = read_only_snapshot
    assert out["schema"] == "ATLAS_SELECTED_R14_PAPER_READINESS_V1"
    assert out["decision"] == "NO_GO"
    assert out["selected_code_verified"] is True
    assert out["selected_code_is_financial_authority"] is False
    assert out["accepted_financial_operating_gates"] == 0
    assert out["total_financial_operating_gates"] == 9
    assert len(out["gates"]) == 9
    assert len({gate["gate"] for gate in out["gates"]}) == 9
    assert all(gate["accepted"] is False
               and gate["status"] == "NOT_INDEPENDENTLY_ACCEPTED"
               and gate["next_evidence"] for gate in out["gates"])
    for field in (
        "desktop_one_click_paper_ready","paper_start_authorized",
        "paper_orders_authorized","live_orders_authorized",
        "provider_access_authorized","financial_ledger_mutation",
        "automatic_startup",
    ):
        assert out[field] is False


@pytest.mark.parametrize("field,value", [
    ("selected_release", "2d4879878bf58bea5a3ed0a986b809791f638fec"),
    ("revision", 12),
    ("native_selection_head", "0"*64),
    ("native_selection_record_verified", False),
    ("financial_authority", True),
])
def test_foreign_or_financial_native_identity_is_refused(read_only_snapshot,field,value):
    snapshot = copy.deepcopy(read_only_snapshot)
    snapshot["selected_code_identity"][field] = value
    with pytest.raises(ValueError, match="R14_READINESS_SELECTED_CODE_IDENTITY_REQUIRED"):
        r14.evaluate(snapshot["selected_code_identity"],snapshot["lifecycle"])


@pytest.mark.parametrize("field,value", [
    ("desktop_start","READY_FOR_PAPER"),
    ("desktop_stop","PAPER_STOP_COMPLETED"),
])
def test_forged_desktop_success_state_fails_closed(read_only_snapshot,field,value):
    lifecycle = copy.deepcopy(read_only_snapshot["lifecycle"])
    lifecycle["workspace_desktop"][field] = value
    with pytest.raises(ValueError, match="R14_READINESS_LIFECYCLE_EVIDENCE_REFUSED"):
        r14.evaluate(read_only_snapshot["selected_code_identity"],lifecycle)


def test_missing_owned_stop_evidence_refuses(read_only_snapshot):
    lifecycle = copy.deepcopy(read_only_snapshot["lifecycle"])
    lifecycle["stop_requires_owned_session_and_durable_flat_receipt"] = False
    with pytest.raises(ValueError, match="R14_READINESS_LIFECYCLE_EVIDENCE_REFUSED"):
        r14.evaluate(read_only_snapshot["selected_code_identity"],lifecycle)


def test_generic_unverified_desktop_does_not_self_promote(read_only_snapshot):
    lifecycle = copy.deepcopy(read_only_snapshot["lifecycle"])
    lifecycle["workspace_desktop"] = {
        "desktop_start":"UNVERIFIED","desktop_stop":"UNVERIFIED"
    }
    report = r14.evaluate(read_only_snapshot["selected_code_identity"],lifecycle)
    assert report["decision"] == "NO_GO"
    assert report["accepted_financial_operating_gates"] == 0
    assert report["desktop_one_click_paper_ready"] is False


def test_pinned_real_native_r13_hash_refusal(monkeypatch):
    monkeypatch.setattr(r14,"R13_SHA","0"*64)
    with pytest.raises(ValueError,match="R14_READINESS_PUBLISHED_REV13_BYTES_CHANGED"):
        r14.collect_selected_reference()


def test_pinned_native_r14_receipt_refusal(monkeypatch):
    monkeypatch.setattr(r14,"R14_SHA","0"*64)
    with pytest.raises(ValueError,match="R14_READINESS_R14_NATIVE_REFERENCE_CHANGED"):
        r14.collect_selected_reference()


def test_no_false_success_exit_in_cli(capsys):
    assert r14.main(["--inspect"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["decision"] == "NO_GO"
    assert out["selected_code_identity"]["revision"] == 13
    assert out["accepted_financial_operating_gates"] == 0


def test_no_cli_execute_mode():
    with pytest.raises(SystemExit):
        r14.main(["--start-paper"])
    with pytest.raises(SystemExit):
        r14.main(["--activate"])
