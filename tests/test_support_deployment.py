"""Support source/fixture engineering; no operational installation authority."""
import copy
import io
import zipfile
from pathlib import Path

import pytest

from scripts import support_deployment as s
from scripts.build_support_deployment import build
from scripts.release_selection import encoded


@pytest.fixture
def package(tmp_path):
    base = Path("D:/AtlasRuntime")
    application = {"release": s.APP, "root": str(base / "releases" / s.APP),
                   "receipt": str(Path("D:/Work/Project Atlas/logs/diagnostics") / ("qd-unselected-release-" + s.APP + ".json")),
                   "receipt_sha256": "a" * 64, "artifact_digest": "b" * 64}
    return build(output=tmp_path / "package", historical_manifest="docs/QD_SELECTOR_LAUNCHER_SUPPORT_MANIFEST_V1_2026-10-30.json",
                 application=application)


def test_complete_exact_package_manifest_and_runtime_inventory(package):
    m, files = s.prepare(package["manifest"], package["archive"], package["manifest_sha256"])
    assert set(files) == s.SOURCES | {"support-manifest.json"}
    assert len(m["files"]) == 10 and m["directories"] == [".", "scripts", "scripts/windows"]
    assert m["runtime"]["providers"] is False and m["runtime"]["financial_writers"] is False
    assert s.validate_manifest(m) == m


@pytest.mark.parametrize("change", [
    lambda m: m.update(schema="V0"), lambda m: m.update(domain="FIXTURE"),
    lambda m: m.update(destination="D:\\AtlasRuntime\\releases\\" + s.APP),
    lambda m: m.update(destination=m["destination"] + "\\.."),
    lambda m: m.update(control=m["selection"]), lambda m: m.update(selection="D:\\AtlasPaper"),
    lambda m: m.update(new_parents=[]), lambda m: m.update(limits={**s.LIMITS, "seconds": 601}),
    lambda m: m.update(exclusions=[]), lambda m: m.update(receipt_schema="DISPOSABLE"),
    lambda m: m["application"].update(release="b" * 40), lambda m: m["application"].update(root="C:\\Atlas"),
    lambda m: m["application"].update(receipt="D:\\AtlasPaper\\account.json"),
    lambda m: m["runtime"].update(workspace_fallback=True), lambda m: m["runtime"].update(bits=32),
    lambda m: m["runtime"].update(providers=True), lambda m: m["runtime"].update(financial_writers=True),
    lambda m: m["files"].append(m["files"][0]), lambda m: m["files"][0].update(path="../outside"),
    lambda m: m["files"][0].update(bytes=True), lambda m: m["files"][0].update(sha256="invalid"),
    lambda m: m.update(directories=["."]), lambda m: m.update(archive_sha256="invalid"),
    lambda m: m.update(extra=True), lambda m: m.pop("destination"),
])
def test_manifest_changes_refuse_before_any_effect(package, change):
    m = copy.deepcopy(package["manifest"]); change(m)
    with pytest.raises((ValueError, KeyError)):
        s.validate_manifest(m)


@pytest.mark.parametrize("damage", ["pin", "archive", "missing", "extra", "duplicate", "content", "symlink"])
def test_source_archive_corruption_and_namespace_refuse(package, damage):
    m = copy.deepcopy(package["manifest"]); path = package["archive"]
    if damage == "pin":
        with pytest.raises(ValueError, match="DEPLOYMENT_PIN"):
            s.prepare(m, path, "f" * 64)
        return
    if damage == "archive":
        path.write_bytes(path.read_bytes() + b"changed")
    else:
        with zipfile.ZipFile(path) as z:
            rows = [(i, z.read(i)) for i in z.infolist()]
        target = io.BytesIO()
        with zipfile.ZipFile(target, "w") as z:
            for index, (item, data) in enumerate(rows):
                if index == 0 and damage == "missing":
                    continue
                if index == 0 and damage == "content":
                    data = b"x" * len(data)
                if index == 0 and damage == "symlink":
                    item.external_attr = 0o120777 << 16
                z.writestr(item, data)
            if damage == "extra":
                z.writestr("scripts/unapproved.py", b"forbidden")
            if damage == "duplicate":
                # Duplicate ZIP entries must refuse even when their bytes match.
                with pytest.warns(UserWarning, match="Duplicate name"):
                    z.writestr(rows[0][0], rows[0][1])
        path.write_bytes(target.getvalue()); m["archive_sha256"] = s.sha(path.read_bytes())
    with pytest.raises(ValueError):
        s.prepare(m, path, s.sha(encoded(m)))


@pytest.mark.parametrize("approval", [None, False, 1, "true"])
def test_default_and_untyped_operation_refuse_without_input_access(approval, monkeypatch):
    monkeypatch.setattr(s, "prepare", lambda *a: pytest.fail("No input access"))
    with pytest.raises(ValueError, match="AUTHORIZATION"):
        s.install_operational(approved=approval)


def test_synthetic_clock_cannot_install_operational_support():
    with pytest.raises(ValueError, match="GENUINE_SUPPORT_CLOCK"):
        s.install_operational(approved=True, clock=object())


@pytest.mark.parametrize("approval", [False, None, 1, "true"])
def test_selection_facade_default_refuses_without_read(approval, monkeypatch):
    monkeypatch.setattr(s, "validate_manifest", lambda m: pytest.fail("No read"))
    with pytest.raises(ValueError, match="AUTHORIZATION"):
        s.select_release(approved=approval)


def test_selection_facade_refuses_synthetic_clock():
    with pytest.raises(ValueError, match="GENUINE_SELECTION_CLOCK"):
        s.select_release(approved=True, clock=object())


def test_operational_manifest_cannot_enter_disposable_installer(package):
    with pytest.raises(ValueError, match="DISPOSABLE_SUPPORT_DOMAIN"):
        s.install_disposable(manifest=package["manifest"], archive=package["archive"],
                             manifest_sha256=package["manifest_sha256"], parent_identity=[1, 2, 3])


@pytest.mark.parametrize("path", ["D:/AtlasRuntime", "D:/AtlasPaper/anything", "C:/temp/case",
                                 "D:/Work/Project Atlas/logs/diagnostics/not-approved/case"])
def test_fixture_domain_cannot_escape(path):
    with pytest.raises(ValueError, match="FIXTURE"):
        s.fixture_base(path)


def test_duplicate_and_nonfinite_json_are_not_accepted():
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}'):
        with pytest.raises(ValueError):
            s.strict(raw)


def test_both_child_programs_compile_and_keep_effect_guard():
    from scripts.installed_nonfinancial_launcher import CHILD, DISPOSABLE_CHILD
    for code in (CHILD, DISPOSABLE_CHILD):
        compile(code, "<native-readonly-child>", "exec")
        assert "NONFINANCIAL_EXTERNAL_EFFECT_REFUSED" in code
        assert "server.server_close()" in code
    assert "spec['domain']!='DISPOSABLE'" in DISPOSABLE_CHILD
