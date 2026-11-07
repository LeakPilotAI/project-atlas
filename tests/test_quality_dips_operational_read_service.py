"""Source composition exercised only with disposable native financial evidence."""
import copy
import importlib.util
import json
import os
import socket
import subprocess
from contextlib import closing, contextmanager
from http.client import HTTPConnection
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from test_quality_dips_read_capability_native import capture

pytest_plugins = ["test_quality_dips_read_capability_native"]
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("qd_operational_read_test", ROOT / "scripts/observation_runtime/quality_dips_read_service.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class FixtureReadServiceAcceptance:
    """Fixed independently captured harness expectations, NOT real approval."""
    def __init__(self, n, process):
        self.account, self.epoch = n.enrollment["account_id"], n.enrollment["epoch"]
        self.enrollment_digest, self.process = m.digest(n.enrollment), copy.deepcopy(process)
        self.available = True

    @contextmanager
    def lease(self, context, now):
        assert context["mode"] == m.MODE
        assert context["account_id"] == self.account and context["epoch"] == self.epoch
        assert context["enrollment_digest"] == self.enrollment_digest and context["process"] == self.process
        yield SimpleNamespace(check=lambda c, t: self.available and c == context)


@pytest.fixture
def composition(native):
    n = native
    process = m.observe_self()
    acceptance = FixtureReadServiceAcceptance(n, process)
    args = {"account_id": n.enrollment["account_id"], "epoch": n.enrollment["epoch"], "enrollment": n.enrollment,
            "custody": n.authority, "clock": lambda: n.x.s.now[0], "resources": n.port,
            "acceptance": acceptance, "observer": m.observe_self}
    service = m.ReadComposition(**args)
    return SimpleNamespace(n=n, args=args, service=service, acceptance=acceptance)


@pytest.mark.parametrize("dependency", ["custody", "clock", "resources", "acceptance", "observer", "enrollment"])
def test_missing_injected_dependencies_refuse(composition, dependency):
    args = {**composition.args, dependency: None}
    with pytest.raises(ValueError, match="DEPENDENCIES_REQUIRED"):
        m.ReadComposition(**args)


@pytest.mark.parametrize("damage", ["account", "acceptance", "stale", "unknown", "missing_source", "identity"])
def test_startup_refuses_before_listener_allocation(composition, monkeypatch, damage):
    c = composition
    if damage == "account":
        with pytest.raises(ValueError, match="ACCOUNT_SCOPE"):
            m.ReadComposition(**{**c.args, "account_id": "foreign"})
        return
    if damage == "acceptance":
        c.acceptance.available = False
    elif damage == "stale":
        c.n.authority.pin["expires_at"] = 0
    elif damage == "unknown":
        c.n.authority.pin["status"] = "UNKNOWN"
    elif damage == "missing_source":
        c.n.port.paths = (str(c.n.tmp_path / "absent"), *c.n.port.paths[1:])
    else:
        c.service.observer = lambda: {**c.service.identity, "creation_filetime": 1}
    monkeypatch.setattr(m.socket, "socket", lambda *a, **k: pytest.fail("listener allocated before admission"))
    host = m.OwnedReadHost(c.service)
    with pytest.raises((ValueError, OSError)):
        host.start()
    assert host.listener is None


def request(ready, path, method="GET", headers=None):
    port = urlsplit(ready["url"]).port
    with closing(HTTPConnection("127.0.0.1", port, timeout=3)) as connection:
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        return response.status, response.read(), response.headers


def test_real_http_existing_screen_read_only_and_owned_shutdown(composition):
    c = composition
    before = capture(c.n.source), capture(c.n.projection), capture(c.n.reports)
    host = m.OwnedReadHost(c.service)
    ready = host.start()
    try:
        assert host.open_read_only_session() == ready
        assert host.verify_read_only_session(ready) is True
        assert ready["process"] == m.observe_self()
        status, raw, headers = request(ready, m.SELECTED)
        view = json.loads(raw)
        assert status == 200 and view["cash"] == "900.0"
        assert view["inception"]["opening_cash"] == "1000"
        assert view["status"] == "ACKNOWLEDGED" and view["report_status"] == "INCOMPLETE"
        assert view["valuation"] is None and not view["startup_authorized"]
        assert headers["Cache-Control"] == "no-store"
        assert request(ready, "/quality_dips.html?mode=selected-paper")[1] == (m.STATIC / "quality_dips.html").read_bytes()
        for asset in ["/static/runtime_poll.js", "/static/quality_dips_selected_paper.js"]:
            assert request(ready, asset)[0] == 200
        assert request(ready, m.SELECTED + "/commands", "POST")[0] == 403
        assert request(ready, "/api/investments/quality-dips")[0] == 404
        assert request(ready, "/health", headers={"Host": "foreign.example"})[0] == 403
        assert request(ready, "/health", headers={"Origin": "https://foreign.example"})[0] == 403
        assert request(ready, "/quality_dips.html?mode=research")[0] == 404
        assert request(ready, "/quality_dips.html")[0] == 404
        with pytest.raises(ValueError, match="ALREADY_OWNED"):
            host.start()
        with pytest.raises(ValueError, match="OWNERSHIP_MISMATCH"):
            host.close({**ready, "host_id": "0" * 32})
        assert host.thread.is_alive()
    finally:
        host.close(ready)
    host.close(ready)
    assert host.close_read_only_session(ready) is True
    with socket.socket() as check:
        check.settimeout(1)
        assert check.connect_ex(("127.0.0.1", urlsplit(ready["url"]).port)) != 0
    assert (capture(c.n.source), capture(c.n.projection), capture(c.n.reports)) == before


@pytest.mark.parametrize("damage", ["unknown", "stale", "acceptance"])
def test_runtime_loss_never_reports_financial_success(composition, damage):
    c = composition
    host = m.OwnedReadHost(c.service)
    ready = host.start()
    try:
        if damage == "acceptance":
            c.acceptance.available = False
        elif damage == "unknown":
            c.n.authority.pin["status"] = "UNKNOWN"
        else:
            c.n.authority.pin["expires_at"] = 0
        status, raw, _ = request(ready, m.SELECTED)
        assert status in (200, 503)
        assert json.loads(raw)["status"] in ("UNKNOWN", "UNAVAILABLE")
    finally:
        host.close(ready)


def test_timeout_retains_owned_references(composition):
    host = m.OwnedReadHost(composition.service)
    host.listener = SimpleNamespace(close=lambda: pytest.fail("premature listener disposal"))
    host.server = SimpleNamespace(should_exit=False)
    host.thread = SimpleNamespace(join=lambda seconds: None, is_alive=lambda: True)
    host.ready = {"host_id": composition.service.host_id}
    with pytest.raises(ValueError, match="TIMEOUT_OWNERSHIP_RETAINED"):
        host.close(host.ready)
    assert host.listener is not None and host.thread is not None


def test_default_cli_cannot_accept_forged_file_or_environment(tmp_path):
    env = {**os.environ, "ATLAS_READ_ACCEPTED": "true"}
    fake = tmp_path / "forged-enrollment.json"
    fake.write_text('{"accepted":true}')
    result = subprocess.run([str(ROOT / "backend/.venv/Scripts/python.exe"), "-B", str(spec.origin), str(fake)],
                            env=env, capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode != 0 and "REFUSED" in result.stderr


def test_control_center_refuses_without_bridge(tmp_path):
    script = tmp_path / "refusal.ps1"
    module = str(ROOT / "scripts/windows/Atlas-SelectedPaper-ReadOnly.psm1").replace("'", "''")
    script.write_text(f"Import-Module '{module}' -Force\nfunction Start-Process {{ throw 'BROWSER_MUST_NOT_START' }}\n"
                      "try { Open-AtlasSelectedPaperDashboard 'unused'; exit 1 } catch {\n"
                      "if ($_.Exception.Message -notlike 'SELECTED_READ_NOT_ENROLLED*') { throw }; 'REFUSAL_VERIFIED' }\n"
                      "Close-AtlasSelectedPaperDashboard\n")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-File", str(script)],
                            capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0 and "REFUSAL_VERIFIED" in result.stdout, result.stderr


@pytest.mark.parametrize("case", ["valid", "ownership", "browser_failure", "close_failure"])
def test_windows_injected_bridge_lifecycle_without_gui_or_real_processes(tmp_path, case):
    module = str(ROOT / "scripts/windows/Atlas-SelectedPaper-ReadOnly.psm1").replace("'", "''")
    script = tmp_path / "bridge.ps1"
    script.write_text(f"Import-Module '{module}' -Force\n$case='{case}'\n" + r'''
$global:browserCalls = 0
function global:Start-Process { param($FilePath, $ErrorAction)
    $global:browserCalls++
    if ($case -eq 'browser_failure') { throw 'synthetic browser failure' }
}
$bridge = [pscustomobject]@{ VerifyOK=($case -ne 'ownership'); CloseOK=($case -ne 'close_failure'); Closes=0 }
$bridge | Add-Member ScriptMethod open_read_only_session {
    [pscustomobject]@{mode='QD_OPERATIONAL_READ_ONLY';host_id=('a'*32);
      url='http://127.0.0.1:18761/quality_dips.html?mode=selected-paper';
      process=[pscustomobject]@{pid=123;creation_filetime=456;image='synthetic-test-only.exe'}}
}
$bridge | Add-Member ScriptMethod verify_read_only_session {param($ready); return $this.VerifyOK}
$bridge | Add-Member ScriptMethod close_read_only_session {param($ready); $this.Closes++; return $this.CloseOK}
$refused=$false
try { Open-AtlasSelectedPaperDashboard 'unused' $bridge } catch { $refused=$true }
if ($case -in @('ownership','browser_failure') -and -not $refused) { throw 'Expected refusal' }
if ($case -eq 'ownership' -and $global:browserCalls -ne 0) { throw 'Unverified browser opened' }
if ($case -eq 'close_failure') {
    try { Close-AtlasSelectedPaperDashboard; throw 'Expected retained ownership' }
    catch { if ($_.Exception.Message -notlike 'SELECTED_READ_EXIT_UNCONFIRMED*') {throw} }
    $bridge.CloseOK=$true
}
Close-AtlasSelectedPaperDashboard
if ($bridge.Closes -lt 1) { throw 'Bridge ownership not closed' }
'BRIDGE_VERIFIED'
''')
    result = subprocess.run(["powershell.exe", "-NoProfile", "-File", str(script)],
                            capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0 and "BRIDGE_VERIFIED" in result.stdout, result.stderr


def test_failed_app_preflight_releases_only_allocated_listener(composition, monkeypatch):
    host = m.OwnedReadHost(composition.service)
    def failed(*args):
        raise ValueError("injected app preflight failure")
    monkeypatch.setattr(m, "build_app", failed)
    with pytest.raises(ValueError, match="injected app preflight"):
        host.start()
    assert host.listener is None and host.thread is None


def test_changed_process_identity_never_stops_owned_host(composition):
    host = m.OwnedReadHost(composition.service)
    ready = host.start()
    observer = composition.service.observer
    try:
        composition.service.observer = lambda: {**host.composition.identity, "pid": 1}
        assert host.verify_read_only_session(ready) is False
        with pytest.raises(ValueError, match="OWNERSHIP_MISMATCH_RETAINED"):
            host.close(ready)
        assert host.thread.is_alive()
    finally:
        composition.service.observer = observer
        host.close(ready)


def test_duplicate_context_and_restart_require_fresh_host_identity(composition):
    first = m.OwnedReadHost(composition.service)
    ready = first.start()
    try:
        with pytest.raises(ValueError, match="CONTEXT_RETIRED_OR_SHARED"):
            m.OwnedReadHost(composition.service).start()
    finally:
        first.close(ready)
    with pytest.raises(ValueError, match="CONTEXT_RETIRED_OR_SHARED"):
        first.start()
    second = m.OwnedReadHost(m.ReadComposition(**composition.args))
    restarted = second.start()
    try:
        assert restarted["host_id"] != ready["host_id"]
        assert second.verify_read_only_session(ready) is False
    finally:
        second.close(restarted)
