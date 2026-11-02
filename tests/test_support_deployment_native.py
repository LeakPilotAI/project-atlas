"""Opt-in real Windows fixture copy, installed controller, HTTP and cleanup."""
import json
import os
import socket
import subprocess
import time
import uuid
from contextlib import closing
from http.client import HTTPConnection
from pathlib import Path

import pytest
from support_native_cleanup import finish_controller

from scripts import support_deployment as s
from scripts.build_support_deployment import build
from scripts.installed_nonfinancial_launcher import read_ready
from scripts.release_selection import ReleaseSelector, encoded
from scripts.release_selection_store import NativeSelectionStore

SCOPE = os.environ.get("ATLAS_SUPPORT_NATIVE_FIXTURE")
pytestmark = pytest.mark.skipif(not SCOPE, reason="Explicit disposable Windows scope required")


class Clock:
    domain = "DISPOSABLE"
    def require_operational(self, runtime):
        return runtime


def protected(path):
    from scripts.volume_inspector import windows_output as w
    with s.held(w.WindowsOutput.create_root(str(path))) as out:
        return s.identity(w, out.root_handle)


def make_package(case, application):
    output = case / ("package-" + uuid.uuid4().hex[:8])
    return build(output=output, historical_manifest="docs/QD_SELECTOR_LAUNCHER_SUPPORT_MANIFEST_V1_2026-10-30.json",
                 application=application, domain="DISPOSABLE", fixture=case)


@pytest.fixture(scope="module")
def deployed():
    from scripts.native_install_candidate import _copy_prepared_code
    from scripts.native_install_plan import prepare_install_inputs
    root = Path(SCOPE).absolute(); assert root.parent == Path.cwd() / "logs/diagnostics"
    assert root.name.startswith("qd-selector-v1-native-")
    case = root / ("case-" + uuid.uuid4().hex[:12]); parent = protected(case)
    protected(case / "releases")
    app = case / "releases" / s.APP
    old = json.loads(Path("logs/diagnostics/qd-unselected-release-" + s.APP + ".json").read_bytes())
    archive = Path("logs/diagnostics/qd-evidence-promotion-package-d08ba9cbba2c405c/archive/atlas-source.zip").absolute()
    prepared = prepare_install_inputs(archive=archive, archive_sha256=old["archive_sha256"], source_commit=s.APP,
                                     dependency_receipt=old, dependency_digest=old["artifact_digest"])
    assert prepared["total"] < 300 * 1024**2
    assert len(prepared["names"]) + len(prepared["directories"]) + 1 < 12000
    start = time.monotonic()
    copied = _copy_prepared_code(destination=app, archive_sha256=old["archive_sha256"], source_commit=s.APP, prepared=prepared,
                                 admission=lambda: time.monotonic() - start < 350)
    assert copied["retained_handles_after_close"] == 0
    receipt = {"schema": "QD_DISPOSABLE_INSTALLED_APPLICATION_V1", "domain": "DISPOSABLE", "root": str(app),
               "release": s.APP, "files": copied["files"], "directories": copied["directories"]}
    receipt_path = case / "application-receipt.json"; receipt_path.write_bytes(encoded(receipt))
    application = {"release": s.APP, "root": str(app), "receipt": str(receipt_path),
                   "receipt_sha256": s.sha(encoded(receipt)), "artifact_digest": s.sha(encoded(receipt["files"]))}
    package = make_package(case, application)
    result = s.install_disposable(manifest=package["manifest"], archive=package["archive"],
                                  manifest_sha256=package["manifest_sha256"], parent_identity=parent)
    assert result["handles_after_close"] == result["independent_readback"]["handles_after_close"] == 0
    state = {"case": case, "parent": parent, "package": package, "result": result, "application": application,
             "copy_seconds": copied["seconds"], "copy_files": len(copied["files"]),
             "copy_directories": len(copied["directories"]), "copy_bytes": copied["charged_bytes"],
             "setup_seconds": round(time.monotonic() - start, 3)}
    (root / "native-setup-result.json").write_bytes(encoded({k: v for k, v in state.items() if k not in ("case", "package")}))
    return state


def test_native_support_install_receipt_ack_and_independent_readback(deployed):
    d = deployed; m = d["package"]["manifest"]
    r = s.verify_deployment(m, expected_receipt_sha256=d["result"]["receipt_sha256"])
    assert r["domain"] == "DISPOSABLE" and r["selected"] is False
    assert len(r["inventory"]["files"]) == 10 and len(r["inventory"]["directories"]) == 3
    assert list(Path(m["selection"]).iterdir()) == []
    with s.SupportLease(r):
        pass


def test_real_installed_powershell_open_close_restart_http_and_rollback(deployed):
    d = deployed; m = d["package"]["manifest"]; r = d["result"]["receipt"]
    store = NativeSelectionStore.disposable(root=Path(m["selection"]), native_root=r["selection_id"])
    selector = ReleaseSelector(store=store, verifier=s.DisposableInstalledReleaseVerifier(), clock=Clock())
    reference = {"schema": "QD_INSTALLED_RELEASE_REFERENCE_V1", "domain": "DISPOSABLE", **d["application"]}
    grant = {"schema": "QD_CODE_SELECTION_AUTHORIZATION_V1", "domain": "DISPOSABLE", "action": "SELECT",
             "operation": uuid.uuid4().hex, "expected_head": None, "target": reference, "restores": None}
    selected = selector.change(grant, approved=True)
    assert selector.current()["selected"] == reference
    binding = {"schema": "QD_NONFINANCIAL_DESKTOP_BINDING_V2", "domain": "DISPOSABLE", "head": selected["head"],
               "native_root": r["selection_id"], "release": s.APP, "seconds": 90, "requests": 96,
               "support_sha256": m["support_manifest_sha256"], "deployment_sha256": d["package"]["manifest_sha256"],
               "support_receipt_sha256": d["result"]["receipt_sha256"], "fixture_base": str(d["case"])}
    binding_path = d["case"] / "binding.json"; binding_path.write_bytes(encoded(binding))
    module = Path(m["destination"]) / "scripts/windows/Atlas-Installed-Nonfinancial.psm1"
    script = d["case"] / "controller.ps1"
    script.write_text("$ErrorActionPreference='Stop'\nImport-Module '" + str(module) + "' -Force\n" +
        "$binding=Get-Content -LiteralPath '" + str(binding_path) + "' -Raw | ConvertFrom-Json\n" +
        "1..2 | ForEach-Object {\n$ready=Open-AtlasInstalledNonfinancialDashboard -Binding $binding -Approved -Disposable\n" +
        "$ready | ConvertTo-Json -Compress\n" +
        "if ([Console]::ReadLine() -cne ('STOP '+$ready.host_id)) { throw 'TEST_OWNER_STOP_MISMATCH' }\n" +
        "Close-AtlasInstalledNonfinancialDashboard | ConvertTo-Json -Compress\n}\n", encoding="utf-8")
    environment = dict(os.environ)
    environment["PSModuleAnalysisCachePath"] = str(d["case"] / "ps-module-analysis.cache")
    child = subprocess.Popen([r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", "-NoProfile", "-File", str(script)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW, env=environment)
    samples, ports, identities = [], [], []
    captured_terminal = None
    try:
        for cycle in range(2):
            ready = json.loads(read_ready(child, seconds=180)); assert ready["mode"] == "DISPOSABLE_NONFINANCIAL_ONLY"
            assert ready["providers"] is ready["financial_writers"] is ready["trading"] is False
            assert Path(ready["image"]) == Path(m["runtime"]["python"])
            port = int(ready["url"].split(":")[-1].rstrip("/")); ports.append(port); identities.append(ready["pid"])
            for page in ("/dashboard", "/dashboard/perps", "/quality_dips.html", "/dashboard/investment",
                         "/dashboard/archive", "/dashboard/command-center"):
                with closing(HTTPConnection("127.0.0.1", port, timeout=3)) as c:
                    c.request("GET", page); response = c.getresponse()
                    assert response.status == 200 and b"<html" in response.read().lower()
                    assert "connect-src 'self'" in response.getheader("Content-Security-Policy")
            with closing(HTTPConnection("127.0.0.1", port, timeout=3)) as c:
                c.request("GET", "/api/investments/quality-dips/selected-paper"); response = c.getresponse(); data = json.loads(response.read())
                assert response.status == 200 and data["cash"] is data["positions"] is None and data["startup_authorized"] is False
            with closing(HTTPConnection("127.0.0.1", port, timeout=3)) as c:
                c.request("POST", "/anything"); response = c.getresponse(); response.read(); assert response.status == 403
            start = time.monotonic(); child.stdin.write(("STOP " + ready["host_id"] + "\n").encode()); child.stdin.flush()
            stopped = json.loads(read_ready(child, seconds=10)); elapsed = time.monotonic() - start
            assert stopped["closed"] is True and stopped["financial_actions"] == 0 and stopped["seconds"] <= 8 and elapsed <= 8
            samples.append({"adapter_seconds": stopped["seconds"], "observed_seconds": elapsed})
            (d["case"] / "controller-progress.json").write_bytes(encoded({"completed_cycles": cycle + 1, "stop_samples": samples}))
            with socket.socket() as sock:
                assert sock.connect_ex(("127.0.0.1", port)) != 0
        child.stdin.close(); child.stdin = None
        stdout, stderr = child.communicate(timeout=10)
        captured_terminal = stdout, stderr
        assert child.returncode == 0 and not stdout and not stderr
    finally:
        def record_terminal(tail, errors):
            (d["case"] / "controller-terminal-stdout.log").write_bytes(tail)
            (d["case"] / "controller-terminal-stderr.log").write_bytes(errors)
        finish_controller(child, store, captured=captured_terminal, record=record_terminal)
    # Real native reopening and append-only rollback to verified UNSELECTED baseline.
    store = NativeSelectionStore.disposable(root=Path(m["selection"]), native_root=r["selection_id"])
    try:
        selector = ReleaseSelector(store=store, verifier=s.DisposableInstalledReleaseVerifier(), clock=Clock())
        assert selector.current()["head"] == selected["head"]
        rolled = selector.change({**grant, "action": "ROLLBACK", "operation": uuid.uuid4().hex,
                                  "expected_head": selected["head"], "target": None, "restores": "BASELINE"}, approved=True)
        assert selector.current() == {"head": rolled["head"], "selected": None}
    finally:
        store.close()
    (Path(SCOPE) / "lifecycle-result.json").write_bytes(encoded({"cycles": 2, "stop_samples": samples,
        "six_pages_per_cycle": True, "financial_unavailable": True, "http_post_refused": True,
        "ports_closed": ports, "runtime_pids_exited": identities, "controller_exited": True,
        "rollback": "UNSELECTED_BASELINE_ACKNOWLEDGED", "financial_actions": 0, "provider_connections": 0}))


def test_native_partial_install_refuses_repeat_and_preserves_evidence(deployed):
    case = Path(SCOPE) / ("partial-" + uuid.uuid4().hex[:12]); parent = protected(case)
    app = {**deployed["application"], "root": str(case / "releases" / s.APP), "receipt": str(case / "application-receipt.json")}
    package = make_package(case, app)
    with pytest.raises(OSError, match="INTERRUPTION"):
        s.install_disposable(manifest=package["manifest"], archive=package["archive"], manifest_sha256=package["manifest_sha256"],
                             parent_identity=parent, interrupt_after=1)
    control = Path(package["manifest"]["control"])
    assert (control / "intent.json").exists() and not (control / "receipt.json").exists() and not (control / "ack.json").exists()
    original = (control / "intent.json").read_bytes()
    with pytest.raises(ValueError, match="EXISTS_PRESERVE"):
        s.install_disposable(manifest=package["manifest"], archive=package["archive"], manifest_sha256=package["manifest_sha256"], parent_identity=parent)
    assert (control / "intent.json").read_bytes() == original


def test_native_wrong_parent_refuses_before_creation(deployed):
    case = Path(SCOPE) / ("wrongparent-" + uuid.uuid4().hex[:12]); parent = protected(case)
    app = {**deployed["application"], "root": str(case / "releases" / s.APP), "receipt": str(case / "application-receipt.json")}
    package = make_package(case, app)
    with pytest.raises(ValueError, match="PARENT_SUBSTITUTION"):
        s.install_disposable(manifest=package["manifest"], archive=package["archive"], manifest_sha256=package["manifest_sha256"],
                             parent_identity=[parent[0], parent[1], parent[2] ^ 1])
    assert not (case / "selection").exists() and not (case / "launchers").exists()


def test_native_support_lease_prevents_replacement_and_releases(deployed):
    r = deployed["result"]["receipt"]; target = Path(r["deployment"]["destination"]) / "scripts/support_deployment.py"
    owner = s.SupportLease(r)
    try:
        with pytest.raises(OSError):
            target.rename(target.with_suffix(".substituted"))
        with pytest.raises(OSError):
            target.open("wb")
    finally:
        owner.close()
    assert owner.files == []


def test_native_missing_ack_and_hardlink_are_refused_without_adoption(deployed):
    m = deployed["package"]["manifest"]; control = Path(m["control"]); ack = control / "ack.json"
    missing = control / "ack.missing-test"
    ack.rename(missing)
    try:
        with pytest.raises(ValueError, match="INCOMPLETE_ACK"):
            s.verify_deployment(m, expected_receipt_sha256=deployed["result"]["receipt_sha256"])
    finally:
        missing.rename(ack)
    target = Path(m["destination"]) / "scripts/support_deployment.py"; link = deployed["case"] / "owned-negative-hardlink.py"
    os.link(target, link)
    try:
        with pytest.raises(ValueError, match="LINK_OR_SIZE"):
            s.verify_deployment(m, expected_receipt_sha256=deployed["result"]["receipt_sha256"])
    finally:
        link.unlink()  # Exactly owned negative alias only; source bytes untouched.
    s.verify_deployment(m, expected_receipt_sha256=deployed["result"]["receipt_sha256"])


def test_native_corrupted_receipt_and_unknown_namespace_refuse(deployed):
    m = deployed["package"]["manifest"]; control = Path(m["control"]); receipt = control / "receipt.json"
    original = receipt.read_bytes()
    receipt.write_bytes(original + b" ")
    try:
        with pytest.raises(ValueError, match="RECEIPT_PIN"):
            s.verify_deployment(m, expected_receipt_sha256=deployed["result"]["receipt_sha256"])
    finally:
        receipt.write_bytes(original)
    probe = Path(m["destination"]) / "unapproved-fixture-file"; probe.write_bytes(b"negative fixture")
    try:
        with pytest.raises(ValueError, match="UNLISTED"):
            s.verify_deployment(m, expected_receipt_sha256=deployed["result"]["receipt_sha256"])
    finally:
        probe.unlink()


def test_native_missing_runtime_dependency_refuses_no_fallback(deployed):
    reference = {"schema": "QD_INSTALLED_RELEASE_REFERENCE_V1", "domain": "DISPOSABLE", **deployed["application"]}
    p = Path(reference["root"]) / "python/python.exe"; hidden = p.with_suffix(".missing-fixture")
    p.rename(hidden)
    try:
        with pytest.raises((ValueError, OSError)), s.DisposableInstalledReleaseVerifier().open(reference):
            pytest.fail("Missing installed runtime must not admit")
    finally:
        hidden.rename(p)
