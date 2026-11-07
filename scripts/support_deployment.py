"""Create-new nonfinancial support deployment. No selection, providers or services.

Operational construction is separately authorized and bound to a reviewed
manifest, real installed application, genuine clock and accepted parent identity.
Disposable construction is a disjoint namespace and never operational authority.
"""
import ctypes as C
import hashlib
import io
import os
import re
import subprocess
import sys
import time
import zipfile
from contextlib import ExitStack, contextmanager
from pathlib import Path

if __name__ == "__main__":
    if "--execute-approved-support-deployment" not in sys.argv:
        raise SystemExit("REFUSED: reviewed exact support manifest and separate explicit invocation required")
    source_root = Path(__file__).absolute().parents[1]
    if source_root != Path("D:/Work/Project Atlas"):
        raise SystemExit("REFUSED: exact reviewed deployment adapter origin required")
    sys.path[:0] = [str(source_root / "backend"), str(source_root)]

from scripts.release_selection import encoded, strict

APP = "2c039af29dfefd1df77e0caa3db3fdf5ed188118"
LIMITS = {"seconds": 600, "entries": 8192, "bytes": 64 * 1024**2}
EXCLUSIONS = ["APPLICATION_PAYLOAD", "FINANCIAL_STATE", "PROVIDERS", "GENESIS",
              "DESKTOP_SHORTCUTS", "WINDOWS_CONFIGURATION", "AUTOMATIC_STARTUP"]
SOURCES = {
    "scripts/build_release_candidate.py", "scripts/install_verified_release.py",
    "scripts/native_install_candidate.py", "scripts/native_install_plan.py",
    "scripts/release_selection.py", "scripts/release_selection_store.py",
    "scripts/installed_nonfinancial_launcher.py", "scripts/support_deployment.py",
    "scripts/windows/Atlas-Installed-Nonfinancial.psm1",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(w, handle):
    row = w.info(handle)
    return [row.volume, row.index_hi, row.index_lo]


def native_id(value):
    if (type(value) is not list or len(value) != 3
            or any(type(n) is not int or not 0 <= n <= 0xffffffff for n in value)):
        raise ValueError("SUPPORT_NATIVE_ID_REQUIRED")
    return value


def pin(value):
    if type(value) is not str or not re.fullmatch("[0-9a-f]{64}", value):
        raise ValueError("SUPPORT_EXACT_PIN_REQUIRED")
    return value


def fixture_base(value):
    path = Path(value).absolute()
    # A test domain is never inferred from an installed package's location.
    repo = Path("D:/Work/Project Atlas")
    try:
        parts = path.relative_to(repo / "logs/diagnostics").parts
    except ValueError:
        raise ValueError("SUPPORT_CONFINED_FIXTURE_REQUIRED") from None
    if len(parts) != 2 or not parts[0].startswith("qd-selector-v1-native-"):
        raise ValueError("SUPPORT_CONFINED_FIXTURE_REQUIRED")
    return path


def validate_manifest(value):
    m = strict(encoded(value))
    fields = {"schema", "domain", "status", "support_manifest_sha256", "archive_sha256",
              "destination", "control", "selection", "new_parents", "files", "directories",
              "application", "limits", "exclusions", "runtime", "receipt_schema"}
    if (type(m) is not dict or set(m) != fields or m["schema"] != "QD_SUPPORT_DEPLOYMENT_V1"
            or m["status"] != "REVIEW_INVENTORY_NOT_PERMISSION"
            or m["domain"] not in ("WINDOWS_LOCAL", "DISPOSABLE")
            or m["limits"] != LIMITS or m["exclusions"] != EXCLUSIONS
            or m["receipt_schema"] != "QD_SUPPORT_INSTALL_RECEIPT_V1"):
        raise ValueError("EXACT_SUPPORT_DEPLOYMENT_MANIFEST_REQUIRED")
    h = pin(m["support_manifest_sha256"]); pin(m["archive_sha256"])
    if m["domain"] == "WINDOWS_LOCAL":
        base = Path("D:/AtlasRuntime")
    else:
        base = fixture_base(Path(m["selection"]).parent)
    expected = {"destination": str(base / "launchers" / h),
                "control": str(base / "support-installations" / h),
                "selection": str(base / "selection")}
    if any(type(m[k]) is not str or m[k] != v for k, v in expected.items()):
        raise ValueError("EXPLICIT_SUPPORT_DESTINATION_REQUIRED")
    if m["new_parents"] != [str(base / "launchers"), str(base / "support-installations")]:
        raise ValueError("EXACT_NEW_SUPPORT_PARENTS_REQUIRED")
    a = m["application"]
    if (type(a) is not dict or set(a) != {"release", "root", "receipt", "receipt_sha256", "artifact_digest"}
            or a["release"] != APP or a["root"] != str(base / "releases" / APP)):
        raise ValueError("EXACT_SUPPORT_APPLICATION_REQUIRED")
    pin(a["receipt_sha256"]); pin(a["artifact_digest"])
    expected_receipt = (Path("D:/Work/Project Atlas/logs/diagnostics") / ("qd-unselected-release-" + APP + ".json")
                        if m["domain"] == "WINDOWS_LOCAL" else base / "application-receipt.json")
    if a["receipt"] != str(expected_receipt):
        raise ValueError("EXACT_SUPPORT_APPLICATION_RECEIPT_REQUIRED")
    if m["runtime"] != {"python": str(base / "releases" / APP / "python/python.exe"),
                        "version": [3, 12], "bits": 64, "app_receipt_inventory": True,
                        "providers": False, "financial_writers": False, "workspace_fallback": False}:
        raise ValueError("EXACT_SUPPORT_RUNTIME_REQUIRED")
    rows = m["files"]
    if type(rows) is not list or len(rows) != len(SOURCES) + 1:
        raise ValueError("EXACT_SUPPORT_FILE_INVENTORY_REQUIRED")
    names = set()
    for row in rows:
        if (type(row) is not dict or set(row) != {"path", "bytes", "sha256"}
                or type(row["path"]) is not str or row["path"] in names
                or row["path"] not in SOURCES | {"support-manifest.json"}
                or type(row["bytes"]) is not int or not 0 < row["bytes"] <= 262144):
            raise ValueError("EXACT_SUPPORT_FILE_INVENTORY_REQUIRED")
        pin(row["sha256"]); names.add(row["path"])
    directories = sorted({"."} | {p.as_posix() for n in names for p in Path(n).parents})
    if names != SOURCES | {"support-manifest.json"} or m["directories"] != directories:
        raise ValueError("EXACT_SUPPORT_NAMESPACE_REQUIRED")
    if (len(rows) + len(directories) + 8 >= LIMITS["entries"]
            or sum(r["bytes"] for r in rows) + (len(rows) + len(directories) + 8) * 4096 >= LIMITS["bytes"]):
        raise ValueError("SUPPORT_PLAN_CAPACITY")
    return m


def safe_read(path, maximum):
    from scripts.build_release_candidate import source_bytes
    path = Path(path)
    return source_bytes(path.parent, path.name, maximum_bytes=maximum)


def prepare(manifest, archive, expected_manifest_sha256):
    m = validate_manifest(manifest)
    if sha(encoded(m)) != pin(expected_manifest_sha256):
        raise ValueError("SUPPORT_DEPLOYMENT_PIN_MISMATCH")
    raw = safe_read(archive, LIMITS["bytes"])
    if sha(raw) != m["archive_sha256"]:
        raise ValueError("SUPPORT_ARCHIVE_PIN_MISMATCH")
    files = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.infolist()) != len(m["files"]):
            raise ValueError("SUPPORT_ARCHIVE_NAMESPACE")
        for expected, item in zip(sorted(m["files"], key=lambda r: r["path"]), sorted(z.infolist(), key=lambda r: r.filename)):
            if (item.filename != expected["path"] or item.file_size != expected["bytes"]
                    or item.flag_bits & 1 or item.is_dir()
                    or (item.external_attr >> 16) & 0o170000 not in (0, 0o100000)):
                raise ValueError("SUPPORT_ARCHIVE_NAMESPACE")
            data = z.read(item)
            if sha(data) != expected["sha256"]:
                raise ValueError("SUPPORT_ARCHIVE_CONTENT")
            files[item.filename] = data
    package = strict(files["support-manifest.json"])
    if (sha(files["support-manifest.json"]) != m["support_manifest_sha256"]
            or package.get("schema") != "QD_NONFINANCIAL_LAUNCHER_SUPPORT_V2"
            or package.get("application_release") != APP
            or package.get("support_sources") != [r for r in m["files"] if r["path"] != "support-manifest.json"]):
        raise ValueError("SUPPORT_PACKAGE_BINDING")
    return m, files


@contextmanager
def held(output):
    """Existing WindowsOutput.close is legacy; require every actual close ACK."""
    from scripts.volume_inspector import windows_output as w
    try:
        yield output
    finally:
        failed = False
        for handle in list(reversed(output.handles)):
            if w.close_handle(handle):
                output.handles.remove(handle)
            else:
                failed = True
        if failed:
            raise OSError("SUPPORT_HANDLE_CLOSE_UNCONFIRMED")


def read_native(output, name, maximum=262144, expected=None):
    from scripts.volume_inspector import windows_output as w
    output._verify()
    handle = w.relative_open(output.root_handle, name, output.sid, False, access=w.READ | w.READ_CONTROL)
    try:
        w.validate_acl(handle, output.sid); info = w.info(handle)
        fid = identity(w, handle); size = info.size_hi << 32 | info.size_lo
        if info.links != 1 or size > maximum or expected is not None and fid != expected:
            raise ValueError("SUPPORT_NATIVE_IDENTITY_LINK_OR_SIZE")
        buffer, count = C.create_string_buffer(size + 1), w.W.DWORD()
        w.check(w.read_file(handle, buffer, size + 1, C.byref(count), None))
        if count.value != size or identity(w, handle) != fid or w.info(handle).links != 1:
            raise ValueError("SUPPORT_NATIVE_READ_CHANGED")
        return buffer.raw[:size], fid
    finally:
        if not w.close_handle(handle):
            raise OSError("SUPPORT_READ_HANDLE_CLOSE_UNCONFIRMED")


def inventory(root, files, directories, bound, *, expected=None):
    from scripts.native_install_candidate import _verify_namespace
    from scripts.volume_inspector import windows_output as w
    rows, dirs = [], []
    with ExitStack() as stack:
        outputs = {}
        for name in sorted(directories, key=lambda n: (len(Path(n).parts), n)):
            bound(); output = stack.enter_context(held(w.WindowsOutput(str(root / name))))
            fid = identity(w, output.root_handle)
            if expected is not None and fid != next(r["id"] for r in expected["directories"] if r["path"] == name):
                raise ValueError("SUPPORT_DIRECTORY_SUBSTITUTION")
            outputs[name] = output; dirs.append({"path": name, "id": fid})
        for row in files:
            bound(); relative = Path(row["path"])
            fid = None if expected is None else next(r["id"] for r in expected["files"] if r["path"] == row["path"])
            raw, actual = read_native(outputs[relative.parent.as_posix()], relative.name,
                                      maximum=row["bytes"], expected=fid)
            if len(raw) != row["bytes"] or sha(raw) != row["sha256"]:
                raise ValueError("SUPPORT_READBACK_CONTENT")
            rows.append({**row, "id": actual})
        _verify_namespace(root, {r["path"] for r in files}, set(directories), bound)
    return {"files": rows, "directories": dirs}


def _no_existing(paths):
    for path in paths:
        if os.path.lexists(path):
            raise ValueError("SUPPORT_EXISTS_PRESERVE_NO_ADOPTION_OR_RETRY")
        for node in path.parents:
            if os.path.lexists(node) and (not node.is_dir() or getattr(node.lstat(), "st_file_attributes", 0) & 0x400):
                raise ValueError("SUPPORT_ANCESTOR_SUBSTITUTION")


def _install(m, files, *, parent_identity, admission, interrupt_after=None):
    from scripts.volume_inspector import windows_output as w
    native_id(parent_identity)
    start = time.monotonic(); base = Path(m["selection"]).parent
    paths = [*[Path(p) for p in m["new_parents"]], Path(m["selection"]), Path(m["destination"]), Path(m["control"])]
    _no_existing(paths)
    created, written = 0, 0
    def bound(extra=0):
        if (admission() is not True or time.monotonic() - start >= LIMITS["seconds"]
                or created >= LIMITS["entries"] or written + extra + (created + 1) * 4096 >= LIMITS["bytes"]):
            raise ValueError("SUPPORT_ADMISSION_OR_CAPACITY_REFUSED_PRESERVE_PARTIAL")
    with ExitStack() as stack:
        accepted_parent = stack.enter_context(held(w.WindowsOutput(str(base))))
        if identity(w, accepted_parent.root_handle) != parent_identity:
            raise ValueError("SUPPORT_ACCEPTED_PARENT_SUBSTITUTION")
        # No parent ACL changes. A new child pins ancestors before any publication.
        bound(); first = stack.enter_context(held(w.WindowsOutput.create_root(str(paths[0])))); created += 1
        parent = first.handles[-2]
        if identity(w, parent) != parent_identity:
            raise ValueError("SUPPORT_ACCEPTED_PARENT_SUBSTITUTION_PRESERVE_PARTIAL")
        outputs = {str(paths[0]): first}
        for path in paths[1:]:
            bound(); outputs[str(path)] = stack.enter_context(held(w.WindowsOutput.create_root(str(path)))); created += 1
        control = outputs[m["control"]]
        def write(out, name, data):
            nonlocal created, written
            bound(len(data)); value = out.write_bound(name, data); created += 1; written += len(data)
            return value
        write(control, "intent.json", encoded({"schema": "QD_SUPPORT_INSTALL_INTENT_V1", "domain": m["domain"],
              "deployment_sha256": sha(encoded(m)), "parent_id": parent_identity, "financial_authority": False}))
        for name in sorted(m["directories"], key=lambda n: (len(Path(n).parts), n)):
            path = Path(m["destination"]) / name
            if name != ".":
                bound(); outputs[str(path)] = stack.enter_context(held(w.WindowsOutput.create_root(str(path)))); created += 1
        for index, row in enumerate(m["files"], 1):
            relative = Path(row["path"])
            write(outputs[str(Path(m["destination"]) / relative.parent)], relative.name, files[row["path"]])
            if interrupt_after == index:
                raise OSError("EXPLICIT_DISPOSABLE_SUPPORT_INTERRUPTION")
        proof = inventory(Path(m["destination"]), m["files"], m["directories"], bound)
        selection = outputs[m["selection"]]
        if list(Path(m["selection"]).iterdir()):
            raise ValueError("NEW_SELECTION_NOT_EMPTY")
        receipt = {"schema": m["receipt_schema"], "domain": m["domain"], "deployment": m,
                   "deployment_sha256": sha(encoded(m)), "inventory": proof,
                   "selection_id": identity(w, selection.root_handle), "control_id": identity(w, control.root_handle),
                   "parent_id": parent_identity, "financial_actions": 0, "selected": False}
        write(control, "receipt.json", encoded(receipt))
        # This is a real separate process and installed support module readback.
        proof = independent_readback(m, sha(encoded(receipt)), timeout=min(180, LIMITS["seconds"] - (time.monotonic() - start) - 5))
        bound()
        write(control, "ack.json", encoded({"schema": "QD_SUPPORT_INSTALL_ACK_V1", "domain": m["domain"],
              "receipt_sha256": sha(encoded(receipt)), "deployment_sha256": sha(encoded(m))}))
        verify_deployment(m, expected_receipt_sha256=sha(encoded(receipt)))
        bound()
    return {"receipt": receipt, "receipt_sha256": sha(encoded(receipt)), "independent_readback": proof,
            "seconds": round(time.monotonic() - start, 3), "created_entries": created, "written_bytes": written,
            "handles_after_close": 0}


def verify_deployment(manifest, *, expected_receipt_sha256, acknowledged=True):
    from scripts.volume_inspector import windows_output as w
    m = validate_manifest(manifest); started = time.monotonic()
    def bound():
        if time.monotonic() - started >= 180:
            raise ValueError("SUPPORT_READBACK_DEADLINE")
    with held(w.WindowsOutput(m["control"])) as control:
        raw, _ = read_native(control, "receipt.json", 65536)
        if sha(raw) != pin(expected_receipt_sha256):
            raise ValueError("SUPPORT_RECEIPT_PIN_MISMATCH")
        r = strict(raw)
        if (type(r) is not dict or set(r) != {"schema", "domain", "deployment", "deployment_sha256", "inventory",
                                             "selection_id", "control_id", "parent_id", "financial_actions", "selected"}
                or r["schema"] != m["receipt_schema"] or r["domain"] != m["domain"] or r["deployment"] != m
                or r["deployment_sha256"] != sha(encoded(m)) or type(r["financial_actions"]) is not int
                or r["financial_actions"] != 0 or r["selected"] is not False
                or r["control_id"] != identity(w, control.root_handle)
                or r["parent_id"] != identity(w, control.handles[-3])):
            raise ValueError("SUPPORT_RECEIPT_BINDING")
        intent, _ = read_native(control, "intent.json", 65536)
        if strict(intent) != {"schema": "QD_SUPPORT_INSTALL_INTENT_V1", "domain": m["domain"],
                              "deployment_sha256": sha(encoded(m)), "parent_id": r["parent_id"], "financial_authority": False}:
            raise ValueError("SUPPORT_INTENT_BINDING")
        expected_names = {"intent.json", "receipt.json"} | ({"ack.json"} if acknowledged else set())
        if {p.name for p in Path(m["control"]).iterdir()} != expected_names:
            raise ValueError("SUPPORT_CONTROL_NAMESPACE_OR_INCOMPLETE_ACK")
        if acknowledged:
            ack, _ = read_native(control, "ack.json", 65536)
            if strict(ack) != {"schema": "QD_SUPPORT_INSTALL_ACK_V1", "domain": m["domain"],
                               "receipt_sha256": sha(raw), "deployment_sha256": sha(encoded(m))}:
                raise ValueError("SUPPORT_ACK_REQUIRED")
        inventory(Path(m["destination"]), m["files"], m["directories"], bound, expected=r["inventory"])
        with held(w.WindowsOutput(m["selection"])) as selection:
            if identity(w, selection.root_handle) != r["selection_id"]:
                raise ValueError("SUPPORT_SELECTION_ROOT_SUBSTITUTION")
    return r


def independent_readback(m, receipt_sha256, *, timeout):
    from scripts.observation_runtime.disposable_host_owner import (
        observe_handle,
        observe_pid,
    )
    if not 0 < timeout <= 180:
        raise ValueError("SUPPORT_READBACK_TIME_REQUIRED")
    code = r'''
import hashlib,json,sys
from pathlib import Path
v=json.loads(sys.stdin.read());m=v['manifest'];root=Path(m['destination']);app=Path(m['application']['root'])
if Path(sys.executable)!=app/'python/python.exe' or Path(sys.base_prefix)!=app/'python':raise ValueError('SUPPORT_READBACK_INTERPRETER')
if any(not Path(p).resolve().is_relative_to(app) for p in sys.path if p):raise ValueError('SUPPORT_READBACK_FOREIGN_IMPORT')
p=root/'scripts/support_deployment.py';raw=p.read_bytes();row=next(r for r in m['files'] if r['path']=='scripts/support_deployment.py')
if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('SUPPORT_VERIFIER_SOURCE_HASH')
sys.path[:0]=[str(root),str(app/'backend'),str(app)]
from scripts.support_deployment import verify_deployment
verify_deployment(m,expected_receipt_sha256=v['receipt'],acknowledged=False)
print(json.dumps({'verified':True,'domain':m['domain'],'handles_after_close':0,'image':sys.executable}))
'''
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    executable = m["runtime"]["python"]
    child = subprocess.Popen([executable, "-I", "-B", "-c", code], cwd=m["application"]["root"], env=env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        observed = observe_pid(child.pid)
        if observed["created"] != observe_handle(int(child._handle)) or observed["image"] != executable.casefold():
            raise ValueError("SUPPORT_READBACK_PROCESS_OWNERSHIP")
        out, err = child.communicate(encoded({"manifest": m, "receipt": receipt_sha256}), timeout=timeout)
        if child.returncode or err or len(out) > 4096:
            raise ValueError("SUPPORT_INDEPENDENT_READBACK_REFUSED:" + err.decode(errors="replace")[-2048:])
        expected = {"verified": True, "domain": m["domain"], "handles_after_close": 0, "image": executable}
        if strict(out) != expected:
            raise ValueError("SUPPORT_READBACK_ACK_REFUSED")
        return expected
    finally:
        if child.poll() is None:
            child.kill(); child.communicate(timeout=5)
        for stream in (child.stdin, child.stdout, child.stderr):
            if stream is not None:
                stream.close()
        child._handle.Close()


def install_disposable(*, manifest, archive, manifest_sha256, parent_identity, interrupt_after=None):
    m, files = prepare(manifest, archive, manifest_sha256)
    if m["domain"] != "DISPOSABLE":
        raise ValueError("DISPOSABLE_SUPPORT_DOMAIN_REQUIRED")
    if interrupt_after is not None and (type(interrupt_after) is not int or not 1 <= interrupt_after <= len(files)):
        raise ValueError("EXPLICIT_SUPPORT_FAULT_REQUIRED")
    return _install(m, files, parent_identity=parent_identity, admission=lambda: True, interrupt_after=interrupt_after)


def install_operational(*, approved=False, manifest=None, archive=None, manifest_sha256=None,
                        parent_identity=None, clock=None):
    if approved is not True:
        raise ValueError("SEPARATE_EXACT_SUPPORT_DEPLOYMENT_AUTHORIZATION_REQUIRED")
    from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock
    from scripts.release_selection import NativeInstalledReleaseVerifier
    if type(clock) is not LocalWindowsClock:
        raise ValueError("GENUINE_SUPPORT_CLOCK_REQUIRED")
    m, files = prepare(manifest, archive, manifest_sha256)
    if m["domain"] != "WINDOWS_LOCAL" or Path(sys.executable) != Path(m["runtime"]["python"]):
        raise ValueError("OPERATIONAL_SUPPORT_DOMAIN_AND_D_INTERPRETER_REQUIRED")
    # Verify every deployed source against the separately reviewed local adapter,
    # not just a caller-supplied archive claiming to contain a verifier.
    repo = Path(__file__).resolve().parents[1]
    for name in SOURCES:
        if safe_read(repo / name, 262144).replace(b'\r\n', b'\n') != files[name]:
            raise ValueError("REVIEWED_SUPPORT_SOURCE_CHANGED")
    reference = {"schema": "QD_INSTALLED_RELEASE_REFERENCE_V1", "domain": "WINDOWS_LOCAL", **m["application"]}
    def admission():
        clock.require_operational("qd-support-deployment-" + manifest_sha256)
        return True
    admission()
    with NativeInstalledReleaseVerifier().open(reference) as receipt:
        package = strict(files["support-manifest.json"])
        actual = {r["path"].replace('\\', '/'): r["sha256"] for r in receipt["files"]}
        for row in package["required_installed_application_sources"]:
            if actual.get(row["path"]) != row["sha256"]:
                raise ValueError("SUPPORT_APPLICATION_DEPENDENCY_MISSING_OR_CHANGED")
        return _install(m, files, parent_identity=parent_identity, admission=admission)


class DisposableInstalledReleaseVerifier:
    """Real native readback, explicitly synthetic account-free application copy."""
    domain = "DISPOSABLE"

    @contextmanager
    def open(self, reference):
        from scripts.release_selection import validate_spec
        spec = validate_spec(reference, self.domain)
        base = fixture_base(Path(spec["root"]).parents[1])
        if Path(spec["root"]) != base / "releases" / APP or Path(spec["receipt"]) != base / "application-receipt.json":
            raise ValueError("DISPOSABLE_INSTALLED_APPLICATION_PATH")
        raw = safe_read(spec["receipt"], 8 * 1024**2)
        if sha(raw) != spec["receipt_sha256"]:
            raise ValueError("DISPOSABLE_APPLICATION_RECEIPT_PIN")
        receipt = strict(raw)
        if (set(receipt) != {"schema", "domain", "root", "release", "files", "directories"}
                or receipt["schema"] != "QD_DISPOSABLE_INSTALLED_APPLICATION_V1" or receipt["domain"] != "DISPOSABLE"
                or receipt["root"] != spec["root"] or receipt["release"] != APP
                or sha(encoded(receipt["files"])) != spec["artifact_digest"]):
            raise ValueError("DISPOSABLE_APPLICATION_RECEIPT_BINDING")
        started = time.monotonic()
        def bound():
            if time.monotonic() - started >= 180:
                raise ValueError("DISPOSABLE_APPLICATION_DEADLINE")
        inventory(Path(spec["root"]), receipt["files"], [r["path"] for r in receipt["directories"]], bound, expected=receipt)
        yield receipt


class DisposableBundleOwner:
    """Native immutable lease, like the real reader; never financial authority."""
    def __init__(self, reference):
        self.reference = strict(encoded(reference))
        self._reference = encoded(reference)
        with DisposableInstalledReleaseVerifier().open(reference) as receipt:
            self.lease = SupportLease({"deployment": {"destination": reference["root"]}, "inventory": receipt})
        self.handles, self.outputs = self.lease.files, []
        self.files = {r["path"] for r in receipt["files"]}
        self.directories = {r["path"] for r in receipt["directories"]}

    def verify(self, *, release_digest):
        if encoded(self.reference) != self._reference or release_digest != self.reference["artifact_digest"] or not self.handles:
            raise ValueError("DISPOSABLE_APPLICATION_ARTIFACT_CHANGED")
        # Files remain read-only/no-delete handle-bound for the entire session.
        # Rehashing 260 MB at Stop is unnecessary and differs from the real reader.
        from scripts.native_install_candidate import _verify_namespace
        _verify_namespace(Path(self.reference["root"]), self.files, self.directories, lambda: None)

    def close(self):
        self.lease.close()


class SupportLease:
    """Pin deployed files and ancestors against write/delete during the runtime."""
    def __init__(self, receipt):
        from scripts.volume_inspector import windows_output as w
        self.w, self.stack, self.files = w, ExitStack(), []
        try:
            m = receipt["deployment"]; outputs = {}
            for row in receipt["inventory"]["directories"]:
                output = self.stack.enter_context(held(w.WindowsOutput(str(Path(m["destination"]) / row["path"]))))
                if identity(w, output.root_handle) != row["id"]:
                    raise ValueError("SUPPORT_LEASE_DIRECTORY_SUBSTITUTION")
                outputs[row["path"]] = output
            for row in receipt["inventory"]["files"]:
                p = Path(row["path"]); out = outputs[p.parent.as_posix()]
                h = w.relative_open(out.root_handle, p.name, out.sid, False, access=w.READ | w.READ_CONTROL)
                self.files.append(h); w.validate_acl(h, out.sid)
                if identity(w, h) != row["id"] or w.info(h).links != 1:
                    raise ValueError("SUPPORT_LEASE_FILE_SUBSTITUTION")
                raw, _ = read_native(out, p.name, maximum=row["bytes"], expected=row["id"])
                if len(raw) != row["bytes"] or sha(raw) != row["sha256"]:
                    raise ValueError("SUPPORT_LEASE_CONTENT_CHANGED")
        except BaseException:
            self.close(); raise

    def close(self):
        for h in list(self.files):
            if not self.w.close_handle(h):
                raise OSError("SUPPORT_LEASE_CLOSE_UNCONFIRMED")
            self.files.remove(h)
        self.stack.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def main():
    import argparse

    from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--execute-approved-support-deployment", action="store_true", required=True)
    p.add_argument("--action", choices=("install", "select", "rollback-baseline"), default="install")
    p.add_argument("--manifest", required=True); p.add_argument("--manifest-sha256", required=True)
    p.add_argument("--archive"); p.add_argument("--parent-native", type=int, nargs=3)
    p.add_argument("--support-receipt-sha256"); p.add_argument("--operation"); p.add_argument("--expected-head")
    a = p.parse_args()
    raw = safe_read(a.manifest, 65536); m = strict(raw)
    if sha(encoded(m)) != a.manifest_sha256:
        raise ValueError("APPROVED_SUPPORT_DEPLOYMENT_PIN_MISMATCH")
    runtime = "qd-support-deployment-" + a.manifest_sha256 if a.action == "install" else "qd-code-selection-" + str(a.operation)
    clock = LocalWindowsClock(expected_source="time.windows.com,0x9", runtime_id=runtime)
    try:
        if a.action == "install":
            result = install_operational(approved=a.execute_approved_support_deployment, manifest=m, archive=a.archive,
                                         manifest_sha256=a.manifest_sha256, parent_identity=a.parent_native, clock=clock)
        else:
            result = select_release(approved=a.execute_approved_support_deployment, manifest=m,
                                    manifest_sha256=a.manifest_sha256, receipt_sha256=a.support_receipt_sha256,
                                    operation=a.operation, expected_head=a.expected_head,
                                    rollback_baseline=a.action == "rollback-baseline", clock=clock)
        print(encoded(result).decode())
    finally:
        clock.revoke()


def select_release(*, approved=False, manifest=None, manifest_sha256=None, receipt_sha256=None,
                   operation=None, expected_head=None, rollback_baseline=False, clock=None):
    """Reviewed exact invocation of the existing selector, not a second selector."""
    if approved is not True:
        raise ValueError("SEPARATE_EXACT_SELECTION_AUTHORIZATION_REQUIRED")
    from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock
    from scripts.release_selection import (
        NativeInstalledReleaseVerifier,
        ReleaseSelector,
    )
    from scripts.release_selection_store import NativeSelectionStore
    if type(clock) is not LocalWindowsClock:
        raise ValueError("GENUINE_SELECTION_CLOCK_REQUIRED")
    m = validate_manifest(manifest)
    if (m["domain"] != "WINDOWS_LOCAL" or sha(encoded(m)) != pin(manifest_sha256)
            or Path(sys.executable) != Path(m["runtime"]["python"])
            or type(operation) is not str or not re.fullmatch("[0-9a-f]{32}", operation)
            or type(rollback_baseline) is not bool):
        raise ValueError("EXACT_REVIEWED_SELECTION_INVOCATION_REQUIRED")
    r = verify_deployment(m, expected_receipt_sha256=receipt_sha256)
    with SupportLease(r):
        store = NativeSelectionStore(root=m["selection"], native_root=r["selection_id"])
        try:
            selector = ReleaseSelector(store=store, verifier=NativeInstalledReleaseVerifier(), clock=clock)
            reference = {"schema": "QD_INSTALLED_RELEASE_REFERENCE_V1", "domain": "WINDOWS_LOCAL", **m["application"]}
            result = selector.change({"schema": "QD_CODE_SELECTION_AUTHORIZATION_V1", "domain": "WINDOWS_LOCAL",
                "action": "ROLLBACK" if rollback_baseline else "SELECT", "operation": operation, "expected_head": expected_head,
                "target": None if rollback_baseline else reference, "restores": "BASELINE" if rollback_baseline else None}, approved=True)
            # Output only. The installer/control namespace is never expanded by
            # a mutable binding file. Caller retains evidence in its approved log.
            result["desktop_binding"] = None if rollback_baseline else {
                "schema": "QD_NONFINANCIAL_DESKTOP_BINDING_V2", "domain": "WINDOWS_LOCAL", "head": result["head"],
                "native_root": r["selection_id"], "release": APP, "seconds": 120, "requests": 96,
                "support_sha256": m["support_manifest_sha256"], "deployment_sha256": manifest_sha256,
                "support_receipt_sha256": receipt_sha256}
            return result
        finally:
            store.close()


if __name__ == "__main__":
    main()
