"""Confined offline-media tests. All custody here is explicitly synthetic."""
import copy
import hashlib
from decimal import Decimal
from types import SimpleNamespace

import pytest
from test_financial_recovery_native import FixtureRecoveryAuthority, m, restore
from test_quality_dips_read_capability_native import capture

pytest_plugins = ["test_quality_dips_read_capability_native"]


def cut_for(manifest):
    return {"schema": "FS_BACKUP_CUT_V1", "backup_manifest_digest": m.digest(manifest),
            "enrollment_digest": m.digest(manifest["enrollment"]), "source_pin_digest": m.digest(manifest["current"]),
            "high_water": manifest["current"]["high_water"], "generation": manifest["current"]["generation"],
            "status": "ACKNOWLEDGED"}


def prepare_offline(n):
    _, _, original_authority = restore(n)
    descriptor = original_authority.accepted[0]
    backup = n.tmp_path / "offline-media"
    with (m.f.w.WindowsOutput(str(n.tmp_path / "restored")) as original,
          m.f.w.WindowsOutput.create_root(str(backup)) as output):
        entries = []
        for item in descriptor["mapping"]:
            raw, _ = m.f.s.read_bound(original, item["target"], item["restored"])
            binding = output.write_bound(item["target"], raw)
            entries.append({"role": item["role"], "leaf": item["leaf"], "original": item["original"],
                            "backup_leaf": item["target"], "backup_binding": binding})
        manifest = {"schema": "FS_OFFLINE_BACKUP_V1", "backup_id": "fixture-media-1",
                    "root": m.f.native.file_identity(output.root_handle), "enrollment": n.enrollment,
                    "current": n.current, "files": entries}
    cut = cut_for(manifest)
    authority = FixtureRecoveryAuthority(n)
    authority.expected = {"schema": "FS_OFFLINE_RECOVERY_REQUEST_V1", "recovery_id": "offline-recovery",
                          "enrollment": n.enrollment, "current": n.current, "source_cut": copy.deepcopy(cut),
                          "backup_id": manifest["backup_id"], "backup_root": manifest["root"]}
    authority.expected = copy.deepcopy(authority.expected)
    n.backup, n.backup_manifest, n.cut, n.recovery_authority = backup, manifest, cut, authority
    n.destination = n.tmp_path / "offline-restored"
    return n


@pytest.fixture
def offline(native):
    return prepare_offline(native)


def ingest(n, **overrides):
    args = {"backup_root": n.backup, "backup_manifest": n.backup_manifest, "source_cut": n.cut,
            "destination": n.destination, "recovery_id": "offline-recovery"}
    args.update(overrides)
    return m.DisposableRecovery(n.recovery_authority).restore_offline(**args)


def test_offline_restore_without_any_original_paths(offline, monkeypatch):
    n = offline
    for root in (n.source, n.projection, n.reports):
        root.rename(n.tmp_path / ("retained-original-" + root.name))
        assert not root.exists()
    def forbidden(*args, **kwargs):
        raise AssertionError("offline recovery attempted operational source access")
    monkeypatch.setattr(m.r.NativeFinancialReadPort, "read_verified", forbidden)
    before = capture(n.backup)
    receipt = ingest(n)
    protocol = m.DisposableRecovery(n.recovery_authority)
    view = protocol.read(n.destination, receipt)
    assert view["evidence"]["state"]["cash"] == "900.0"
    assert len(view["evidence"]["state"]["positions"]) == 1
    assert view["startup_authorized"] is False and view["financial_writes_authorized"] is False
    assert n.recovery_authority.accepted[0]["schema"] == "FS_RECOVERY_ARCHIVE_V2"
    assert capture(n.backup) == before
    with pytest.raises(ValueError, match="AUTHORITY_REJECTED"):
        ingest(n)


@pytest.mark.parametrize("kind", ["missing_manifest", "untrusted", "cut_mismatch", "stale", "rollback", "unknown",
                                  "missing_file", "tampered", "duplicate", "extra_file", "substituted_root",
                                  "file_identity", "unsupported_schema"])
def test_bad_backup_never_publishes_destination(offline, kind):
    n = offline
    args = {}
    if kind == "missing_manifest":
        args["backup_manifest"] = None
    elif kind == "untrusted":
        n.recovery_authority.valid = False
    elif kind == "cut_mismatch":
        n.cut["high_water"] += 1
    elif kind in ("stale", "rollback", "unknown"):
        if kind == "stale":
            n.backup_manifest["current"]["generation"] -= 1
        elif kind == "rollback":
            n.backup_manifest["current"]["source"]["entries"] = []
            n.backup_manifest["current"]["high_water"] = 0
            n.backup_manifest["current"]["acknowledged_revision"] = 0
        else:
            n.backup_manifest["current"]["status"] = "UNKNOWN"
        n.cut = cut_for(n.backup_manifest)  # Coherent local hashes still supply no authority.
    elif kind == "missing_file":
        (n.backup / n.backup_manifest["files"][0]["backup_leaf"]).rename(n.tmp_path / "retained-missing.json")
    elif kind == "tampered":
        (n.backup / n.backup_manifest["files"][0]["backup_leaf"]).write_bytes(b"{}")
    elif kind == "duplicate":
        n.backup_manifest["files"].append(copy.deepcopy(n.backup_manifest["files"][0]))
        n.cut = cut_for(n.backup_manifest)
    elif kind == "extra_file":
        (n.backup / "uncommitted.json").write_bytes(b"{}")
    elif kind == "substituted_root":
        args["backup_root"] = n.tmp_path / "restored"
    elif kind == "file_identity":
        file = n.backup / n.backup_manifest["files"][0]["backup_leaf"]
        raw = file.read_bytes()
        file.rename(n.tmp_path / "retained-original-copy.json")
        file.write_bytes(raw)
    else:
        n.backup_manifest["schema"] = "FS_OFFLINE_BACKUP_V999"
    with pytest.raises((ValueError, TypeError, KeyError, OSError)):
        ingest(n, **args)
    assert not n.destination.exists()


@pytest.mark.parametrize("boundary", ["intent.json", "copy-0000.json", "commit.json", "authority"])
def test_interrupted_offline_publication_retained_unknown(offline, monkeypatch, boundary):
    n = offline
    original = m.f.w.WindowsOutput.write_bound
    def fail(output, leaf, raw):
        binding = original(output, leaf, raw)
        if leaf == boundary:
            raise OSError("injected offline recovery interruption")
        return binding
    monkeypatch.setattr(m.f.w.WindowsOutput, "write_bound", fail)
    n.recovery_authority.fail = boundary == "authority"
    with pytest.raises(OSError):
        ingest(n)
    before = capture(n.destination)
    assert before and n.recovery_authority.accepted is None
    monkeypatch.setattr(m.f.w.WindowsOutput, "write_bound", original)
    n.recovery_authority.fail = False
    with pytest.raises((ValueError, OSError)):
        ingest(n)
    assert capture(n.destination) == before


def test_recovered_offline_read_never_reopens_backup(offline):
    n = offline
    receipt = ingest(n)
    n.backup.rename(n.tmp_path / "retained-offline-media")
    before = capture(n.destination)
    protocol = m.DisposableRecovery(n.recovery_authority)
    assert protocol.read(n.destination, receipt)["status"] == "VERIFIED_ARCHIVE_ONLY"
    assert capture(n.destination) == before
    assert not hasattr(protocol, "execute")


def authorize_fixture_mutation(n):
    """Let structural tests reach validation; never represent independent trust."""
    n.cut = cut_for(n.backup_manifest)
    n.recovery_authority.expected.update(enrollment=copy.deepcopy(n.backup_manifest["enrollment"]),
                                        current=copy.deepcopy(n.backup_manifest["current"]), source_cut=copy.deepcopy(n.cut))


@pytest.mark.parametrize("kind", ["duplicate_file", "duplicate_backup_leaf", "bool_revision", "pin_schema", "missing_mapping"])
def test_authenticated_but_structurally_invalid_manifest_refuses(offline, kind):
    n = offline
    if kind == "duplicate_file":
        n.backup_manifest["files"].append(copy.deepcopy(n.backup_manifest["files"][0]))
    elif kind == "duplicate_backup_leaf":
        n.backup_manifest["files"][1]["backup_leaf"] = n.backup_manifest["files"][0]["backup_leaf"]
    elif kind == "bool_revision":
        n.backup_manifest["current"]["acknowledged_revision"] = True
    elif kind == "pin_schema":
        n.backup_manifest["current"]["source"]["schema"] = "FS2_TEST_PIN_V999"
    else:
        n.backup_manifest["files"].pop()
    authorize_fixture_mutation(n)
    with pytest.raises((ValueError, KeyError)):
        ingest(n)
    assert not n.destination.exists()


@pytest.mark.parametrize("role,leaf", [("source", "0001-record.json"), ("projection", "-ack.json"),
                                      ("reports", "0001-report.json")])
def test_original_logical_lineage_revalidated_from_backup_bytes(offline, role, leaf):
    n = offline
    item = next(item for item in n.backup_manifest["files"] if item["role"] == role and item["leaf"].endswith(leaf))
    path = n.backup / item["backup_leaf"]
    value = m.strict(path.read_text())
    if role == "source":
        value["previous"]["revision"] = 99
    elif role == "projection":
        value["context"]["source_revision"] = 99
    else:
        value["previous"] = {"id": [1, 2, 3], "sha256": "0" * 64}
    path.rename(n.tmp_path / "retained-original-backup-record.json")
    raw = m.f.encoded(value)
    with m.f.w.WindowsOutput(str(n.backup)) as output:
        item["backup_binding"] = output.write_bound(item["backup_leaf"], raw)
    item["original"]["sha256"] = hashlib.sha256(raw).hexdigest()
    if role == "source":
        n.backup_manifest["current"]["source"]["entries"][0]["record"] = copy.deepcopy(item["original"])
    elif role == "reports":
        n.backup_manifest["current"]["reports"]["reports"][0] = copy.deepcopy(item["original"])
    # Fixture acceptance of transport metadata is insufficient to bypass lineage.
    authorize_fixture_mutation(n)
    with pytest.raises(ValueError):
        ingest(n)
    assert not n.destination.exists()


def test_custody_loss_after_read_refuses_before_publication(offline):
    n = offline
    checks = iter([True, False])
    n.recovery_authority.check = lambda: next(checks)
    with pytest.raises(ValueError, match="CUSTODY_CHANGED"):
        ingest(n)
    assert not n.destination.exists()


def test_offline_backup_hardlink_refused(offline):
    import os
    n = offline
    os.link(n.backup / n.backup_manifest["files"][0]["backup_leaf"], n.tmp_path / "offline-extra-link.json")
    with pytest.raises((ValueError, OSError)):
        ingest(n)
    assert not n.destination.exists()


@pytest.mark.parametrize("phase,cash", [("partial", "943.968"), ("final", "1009.920")])
def test_offline_partial_and_full_exit_history(native, phase, cash):
    from qd_http_fixture import build_fixture
    root = native.tmp_path / "synthetic-phases"
    root.mkdir()
    build_fixture(root)
    data = m.strict((root / "fixture.json").read_text())["phases"][phase]
    n = prepare_offline(SimpleNamespace(tmp_path=native.tmp_path, enrollment=data["enrollment"], current=data["current"],
                                       source=root / phase / "source", projection=root / phase / "projection",
                                       reports=root / phase / "reports"))
    for original in (n.source, n.projection, n.reports):
        original.rename(n.tmp_path / ("retained-" + original.name))
    receipt = ingest(n)
    state = m.DisposableRecovery(n.recovery_authority).read(n.destination, receipt)["evidence"]["state"]
    assert Decimal(state["cash"]) == Decimal(cash)


def test_short_native_write_retained_without_acknowledgement(offline, monkeypatch):
    n = offline
    write_bound = m.f.w.WindowsOutput.write_bound
    write_file = m.f.w.write_file
    def partial(handle, data, length, count, overlapped):
        return write_file(handle, data, length // 2, count, overlapped)
    def interrupt(output, leaf, raw):
        if leaf == "copy-0000.json":
            with monkeypatch.context() as patch:
                patch.setattr(m.f.w, "write_file", partial)
                return write_bound(output, leaf, raw)
        return write_bound(output, leaf, raw)
    monkeypatch.setattr(m.f.w.WindowsOutput, "write_bound", interrupt)
    with pytest.raises(OSError, match="Partial output retained"):
        ingest(n)
    assert (n.destination / "copy-0000.json").is_file()
    assert not (n.destination / "commit.json").exists()
    assert n.recovery_authority.accepted is None
