"""R23 local human approval helper: no tests create a decision or install release."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts import atlas_r23_code_only_install as installer
from scripts import atlas_r23_local_operator_consent as local


def test_exact_current_source_and_distinct_code_only_scope():
    assert local.EXPECTED_HASH == installer.source_hash()
    assert local.SCOPE == installer.SCOPE
    assert local.SOURCE_ROOT == Path("D:/Work/Project Atlas")


def test_headless_remote_invocation_fails_before_preflight_or_approval(monkeypatch):
    monkeypatch.setattr(
        local, "require_visible_local_console",
        lambda: (_ for _ in ()).throw(
            ValueError("R23_VISIBLE_LOCAL_WINDOWS_OPERATOR_CONSOLE_REQUIRED")
        ),
    )
    monkeypatch.setattr(
        local, "preflight",
        lambda: pytest.fail("No native review or decision without local console"),
    )
    with pytest.raises(ValueError, match="VISIBLE_LOCAL_WINDOWS_OPERATOR"):
        local.main(["--approve-and-install"])


def test_review_mode_only_displays_preflight_result(monkeypatch, capsys):
    monkeypatch.setattr(
        local, "preflight",
        lambda: {
            "status": "PREPARED_LOCAL_OPERATOR_DECISION_NOT_APPROVED",
            "paper_start_authorized": False,
        },
    )
    assert local.main(["--review"]) == 0
    output = capsys.readouterr().out
    assert "PREPARED_LOCAL_OPERATOR_DECISION_NOT_APPROVED" in output
    assert '"paper_start_authorized": false' in output


def test_decision_record_never_grants_accounts_trading_or_selection(monkeypatch):
    from scripts.volume_inspector import windows_output
    monkeypatch.setattr(installer, "original_selected_r21", lambda: {
        "artifact_digest": "a" * 64,
    })
    monkeypatch.setattr(windows_output, "current_sid", lambda: "S-1-5-21-test")
    row = local.approval_record()
    assert row["operator_sid"] == "S-1-5-21-test"
    assert row["native_predecessor_artifact_digest"] == "a" * 64
    assert row["installer_source_sha256"] == local.EXPECTED_HASH
    assert row["scope"] == local.SCOPE
    assert row["one_shot"] is True
    assert all(row[key] is False for key in (
        "financial_authority", "provider_access", "paper_accounts",
        "paper_start_authorized", "live_trading_authorized",
    ))
