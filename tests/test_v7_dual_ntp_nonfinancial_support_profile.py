"""V7 nonfinancial dual-NTP support profile; no live selection or install."""
import copy
import json
from pathlib import Path

import pytest

from scripts import support_deployment as support
from scripts import build_support_deployment as builder
from scripts import release_selection as selection

ROOT = Path(__file__).resolve().parents[1]
V7 = "af96bec0484a8e43f9965610e071a907a0d316bf"
APP_RECEIPT_SHA = "105c89ab10d20771474fe030489da7aabeb6900f22be57d25b745135bf28ac4d"
APP_ARTIFACT = "94374eda7eea82ac1c44905b21ab56b524128bc49e4253f3522838d230961827"
NTP_SOURCE = "230a35d8b293be0d38ded533bb964d36bc5bf3c80d432a85656bc4c22650979c"
LEGACY = "247a4f4e1d78594cdb55ef55f185ef37921bf535"


def app(release=V7):
    return {
        "release": release,
        "root": str(Path("D:/AtlasRuntime/releases") / release),
        "receipt": str(ROOT / "logs/diagnostics"/("qd-unselected-release-"+release+".json")),
        "receipt_sha256": APP_RECEIPT_SHA,
        "artifact_digest": APP_ARTIFACT,
    }


def test_v7_requires_exact_native_release_receipt_and_artifact():
    assert support.support_clock_profile({"application": app()}) == support.V7_NTP_CLOCK_PROFILE
    for field in ("receipt_sha256", "artifact_digest"):
        damaged = app()
        damaged[field] = "f"*64
        with pytest.raises(ValueError, match="V7_NTP_INSTALLED_APPLICATION_PIN_REQUIRED"):
            support.support_clock_profile({"application":damaged})
    assert support.support_clock_profile({"application":app(LEGACY)}) == "WINDOWS_TIME_CODE_SELECTION_V1"
    with pytest.raises(ValueError,match="REVIEWED_SUPPORT_APPLICATION_REQUIRED"):
        support.support_clock_profile({})


def test_v7_support_manifest_requires_new_clock_and_real_ntp_source(tmp_path,monkeypatch):
    # Fixture path uses original receipt bytes but is purely source/read-only;
    # only the package is written under an isolated diagnostics output.
    raw = (ROOT/"logs/diagnostics"/("qd-unselected-release-"+V7+".json")).read_bytes()
    actual = json.loads(raw)
    assert actual["artifact_digest"] == APP_ARTIFACT
    assert support.sha(raw) == APP_RECEIPT_SHA
    native = {r["path"].replace("\\", "/"):r["sha256"] for r in actual["files"]}
    assert native["scripts/observation_runtime/atlas_independent_ntp_clock.py"] == NTP_SOURCE
    accepted = {str(Path("D:/AtlasRuntime")/key):[1, 2, i]
                for i,key in enumerate(("launchers","support-installations","selection"),10)}
    from scripts import build_support_deployment as mod
    original = mod.source_bytes

    def read(root,name,**kw):
        if Path(root)/name == ROOT/"logs/diagnostics"/("qd-unselected-release-"+V7+".json"):
            return raw
        return original(root,name,**kw)

    monkeypatch.setattr(mod,"source_bytes",read)
    fixture = ROOT/"logs/diagnostics"/("qd-selector-v1-native-v7ntp-testfixture")
    fixture.mkdir(exist_ok=True)
    folder = fixture/("generated-"+tmp_path.name)
    if folder.exists():
        pytest.skip("create-only fixture from older run already exists")
    package = builder.build(
        output=folder,
        historical_manifest=ROOT/"docs/QD_SELECTOR_LAUNCHER_SUPPORT_MANIFEST_V1_2026-10-30.json",
        application=app(),accepted_parents=accepted)
    m, files = support.prepare(package["manifest"],package["archive"],package["manifest_sha256"])
    src = support.strict(files["support-manifest.json"])
    assert src["clock"]["issuer"]=="ATLAS_INDEPENDENT_DUAL_NTP_V1_GOOGLE_CLOUDFLARE"
    assert {"path":"scripts/observation_runtime/atlas_independent_ntp_clock.py",
            "sha256":NTP_SOURCE} in src["required_installed_application_sources"]
    assert m["application"]["release"]==V7
    assert m["runtime"]["providers"] is False and m["runtime"]["financial_writers"] is False
    assert m["status"]=="REVIEW_INVENTORY_NOT_PERMISSION"
    assert m["schema"]=="QD_SUPPORT_DEPLOYMENT_V2"
    # A manifest declaring Windows Time for V7 cannot be treated as correct
    # even when its new ZIP and package hash are internally consistent.
    assert all("ATLAS_INDEPENDENT" not in x["path"] for x in m["files"])
    assert folder.exists()  # source-only, no native support root touched


def test_exact_profile_new_release_only_and_old_launch_stays_legacy():
    text = (ROOT/"scripts/installed_nonfinancial_launcher.py").read_text(encoding="utf-8")
    assert "elif args.release == \""+V7+"\"" in text
    assert "clock = IndependentNtpClock(runtime_id=" in text
    assert "V7_INSTALLED_NTP_LAUNCHER_PIN_REQUIRED" in text
    assert 'clock_profile = "WINDOWS_TIME_CODE_SELECTION_V1"' in text
    assert "clock = LocalWindowsClock(" in text


def test_selector_has_distinct_default_denied_no_untyped_clock_expansion():
    text = (ROOT/"scripts/release_selection.py").read_text(encoding="utf-8")
    assert 'clock_profile="WINDOWS_TIME_CODE_SELECTION_V1"' in text
    assert "type(clock) is IndependentNtpClock" in text
    assert "type(clock) is LocalWindowsClock" in text
    assert "EXACT_V7_INDEPENDENT_NTP_SELECTION_REQUIRED" in text
    assert "SELECTION_COMPONENT_SUBSTITUTION" in text


def test_no_code_path_silently_changes_financial_flags():
    for path in ("scripts/support_deployment.py","scripts/installed_nonfinancial_launcher.py"):
        text=(ROOT/path).read_text(encoding="utf-8")
        assert "FINANCIAL_STATE" in text or "NONFINANCIAL" in text
    assert support.EXCLUSIONS == [
        "APPLICATION_PAYLOAD", "FINANCIAL_STATE", "PROVIDERS", "GENESIS",
        "DESKTOP_SHORTCUTS", "WINDOWS_CONFIGURATION", "AUTOMATIC_STARTUP",
    ]
