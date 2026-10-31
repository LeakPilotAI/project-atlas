"""Real loopback and shipped PowerShell action; no operational processes/stores."""

import hashlib
import json
import os
import socket
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import pytest
from test_quality_dips_autonomous_runtime_http import owner_module, request

REPO = Path(__file__).resolve().parents[1]


def control(owner, *, mode="SHUTDOWN_FLATTEN", token=None, origin=None):
    url = owner.ready["url"]
    req = Request(
        url + "/_atlas/control/stop",
        method="POST",
        data=json.dumps({"mode": mode}).encode(),
        headers={
            "Content-Type": "application/json",
            "Origin": origin or url,
            "X-Atlas-Control": token or owner.ready["control_token"],
        },
    )
    try:
        response = urlopen(req, timeout=15)
    except HTTPError as e:
        response = e
    with response:
        raw = response.read()
        return response.status, json.loads(raw) if raw else {"status": "HTTP_REFUSED"}


@pytest.fixture
def host_factory():
    assert os.environ.get("ATLAS_CONTROL_HTTP_AUTHORIZED") == "DISPOSABLE_ONLY"
    owners = []

    def create(damage="none", partial=False):
        root = (
            REPO / "logs/diagnostics" / ("qd-http-browser-runtime-" + uuid.uuid4().hex)
        )
        root.mkdir()
        raw = json.dumps(
            {"schema": "QD_CONTROL_DISPOSABLE_V1", "damage": damage, "partial": partial}
        ).encode()
        (root / "fixture.json").write_bytes(raw)
        owner = owner_module.OwnedHost(
            root, hashlib.sha256(raw).hexdigest(), control_fixture=True
        )
        owners.append((owner, root))
        return owner, root

    try:
        yield create
    finally:
        for owner, root in owners:
            owner.close(owner.identity)
            with socket.socket() as sock:
                assert (
                    sock.connect_ex(("127.0.0.1", urlparse(owner.ready["url"]).port))
                    != 0
                )


@pytest.mark.parametrize("partial", [False, True])
def test_http_stop_full_partial_duplicate_restart_and_readonly(host_factory, partial):
    owner, root = host_factory(partial=partial)
    assert request(owner)[0] == 200
    code, result = control(owner)
    assert code == 200 and result["outcome"]["status"] == "FLATTENED", result
    assert result["outcome"]["position_state"] == "FLAT"
    before = {p: p.read_bytes() for p in (root / "account").rglob("*.json")}
    assert control(owner)[1] == result
    code, raw = request(owner)
    assert code == 200
    view = json.loads(raw)
    assert "autonomous" in view, view
    assert view["autonomous"]["shutdown_outcome"]["status"] == "FLATTENED"
    assert not view["positions"]
    assert before == {p: p.read_bytes() for p in (root / "account").rglob("*.json")}
    assert "refused" in owner.runtime_control("start")["runtime"]


@pytest.mark.parametrize("damage", ["closed", "stale", "disconnect", "unknown"])
def test_http_unresolved_stop_is_explicit_and_no_replay(host_factory, damage):
    owner, root = host_factory(damage)
    code, result = control(owner)
    assert code == 200 and result["outcome"]["status"] == "SHUTDOWN_INCOMPLETE", result
    assert result["outcome"]["position_state"] == (
        "UNKNOWN" if damage == "unknown" else "POSITION_OPEN"
    )
    before = {p: p.read_bytes() for p in (root / "account").rglob("*.json")}
    assert control(owner)[1] == result
    assert before == {p: p.read_bytes() for p in (root / "account").rglob("*.json")}
    assert "refused" in owner.runtime_control("start")["runtime"]


def test_http_transport_refuses_foreign_authority_and_emergency_separate(host_factory):
    owner, _ = host_factory()
    assert control(owner, token="forged")[0] == 403
    assert control(owner, origin="http://foreign.invalid")[0] == 403
    assert control(owner, mode="START")[0] == 409
    code, result = control(owner, mode="EMERGENCY")
    assert code == 200 and result["outcome"]["position_state"] == "UNVERIFIED"
    assert json.loads(request(owner)[1])["positions"]


def test_shipped_control_center_action_calls_genuine_http_without_legacy_fallback(
    host_factory,
):
    owner, _ = host_factory()
    script = """
    Import-Module './scripts/windows/Atlas-Control-Center.psm1' -Force
    $bridge = [pscustomobject]@{ url=$env:QD_TEST_URL; token=$env:QD_TEST_TOKEN }
    $bridge | Add-Member ScriptMethod verify_session { return $true }
    $bridge | Add-Member ScriptMethod request_stop {
      param($mode)
      Invoke-RestMethod -Uri ($this.url+'/_atlas/control/stop') -Method Post -ContentType 'application/json' -Headers @{Origin=$this.url;'X-Atlas-Control'=$this.token} -Body (@{mode=$mode}|ConvertTo-Json -Compress)
    }
    Invoke-AtlasPaperStop $bridge | ConvertTo-Json -Depth 12 -Compress
    """
    env = dict(
        os.environ,
        QD_TEST_URL=owner.ready["url"],
        QD_TEST_TOKEN=owner.ready["control_token"],
    )
    result = subprocess.run(
        [
            str(
                Path(os.environ["SystemRoot"])
                / "System32/WindowsPowerShell/v1.0/powershell.exe"
            ),
            "-NoProfile",
            "-Command",
            script,
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["outcome"]["status"] == "FLATTENED"
    code = (REPO / "scripts/windows/Atlas-Background-Controls.ps1").read_text()
    handler = code.split("$stopButton.Add_Click({")[1].split("$runtimeSummary")[0]
    assert "Invoke-AtlasPaperStop $AcceptedPaperSession" in handler
    assert "Start-BackgroundManager" not in handler


def test_stop_preserves_exact_unrelated_sentinel_and_refuses_foreign_close(
    host_factory,
):
    owner, root = host_factory()
    # An explicitly test-owned stand-in, never a Genesis process or service.
    sentinel = root / "unrelated-sentinel.py"
    sentinel.write_text('import sys\nprint("ready",flush=True)\nsys.stdin.readline()\n')
    process = subprocess.Popen(
        [sys._base_executable, "-B", str(sentinel)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        assert process.stdout.readline().strip() == "ready"
        identity = owner_module.observe_pid(process.pid)
        assert control(owner)[1]["outcome"]["status"] == "FLATTENED"
        assert process.poll() is None
        assert owner_module.observe_pid(process.pid) == identity
        with pytest.raises(ValueError, match="FOREIGN_OR_MISMATCHED"):
            owner.close(identity)
        assert owner.process.poll() is None
    finally:
        process.stdin.close()
        process.wait(timeout=5)
