"""FS2 confined disposable native tests; no operational authority or stores."""
import copy
import ctypes as C
import importlib.util
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
spec = importlib.util.spec_from_file_location("fs2", REPO / "scripts/volume_inspector/financial_record_store.py")
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
GOLDEN = json.loads((REPO / "tests/fixtures/fs1/legacy-synthetic-golden.json").read_text())["cases"]


class TestPins:
    __test__ = False
    def __init__(self, pin):
        self.pin, self.available, self.now = copy.deepcopy(pin), True, 0
    def current(self):
        if not self.available:
            raise f.Refused("Test pin unavailable")
        return copy.deepcopy(self.pin)
    def check_clock(self, timestamp):
        if type(timestamp) is not int or not self.now <= timestamp <= self.now + 30:
            raise f.Refused("Test clock window unavailable or stale")
    def advance(self, old, new):
        if f.body(self.current()) != f.body(old):
            raise f.Refused("Test pin compare-and-swap conflict")
        self.pin = copy.deepcopy(new)


@pytest.fixture(autouse=True)
def confined(tmp_path):
    root = Path(os.environ["ATLAS_D1_RUN_ROOT"])
    assert root.parent == REPO / "logs/diagnostics" and root.name.startswith(("qd-d1-financial-records-", "qd-fs3-report-projection-"))
    assert tmp_path.is_relative_to(root)
    assert all(not p.is_symlink() and not p.is_junction() for p in [tmp_path, *tmp_path.parents])


@pytest.fixture
def setup(tmp_path):
    case = copy.deepcopy(GOLDEN[0])
    root = str(tmp_path / "financial")
    trust = TestPins(f.FinancialRecordStore.provision_disposable(root, case["manifest"]))
    commands = [f.strict(row[2]) for row in case["sql_rows"]]
    trust.now = commands[0]["timestamp"]
    store = f.FinancialRecordStore(root, trust)
    try:
        yield store, trust, commands, case
    finally:
        store.close()


def reopen(store, trust):
    return f.FinancialRecordStore(store.output.root, trust)


def test_creation_identity_from_original_handle(setup, monkeypatch):
    store, _, _, _ = setup
    identities = []
    original = f.w.write_file
    opens = []
    relative = f.w.relative_open
    def observe_open(*args, **kwargs):
        opens.append((args, kwargs))
        return relative(*args, **kwargs)
    monkeypatch.setattr(f.w, "relative_open", observe_open)
    def write(handle, *args):
        identities.append(f.native.file_identity(handle))
        return original(handle, *args)
    monkeypatch.setattr(f.w, "write_file", write)
    binding = store.output.write_bound("creation-test.json", b"{}")
    assert len(opens) == 1 and opens[0][1]["create"] is True
    assert identities == [binding["id"]]
    assert f.s.read_bound(store.output, "creation-test.json", binding)[0] == b"{}"


def test_full_partial_replay_audit_and_restart(setup):
    store, trust, commands, case = setup
    for command in commands:
        trust.now = command["timestamp"]
        receipt = store.execute(command)
        assert not receipt["startup_authorized"]
    view = store.snapshot()
    assert all(view["state"][k] == v for k, v in case["snapshot"].items() if k in view["state"])
    with_store = reopen(store, trust)
    try:
        assert with_store.snapshot() == view
    finally:
        with_store.close()


def test_overnight_open_is_not_flat_or_valued(setup):
    store, _, commands, _ = setup
    store.execute(commands[0])
    state = store.snapshot()
    assert next(iter(state["state"]["positions"].values()))["remaining"] != "0"
    assert state["valuation"] is None and not state["startup_authorized"]


def test_duplicate_idempotence_conflict_and_concurrent_retry(setup):
    store, trust, commands, _ = setup
    other = reopen(store, trust)
    try:
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda value: value.execute(commands[0]), [store, other]))
        assert results[0] == results[1] and len(trust.pin["entries"]) == 1
        changed = {**commands[0], "quantity": "0.01"}
        with pytest.raises(f.Refused): store.execute(changed)
    finally:
        other.close()


@pytest.mark.parametrize("phase", ["intent", "record", "commit", "ack"])
@pytest.mark.parametrize("moment", ["before", "after"])
def test_publication_failure_refuses_retry_and_restart(setup, monkeypatch, phase, moment):
    store, trust, commands, _ = setup
    original = store.output.write_bound
    def fail(leaf, data):
        if leaf == f.name(1, phase) and moment == "before":
            raise OSError("Injected storage failure before publication")
        binding = original(leaf, data)
        if leaf == f.name(1, phase) and moment == "after":
            raise OSError("Injected lost acknowledgement after flush")
        return binding
    monkeypatch.setattr(store.output, "write_bound", fail)
    with pytest.raises(OSError): store.execute(commands[0])
    with pytest.raises(f.Refused): store.execute(commands[0])
    with pytest.raises(f.Refused): reopen(store, trust)
    assert len(trust.pin["entries"]) == 0


def test_committed_projection_is_unknown_not_reportable_or_replayed(setup):
    store, trust, commands, _ = setup
    result = store.execute(commands[0], projection_required=True)
    assert result["status"] == "UNKNOWN" and not result["fully_acknowledged"]
    assert (Path(store.output.root) / f.name(1, "commit")).exists()
    assert not (Path(store.output.root) / f.name(1, "ack")).exists()
    with pytest.raises(f.Refused): store.snapshot()
    with pytest.raises(f.Refused): reopen(store, trust)


@pytest.mark.parametrize("surface", ["intent", "record", "commit", "ack"])
def test_substitution_refused_before_payload_read(setup, monkeypatch, surface):
    store, _, commands, _ = setup
    store.execute(commands[0])
    path = Path(store.output.root) / f.name(1, surface)
    raw = path.read_bytes()
    path.rename(path.with_suffix(".retained"))
    substitute = store.output.write_bound(path.name, raw)
    read_ids = []
    original = f.w.read_file
    def read(handle, *args):
        read_ids.append(f.native.file_identity(handle))
        return original(handle, *args)
    monkeypatch.setattr(f.w, "read_file", read)
    with pytest.raises(f.Refused): store.snapshot()
    assert substitute["id"] not in read_ids


@pytest.mark.parametrize("attack", ["hardlink", "corrupt", "missing", "extra", "pin-rollback", "wrong-root", "unavailable"])
def test_namespace_corruption_and_pin_uncertainty(setup, attack):
    store, trust, commands, _ = setup
    old = copy.deepcopy(trust.pin)
    store.execute(commands[0])
    path = Path(store.output.root) / f.name(1, "record")
    if attack == "hardlink": os.link(path, path.with_suffix(".linked"))
    if attack == "corrupt": path.write_bytes(b"broken")
    if attack == "missing": path.rename(path.with_suffix(".missing"))
    if attack == "extra": store.output.write_bound("unexpected.json", b"{}")
    if attack == "pin-rollback": trust.pin = old
    if attack == "wrong-root": trust.pin["root"] = [0, 0, 0]
    if attack == "unavailable": trust.available = False
    with pytest.raises((f.Refused, OSError, ValueError)): store.snapshot()


@pytest.mark.parametrize("clock", ["stale", "future", "boolean"])
def test_clock_refusal_precedes_intent(setup, clock):
    store, trust, commands, _ = setup
    trust.now += 31 if clock == "stale" else -31
    command = copy.deepcopy(commands[0])
    if clock == "boolean": command["timestamp"] = True
    with pytest.raises(f.Refused): store.execute(command)
    assert not (Path(store.output.root) / f.name(1, "intent")).exists()


def test_capacity_refusal_no_new_record(setup, monkeypatch):
    store, _, commands, _ = setup
    store.execute(commands[0])
    monkeypatch.setattr(f, "MAX_OPERATIONS", 1)
    with pytest.raises(f.Refused, match="Capacity"): store.execute(commands[1])
    assert not (Path(store.output.root) / f.name(2, "intent")).exists()


@pytest.mark.parametrize("failure", ["short", "flush", "write", "full-disk"])
def test_native_write_failure_retains_uncertainty(setup, monkeypatch, failure):
    store, trust, commands, _ = setup
    original = f.w.write_file
    def write(handle, data, length, count, overlapped):
        if failure in ("write", "full-disk"):
            raise OSError(28 if failure == "full-disk" else 5, "Injected write failure")
        return original(handle, data, length - 1, count, overlapped)
    if failure == "flush":
        monkeypatch.setattr(f.w, "flush", lambda handle: False)
    else:
        monkeypatch.setattr(f.w, "write_file", write)
    with pytest.raises(OSError): store.execute(commands[0])
    with pytest.raises(f.Refused): store.snapshot()
    with pytest.raises((f.Refused, OSError)): reopen(store, trust)


def test_directory_retained_and_symlink_capability(setup):
    store, _, _, _ = setup
    path = Path(store.output.root)
    with pytest.raises(OSError): path.rename(path.with_name("replaced-root"))
    link = path.parent / "true-link"
    try:
        os.symlink(path, link, target_is_directory=True)
    except OSError as exc:
        if exc.winerror == 1314:
            pytest.skip("NOT EXECUTED: true symlink privilege unavailable (1314)")
        raise
    with pytest.raises((OSError, ValueError)): f.w.WindowsOutput(str(link))


CHILD = r"""
import sys,os,json,importlib.util,copy
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'backend'))
spec=importlib.util.spec_from_file_location('fs2',Path(sys.argv[1])/'scripts/volume_inspector/financial_record_store.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
class Pins:
 def current(self):return json.loads(Path(sys.argv[3]).read_text())
 def check_clock(self,t):pass
 def advance(self,old,new):
  Path(sys.argv[3]).write_text(json.dumps(new))
p=Pins();store=f.FinancialRecordStore(sys.argv[2],p);original=store.output.write_bound
boundary=sys.argv[5]
if boundary=='concurrent':
 import time
 Path(sys.argv[6]).write_text('ready')
 deadline=time.monotonic()+5
 while not Path(sys.argv[7]).exists():
  if time.monotonic()>deadline:os._exit(26)
  time.sleep(.01)
def write(leaf,data):
 if boundary=='before-'+leaf:os._exit(24)
 binding=original(leaf,data)
 if boundary=='after-'+leaf:os._exit(24)
 return binding
store.output.write_bound=write
store.execute(json.loads(sys.argv[4]));os._exit(25)
"""


def helper(args, cwd):
    child = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    W = f.native.W
    creation, exited, kernel, user = W.FILETIME(), W.FILETIME(), W.FILETIME(), W.FILETIME()
    times = f.w.bind(f.w.K, "GetProcessTimes", [W.HANDLE, C.POINTER(W.FILETIME), C.POINTER(W.FILETIME),
                                             C.POINTER(W.FILETIME), C.POINTER(W.FILETIME)])
    f.w.check(times(child._handle, C.byref(creation), C.byref(exited), C.byref(kernel), C.byref(user)))
    identity = [child.pid, (creation.dwHighDateTime << 32) | creation.dwLowDateTime]
    try:
        out, err = child.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        raise AssertionError("Test child timeout; retained, never force-killed") from None
    with (Path(os.environ["ATLAS_D1_ATTEMPT"]) / "observations.jsonl").open("a") as h:
        h.write(json.dumps({"case": "helper", "pid": child.pid, "returncode": child.returncode,
                            "status": "EXITED", "identity": identity, "command": args}) + "\n")
    return child.returncode, out, err


@pytest.mark.parametrize("boundary", ["before-0001-intent.json", "after-0001-intent.json",
    "after-0001-record.json", "after-0001-commit.json", "after-0001-ack.json", "complete"])
def test_abrupt_child_restart_boundary(setup, tmp_path, boundary):
    store, trust, commands, _ = setup
    pin_file = tmp_path / "test-only-pin.json"
    pin_file.write_text(json.dumps(trust.pin))
    code, _, err = helper([sys.executable, "-I", "-B", "-c", CHILD, str(REPO), store.output.root,
                            str(pin_file), json.dumps(commands[0]), boundary], tmp_path)
    assert code == (25 if boundary == "complete" else 24), err
    trust.pin = json.loads(pin_file.read_text())
    if boundary == "complete":
        restarted = reopen(store, trust)
        try:
            assert restarted.snapshot()["state"]["revision"] == 1
            restarted.execute(commands[0])
            assert len(trust.pin["entries"]) == 1
        finally:
            restarted.close()
    else:
        with pytest.raises(f.Refused): reopen(store, trust)
        # Refusal must remain after the abandoned mutex has been observed.
        with pytest.raises(f.Refused): reopen(store, trust)


def test_parent_junction_refused(setup, tmp_path):
    store, trust, _, _ = setup
    link = tmp_path / "parent-junction"
    code, _, err = helper([os.environ["COMSPEC"], "/d", "/c", "mklink", "/J", str(link), store.output.root], tmp_path)
    assert code == 0, err
    with pytest.raises((OSError, ValueError)): f.FinancialRecordStore(str(link), trust)


def test_restricted_token_cannot_read_or_create_financial_files(setup):
    store, _, _, _ = setup
    w, W = f.w, f.native.W
    normal, restricted, everyone = W.HANDLE(), W.HANDLE(), C.c_void_p()
    convert = w.bind(w.A, "ConvertStringSidToSidW", [W.LPCWSTR, C.POINTER(C.c_void_p)])
    restrict = w.bind(w.A, "CreateRestrictedToken", [W.HANDLE, W.DWORD, W.DWORD, C.c_void_p, W.DWORD,
        C.c_void_p, W.DWORD, C.POINTER(w.SidAttr), C.POINTER(W.HANDLE)])
    impersonate = w.bind(w.A, "ImpersonateLoggedOnUser", [W.HANDLE])
    revert = w.bind(w.A, "RevertToSelf", [])
    try:
        w.check(w.open_token(w.process(), 0xE, C.byref(normal)))
        w.check(convert("S-1-1-0", C.byref(everyone)))
        entry = w.SidAttr(everyone, 0)
        w.check(restrict(normal, 1, 0, None, 0, None, 1, C.byref(entry), C.byref(restricted)))
        w.check(impersonate(restricted))
        try:
            for leaf, access, creation in [("inception.json", w.READ, 3), ("inception.json", w.WRITE, 3),
                                           ("foreign-write.json", w.WRITE, 1)]:
                handle = w.create_file(str(Path(store.output.root) / leaf), access, 7, None, creation, 0, None)
                error = C.get_last_error()
                if handle != w.INVALID: w.close_handle(handle)
                assert handle == w.INVALID and error == 5
        finally:
            w.check(revert())
    finally:
        if normal: w.close_handle(normal)
        if restricted: w.close_handle(restricted)
        if everyone: w.local_free(everyone)


@pytest.mark.parametrize("bad", [None, {}, {"id": [True, 1, 2], "sha256": "a" * 64},
                                 {"id": [1, 2, 3], "sha256": "bad"}])
def test_bad_binding_never_reads(setup, monkeypatch, bad):
    store, trust, _, _ = setup
    trust.pin["inception"] = bad
    monkeypatch.setattr(f.w, "read_file", lambda *args: pytest.fail("Read before binding validation"))
    with pytest.raises(f.Refused): store.snapshot()


def test_lost_pin_ack_never_reapplies(setup, monkeypatch):
    store, trust, commands, _ = setup
    monkeypatch.setattr(trust, "advance", lambda *args: (_ for _ in ()).throw(OSError("Lost pin acknowledgement")))
    with pytest.raises(OSError): store.execute(commands[0])
    with pytest.raises(f.Refused): reopen(store, trust)
    assert len(list(Path(store.output.root).glob("*-record.json"))) == 1


def test_read_lease_excludes_replacement_and_write(setup, monkeypatch):
    store, _, _, _ = setup
    original = f.w.read_file
    attempts = []
    def read(handle, *args):
        path = Path(store.output.root) / "inception.json"
        opened = f.w.create_file(str(path), f.w.WRITE, 7, None, 3, 0, None)
        error = C.get_last_error()
        if opened != f.w.INVALID: f.w.close_handle(opened)
        assert opened == f.w.INVALID and error == 32
        with pytest.raises(OSError): path.rename(path.with_suffix(".raced"))
        attempts.append(error)
        return original(handle, *args)
    monkeypatch.setattr(f.w, "read_file", read)
    store.snapshot()
    assert attempts == [32]


def test_file_capacity_and_no_replace(setup):
    store, _, _, _ = setup
    before = (Path(store.output.root) / "inception.json").read_bytes()
    with pytest.raises(OSError): store.output.write_bound("inception.json", b"replacement")
    with pytest.raises(ValueError): store.output.write_bound("oversized.json", b"x" * 65537)
    assert (Path(store.output.root) / "inception.json").read_bytes() == before
    assert not (Path(store.output.root) / "oversized.json").exists()


def test_coherent_test_pin_rollback_is_explicitly_not_independent_authority(setup):
    store, trust, commands, _ = setup
    original = copy.deepcopy(trust.pin)
    store.execute(commands[0])
    # Demonstrate the declared limit: simultaneous rollback of test custody AND
    # all local records cannot be detected by hashes. No operational claim.
    for p in Path(store.output.root).glob("0001-*.json"):
        p.rename(p.parent.parent / ("retained-" + p.name))
    trust.pin = original
    assert store.snapshot()["state"]["revision"] == 0


def test_perpetual_fixture_replay_reuses_fs1_without_sqlite(tmp_path):
    case = copy.deepcopy(GOLDEN[1])
    root = str(tmp_path / "perps")
    trust = TestPins(f.FinancialRecordStore.provision_disposable(root, case["manifest"]))
    store = f.FinancialRecordStore(root, trust)
    try:
        for row in case["sql_rows"]:
            command = f.strict(row[2])
            trust.now = command["timestamp"]
            assert f.body(store.execute(command)) == row[5]
        assert store.snapshot()["state"]["net_r"] == case["snapshot"]["net_r"]
    finally:
        store.close()


def test_wrong_protected_acl_refused(setup):
    store, _, _, _ = setup
    path = str(Path(store.output.root) / "inception.json")
    set_security = f.w.bind(f.w.A, "SetFileSecurityW", [f.native.W.LPCWSTR, f.native.W.DWORD, C.c_void_p])
    descriptor = C.c_void_p()
    f.w.check(f.w.sddl_sd(f"D:(A;;FA;;;{store.output.sid})(A;;FA;;;SY)", 1, C.byref(descriptor), None))
    try:
        f.w.check(set_security(path, 4 | 0x20000000, descriptor))
    finally:
        f.w.local_free(descriptor)
    with pytest.raises(PermissionError): store.snapshot()


@pytest.mark.parametrize("phase", ["intent", "record", "commit", "ack"])
def test_missing_ack_or_broken_committed_chain_refused(setup, phase):
    store, trust, commands, _ = setup
    store.execute(commands[0])
    path = Path(store.output.root) / f.name(1, phase)
    raw = f.strict(path.read_text())
    # Even a test authority supplied replacement binding cannot excuse malformed
    # semantic lineage. Retain original bytes, never repair them in place.
    raw["revision"] = 77
    path.rename(path.parent.parent / ("retained-" + path.name))
    trust.pin["entries"][0][phase] = store.output.write_bound(path.name, f.encoded(raw))
    with pytest.raises(f.Refused, match="Contradictory"): store.snapshot()


def test_independent_audit_detects_bad_computation():
    case = GOLDEN[0]
    rows = [f.event_stream_record(*row) for row in case["sql_rows"]]
    state, _, _ = f.replay_verified_events(case["manifest"], rows)
    state["cash"] = "100000"
    with pytest.raises(ValueError, match="reconciliation"):
        f.audit_financial_events(case["manifest"], rows, state)


def test_no_sql_financial_authority_or_operational_registration():
    import ast
    tree = ast.parse((REPO / "scripts/volume_inspector/financial_record_store.py").read_text())
    imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(n and ("fixture" in n or "sqlite" in n) for n in imports)
    for relative in ["backend/app/main.py", "backend/app/core/production_startup_lock.py",
                     "scripts/windows/Atlas-Background-Manager.ps1"]:
        path = REPO / relative
        if path.exists(): assert "financial_record_store" not in path.read_text()



def test_two_owned_subprocesses_share_exclusion_and_retry_identity(setup, tmp_path):
    import time
    store, trust, commands, _ = setup
    pin_file, go = tmp_path / "shared-test-pin.json", tmp_path / "go"
    pin_file.write_text(json.dumps(trust.pin))
    ready = [tmp_path / "child-one-ready", tmp_path / "child-two-ready"]
    base = [sys.executable, "-I", "-B", "-c", CHILD, str(REPO), store.output.root,
            str(pin_file), json.dumps(commands[0]), "concurrent"]
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(helper, [*base, str(r), str(go)], tmp_path) for r in ready]
        deadline = time.monotonic() + 4
        while not all(r.exists() for r in ready) and time.monotonic() < deadline:
            time.sleep(.01)
        assert all(r.exists() for r in ready)
        go.write_text("go")
        results = [future.result() for future in futures]
    assert all(code == 25 for code, _, _ in results), results
    trust.pin = json.loads(pin_file.read_text())
    assert len(trust.pin["entries"]) == 1
    assert store.snapshot()["state"]["revision"] == 1
    assert len(list(Path(store.output.root).glob("*-record.json"))) == 1


def test_actual_128_operation_capacity_and_cash_replay(setup):
    from decimal import Decimal
    store, trust, commands, _ = setup
    entry = commands[0]
    position = None
    for index in range(128):
        command = copy.deepcopy(entry if index % 2 == 0 else commands[1])
        command.update(operation_id=f"capacity-{index}", expected_source_revision=index,
                       timestamp=entry["timestamp"] + index, quantity="0.1")
        command["quote"].update(price="100", observed_at=command["timestamp"])
        if index % 2 == 0:
            command["origin_ref"] = f"capacity-source-{index}"
        else:
            command.update(position_id=position, expected_position_revision=1)
        trust.now = command["timestamp"]
        position = store.execute(command)["position_id"]
    state = store.snapshot()["state"]
    assert state["revision"] == 128
    assert all(Decimal(p["remaining"]) == 0 for p in state["positions"].values())
    assert Decimal(state["costs"]) == Decimal("0.512")
    command = {**entry, "operation_id": "overflow", "expected_source_revision": 128,
               "timestamp": trust.now}
    with pytest.raises(f.Refused, match="Capacity"): store.execute(command)
    assert not (Path(store.output.root) / f.name(129, "intent")).exists()



def test_boolean_ack_revision_is_not_integer_one(setup):
    store, trust, commands, _ = setup
    store.execute(commands[0])
    path = Path(store.output.root) / f.name(1, "ack")
    raw = f.strict(path.read_text())
    raw["revision"] = True
    path.rename(path.parent.parent / "retained-integer-ack.json")
    trust.pin["entries"][0]["ack"] = store.output.write_bound(path.name, f.encoded(raw))
    with pytest.raises(f.Refused, match="Contradictory"): store.snapshot()
