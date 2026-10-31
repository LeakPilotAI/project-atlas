import copy
import io
import json
import socket
import subprocess
import threading
from contextlib import closing, contextmanager
from http.client import HTTPConnection
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import installed_nonfinancial_launcher as launcher
from scripts.release_selection import (
    NativeInstalledReleaseVerifier,
    ReleaseSelector,
    encoded,
)
from scripts.release_selection_store import NativeSelectionStore


class Handle:
    def __init__(self):
        self.closed = False

    def __int__(self):
        return 99

    def Close(self):
        self.closed = True


class Child:
    pid = 1234

    def __init__(self):
        self.stdin, self.stdout, self.stderr = io.BytesIO(), io.BytesIO(), io.BytesIO()
        self._handle = Handle()
        self.returncode = None
        self.timeout = False
        self.stderr_bytes = b""
        self.outcome = {
            "stage": "CLOSED",
            "financial_actions": 0,
            "provider_connections": 0,
            "handles_after_close": 0,
            "counts": {
                "total_attempted": 1,
                "admitted": 1,
                "rejected": 0,
                "pending": 0,
            },
        }

    def poll(self):
        return self.returncode

    def communicate(self, *, timeout):
        assert 0 < timeout <= 8
        if self.timeout:
            raise subprocess.TimeoutExpired("SYNTHETIC_OWNED_PROCESS", timeout)
        self.returncode = 0
        return encoded(self.outcome) + b"\n", self.stderr_bytes

    def kill(self):
        pytest.fail("No process termination authorized by launcher")

    def wait(self, timeout):
        self.timeout = False
        self.returncode = 0
        return 0


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root = tmp_path / "installed"
    (root / "python").mkdir(parents=True)
    (root / "python/python.exe").write_bytes(b"DISPOSABLE_NOT_EXECUTABLE")
    reference = {"root": str(root), "release": "a" * 40}
    selected = ReleaseSelector.__new__(ReleaseSelector)
    selected.domain = "WINDOWS_LOCAL"
    selected.store = NativeSelectionStore.__new__(NativeSelectionStore)
    selected.verifier = NativeInstalledReleaseVerifier()
    selected.clock = SimpleNamespace(require_operational=lambda runtime: runtime)
    lease_events = []

    @contextmanager
    def lease(*, expected_head):
        assert expected_head == "b" * 64
        lease_events.append("open")
        try:
            yield {"selected": copy.deepcopy(reference)}, {}
        finally:
            lease_events.append("close")

    selected.lease = lease
    owner = launcher.InstalledNonfinancialLauncher(selector=selected)
    child = Child()
    starts = []

    def popen(args, **kwargs):
        starts.append((args, kwargs))
        assert args[:3] == [str(root / "python/python.exe"), "-I", "-B"]
        assert kwargs["cwd"] == str(root)
        assert not {"PYTHONPATH", "PYTHONHOME"} & kwargs["env"].keys()
        return child

    monkeypatch.setattr(launcher.subprocess, "Popen", popen)
    monkeypatch.setattr(launcher.subprocess, "CREATE_NO_WINDOW", 0, raising=False)
    from scripts.observation_runtime import disposable_host_owner as identity

    monkeypatch.setattr(
        identity,
        "observe_pid",
        lambda pid: {
            "pid": pid,
            "created": 123,
            "image": str(root / "python/python.exe").casefold(),
        },
    )
    monkeypatch.setattr(identity, "observe_handle", lambda handle: 123)
    ready = {
        "stage": "READY",
        "mode": "INSTALLED_NONFINANCIAL_ONLY",
        "release": "a" * 40,
        "head": "b" * 64,
        "pid": 1234,
        "created": 123,
        "image": str(root / "python/python.exe"),
        "host_id": "d" * 32,
        "url": "http://127.0.0.1:12345/",
        "providers": False,
        "financial_writers": False,
        "trading": False,
        "automatic_startup": False,
    }
    monkeypatch.setattr(launcher, "read_ready", lambda p: encoded(ready) + b"\n")

    class Connection:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def close(self):
            pass

        def request(self, method, path):
            assert (method, path) == ("GET", "/health")

        def getresponse(self):
            return SimpleNamespace(
                status=200,
                read=lambda limit: encoded(
                    {
                        "host_id": "d" * 32,
                        "pid": 1234,
                        "financial_writers": False,
                        "mode": "OBSERVATION_ONLY",
                        "production": "NO-GO",
                    }
                ),
            )

    monkeypatch.setattr("http.client.HTTPConnection", Connection)
    return SimpleNamespace(
        owner=owner,
        child=child,
        root=root,
        starts=starts,
        events=lease_events,
        ready=ready,
    )


def test_valid_owned_start_stop_repeat_restart_and_lease_release(setup):
    s = setup
    assert s.owner.open(expected_head="b" * 64, approved=True)["providers"] is False
    assert len(s.starts) == 1 and s.events == ["open"]
    assert s.owner.close()["closed"]
    assert s.events == ["open", "close"] and s.child._handle.closed
    assert s.owner.close()["closed"]  # Idempotent; never launches or replays.


@pytest.mark.parametrize("value", [False, None, 1, "true"])
def test_launch_default_refuses_before_selected_release_access(setup, value):
    with pytest.raises(ValueError, match="AUTHORIZATION"):
        setup.owner.open(approved=value)
    assert not setup.starts and not setup.events


@pytest.mark.parametrize(
    "seconds,requests", [(0, 96), (121, 96), (True, 96), (30, 0), (30, 97), (30, True)]
)
def test_unbounded_launch_refuses_before_effect(setup, seconds, requests):
    with pytest.raises(ValueError):
        setup.owner.open(
            expected_head="b" * 64, approved=True, seconds=seconds, requests=requests
        )
    assert not setup.starts


def test_missing_runtime_never_falls_back_to_workspace_or_host_python(setup):
    (setup.root / "python/python.exe").unlink()
    with pytest.raises(ValueError, match="NO_FALLBACK"):
        setup.owner.open(expected_head="b" * 64, approved=True)
    assert not setup.starts and setup.events == ["open", "close"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("providers", True),
        ("financial_writers", True),
        ("trading", True),
        ("automatic_startup", True),
        ("release", "c" * 40),
        ("head", "c" * 64),
        ("pid", 42),
        ("created", 42),
        ("image", "FOREIGN"),
        ("url", "http://0.0.0.0:12345/"),
        ("url", "https://127.0.0.1:12345/"),
    ],
)
def test_incorrect_owner_release_or_unsafe_readiness_refuses_and_closes(
    setup, field, value
):
    setup.ready[field] = value
    with pytest.raises(ValueError):
        setup.owner.open(expected_head="b" * 64, approved=True)
    assert setup.events == ["open", "close"] and setup.child._handle.closed


def test_incomplete_stop_retains_exact_process_and_selection_lease(setup):
    setup.owner.open(expected_head="b" * 64, approved=True)
    setup.child.timeout = True
    with pytest.raises(ValueError, match="INCOMPLETE_RETAINED"):
        setup.owner.close()
    assert setup.owner.child is setup.child and setup.events == ["open"]
    assert not setup.child._handle.closed
    setup.child.timeout = False
    assert setup.owner.close()["closed"] and setup.events == ["open", "close"]


@pytest.mark.parametrize(
    "outcome",
    [
        {
            "stage": "CLOSED",
            "financial_actions": 1,
            "provider_connections": 0,
            "handles_after_close": 0,
        },
        {
            "stage": "CLOSED",
            "financial_actions": 0,
            "provider_connections": 1,
            "handles_after_close": 0,
        },
        {
            "stage": "CLOSED",
            "financial_actions": 0,
            "provider_connections": 0,
            "handles_after_close": 1,
        },
        {
            "stage": "UNKNOWN",
            "financial_actions": 0,
            "provider_connections": 0,
            "handles_after_close": 0,
        },
    ],
)
def test_bad_shutdown_ack_not_reported_clean_but_exited_resources_release(
    setup, outcome
):
    setup.owner.open(expected_head="b" * 64, approved=True)
    setup.child.outcome = outcome
    with pytest.raises(ValueError, match="DRAIN_UNVERIFIED"):
        setup.owner.close()
    assert setup.child._handle.closed and setup.events == ["open", "close"]
    with pytest.raises(ValueError, match="DRAIN_UNVERIFIED"):
        setup.owner.close()


def test_wrong_thread_stop_cannot_release_another_thread_selection(setup):
    setup.owner.open(expected_head="b" * 64, approved=True)
    errors = []

    def wrong():
        try:
            setup.owner.close()
        except ValueError as e:
            errors.append(str(e))

    t = threading.Thread(target=wrong)
    t.start()
    t.join(1)
    assert (
        errors == ["INSTALLED_LAUNCHER_OWNER_THREAD_REQUIRED"]
        and not setup.child._handle.closed
    )
    setup.owner.close()


def test_fixture_ports_never_construct_operational_launcher():
    with pytest.raises(ValueError):
        launcher.InstalledNonfinancialLauncher()
    with pytest.raises(ValueError):
        launcher.InstalledNonfinancialLauncher(
            selector=SimpleNamespace(domain="DISPOSABLE")
        )
    with pytest.raises(ValueError, match="ENTRY_AUTHORIZATION"):
        launcher.run_installed_entry(None)


def test_child_policy_is_valid_code_and_rejects_foreign_interpreter_without_side_effects(
    tmp_path,
):
    request = {"reference": {"root": str(tmp_path), "release": "a" * 40}}
    out = subprocess.run(
        [__import__("sys").executable, "-I", "-B", "-c", launcher.CHILD],
        input=encoded(request) + b"\n",
        capture_output=True,
        timeout=8,
        check=False,
    )
    assert out.returncode != 0 and b"EXACT_INSTALLED_INTERPRETER_REQUIRED" in out.stderr
    assert not list(tmp_path.iterdir())


def test_genuine_disposable_http_original_ui_unavailable_financial_state_and_cleanup():
    """Actual loopback source fixture, NOT installed operational acceptance."""
    from scripts.observation_runtime import desktop_observation as app

    class Unavailable:
        def snapshot(self):
            return app.initial()

        def history(self):
            return {"status": "UNAVAILABLE", "sessions": []}

        def research(self):
            return {"status": "UNAVAILABLE"}

        def diagnostics(self):
            return {"status": "UNAVAILABLE"}

    server, _identity = app.make_host(
        Unavailable(), request_limit=12, deadline_seconds=10
    )
    import ast

    handler = next(
        n
        for n in ast.parse(launcher.CHILD).body
        if isinstance(n, ast.Try)
        for n in n.body
        if isinstance(n, ast.ClassDef) and n.name == "BrowserIsolatedHandler"
    )
    namespace = {"base_handler": server.RequestHandlerClass}
    exec(  # noqa: S102 - Compile only the reviewed, constant bootstrap class for this fixture.
        compile(
            ast.Module(body=[handler], type_ignores=[]),
            "<bootstrap-browser-isolation>",
            "exec",
        ),
        namespace,
    )
    server.RequestHandlerClass = namespace["BrowserIsolatedHandler"]
    port = server.server_port
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    try:
        for page in (
            "/dashboard",
            "/dashboard/perps",
            "/quality_dips.html",
            "/dashboard/investment",
            "/dashboard/archive",
            "/dashboard/command-center",
        ):
            with closing(HTTPConnection("127.0.0.1", port, timeout=2)) as connection:
                connection.request("GET", page)
                response = connection.getresponse()
                assert "connect-src 'self'" in response.getheader(
                    "Content-Security-Policy"
                )
                assert response.status == 200 and b"<html" in response.read().lower()
        with closing(HTTPConnection("127.0.0.1", port, timeout=2)) as connection:
            connection.request("GET", "/api/investments/quality-dips/selected-paper")
            response = connection.getresponse()
            payload = json.loads(response.read())
            assert payload["cash"] is None and payload["positions"] is None
            assert payload["startup_authorized"] is False
        with closing(HTTPConnection("127.0.0.1", port, timeout=2)) as connection:
            connection.request("POST", "/anything")
            response = connection.getresponse()
            assert response.status == 403
            response.read()
    finally:
        server.shutdown()
        worker.join(3)
        assert not worker.is_alive()
    assert server.counts() == {
        "total_attempted": 8,
        "admitted": 7,
        "rejected": 1,
        "pending": 0,
    }
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", port)) != 0


def test_stop_cannot_use_substituted_process_object(setup):
    setup.owner.open(expected_head="b" * 64, approved=True)
    original = setup.owner.child
    setup.owner.child = Child()
    with pytest.raises(ValueError, match="PROCESS_SUBSTITUTION"):
        setup.owner.close()
    assert not original._handle.closed
    setup.owner.child = original
    setup.owner.close()


@pytest.mark.parametrize(
    "counts",
    [
        {"total_attempted": 97, "admitted": 97, "rejected": 0, "pending": 0},
        {"total_attempted": 2, "admitted": 1, "rejected": 0, "pending": 0},
        {"total_attempted": 1, "admitted": 1, "rejected": 0, "pending": 1},
        {"total_attempted": True, "admitted": 1, "rejected": 0, "pending": 0},
    ],
)
def test_request_budget_and_pending_ack_are_verified_at_stop(setup, counts):
    setup.owner.open(expected_head="b" * 64, approved=True)
    setup.child.outcome["counts"] = counts
    with pytest.raises(ValueError, match="DRAIN_UNVERIFIED"):
        setup.owner.close()


def test_stop_budget_cannot_be_reset_by_repeated_stop(setup):
    setup.owner.open(expected_head="b" * 64, approved=True)
    setup.owner._stop_started = launcher.time.monotonic() - 9
    with pytest.raises(ValueError, match="STOP_TIMING_REFUSED"):
        setup.owner.close()
    assert setup.child._handle.closed and setup.events == ["open", "close"]
    with pytest.raises(ValueError, match="STOP_TIMING_REFUSED"):
        setup.owner.close()


@pytest.mark.parametrize(
    "action",
    [
        "from pathlib import Path;Path('forbidden').write_text('NO')",
        "from pathlib import Path;Path('forbidden').mkdir()",
        "import socket;socket.getaddrinfo('example.invalid',443)",
        "import socket;s=socket.socket();s.connect(('203.0.113.1',443))",
        "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.sendto(b'x',('203.0.113.1',123))",
        "import socket;s=socket.socket();s.bind(('0.0.0.0',0))",
        "import subprocess;subprocess.Popen(['never-run'])",
        "import os;os.kill(os.getpid(),0)",
    ],
)
def test_actual_child_audit_blocks_external_effects_before_execution(tmp_path, action):
    import ast
    import sys

    tree = ast.parse(launcher.CHILD)
    audit = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "audit"
    )
    code = ast.unparse(audit)
    script = "import sys,os\n" + code + "\nsys.addaudithook(audit)\n"
    script += (
        "try:\n "
        + action
        + "\nexcept PermissionError:\n print('REFUSED_BEFORE_EFFECT')\nelse:\n raise AssertionError('Effect allowed')\n"
    )
    out = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script],
        cwd=tmp_path,
        capture_output=True,
        timeout=8,
        check=False,
    )
    assert out.returncode == 0, out.stderr.decode(errors="replace")
    assert out.stdout.strip() == b"REFUSED_BEFORE_EFFECT"
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("mode", ["ready", "timeout", "eof"])
def test_genuine_owned_disposable_pipe_readiness_and_cleanup(mode):
    import sys

    code = (
        "import sys;print('READY',flush=True);sys.stdin.readline()"
        if mode == "ready"
        else "import sys;sys.stdin.readline()"
        if mode == "timeout"
        else "pass"
    )
    with subprocess.Popen(
        [sys.executable, "-I", "-B", "-c", code],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as child:
        try:
            if mode == "ready":
                assert launcher.read_ready(child, seconds=3) == b"READY\r\n"
            else:
                with pytest.raises(ValueError, match="READINESS"):
                    launcher.read_ready(child, seconds=0.1 if mode == "timeout" else 3)
        finally:
            child.stdin.close()
            child.stdin = None
            _out, _err = child.communicate(timeout=3)
            assert child.returncode == 0
    child._handle.Close()


def test_entry_retains_and_drains_original_child_after_failed_stop(setup):
    setup.owner.open(expected_head="b" * 64, approved=True)
    setup.child.timeout = True
    with pytest.raises(ValueError, match="INCOMPLETE_RETAINED"):
        launcher.finish_owned_entry(setup.owner)
    assert setup.child._handle.closed and setup.events == ["open", "close"]


@pytest.mark.parametrize(
    "fault", [None, "missing_sdk", "hash", "extra", "foreign_python"]
)
def test_installed_support_package_admission_has_no_workspace_fallback(
    tmp_path, monkeypatch, fault
):
    import hashlib
    import sys

    names = [
        "scripts/release_selection.py",
        "scripts/release_selection_store.py",
        "scripts/installed_nonfinancial_launcher.py",
        "scripts/build_release_candidate.py",
        "scripts/install_verified_release.py",
        "scripts/native_install_candidate.py",
        "scripts/native_install_plan.py",
        "scripts/windows/Atlas-Installed-Nonfinancial.psm1",
    ]
    rows = []
    for name in names:
        raw = ("DISPOSABLE_SUPPORT_" + name).encode()
        rows.append(
            {"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        )
    raw = encoded(
        {
            "schema": "QD_NONFINANCIAL_LAUNCHER_SUPPORT_V1",
            "application_release": "a" * 40,
            "support_sources": rows,
        }
    )
    pin = hashlib.sha256(raw).hexdigest()
    tools = tmp_path / "tools"
    tools.mkdir()
    tool = tools / pin
    tool.mkdir()
    for name in names:
        path = tool / name
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_bytes(("DISPOSABLE_SUPPORT_" + name).encode())
    (tool / "support-manifest.json").write_bytes(raw)
    app = tmp_path / "releases" / ("a" * 40)
    app.mkdir(parents=True)
    real = Path

    def mapping(value):
        if str(value) == "D:/AtlasRuntime/launchers":
            return tools
        if str(value) == "D:/AtlasRuntime/releases":
            return tmp_path / "releases"
        return real(value)

    monkeypatch.setattr(launcher, "Path", mapping)
    monkeypatch.setattr(
        launcher, "__file__", str(tool / "scripts/installed_nonfinancial_launcher.py")
    )
    monkeypatch.setattr(sys, "executable", str(app / "python/python.exe"))
    monkeypatch.setattr(sys, "base_prefix", str(app / "python"))
    monkeypatch.setattr(sys, "path", [str(app / "python/Lib")])
    if fault == "missing_sdk":
        (tool / "scripts/native_install_plan.py").unlink()
    elif fault == "hash":
        (tool / "scripts/native_install_plan.py").write_bytes(b"WRONG")
    elif fault == "extra":
        (tool / "unreviewed.py").write_bytes(b"NO")
    elif fault == "foreign_python":
        monkeypatch.setattr(sys, "executable", str(tmp_path / "workspace-python"))
    args = [
        "--execute-approved-nonfinancial",
        "--release",
        "a" * 40,
        "--expected-head",
        "b" * 64,
        "--native-root",
        "1",
        "2",
        "3",
        "--support-sha256",
        pin,
    ]
    if fault is None:
        accepted = launcher.support_entry(args)
        assert accepted.release == "a" * 40 and accepted.native_root == [1, 2, 3]
    else:
        with pytest.raises((ValueError, OSError)):
            launcher.support_entry(args)


@pytest.mark.parametrize("mode", ["default", "fixture_domain", "workspace"])
def test_actual_windows_control_adapter_refuses_unaccepted_or_workspace_start(
    tmp_path, mode
):
    import os

    repo = Path(__file__).resolve().parents[1]
    module = repo / "scripts/windows/Atlas-Installed-Nonfinancial.psm1"
    script = r"""
$ErrorActionPreference='Stop'
Import-Module $env:ATLAS_SOURCE_CONTROL_MODULE -Force
$binding=[pscustomobject]@{schema='QD_NONFINANCIAL_DESKTOP_BINDING_V1';domain='WINDOWS_LOCAL';
 release=('a'*40);head=('b'*64);support_sha256=('c'*64);native_root=@(1,2,3);seconds=30;requests=12}
if($env:ATLAS_TEST_MODE -eq 'fixture_domain'){$binding.domain='DISPOSABLE'}
try {
 if($env:ATLAS_TEST_MODE -eq 'default'){Open-AtlasInstalledNonfinancialDashboard -Binding $binding}
 else {Open-AtlasInstalledNonfinancialDashboard -Binding $binding -Approved}
 throw 'UNEXPECTED_START'
} catch {
 $expected=switch($env:ATLAS_TEST_MODE) {
  'default' {'EXPLICIT_NONFINANCIAL_DESKTOP_AUTHORIZATION_REQUIRED'}
  'fixture_domain' {'EXACT_NONFINANCIAL_DESKTOP_BINDING_REQUIRED'}
  'workspace' {'INSTALLED_DESKTOP_ADAPTER_REQUIRED_NO_WORKSPACE_FALLBACK'}
 }
 if($_.Exception.Message -cne $expected){throw}
}
$closed=Close-AtlasInstalledNonfinancialDashboard
if(-not $closed.closed -or $closed.status -cne 'NO_OWNED_NONFINANCIAL_RUNTIME'){throw 'OWNER_UNEXPECTED'}
Write-Output 'REFUSED_WITHOUT_STARTUP'
"""
    env = dict(
        os.environ,
        ATLAS_SOURCE_CONTROL_MODULE=str(module),
        ATLAS_TEST_MODE=mode,
        PSModulePath=r"C:\Windows\System32\WindowsPowerShell\v1.0\Modules",
        PSModuleAnalysisCachePath=str(tmp_path / "module-cache"),
    )
    out = subprocess.run(
        [
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ],
        env=env,
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert out.returncode == 0, out.stderr.decode(errors="replace")
    assert b"REFUSED_WITHOUT_STARTUP" in out.stdout
