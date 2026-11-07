"""Offline V5 authorization contract tests. No native execution."""

import json
from pathlib import Path

import pytest

from scripts.observation_runtime import personal_native_compatibility_run as runner
from scripts.observation_runtime import personal_native_scope as scope
from scripts.observation_runtime.native_fixture_budget import (
    BudgetRefused,
    session_limits,
)

V4 = "P-ATLAS-PERSONAL-NATIVE-COMPATIBILITY-V4"
V5 = "P-ATLAS-PERSONAL-NATIVE-COMPATIBILITY-V5"

V5_APPROVAL = (
    "PERSONAL_NATIVE_COMPATIBILITY_OPERATOR_APPROVAL_V5.json"
)


def test_v5_is_active_authorization():
    assert scope.AUTHORIZATION == V5
    assert runner.AUTHORIZATION == V5


def test_v5_has_distinct_fixture_root():
    assert "continuation-fixture-" in scope.ROOT
    assert scope.ROOT != (
        r"D:\Work\Project Atlas\logs\diagnostics"
        r"\continuation-fixture-971b3f74095c43c89d4e48c29ffa93bd"
    )


def test_v4_cannot_authorize_v5():
    with pytest.raises((ValueError, BudgetRefused)):
        scope.require_scope(V4, scope.ROOT)

    with pytest.raises((ValueError, BudgetRefused)):
        session_limits(V4, scope.ROOT)


def test_v5_budget_is_exact():
    assert session_limits(V5, scope.ROOT) == (
        600,
        4096,
        134217728,
    )


def test_runner_uses_separate_v5_approval():
    source = Path(runner.__file__).read_text(encoding="utf-8")

    assert V5_APPROVAL in source
    assert (
        "PERSONAL_NATIVE_COMPATIBILITY_OPERATOR_APPROVAL_V4.json"
        not in source
    )


def test_missing_v5_approval_refuses(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "REPO", tmp_path)

    with pytest.raises(
        (ValueError, FileNotFoundError),
        match="APPROVAL|approval",
    ):
        runner.require_operator_approval(V5)


def test_v4_approval_cannot_substitute_for_v5(monkeypatch, tmp_path):
    approval_dir = tmp_path / "docs"
    approval_dir.mkdir()

    approval = {
        "schema": "ATLAS_NATIVE_OPERATOR_APPROVAL_V1",
        "authorization": V4,
        "root": scope.ROOT,
        "decision": "APPROVED_FOR_NATIVE_TESTS_ONLY",
        "financial_startup_authorized": False,
        "live_trading_authorized": False,
    }

    (approval_dir / V5_APPROVAL).write_text(
        json.dumps(approval),
        encoding="utf-8",
    )

    monkeypatch.setattr(runner, "REPO", tmp_path)

    with pytest.raises(ValueError):
        runner.require_operator_approval(V5)


def test_v5_plan_does_not_grant_execution():
    plan = runner.plan()

    assert plan["authorization_required"] == V5
    assert plan["status"] == "PROPOSED_NOT_AUTHORIZED"
    assert plan["operational_accounts"] is False
    assert plan["providers"] is False
    assert plan["genesis"] is False