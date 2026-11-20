"""Only run through the explicit confined native runner. No application imports."""
import copy
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reviewed_snapshot_cases", REPO / "tests/test_r7e47f_snapshot_store.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
m = old.m


def note(case, **values):
    with (Path(os.environ["ATLAS_D1_ATTEMPT"]) / "observations.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"case": case, **values}) + "\n")


@pytest.fixture(autouse=True)
def confinement(tmp_path):
    root = Path(os.environ["ATLAS_D1_RUN_ROOT"])
    assert root.parent == REPO / "logs/diagnostics" and root.name.startswith("qd-d1-native-acceptance-")
    assert tmp_path.is_relative_to(root)
    for p in [tmp_path, *tmp_path.parents]:
        assert not p.is_symlink() and not p.is_junction()


@pytest.fixture
def store(tmp_path):
    value = m.SnapshotStore.provision_synthetic(str(tmp_path / "state"), str(tmp_path / "witness"))
    note("provision", root=value.pin["root_id"], witness=value.pin["witness_root_id"], snapshot=value.pin["snapshot"])
    try:
        yield value
    finally:
        value.close()


def test_valid_identity_restart(store):
    old.test_snapshot_roundtrip_and_revision_bound_restart(store)


@pytest.mark.parametrize("attack", ["same-bytes-replacement", "corrupt", "incomplete", "hardlink"])
def test_identity_before_decode(store, monkeypatch, attack):
    old.test_unsafe_snapshot_rejected_before_decode_or_admission(store, monkeypatch, attack)


@pytest.mark.parametrize("surface", ["snapshot", "commit"])
def test_no_read_of_replaced_identity(store, monkeypatch, surface):
    old.test_identity_mismatch_never_reads_substitute_handle(store, monkeypatch, surface)


def test_share_lease_denies_concurrent_write_delete(store, monkeypatch):
    old.test_native_read_handle_denies_concurrent_write_and_rename(store, monkeypatch)
    note("sharing", write_error=32, rename_error=32, enforcement="OS; asserted native observations")


@pytest.mark.parametrize("leaf", ["../escape", "x/y", "x\\y", ".."])
def test_relative_traversal_refused(store, leaf):
    with pytest.raises(ValueError): m.read_bound(store.output, leaf)


def test_wrong_root_pin_refused(store):
    old.test_malformed_or_substituted_authority_pin_refused(store, "bad-root")


def test_directory_rename_denied_while_retained(store):
    path = Path(store.output.root)
    with pytest.raises(OSError) as error: path.rename(path.with_name("retained-renamed"))
    note("directory_rename", winerror=error.value.winerror)
    assert error.value.winerror in (5, 32)


def test_native_symlink_if_available(store):
    old.test_true_symlink_refused_when_native_creation_available(store, Path(store.output.root).parent)


def test_restricted_token_denial(store):
    old.test_native_restricted_token_denies_snapshot_and_witness(store)
    note("restricted_token", snapshot_read=5, snapshot_write=5, witness_read=5, witness_write=5)


@pytest.mark.parametrize("phase", ["snapshot", "commit"])
def test_interruption_after_intent(store, monkeypatch, phase):
    old.test_interrupted_publication_blocks_old_state(store, monkeypatch, phase)


def test_before_intent_failure_latches(store, monkeypatch):
    def fail(*args):
        raise OSError("Disposable pre-intent interruption")
    monkeypatch.setattr(store.witness, "_write", fail)
    with pytest.raises(OSError): store.reserve_start("test-start", old.ident())
    with pytest.raises(m.Refused): store.snapshot()


def test_commit_without_caller_ack_stale_restart_refuses(store):
    pin = copy.deepcopy(store.pin)
    store.reserve_start("test-start", old.ident())
    with pytest.raises(m.Refused): m.SnapshotStore(store.output.root, store.witness.root, pin)


def test_unknown_inspection_never_automatically_recovers(store):
    store.inspect("test-inspect", "c" * 64, approved=True)
    with pytest.raises(m.Refused): store.reserve_start("test-start", old.ident())
    with pytest.raises(m.Refused): store.recover(object(), {}, {}, 1000)
    assert store.snapshot()["inspection"]["phase"] == "UNCERTAIN"


@pytest.mark.parametrize("role", ["projection", "report", "admission-close"])
def test_metadata_interruption_never_publishes_success(store, monkeypatch, role):
    output = store.output
    original = output._write
    def fail(directory, name, raw):
        if name == "audit.json": raise OSError("Synthetic publication interruption")
        return original(directory, name, raw)
    monkeypatch.setattr(output, "_write", fail)
    metadata = {"schema": 1, "service": "postgres", "status": "METADATA_COMPLETE_COVERAGE_UNPROVEN",
                "files": 0, "directories": 0, "logical_file_bytes": 0,
                "effective_configuration": "NOT_ESTABLISHED", "payloads_read": False}
    with pytest.raises(OSError): output.publish(role + ".json", metadata)
    with pytest.raises(OSError): output.read(role + ".json")
    assert (Path(output.root) / (role + ".json.pending")).is_dir()


@pytest.mark.parametrize("mode", ["DELETE", "WAL"])
def test_sqlite_sidecar_creation_and_acl_surface(store, mode):
    path = Path(store.output.root) / "probe.sqlite"
    db = sqlite3.connect(path)
    try:
        assert db.execute("PRAGMA journal_mode=" + mode).fetchone()[0].upper() == mode
        db.execute("CREATE TABLE probe(value)")
        db.commit()
        db.execute("INSERT INTO probe VALUES('synthetic')")
        surfaces = [path, Path(str(path) + "-journal")] if mode == "DELETE" else [path, Path(str(path) + "-wal"), Path(str(path) + "-shm")]
        for p in surfaces:
            assert p.exists()
            # Metadata observation shares with SQLite's existing write handle.
            # This is NOT a trusted payload read or the identity-before-read lease.
            handle = m.w.create_file(str(p), m.w.ATTR | m.w.READ_CONTROL, 7, None, 3, 0x00200000, None)
            assert handle != m.w.INVALID
            try:
                fid = m.native.file_identity(handle)
                try:
                    m.w.validate_acl(handle, store.output.sid)
                    protected = True
                except PermissionError:
                    protected = False
            finally:
                m.w.close_handle(handle)
            note("sqlite_surface", mode=mode, surface=p.suffix, identity=fid, exact_protected_acl=protected)
        # Transaction holds the SQLite writer lock, not namespace authority.
        other = sqlite3.connect(path, timeout=0)
        try:
            with pytest.raises(sqlite3.OperationalError): other.execute("INSERT INTO probe VALUES('alternate')")
        finally:
            other.close()
    finally:
        db.rollback()
        db.close()


def test_sqlite_verified_main_can_be_substituted_before_path_open(store):
    root = Path(store.output.root)
    for name, value in [("main.sqlite", "original"), ("other.sqlite", "substitute")]:
        with closing(sqlite3.connect(root / name)) as db, db:
            db.execute("CREATE TABLE probe(value)")
            db.execute("INSERT INTO probe VALUES(?)", (value,))
    h = m.w.relative_open(store.output.root_handle, "main.sqlite", store.output.sid, False)
    before = m.native.file_identity(h)
    m.w.close_handle(h)
    (root / "main.sqlite").rename(root / "retained.sqlite")
    (root / "other.sqlite").rename(root / "main.sqlite")
    with sqlite3.connect(root / "main.sqlite") as db:
        assert db.execute("SELECT value FROM probe").fetchone()[0] == "substitute"
    note("sqlite_main_substitution", original_identity=before, security_outcome="PATH_BASED_ACCESS_NOT_PROTECTED", attack_reproduced=True)


def test_failed_intent_persisted_latch_survives_restart(store, monkeypatch):
    original = store.witness._write
    def fail(directory, leaf, raw):
        if leaf.startswith("intent-"): raise OSError("Injected intent failure")
        return original(directory, leaf, raw)
    monkeypatch.setattr(store.witness, "_write", fail)
    pin = copy.deepcopy(store.pin)
    with pytest.raises(OSError, match="Injected"): store.reserve_start("test-start", old.ident())
    with pytest.raises(m.Refused): store.snapshot()
    with pytest.raises(m.Refused): m.SnapshotStore(store.output.root, store.witness.root, pin)


def test_inherited_file_acl_rejected(store):
    path = Path(store.output.root) / "inherited.json"
    path.write_bytes(b"synthetic")
    with pytest.raises(PermissionError): m.read_bound(store.output, path.name)


def test_acl_change_between_verification_and_read_refused(store):
    path = Path(store.output.root) / "snapshot-00000000.json"
    api = m.w.bind(m.w.A, "SetFileSecurityW", [m.native.W.LPCWSTR, m.native.W.DWORD, m.C.c_void_p])
    sd = m.C.c_void_p()
    # Still only owner/SYSTEM; remove PROTECTED control, not grant broad access.
    m.w.check(m.w.sddl_sd(f"D:(A;;FA;;;{store.output.sid})(A;;FA;;;SY)", 1, m.C.byref(sd), None))
    try:
        m.w.check(api(str(path), 4 | 0x20000000, sd))
    finally:
        m.w.local_free(sd)
    with pytest.raises((PermissionError, m.Refused)): store.snapshot()


def test_restricted_token_denies_delete_and_new_sidecars(store):
    c, W, w = m.C, m.native.W, m.w
    normal, restricted, everyone = W.HANDLE(), W.HANDLE(), c.c_void_p()
    convert = w.bind(w.A, "ConvertStringSidToSidW", [W.LPCWSTR, c.POINTER(c.c_void_p)])
    restrict = w.bind(w.A, "CreateRestrictedToken", [W.HANDLE, W.DWORD, W.DWORD, c.c_void_p, W.DWORD, c.c_void_p, W.DWORD, c.POINTER(w.SidAttr), c.POINTER(W.HANDLE)])
    impersonate = w.bind(w.A, "ImpersonateLoggedOnUser", [W.HANDLE])
    revert = w.bind(w.A, "RevertToSelf", [])
    observed = []
    try:
        w.check(w.open_token(w.process(), 0xE, c.byref(normal)))
        w.check(convert("S-1-1-0", c.byref(everyone)))
        entry = w.SidAttr(everyone, 0)
        w.check(restrict(normal, 1, 0, None, 0, None, 1, c.byref(entry), c.byref(restricted)))
        w.check(impersonate(restricted))
        try:
            targets = [("snapshot-00000000.json", w.DELETE, 3)] + [("new" + s, w.WRITE, 1) for s in ("-wal", "-shm", "-journal")]
            for name, access, disposition in targets:
                handle = w.create_file(str(Path(store.output.root) / name), access, 7, None, disposition, 0, None)
                error = c.get_last_error()
                if handle != w.INVALID: w.close_handle(handle)
                observed.append(error)
                assert handle == w.INVALID and error == 5
        finally:
            w.check(revert())
    finally:
        if normal: w.close_handle(normal)
        if restricted: w.close_handle(restricted)
        if everyone: w.local_free(everyone)
    note("restricted_delete_sidecar_create", observed_errors=observed)


def owned_helper(args, cwd):
    """Fixed test commands only; retain exact native process handle, never kill."""
    child = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    created, exited, kernel, user = (m.native.W.FILETIME() for _ in range(4))
    times = m.w.bind(m.w.K, "GetProcessTimes", [m.native.W.HANDLE] + [m.C.POINTER(m.native.W.FILETIME)] * 4)
    m.w.check(times(int(child._handle), m.C.byref(created), m.C.byref(exited), m.C.byref(kernel), m.C.byref(user)))
    try:
        stdout, stderr = child.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        note("helper", pid=child.pid, created=(created.dwHighDateTime << 32) | created.dwLowDateTime,
             status="UNKNOWN_TIMEOUT_NOT_KILLED", command=args)
        raise
    note("helper", pid=child.pid, created=(created.dwHighDateTime << 32) | created.dwLowDateTime,
         status="EXITED", returncode=child.returncode, command=args)
    return child.returncode, stdout, stderr


def test_junction_substitution_refused(store, tmp_path):
    path = Path(store.output.root) / "snapshot-00000000.json"
    path.rename(path.with_name("retained-original"))
    target = tmp_path / "synthetic-target"
    target.mkdir()
    code, _, stderr = owned_helper(["cmd.exe", "/d", "/c", "mklink", "/J", str(path), str(target)], tmp_path)
    assert code == 0, stderr
    with pytest.raises((OSError, m.Refused)): store.snapshot()


@pytest.mark.parametrize("phase", ["after_intent", "after_commit"])
def test_owned_abrupt_process_exit_preserves_refusal(store, tmp_path, phase):
    script = """import importlib.util,json,sys,os
from pathlib import Path
root=Path(sys.argv[1]);state=Path(sys.argv[3]);witness=Path(sys.argv[4])
assert state.is_relative_to(root) and witness.is_relative_to(root)
s=importlib.util.spec_from_file_location('native_child',sys.argv[2]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
value=m.SnapshotStore(str(state),str(witness),json.loads(sys.argv[5]))
if sys.argv[6]=='after_intent':
 def crash(*args):os._exit(24)
 value.output._write=crash
value.reserve_start('test-child',{'pid':1000,'created':1000,'exe':'a'*64,'command':'b'*64})
os._exit(24)
"""
    code, _, stderr = owned_helper([sys.executable, "-I", "-B", "-c", script, os.environ["ATLAS_D1_RUN_ROOT"],
        str(REPO / "scripts/volume_inspector/snapshot_store.py"), store.output.root, store.witness.root,
        json.dumps(store.pin), phase], tmp_path)
    assert code == 24, stderr
    with pytest.raises(m.Refused): store.snapshot()
    assert (Path(store.witness.root) / "recovery-required.json").exists()


@pytest.mark.parametrize("suffix", ["-journal", "-wal", "-shm"])
def test_active_sqlite_sidecar_rename_is_os_denied(store, suffix):
    path = Path(store.output.root) / "active.sqlite"
    db = sqlite3.connect(path)
    try:
        mode = "DELETE" if suffix == "-journal" else "WAL"
        db.execute("PRAGMA journal_mode=" + mode)
        db.execute("CREATE TABLE probe(value)")
        db.commit()
        db.execute("INSERT INTO probe VALUES('synthetic')")
        sidecar = Path(str(path) + suffix)
        assert sidecar.exists()
        with pytest.raises(OSError) as error:
            sidecar.rename(Path(store.output.root) / ("retained-active" + suffix))
        assert error.value.winerror in (5, 32)
        note("active_sqlite_sidecar_rename", suffix=suffix, winerror=error.value.winerror, enforcement="SQLITE_OPEN_HANDLE_OS_LOCK_ONLY")
    finally:
        db.rollback()
        db.close()


@pytest.mark.parametrize("suffix", ["-journal", "-wal", "-shm"])
def test_pinned_sidecar_hardlink_refused_before_read(store, monkeypatch, suffix):
    leaf = "generated-sidecar" + suffix
    store.output._write(store.output.root_handle, leaf, b"explicit-generated-sidecar-probe")
    _, pin = m.read_bound(store.output, leaf)
    path = Path(store.output.root) / leaf
    os.link(path, path.with_name("retained-link" + suffix))
    reads = []
    original = m.w.read_file
    def observed(*args):
        reads.append(True)
        return original(*args)
    monkeypatch.setattr(m.w, "read_file", observed)
    with pytest.raises(m.Refused): m.read_bound(store.output, leaf, pin)
    assert not reads
    note("pinned_sidecar_hardlink", suffix=suffix, enforcement="NATIVE_LINK_COUNT_BEFORE_READ", sqlite_vfs_claim=False)


def test_sqlite_parent_junction_substitution_reproduces_path_gap(tmp_path):
    before, alternate = tmp_path / "observed", tmp_path / "alternate"
    for directory, value in [(before, "original"), (alternate, "substitute")]:
        directory.mkdir()
        with closing(sqlite3.connect(directory / "probe.sqlite")) as db, db:
            db.execute("CREATE TABLE probe(value)")
            db.execute("INSERT INTO probe VALUES(?)", (value,))
    handle = m.w.create_file(str(before / "probe.sqlite"), m.w.ATTR, 7, None, 3, 0x00200000, None)
    assert handle != m.w.INVALID
    observed_id = m.native.file_identity(handle)
    m.w.close_handle(handle)
    before.rename(tmp_path / "retained-observed")
    code, _, stderr = owned_helper(["cmd.exe", "/d", "/c", "mklink", "/J", str(before), str(alternate)], tmp_path)
    assert code == 0, stderr
    with closing(sqlite3.connect(before / "probe.sqlite")) as db:
        assert db.execute("SELECT value FROM probe").fetchone()[0] == "substitute"
    note("sqlite_parent_substitution", observed_file_id=observed_id, attack_reproduced=True,
         security_outcome="PATH_BASED_SQLITE_PARENT_NOT_PINNED", target_confined_to_run=True)


@pytest.mark.parametrize("phase", ["before_close_commit", "after_close_commit"])
def test_disposable_admission_closure_interruption(store, phase):
    loader = importlib.util.spec_from_file_location("disposable_writer_only", REPO / "backend/app/services/paper_writer_fixture.py")
    writer = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(writer)  # Pure fixture SQLite contract; no native financial service imports.
    path = Path(store.output.root) / "admission.sqlite"
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("CREATE TABLE control(stopped INTEGER)")
        db.execute("INSERT INTO control VALUES(0)")
    roster = {"disposable-writer": "one"}
    writer.provision_fixture_writers(path, roster)
    writer.fixture_writer_operation(path, writer="disposable-writer", incarnation="one", operation="pending", payload="a" * 64)
    def interruption(at):
        if at == phase: raise OSError("Disposable closure interruption")
    with pytest.raises(OSError): writer.close_fixture_writers(path, roster, fault=interruption)
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT stopped FROM control").fetchone()[0] == (phase == "after_close_commit")
    result = writer.close_fixture_writers(path, roster)
    assert result["status"] == "INCOMPLETE" and result["pending"] == ["pending"]
    assert result["production_authorized"] is False
    note("admission_closure_interruption", phase=phase, restart_result="INCOMPLETE", financial_payload=False)


@pytest.mark.parametrize("suffix", ["-journal", "-wal", "-shm"])
def test_main_identity_does_not_pin_sidecar_identity(store, suffix):
    root = Path(store.output.root)
    store.output._write(store.output.root_handle, "main.sqlite", b"synthetic-main-not-opened-by-sqlite")
    store.output._write(store.output.root_handle, "main.sqlite" + suffix, b"synthetic-sidecar-not-opened-by-sqlite")
    h = m.w.relative_open(store.output.root_handle, "main.sqlite" + suffix, store.output.sid, False)
    before = m.native.file_identity(h)
    m.w.close_handle(h)
    (root / ("main.sqlite" + suffix)).rename(root / ("retained" + suffix))
    store.output._write(store.output.root_handle, "main.sqlite" + suffix, b"substitute-sidecar-not-opened-by-sqlite")
    h = m.w.relative_open(store.output.root_handle, "main.sqlite" + suffix, store.output.sid, False)
    after = m.native.file_identity(h)
    m.w.close_handle(h)
    assert before != after
    note("sidecar_replacement", suffix=suffix, before=before, after=after, security_outcome="MAIN_ID_ALONE_INSUFFICIENT", synthetic_namespace_probe=True)
