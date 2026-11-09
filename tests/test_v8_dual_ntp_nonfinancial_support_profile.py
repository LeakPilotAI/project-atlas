"""V8 independently installed native app support is source-only, unselected.

The review package binds actual V8 receipt, source hashes and existing native
parents. No V8 activation or selector output is authorized by these tests.
"""
import hashlib
import json
from pathlib import Path

import pytest

from scripts import support_deployment as support
from scripts import build_support_deployment as builder
from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock

ROOT = Path(__file__).resolve().parents[1]
V8 = "c8cc4846508b29483d10a0b4c4353f8a26f1fc9c"
V7 = "af96bec0484a8e43f9965610e071a907a0d316bf"
RECEIPT_SHA = "ecb94e00e262e371caea494b1cc552352c892fa437a3b5f4946b54f7f863ae34"
ARTIFACT = "65c4b4661ec6aef7359e9dae716a416327379f5082a5b309ccdb5a148a569c95"
SOURCE = "230a35d8b293be0d38ded533bb964d36bc5bf3c80d432a85656bc4c22650979c"
OPERATOR = "ded15bde4e2b3ce845b2eaf95818b6c81fb3b759daf2b9375a68533710599e8d"
FOLDER = ROOT / "logs/diagnostics/atlas-v8-ntp-support-offline-proposal-20261108-r11"
MANIFEST_SHA = "13fbcf6b90cf1c2e6f5aa74aa60a057f6865d52097916db4d6e03669275eab86"
ARCHIVE_SHA = "77ed856d98f0fec39cc45280c35299c38147014aae933adbf6e5f7f3e0dae76d"


def manifest():
    m = json.loads((FOLDER / "deployment.json").read_bytes())
    assert support.sha(support.encoded(m)) == MANIFEST_SHA
    return m


def test_v8_support_profile_pinned_to_exact_native_app_receipt():
    m = manifest()
    assert m["application"] == {
        "release": V8,
        "root": "D:\\AtlasRuntime\\releases\\" + V8,
        "receipt": str(ROOT / "logs/diagnostics" / ("qd-unselected-release-" + V8 + ".json")),
        "receipt_sha256": RECEIPT_SHA,
        "artifact_digest": ARTIFACT,
    }
    assert support.support_clock_profile(m) == support.V7_NTP_CLOCK_PROFILE
    assert support.V8_NTP_APP == V8
    for field in ("receipt_sha256", "artifact_digest"):
        damaged = json.loads(json.dumps(m))
        damaged["application"][field] = "f" * 64
        with pytest.raises(ValueError, match="V8_NTP_INSTALLED_APPLICATION_PIN_REQUIRED"):
            support.support_clock_profile(damaged)
    assert support.support_clock_profile({"application": {
        **m["application"], "release": V7,
        "receipt_sha256": support.V7_NTP_RECEIPT_SHA256,
        "artifact_digest": support.V7_NTP_ARTIFACT_DIGEST,
    }}) == support.V7_NTP_CLOCK_PROFILE


def test_v8_exact_review_package_inventory_and_independent_ntp_bindings():
    m = manifest()
    assert m["schema"] == "QD_SUPPORT_DEPLOYMENT_V2"
    assert m["status"] == "REVIEW_INVENTORY_NOT_PERMISSION"
    assert m["domain"] == "WINDOWS_LOCAL"
    assert m["runtime"]["financial_writers"] is False
    assert m["runtime"]["providers"] is False
    assert m["runtime"]["workspace_fallback"] is False
    assert m["runtime"]["python"].endswith(V8 + "\\python\\python.exe")
    assert m["archive_sha256"] == ARCHIVE_SHA
    assert hashlib.sha256((FOLDER/"support-source.zip").read_bytes()).hexdigest() == ARCHIVE_SHA
    m2, files = support.prepare(m, FOLDER / "support-source.zip", MANIFEST_SHA)
    assert m2 == m
    pkg = support.strict(files["support-manifest.json"])
    assert pkg["application_release"] == V8
    assert pkg["installation_authorized"] is False
    assert pkg["financial_startup_authorized"] is False
    assert pkg["promotion_authorized"] is False
    assert pkg["providers_authorized"] is False
    assert pkg["clock"] == {
        "issuer": "ATLAS_INDEPENDENT_DUAL_NTP_V1_GOOGLE_CLOUDFLARE",
        "maximum_evidence_age_seconds": 120,
        "maximum_uncertainty_ms": 1000,
    }
    required = {x["path"]: x["sha256"] for x in pkg["required_installed_application_sources"]}
    assert required["scripts/observation_runtime/atlas_independent_ntp_clock.py"] == SOURCE
    assert required["scripts/observation_runtime/personal_v7_operator_clock.py"] == OPERATOR
    assert len(m["files"]) == 10 and len(required) == 17
    receipt = ROOT / "logs/diagnostics" / ("qd-unselected-release-" + V8 + ".json")
    assert hashlib.sha256(receipt.read_bytes()).hexdigest() == RECEIPT_SHA
    assert support.EXCLUSIONS == [
        "APPLICATION_PAYLOAD", "FINANCIAL_STATE", "PROVIDERS", "GENESIS",
        "DESKTOP_SHORTCUTS", "WINDOWS_CONFIGURATION", "AUTOMATIC_STARTUP",
    ]


def test_v8_parent_resource_ids_bound_to_existing_installed_v7_support():
    old = json.loads((ROOT/"logs/diagnostics/atlas-v7-ntp-support-offline-proposal-20261108-r10/deployment.json").read_bytes())
    m = manifest()
    assert m["accepted_parents"] == old["accepted_parents"]
    assert set(m["accepted_parents"]) == {
        "D:\\AtlasRuntime\\launchers",
        "D:\\AtlasRuntime\\support-installations",
        "D:\\AtlasRuntime\\selection",
    }
    assert len({tuple(x) for x in m["accepted_parents"].values()}) == 3
    assert m["application"]["release"] != old["application"]["release"]
    assert m["destination"] != old["destination"]
    assert m["control"] != old["control"]


def test_v8_support_is_deliberately_not_selected_or_financial():
    m = manifest()
    destination, control = Path(m["destination"]), Path(m["control"])
    if destination.exists() or control.exists():
        # After the authorized code-only install, retain native exact receipt
        # verification; never count a partial directory as an acceptance.
        assert destination.is_dir() and control.is_dir()
        receipt_bytes = (control / "receipt.json").read_bytes()
        receipt = support.verify_deployment(
            m, expected_receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest())
        assert receipt["selected"] is False
        assert receipt["financial_actions"] == 0
    else:
        assert not destination.exists() and not control.exists()
    assert not Path(r"D:\AtlasRuntime\selection\r0012.json").exists()
    from scripts.release_selection import digest
    current = json.loads(Path(r"D:\AtlasRuntime\selection\r0011.json").read_bytes())["record"]
    assert current["revision"] == 11 and current["selected"]["release"] == V7
    assert digest(current) == "933482b46a31af43270a193a94a83353e945fbecc4eb4661e8b7f8e9c8262997"


def test_v8_selection_is_refused_before_reading_native_support(monkeypatch):
    m = manifest()
    monkeypatch.setattr(support, "verify_deployment",
                        lambda *a,**kw: pytest.fail("cannot read V8 native support before clock handoff"))
    clock = object.__new__(IndependentNtpClock)
    with pytest.raises(ValueError, match="V8_SELECTION_CLOCK_HANDOFF_NOT_CERTIFIED"):
        support.select_release(approved=True, manifest=m,
            manifest_sha256=MANIFEST_SHA, receipt_sha256="f"*64,
            operation="d"*32, expected_head="f"*64, clock=clock)


def test_foreign_clock_and_missing_explicit_deployment_refused_without_install(monkeypatch):
    m = manifest()
    archive=FOLDER/"support-source.zip"
    monkeypatch.setattr(support, "_install",
                        lambda *a, **kw: pytest.fail("native write before review"))
    with pytest.raises(ValueError, match="SEPARATE_EXACT_SUPPORT_DEPLOYMENT_AUTHORIZATION_REQUIRED"):
        support.install_operational(manifest=m,archive=archive,
            manifest_sha256=MANIFEST_SHA,parent_identity=[1,2,3],clock=object())
    with pytest.raises(ValueError, match="GENUINE_SUPPORT_CLOCK_REQUIRED"):
        support.install_operational(approved=True,manifest=m,archive=archive,
            manifest_sha256=MANIFEST_SHA,parent_identity=[1,2,3],clock=object())


@pytest.mark.parametrize("field", ["receipt_sha256", "artifact_digest", "release"])
def test_v8_wrong_app_binding_never_passes_support_profile(field):
    m = manifest()
    m["application"][field] = "f"*64 if field != "release" else V7
    if field != "release":
        with pytest.raises(ValueError, match="V8_NTP_INSTALLED_APPLICATION_PIN_REQUIRED"):
            support.support_clock_profile(m)
    else:
        with pytest.raises(ValueError, match="V7_NTP_INSTALLED_APPLICATION_PIN_REQUIRED"):
            support.support_clock_profile(m)
