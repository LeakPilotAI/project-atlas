"""Read source pins and fake the reservation boundary; no native children."""
import copy
import hashlib
import json
from unittest.mock import Mock

import pytest

from scripts.observation_runtime import native_fixture_budget as budget
from scripts.observation_runtime import personal_native_compatibility_run as runner


def manifest():
    return json.loads(runner.SCOPE_FILE.read_text(encoding="utf8"))


def test_review_manifest_matches_all_declared_source_files():
    runner.verify_source_scope(manifest())
    assert len(set(runner.SOURCE_FILES)) == len(runner.SOURCE_FILES)
    for name in ("personal_native_job.py", "personal_native_windows_api.py", "personal_native_launch_contract.py"):
        assert "scripts/observation_runtime/" + name in runner.SOURCE_FILES


def test_raw_source_snapshot_also_matches():
    value = manifest()
    assert set(value["raw_source_files"]) == set(runner.SOURCE_FILES)
    for name, expected in value["raw_source_files"].items():
        assert hashlib.sha256((runner.REPO / name).read_bytes()).hexdigest() == expected


@pytest.mark.parametrize("name", [
    "scripts/observation_runtime/personal_native_job.py",
    "scripts/observation_runtime/personal_native_windows_api.py",
    "tests/personal_native_compatibility_fixture.py",
])
def test_native_or_owner_source_drift_is_refused(name):
    value = copy.deepcopy(manifest())
    value["source_files"][name] = "0" * 64
    with pytest.raises(ValueError, match="NATIVE_SCOPE_SOURCE_CHANGED"):
        runner.verify_source_scope(value)


def test_manifest_is_not_authority_or_execution_readiness():
    value = manifest()
    assert value["status"] == "PROPOSED_NOT_AUTHORIZED"
    assert value["execution_ready"] is False
    assert value["financial_startup_authorized"] is False
    assert value["native_execution_authorized"] is False
    assert len(value["blocking_acceptance_tests"]) == 4
    assert value["root"] == runner.ROOT
    assert value["limits"] == {"seconds":600,"entries":4096,"charged_bytes":134217728}


def test_missing_real_v5_approval_still_refuses():
    assert not (runner.REPO / "docs/PERSONAL_NATIVE_COMPATIBILITY_OPERATOR_APPROVAL_V5.json").exists()
    with pytest.raises(ValueError, match="NATIVE_OPERATOR_APPROVAL_RECORD_REQUIRED"):
        runner.require_operator_approval(runner.AUTHORIZATION)


def test_matching_manifest_cannot_create_root_before_containment_is_ready(monkeypatch):
    # Explicit test-only approval stub. No approval file is created.
    monkeypatch.setattr(runner,"require_operator_approval",lambda scope:None)
    create = Mock(side_effect=AssertionError("must not create native fixture"))
    monkeypatch.setattr(budget,"create_session",create)
    with pytest.raises(ValueError,match="NATIVE_CONTAINMENT_NOT_READY_FOR_EXECUTION"):
        runner.execute(runner.AUTHORIZATION)
    create.assert_not_called()
