"""Native selected-release financial issuer preflight: no fake release enrollment."""
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.observation_runtime import personal_activation_commission as activation
from scripts.observation_runtime import (
    personal_native_financial_release_origin as origin,
)
from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE
from scripts.observation_runtime.personal_version_safe_release_clock import PROFILE
from scripts.release_selection import validate_spec

RELEASE = "c" * 40
ARTIFACT = "a" * 64
ROOT = Path("D:/AtlasRuntime/releases") / RELEASE
MODULE = ROOT / "scripts/observation_runtime/personal_activation_commission.py"
EXECUTABLE = ROOT / "python/python.exe"


def specimen():
    return {
        "schema": "QD_INSTALLED_RELEASE_REFERENCE_V1",
        "domain": "WINDOWS_LOCAL",
        "release": RELEASE,
        "root": str(ROOT),
        "receipt": str(Path("D:/Work/Project Atlas/logs/diagnostics")
                       / ("qd-unselected-release-" + RELEASE + ".json")),
        "receipt_sha256": "b" * 64,
        "artifact_digest": ARTIFACT,
    }


def test_exact_installed_image_source_and_selected_artifact_path_is_only_precondition():
    report = origin.validate_origin(
        module_path=MODULE,
        executable=EXECUTABLE,
        selected=specimen(),
        release_digest=ARTIFACT,
    )
    assert report["installed_source_and_process_path_bound"]
    assert report["selected_artifact_digest_bound"]
    assert report["schema"] == origin.SCHEMA
    assert not report["financial_writer_lease_issued"]
    assert not report["financial_activation_published"]
    assert not report["paper_start_authorized"]
    assert not report["live_trading_authorized"]


@pytest.mark.parametrize("damage", [
    "workspace_code", "unselected_code", "foreign_executable",
    "foreign_python_release", "old_release", "wrong_digest",
    "wrong_spec_root", "bad_spec_schema", "nonexact_digest", "bad_module",
])
def test_foreign_source_or_release_never_qualifies_financial_precondition(damage):
    spec = specimen()
    module, executable, release_digest = MODULE, EXECUTABLE, ARTIFACT
    if damage == "workspace_code":
        module = Path("D:/Work/Project Atlas/scripts/observation_runtime/personal_activation_commission.py")
    elif damage == "unselected_code":
        module = Path("D:/AtlasRuntime/releases/" + "d"*40 + "/scripts/observation_runtime/personal_activation_commission.py")
    elif damage == "foreign_executable":
        executable = Path("C:/Python312/python.exe")
    elif damage == "foreign_python_release":
        executable = Path("D:/AtlasRuntime/releases/" + "d"*40 + "/python/python.exe")
    elif damage == "old_release":
        spec["release"] = "d"*40
    elif damage == "wrong_digest":
        release_digest = "c"*64
    elif damage == "wrong_spec_root":
        spec["root"] = str(Path("D:/AtlasRuntime/releases") / ("d"*40))
    elif damage == "bad_spec_schema":
        spec["schema"] = "UNTRUSTED"
    elif damage == "nonexact_digest":
        release_digest = True
    elif damage == "bad_module":
        module = MODULE.with_name("not_an_activation.py")
    with pytest.raises(ValueError, match="FINANCIAL_ACTIVATION|EXACT_INSTALLED|SELECTION_FOREIGN"):
        origin.validate_origin(
            module_path=module, executable=executable,
            selected=spec, release_digest=release_digest)


def test_no_additional_fields_or_source_placeholders_qualify_selection():
    spec = specimen()
    spec["financial_writer_lease_issued"] = True
    with pytest.raises(ValueError, match="EXACT_INSTALLED"):
        origin.validate_origin(module_path=MODULE, executable=EXECUTABLE,
                               selected=spec, release_digest=ARTIFACT)


def test_no_workspace_financial_activation_before_reading_any_json(monkeypatch):
    # The host checkout must never become a native financial activation issuer.
    # An installed successor must execute its installed copy instead.
    calls = []
    monkeypatch.setattr(
        activation, "read_bounded_activation_input",
        lambda *_args, **_kwargs: calls.append("read") or pytest.fail("JSON_READ"))
    monkeypatch.setattr(
        activation, "publish_personal_activation",
        lambda **_kwargs: pytest.fail("FINANCIAL_PUBLISHED"))
    with pytest.raises(ValueError, match="FINANCIAL_ACTIVATION_SOURCE_MUST_BE_INSTALLED"):
        activation.commission(
            root=r"D:\AtlasCustody\PersonalPaper\future-disposable-not-created",
            record_path="missing.json", policy_path="missing.json",
            release_digest=ARTIFACT, accounts_path="missing.json",
            expected_clock_source=SOURCE, runtime_id="offline-only",
            qd_enrollment_path="missing-qd.json",
            perp_enrollment_path="missing-perp.json",
            clock_profile=PROFILE,
        )
    assert calls == []


def test_local_workspace_origin_refuses_before_selector_store(monkeypatch):
    from scripts import release_selection_store as store
    monkeypatch.setattr(
        store, "NativeSelectionStore",
        lambda **_kwargs: pytest.fail("SELECTOR_NEVER_OPEN_ON_WORKSPACE"))
    with pytest.raises(ValueError, match="FINANCIAL_ACTIVATION_SOURCE_MUST_BE_INSTALLED"):
        origin.require_selected_native_origin(release_digest=ARTIFACT)


def test_current_selected_reference_is_proven_without_financial_grant():
    # Read the current native selection, not a historical hardcoded R16
    # selector. A pure path proof does NOT grant financial writer authority.
    from scripts.observation_runtime.personal_version_safe_release_clock import (
        SELECTOR_NATIVE,
    )
    from scripts.release_selection_store import NativeSelectionStore

    store = NativeSelectionStore(
        root=r"D:\AtlasRuntime\selection", native_root=list(SELECTOR_NATIVE))
    try:
        with store.locked():
            rows = store.records()
        assert len(rows) in (15, 16)
        assert rows[-1]["revision"] == len(rows)
        selection = validate_spec(rows[-1]["selected"], "WINDOWS_LOCAL")
    finally:
        store.close()
    selected_release = Path(selection["root"])
    assert selection["release"] == selected_release.name
    report = origin.validate_origin(
        module_path=selected_release / "scripts/observation_runtime/personal_activation_commission.py",
        executable=selected_release / "python/python.exe",
        selected=deepcopy(selection),
        release_digest=selection["artifact_digest"],
    )
    assert report["selected_code_release"] == selection["release"]
    assert report["selected_artifact_digest_bound"]
    assert not report["financial_writer_lease_issued"]


def test_direct_activation_publisher_refuses_workspace_origin_before_native_file_write(
        monkeypatch):
    from scripts.observation_runtime import personal_activation_publisher as publisher
    from scripts.observation_runtime import personal_windows_clock as window_clock
    from scripts.volume_inspector import windows_output

    class FakeLocalWindowsClock:
        def require_operational(self, runtime_id):
            assert runtime_id == "synthetic-readonly"
        def runtime_sample(self):
            return {"utc": 1700000000}
        def verify_runtime_sample(self, sample):
            return sample == {"utc": 1700000000}

    monkeypatch.setattr(window_clock, "LocalWindowsClock", FakeLocalWindowsClock)
    monkeypatch.setattr(windows_output, "current_sid", lambda: "synthetic-operator")
    monkeypatch.setattr(
        "backend.app.services.personal_paper_runtime.validate_activation_record",
        lambda *_args, **_kwargs: True)
    monkeypatch.setattr(publisher, "_native_store",
                        lambda: pytest.fail("UNINSTALLED_WORKSPACE_ENTERED_NATIVE_WRITER"))
    with pytest.raises(publisher.PersonalActivationPublicationRefused,
                       match="Selected installed native activation origin required"):
        publisher.publish_personal_activation(
            root=r"D:\AtlasCustody\PersonalPaper\workspace-must-refuse",
            record={"actions": ["READ_ONLY"]}, policy={},
            operator_id="synthetic-operator",
            release_digest=ARTIFACT, accounts={"QUALITY_DIPS": "b"*64},
            clock=FakeLocalWindowsClock(), runtime_id="synthetic-readonly",
        )


def test_origin_helper_resolves_exact_native_activation_sibling_not_itself():
    helper = ROOT / "scripts/observation_runtime/personal_native_financial_release_origin.py"
    assert origin.resolve_installed_activation_module(helper) == MODULE
    assert origin.resolve_installed_activation_module(helper) != helper
    # The wrong helper-as-activation path was previously passed to this
    # validator and rejected even when R17 was genuinely selected.
    with pytest.raises(ValueError, match="EXACT_NATIVE_CODE_ORIGIN"):
        origin.validate_origin(module_path=helper, executable=EXECUTABLE,
                               selected=specimen(), release_digest=ARTIFACT)
    report = origin.validate_origin(
        module_path=origin.resolve_installed_activation_module(helper),
        executable=EXECUTABLE,
        selected=specimen(),
        release_digest=ARTIFACT,
    )
    assert report["selected_code_release"] == RELEASE
    assert report["financial_writer_lease_issued"] is False


@pytest.mark.parametrize("helper", [
    MODULE,
    Path("D:/Work/Project Atlas/scripts/observation_runtime/not_origin.py"),
    Path("D:/AtlasRuntime/releases/" + "c"*40 + "/scripts/foreign/personal_native_financial_release_origin.py"),
    Path("D:/AtlasRuntime/releases/" + "c"*40 + "/foreign/personal_native_financial_release_origin.py"),
    Path("relative/personal_native_financial_release_origin.py"),
    "D:/AtlasRuntime/releases/" + "c"*40 + "/scripts/observation_runtime/personal_native_financial_release_origin.py",
])
def test_activation_helper_never_accepts_unexpected_module_identity(helper):
    with pytest.raises(ValueError, match="EXACT_ORIGIN_HELPER_REQUIRED"):
        origin.resolve_installed_activation_module(helper)
