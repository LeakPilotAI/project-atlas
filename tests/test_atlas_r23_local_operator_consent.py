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


def test_separate_native_selection_scope_source_and_no_financial_authority(monkeypatch):
    from scripts import atlas_r23_code_only_select as selector
    from scripts.volume_inspector import windows_output

    assert local.EXPECTED_SELECTOR_HASH == selector.source_hash()
    assert local.SELECTION_SCOPE == selector.SCOPE
    monkeypatch.setattr(windows_output, "current_sid", lambda: "S-1-5-21-test")
    row = {
        "previous": "a" * 64,
        "selected": {
            "release": installer.SOURCE,
            "receipt_sha256": "b" * 64,
            "artifact_digest": "c" * 64,
        },
    }
    decision = local.selection_approval_record(row)
    assert decision["action"] == "ONE_SHOT_R23_NATIVE_CODE_ONLY_SELECT"
    assert decision["scope"] != local.SCOPE
    assert decision["scope"] == local.SELECTION_SCOPE
    assert decision["revision"] == 21
    assert decision["one_shot"] is True
    assert all(decision[k] is False for k in (
        "financial_authority", "provider_access", "paper_accounts",
        "paper_start_authorized", "live_trading_authorized",
    ))


@pytest.mark.parametrize("outcome", ("decline", "verified"))
def test_separate_selection_requires_second_distinct_local_phrase(
    monkeypatch, outcome,
):
    from scripts import atlas_r23_code_only_select as selector

    monkeypatch.setattr(local, "require_visible_local_console", lambda: True)
    monkeypatch.setattr(local, "preflight", lambda: {
        "code_only_scope": local.SCOPE,
    })
    monkeypatch.setattr(local, "pin_after_human_action", lambda: "a" * 64)
    monkeypatch.setattr(local.inst, "main", lambda args: {
        "status": "R23_CODE_ONLY_NATIVE_INSTALL_VERIFIED_UNSELECTED",
        "paper_start_authorized": False,
        "financial_authority": False,
    })
    monkeypatch.setattr(local, "selection_review", lambda: {
        "scope": local.SELECTION_SCOPE,
        "paper_start_authorized": False,
    })
    typed = iter([local.SCOPE,
                  local.SELECTION_SCOPE if outcome == "verified" else ""])
    monkeypatch.setattr("builtins.input", lambda prompt: next(typed))
    if outcome == "decline":
        monkeypatch.setattr(
            local, "pin_selection_after_human_action",
            lambda: pytest.fail("No local selection on missing second scope"),
        )
        assert local.main(["--approve-install-and-select"]) == 2
    else:
        calls = []
        monkeypatch.setattr(
            local, "pin_selection_after_human_action",
            lambda: "b" * 64,
        )
        monkeypatch.setattr(
            selector, "main",
            lambda args: calls.append(args) or {
                "status": "R23_NATIVE_CODE_ONLY_SELECTED_NO_FINANCIAL_START",
            },
        )
        assert local.main(["--approve-install-and-select"]) == 0
        assert calls == [[
            "--execute-approved-code-only",
            "--confirm-scope", local.SELECTION_SCOPE,
        ]]


def test_failed_native_install_refuses_second_scope_even_if_user_wants(monkeypatch):
    monkeypatch.setattr(local, "require_visible_local_console", lambda: True)
    monkeypatch.setattr(local, "preflight", lambda: {"scope": local.SCOPE})
    monkeypatch.setattr(local, "pin_after_human_action", lambda: "a" * 64)
    monkeypatch.setattr("builtins.input", lambda prompt: local.SCOPE)
    monkeypatch.setattr(local.inst, "main", lambda args: {
        "status": "UNKNOWN_PARTIAL_INSTALL",
        "paper_start_authorized": False,
        "financial_authority": False,
    })
    monkeypatch.setattr(
        local, "selection_review",
        lambda: pytest.fail("No selector admission after incomplete native copy"),
    )
    with pytest.raises(ValueError, match="SUCCESS_REQUIRED_BEFORE_SELECTION"):
        local.main(["--approve-install-and-select"])
