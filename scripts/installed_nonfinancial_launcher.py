"""Owned selected-release dashboard only; no providers, journals or trading."""

import argparse
import hashlib
import os
import re
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path
from threading import get_ident


def support_entry(argv):
    """Validate the future installed tool package before any Atlas import."""
    if "--execute-approved-nonfinancial" not in argv:
        raise SystemExit(
            "REFUSED: explicit accepted selection and bounded nonfinancial launch authorization required."
        )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-approved-nonfinancial", action="store_true")
    parser.add_argument("--release", required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--native-root", required=True, nargs=3, type=int)
    parser.add_argument("--support-sha256", required=True)
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument("--requests", type=int, default=96)
    args = parser.parse_args(argv)
    if (
        not re.fullmatch("[0-9a-f]{40}", args.release)
        or any(
            not re.fullmatch("[0-9a-f]{64}", value)
            for value in (args.expected_head, args.support_sha256)
        )
        or any(not 0 <= n <= 0xFFFFFFFF for n in args.native_root)
        or not 1 <= args.seconds <= 120
        or not 1 <= args.requests <= 96
    ):
        raise ValueError("EXACT_BOUNDED_INSTALLED_LAUNCH_ARGUMENTS_REQUIRED")
    support = Path(__file__).absolute().parents[1]
    if support != Path("D:/AtlasRuntime/launchers") / args.support_sha256:
        raise ValueError("INSTALLED_SUPPORT_ROOT_REQUIRED_NO_WORKSPACE_FALLBACK")
    app = Path("D:/AtlasRuntime/releases") / args.release
    if (
        Path(sys.executable) != app / "python/python.exe"
        or Path(sys.base_prefix) != app / "python"
    ):
        raise ValueError("EXACT_SELECTED_D_INTERPRETER_REQUIRED")

    def read(path, limit):
        for node in (path, *path.parents):
            if getattr(node.lstat(), "st_file_attributes", 0) & 0x400:
                raise ValueError("INSTALLED_SUPPORT_REPARSE")
        if path.stat().st_nlink != 1:
            raise ValueError("INSTALLED_SUPPORT_LINK")
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("INSTALLED_SUPPORT_CAPACITY")
        return data

    raw = read(support / "support-manifest.json", 65536)
    if hashlib.sha256(raw).hexdigest() != args.support_sha256:
        raise ValueError("INSTALLED_SUPPORT_MANIFEST_HASH")
    import json

    manifest = json.loads(raw)
    expected = {
        "scripts/release_selection.py",
        "scripts/release_selection_store.py",
        "scripts/installed_nonfinancial_launcher.py",
        "scripts/build_release_candidate.py",
        "scripts/install_verified_release.py",
        "scripts/native_install_candidate.py",
        "scripts/native_install_plan.py",
        "scripts/windows/Atlas-Installed-Nonfinancial.psm1",
    }
    rows = manifest.get("support_sources")
    if (
        manifest.get("schema") != "QD_NONFINANCIAL_LAUNCHER_SUPPORT_V1"
        or manifest.get("application_release") != args.release
        or type(rows) is not list
        or len(rows) != len(expected)
        or {r.get("path") for r in rows} != expected
    ):
        raise ValueError("INSTALLED_SUPPORT_EXACT_INVENTORY_REQUIRED")
    for row in rows:
        data = read(support / row["path"], 262144)
        if (
            len(data) != row["bytes"]
            or hashlib.sha256(data).hexdigest() != row["sha256"]
        ):
            raise ValueError("INSTALLED_SUPPORT_SOURCE_HASH")
    allowed_files = expected | {"support-manifest.json"}
    allowed_dirs = {"."} | {
        p.as_posix() for name in expected for p in Path(name).parents
    }
    found_files = set()
    found_dirs = {"."}
    for parent, dirs, files in os.walk(support, followlinks=False):
        for name in dirs + files:
            path = Path(parent) / name
            if getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
                raise ValueError("INSTALLED_SUPPORT_REPARSE")
            relative = path.relative_to(support).as_posix()
            (found_dirs if name in dirs else found_files).add(relative)
    if found_files != allowed_files or found_dirs != allowed_dirs:
        raise ValueError("INSTALLED_SUPPORT_UNLISTED_NAMESPACE")
    if any(not Path(p).resolve().is_relative_to(app) for p in sys.path if p):
        raise ValueError("INSTALLED_SUPPORT_FOREIGN_IMPORT_PATH")
    sys.path[:0] = [str(support), str(app / "backend"), str(app)]
    return args


if __name__ == "__main__" and "--execute-approved-nonfinancial" not in sys.argv[1:]:
    raise SystemExit(
        "REFUSED: explicit accepted selection and bounded nonfinancial launch authorization required."
    )

_entry_args = support_entry(sys.argv[1:]) if __name__ == "__main__" else None

from scripts.release_selection import ReleaseSelector, encoded, strict

# Executed by the selected installed Python. Application imports resolve only
# there; this reviewed bootstrap is not a workspace application fallback.
CHILD = r"""
import hashlib,json,os,sys,threading,time
from pathlib import Path
line=sys.stdin.buffer.readline(2049)
if len(line)>2048 or not line.endswith(b'\n'):raise ValueError('LAUNCH_INPUT_BOUND')
request=json.loads(line);spec=request['reference'];root=Path(spec['root'])
if (set(request)!={'reference','head','seconds','requests'}
 or set(spec)!={'schema','domain','release','root','receipt','receipt_sha256','artifact_digest'}
 or spec.get('domain')!='WINDOWS_LOCAL' or spec.get('schema')!='QD_INSTALLED_RELEASE_REFERENCE_V1'
 or root!=Path('D:/AtlasRuntime/releases')/spec['release']
 or Path(spec['receipt'])!=Path('D:/Work/Project Atlas/logs/diagnostics')/('qd-unselected-release-'+spec['release']+'.json')
 or Path(sys.executable)!=root/'python/python.exe'
 or Path(sys.base_prefix)!=root/'python' or sys.version_info[:2]!=(3,12)):
 raise ValueError('EXACT_INSTALLED_INTERPRETER_REQUIRED')
if any(not Path(p).resolve().is_relative_to(root) for p in sys.path if p):
 raise ValueError('WORKSPACE_IMPORT_FALLBACK_REFUSED')
if (type(request['seconds']) is not int or not 1<=request['seconds']<=120
 or type(request['requests']) is not int or not 1<=request['requests']<=96):
 raise ValueError('BOUNDED_NONFINANCIAL_LAUNCH_REQUIRED')
sys.path[:0]=[str(root/'backend'),str(root)]
sys.dont_write_bytecode=True
def audit(event,args):
 if event in ('subprocess.Popen','os.system','os.startfile','os.kill','socket.connect','socket.sendto','socket.sendmsg'):
  raise PermissionError('NONFINANCIAL_EXTERNAL_EFFECT_REFUSED:'+event)
 if event in ('socket.getaddrinfo','socket.gethostbyname','socket.gethostbyaddr') and args[0] not in ('127.0.0.1','localhost'):
  raise PermissionError('NONFINANCIAL_EXTERNAL_RESOLVER_REFUSED')
 if event=='socket.bind' and (not isinstance(args[1],tuple) or args[1][0]!='127.0.0.1'):
  raise PermissionError('NONFINANCIAL_LOOPBACK_ONLY')
 if event=='open':
  path,mode,flags=args
  if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (
    isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
   raise PermissionError('NONFINANCIAL_FILESYSTEM_WRITE_REFUSED')
 if event in ('os.mkdir','os.remove','os.rmdir','os.rename','os.link','os.symlink','os.chmod','os.truncate','os.utime'):
  raise PermissionError('NONFINANCIAL_FILESYSTEM_MUTATION_REFUSED')
sys.addaudithook(audit)
from scripts.observation_runtime.personal_release_identity import NativePersonalReleaseIdentity
from scripts.observation_runtime import desktop_observation as app
from scripts.observation_runtime.disposable_host_owner import observe_pid
receipt_path=Path(spec['receipt'])
for component in (receipt_path,*receipt_path.parents):
 if getattr(component.lstat(),'st_file_attributes',0)&0x400:raise ValueError('NONFINANCIAL_RECEIPT_REPARSE')
if receipt_path.stat().st_nlink!=1:raise ValueError('NONFINANCIAL_RECEIPT_LINK')
with receipt_path.open('rb') as stream:receipt_bytes=stream.read(8*1024**2+1)
if len(receipt_bytes)>8*1024**2 or hashlib.sha256(receipt_bytes).hexdigest()!=spec['receipt_sha256']:
 raise ValueError('NONFINANCIAL_RECEIPT_HASH')
receipt=json.loads(receipt_bytes)
if (hashlib.sha256(json.dumps(receipt['files'],sort_keys=True,separators=(',',':')).encode()).hexdigest()!=spec['artifact_digest']
 or receipt['source_commit']!=spec['release'] or receipt['release_path']!=str(root)):
 raise ValueError('NONFINANCIAL_RECEIPT_BINDING')
owner=NativePersonalReleaseIdentity(receipt=receipt,artifact_digest=spec['artifact_digest'])
server=None
try:
 proof=owner.verify(release_digest=spec['artifact_digest'])
 class UnavailableSession:
  def snapshot(self):return app.initial()
  def history(self):return {'sessions':[],'status':'UNAVAILABLE','reason':'NO_RETAINED_JOURNAL_AUTHORITY'}
  def research(self):return {'status':'UNAVAILABLE','reason':'NO_CURRENT_SOURCE_AUTHORITY'}
  def diagnostics(self):return {'status':'UNAVAILABLE','reason':'NONFINANCIAL_NO_PROVIDERS_OR_ACCOUNTS'}
 server,host_id=app.make_host(UnavailableSession(),request_limit=request['requests'],deadline_seconds=request['seconds'])
 base_handler=server.RequestHandlerClass
 class BrowserIsolatedHandler(base_handler):
  def end_headers(self):
   self.send_header('Content-Security-Policy',"connect-src 'self'; form-action 'none'; object-src 'none'; base-uri 'self'")
   super().end_headers()
 server.RequestHandlerClass=BrowserIsolatedHandler
 server.timeout=.1;stop=threading.Event()
 def commands():
  for command in sys.stdin:
   if command.strip()=='STOP '+host_id:
    stop.set();return
  stop.set()
 reader=threading.Thread(target=commands,daemon=True);reader.start()
 identity=observe_pid(os.getpid())
 print(json.dumps(dict(stage='READY',mode='INSTALLED_NONFINANCIAL_ONLY',host_id=host_id,
  release=spec['release'],head=request['head'],image=identity['image'],pid=identity['pid'],
  created=identity['created'],url='http://127.0.0.1:'+str(server.server_port)+'/',
  providers=False,financial_writers=False,trading=False,automatic_startup=False)),flush=True)
 deadline=time.monotonic()+request['seconds']
 while (not stop.is_set() and time.monotonic()<deadline
        and server.counts()['total_attempted']<request['requests']):
  server.handle_request()
 owner.verify(release_digest=spec['artifact_digest'])
finally:
 if server is not None:server.server_close()
 owner.close()
print(json.dumps(dict(stage='CLOSED',financial_actions=0,provider_connections=0,
 handles_after_close=len(owner.handles)+len(owner.outputs),counts=server.counts())),flush=True)
"""


def read_ready(child, *, seconds=180):
    """Bounded Windows pipe peek: no abandoned stdout reader thread."""
    import ctypes as C
    import msvcrt
    from ctypes import wintypes as W

    kernel = C.WinDLL("kernel32", use_last_error=True)
    peek = kernel.PeekNamedPipe
    peek.argtypes = [
        W.HANDLE,
        C.c_void_p,
        W.DWORD,
        C.c_void_p,
        C.POINTER(W.DWORD),
        C.c_void_p,
    ]
    handle = msvcrt.get_osfhandle(child.stdout.fileno())
    deadline, result = time.monotonic() + seconds, bytearray()
    while time.monotonic() < deadline:
        available = W.DWORD()
        if not peek(handle, None, 0, None, C.byref(available), None):
            raise ValueError("INSTALLED_READINESS_PIPE_REFUSED")
        if available.value:
            result.extend(os.read(child.stdout.fileno(), 1))
            if result[-1:] == b"\n":
                return bytes(result)
            if len(result) > 65536:
                raise ValueError("INSTALLED_READINESS_CAPACITY")
        elif child.poll() is not None:
            raise ValueError("INSTALLED_READINESS_EOF")
        else:
            time.sleep(0.01)
    raise ValueError("INSTALLED_READINESS_TIMEOUT")


class InstalledNonfinancialLauncher:
    """Selection lease and retained process ownership last until exact Stop."""

    def __init__(self, *, selector=None):
        from scripts.release_selection import NativeInstalledReleaseVerifier
        from scripts.release_selection_store import NativeSelectionStore

        if (
            type(selector) is not ReleaseSelector
            or selector.domain != "WINDOWS_LOCAL"
            or type(selector.store) is not NativeSelectionStore
            or type(selector.verifier) is not NativeInstalledReleaseVerifier
        ):
            raise ValueError("ACCEPTED_NATIVE_SELECTION_REQUIRED")
        self.selector = selector
        self._selector = selector
        self.child = self.lease = self.ready = None
        self._owned_child = self._owned_handle = self._owned_created = None
        self.owner_thread = None
        self._stop_started = self._last_outcome = None
        self._terminal_error = None

    def open(
        self,
        *,
        expected_head=None,
        expected_release=None,
        approved=False,
        seconds=120,
        requests=96,
    ):
        if approved is not True:
            raise ValueError("EXPLICIT_NONFINANCIAL_LAUNCH_AUTHORIZATION_REQUIRED")
        if (
            self.selector is not self._selector
            or self._terminal_error is not None
            or self.child is not None
            or type(seconds) is not int
            or not 1 <= seconds <= 120
            or type(requests) is not int
            or not 1 <= requests <= 96
        ):
            raise ValueError("BOUNDED_FRESH_NONFINANCIAL_LAUNCH_REQUIRED")
        from scripts.observation_runtime.disposable_host_owner import (
            observe_handle,
            observe_pid,
        )

        self.lease = self.selector.lease(
            expected_head=expected_head,
            **(
                {"expected_release": expected_release}
                if expected_release is not None
                else {}
            ),
        )
        self.owner_thread = get_ident()
        self._stop_started = self._last_outcome = None
        self._request_limit = requests
        try:
            record, _receipt = self.lease.__enter__()
            reference = record["selected"]
            if (
                expected_release is not None
                and reference["release"] != expected_release
            ):
                raise ValueError("EXACT_SELECTED_RELEASE_REQUIRED")
            executable = Path(reference["root"]) / "python/python.exe"
            if not executable.is_file():
                raise ValueError("INSTALLED_PYTHON_REQUIRED_NO_FALLBACK")
            self.selector.clock.require_operational(
                "qd-installed-nonfinancial-" + expected_head
            )
            env = {
                k: v
                for k, v in os.environ.items()
                if k not in ("PYTHONPATH", "PYTHONHOME")
            }
            env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
            self.child = subprocess.Popen(
                [str(executable), "-I", "-B", "-c", CHILD],
                cwd=reference["root"],
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._owned_child = self.child
            self._owned_handle = int(self.child._handle)
            self._owned_created = observe_handle(self._owned_handle)
            identity = observe_pid(self.child.pid)
            if (
                identity["created"] != observe_handle(int(self.child._handle))
                or identity["image"] != str(executable).casefold()
            ):
                raise ValueError("INSTALLED_CHILD_OWNERSHIP_REFUSED")
            request = (
                encoded(
                    {
                        "reference": reference,
                        "head": expected_head,
                        "seconds": seconds,
                        "requests": requests,
                    }
                )
                + b"\n"
            )
            if len(request) > 2048:
                raise ValueError("INSTALLED_LAUNCH_REQUEST_CAPACITY")
            self.child.stdin.write(request)
            self.child.stdin.flush()
            self.identity = identity
            raw = read_ready(self.child)
            ready = strict(raw)
            if (
                len(raw) > 65536
                or ready.get("stage") != "READY"
                or ready.get("mode") != "INSTALLED_NONFINANCIAL_ONLY"
                or ready.get("release") != reference["release"]
                or ready.get("head") != expected_head
                or ready.get("pid") != identity["pid"]
                or ready.get("created") != identity["created"]
                or ready.get("image", "").casefold() != identity["image"]
                or type(ready.get("host_id")) is not str
                or not re.fullmatch("[0-9a-f]{32}", ready["host_id"])
                or any(
                    ready.get(k) is not False
                    for k in (
                        "providers",
                        "financial_writers",
                        "trading",
                        "automatic_startup",
                    )
                )
            ):
                raise ValueError("INSTALLED_READINESS_IDENTITY_REFUSED")
            from urllib.parse import urlsplit

            url = urlsplit(ready.get("url", ""))
            if (
                url.scheme != "http"
                or url.hostname != "127.0.0.1"
                or not url.port
                or url.path != "/"
                or url.query
                or url.fragment
                or url.username
            ):
                raise ValueError("INSTALLED_READINESS_LOOPBACK_REFUSED")
            # No browser is opened by this adapter. The caller may open only
            # after independent loopback health matches this exact readiness.
            from http.client import HTTPConnection

            with closing(
                HTTPConnection("127.0.0.1", url.port, timeout=3)
            ) as connection:
                connection.request("GET", "/health")
                response = connection.getresponse()
                health = strict(response.read(65537))
            if (
                response.status != 200
                or health.get("host_id") != ready.get("host_id")
                or health.get("pid") != identity["pid"]
                or health.get("financial_writers") is not False
                or health.get("mode") != "OBSERVATION_ONLY"
                or health.get("production") != "NO-GO"
            ):
                raise ValueError("INSTALLED_HTTP_READINESS_REFUSED")
            self.ready = ready
            return dict(ready)
        except BaseException as original:
            try:
                self.close()
            except BaseException as cleanup:  # noqa: BLE001 - Preserve both original and cleanup failures.
                raise BaseExceptionGroup(
                    "LAUNCH_REFUSED_CLEANUP_EVIDENCE_RETAINED", [original, cleanup]
                ) from None
            raise

    def close(self):
        if self._terminal_error is not None:
            raise ValueError(self._terminal_error)
        if self._last_outcome is not None:
            if not self._last_outcome["within_stop_budget"]:
                raise ValueError("OWNED_NONFINANCIAL_STOP_TIMING_REFUSED")
            return dict(self._last_outcome)
        if self.lease is not None and self.owner_thread != get_ident():
            raise ValueError("INSTALLED_LAUNCHER_OWNER_THREAD_REQUIRED")
        if self._stop_started is None:
            self._stop_started = time.monotonic()
        start = self._stop_started
        error = None
        if self.child is not None:
            child = self.child
            from scripts.observation_runtime.disposable_host_owner import observe_handle

            if (
                child is not self._owned_child
                or int(child._handle) != self._owned_handle
                or self._owned_created is not None
                and observe_handle(int(child._handle)) != self._owned_created
            ):
                raise ValueError("OWNED_NONFINANCIAL_PROCESS_SUBSTITUTION")
            # Only the directly retained creation handle and owned stdin are used.
            if child.poll() is None and child.stdin is not None:
                try:
                    if self.ready is not None:
                        child.stdin.write(
                            ("STOP " + self.ready["host_id"] + "\n").encode()
                        )
                        child.stdin.flush()
                except BrokenPipeError:
                    pass
                finally:
                    child.stdin.close()
                    child.stdin = None
            try:
                stdout, stderr = child.communicate(
                    timeout=max(0.1, 8 - (time.monotonic() - start))
                )
            except subprocess.TimeoutExpired:
                raise ValueError(
                    "OWNED_NONFINANCIAL_STOP_INCOMPLETE_RETAINED"
                ) from None
            try:
                if child.returncode or stderr or not stdout:
                    raise ValueError("OWNED_NONFINANCIAL_EXIT_UNVERIFIED")
                outcome = strict(stdout.splitlines()[-1])
                required = {
                    "stage": "CLOSED",
                    "financial_actions": 0,
                    "provider_connections": 0,
                    "handles_after_close": 0,
                }
                counts = outcome.get("counts")
                if (
                    set(outcome) != {*required, "counts"}
                    or any(outcome[k] != v for k, v in required.items())
                    or any(
                        type(outcome[k]) is not int
                        for k in (
                            "financial_actions",
                            "provider_connections",
                            "handles_after_close",
                        )
                    )
                    or type(counts) is not dict
                    or set(counts)
                    != {"total_attempted", "admitted", "rejected", "pending"}
                    or any(type(v) is not int or v < 0 for v in counts.values())
                    or counts["pending"] != 0
                    or counts["total_attempted"]
                    != counts["admitted"] + counts["rejected"]
                    or counts["total_attempted"] > self._request_limit
                ):
                    raise ValueError("OWNED_NONFINANCIAL_DRAIN_UNVERIFIED")
            except (ValueError, TypeError) as failure:
                error = failure
            finally:
                for stream in (child.stdin, child.stdout, child.stderr):
                    if stream is not None:
                        stream.close()
                child._handle.Close()
                self.child = None
                self._owned_child = self._owned_handle = self._owned_created = None
        if self.lease is not None:
            self.lease.__exit__(None, None, None)
            self.lease = None
        self.ready = None
        self.owner_thread = None
        if error is not None:
            self._terminal_error = str(error)
            raise error
        elapsed = time.monotonic() - start
        self._last_outcome = {
            "closed": True,
            "seconds": elapsed,
            "within_stop_budget": elapsed <= 8,
            "financial_actions": 0,
        }
        if elapsed > 8:
            raise ValueError("OWNED_NONFINANCIAL_STOP_TIMING_REFUSED")
        return dict(self._last_outcome)


def run_installed_entry(args, *, approved=False):
    """Owned stdin only; no browser, shortcut edit, service or financial controls."""
    if approved is not True:
        raise ValueError("EXPLICIT_NONFINANCIAL_ENTRY_AUTHORIZATION_REQUIRED")
    support = Path(__file__).absolute().parents[1]
    app = Path("D:/AtlasRuntime/releases") / args.release
    if (
        support != Path("D:/AtlasRuntime/launchers") / args.support_sha256
        or Path(sys.executable) != app / "python/python.exe"
        or Path(sys.base_prefix) != app / "python"
    ):
        raise ValueError("INSTALLED_ENTRY_REQUIRED_NO_WORKSPACE_FALLBACK")
    from types import SimpleNamespace

    from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock
    from scripts.release_selection import NativeInstalledReleaseVerifier
    from scripts.release_selection_store import NativeSelectionStore

    clock = LocalWindowsClock(
        expected_source="time.windows.com,0x9",
        runtime_id="qd-installed-nonfinancial-" + args.expected_head,
    )
    store = owner = None
    try:
        store = NativeSelectionStore(
            root="D:\\AtlasRuntime\\selection", native_root=args.native_root
        )
        selector = ReleaseSelector(
            store=store, verifier=NativeInstalledReleaseVerifier(), clock=clock
        )
        owner = InstalledNonfinancialLauncher(selector=selector)
        ready = owner.open(
            expected_head=args.expected_head,
            expected_release=args.release,
            approved=True,
            seconds=args.seconds,
            requests=args.requests,
        )
        from scripts.observation_runtime.disposable_host_owner import observe_pid

        controller = observe_pid(os.getpid())
        print(
            encoded(
                {
                    "schema": "QD_INSTALLED_NONFINANCIAL_CONTROLLER_V1",
                    "controller": controller,
                    "dashboard": ready,
                }
            ).decode(),
            flush=True,
        )
        deadline = time.monotonic() + args.seconds
        for _ in range(8):
            remaining = deadline - time.monotonic()
            if remaining <= 0 or owner.child.poll() is not None:
                break
            try:
                line = read_ready(
                    SimpleNamespace(stdout=sys.stdin.buffer, poll=lambda: None),
                    seconds=remaining,
                )
            except ValueError as error:
                if str(error) not in (
                    "INSTALLED_READINESS_TIMEOUT",
                    "INSTALLED_READINESS_PIPE_REFUSED",
                ):
                    raise
                break  # Owned EOF/deadline is a graceful close, never restart.
            if line.strip() == ("STOP " + ready["host_id"]).encode():
                break
            print(
                encoded(
                    {"stage": "REFUSED", "reason": "OWNER_OR_COMMAND_MISMATCH"}
                ).decode(),
                flush=True,
            )
        print(encoded(owner.close()).decode(), flush=True)
    finally:
        clock.revoke()
        try:
            if owner is not None and owner.child is not None:
                finish_owned_entry(owner)
        finally:
            if store is not None and store.owner is None:
                store.close()


def finish_owned_entry(owner):
    """Never abandon the retained child after an eight-second Stop refusal.

    Normal completion remains bounded by the child's accepted session deadline.
    A genuinely stuck OS child keeps this supervisor/selection lease alive and
    visibly unresolved; it is not reported closed or killed as a fallback.
    """
    try:
        return owner.close()
    except ValueError as original:
        child = owner.child
        if child is None:
            raise
        if child is not owner._owned_child or int(child._handle) != owner._owned_handle:
            raise ValueError("ENTRY_PROCESS_OWNERSHIP_UNRESOLVED") from original
        print(
            encoded(
                {"stage": "STOP_INCOMPLETE_RETAINED", "reason": str(original)}
            ).decode(),
            flush=True,
        )
        while child.poll() is None:
            try:
                child.wait(timeout=1)
            except subprocess.TimeoutExpired:
                continue  # Keep ownership; no process-name/PID termination.
        # Late cleanup must preserve the first Stop's failed timing/ACK status.
        try:
            owner.close()
        except ValueError as late:
            raise BaseExceptionGroup(
                "ENTRY_STOP_NOT_ACCEPTED_RESOURCES_RECONCILED", [original, late]
            ) from None
        raise


if __name__ == "__main__":
    run_installed_entry(_entry_args, approved=_entry_args.execute_approved_nonfinancial)
