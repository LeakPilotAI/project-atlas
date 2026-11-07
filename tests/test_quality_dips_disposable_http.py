"""Genuine Windows loopback HTTP/owned-process tests, synthetic sources only."""
import importlib.util
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest
from qd_http_fixture import financial_hashes

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("disposable_owner", REPO / "scripts/observation_runtime/disposable_host_owner.py")
ownership = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ownership)
ENDPOINT = "/api/investments/quality-dips/selected-paper"


@pytest.fixture(scope="module")
def host():
    path = os.environ.get("ATLAS_QD_HTTP_ROOT")
    if not path:
        pytest.skip("NOT EXECUTED: explicitly authorized native HTTP fixture root required")
    root = Path(path)
    assert root.parent == REPO / "logs/diagnostics" and root.name.startswith("qd-http-browser-")
    assert all(not p.is_symlink() and not p.is_junction() for p in [root, *root.parents])
    before = financial_hashes(root)
    owner = ownership.OwnedHost(root, (root / "fixture-sha256.txt").read_text())
    try:
        yield owner, root
    finally:
        owner.close(owner.identity)
        assert financial_hashes(root) == before
        with socket.socket() as probe:
            assert probe.connect_ex(("127.0.0.1", urlparse(owner.ready["url"]).port)) != 0


def request(owner, path, *, method="GET", headers=None):
    supplied = dict(headers or {})
    if method == "POST":
        supplied.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(owner.ready["url"] + path, method=method, headers=supplied,
                                 data=b"{}" if method == "POST" else None)
    try:
        response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read()
        return response.status, raw, dict(response.headers)


def test_real_readiness_and_assets(host):
    owner, _ = host
    status, raw, headers = request(owner, "/health")
    assert status == 200 and json.loads(raw)["host_id"] == owner.ready["host_id"]
    assert json.loads(raw)["pid"] == owner.identity["pid"]
    assert headers["cache-control"] == "no-store"
    for asset in ["/quality_dips.html?mode=selected-paper", "/static/runtime_poll.js", "/static/quality_dips_selected_paper.js"]:
        assert request(owner, asset)[0] == 200


@pytest.mark.parametrize("phase,cash,remaining,net", [
    ("entry", "900.0", "2.5", "0"), ("partial", "943.968", "1.5", "3.968"), ("final", "1009.920", None, "9.920")])
def test_native_financial_phases_over_real_http(host, phase, cash, remaining, net):
    owner, _ = host
    owner.control(phase=phase)
    status, raw, _ = request(owner, ENDPOINT)
    view = json.loads(raw)
    assert status == 200 and view["status"] == "ACKNOWLEDGED"
    assert view["account_id"] == "synthetic-selected" and view["epoch"] == "fs1-quality_dips"
    assert len(view["policy_digest"]) == 64 and view["cash"] == cash and view["realized"]["net"] == net
    assert view["inception"]["opening_cash"] == "1000" and view["valuation"] is None
    assert view["report_status"] == "INCOMPLETE" and view["report"]["period"]["effective_end_exclusive"] > 0
    assert view["realized"]["fees"] is None
    if remaining:
        assert next(iter(view["positions"].values()))["remaining"] == remaining
    else:
        assert not view["positions"]


@pytest.mark.parametrize("mode,status,code", [("unknown", "UNKNOWN", 200), ("stale", "UNKNOWN", 200),
    ("unavailable", "UNAVAILABLE", 200), ("network_failure", None, 503)])
def test_refusal_modes_over_http(host, mode, status, code):
    owner, _ = host
    owner.control(mode=mode)
    actual, raw, _ = request(owner, ENDPOINT)
    assert actual == code
    if status:
        view = json.loads(raw)
        assert view["status"] == status and view["cash"] is None and view["positions"] is None


@pytest.mark.parametrize("path", ["/api/investments/quality-dips", "/api/live", "/docs", "/static/../main.py", "/quality_dips.html?mode=research"])
def test_unauthorized_paths_refused(host, path):
    assert request(host[0], path)[0] == 404


@pytest.mark.parametrize("headers", [{"Host": "localhost:9999"}, {"Origin": "https://foreign.invalid"}, {"Sec-Fetch-Site": "cross-site"}])
def test_host_origin_refused(host, headers):
    assert request(host[0], "/health", headers=headers)[0] == 403


def test_command_refused_and_identity_mismatch_does_not_signal_child(host):
    owner, _ = host
    assert request(owner, ENDPOINT + "/commands", method="POST")[0] == 403
    for field, value in [("pid", owner.identity["pid"] + 1), ("created", owner.identity["created"] + 1), ("image", "foreign.exe")]:
        with pytest.raises(ValueError):
            owner.close({**owner.identity, field: value})
        assert request(owner, "/health")[0] == 200


def test_concurrent_http_reads_and_freshness_renewal_leave_evidence_unchanged(host):
    owner, root = host
    owner.control(phase="partial")
    before = financial_hashes(root)
    with ThreadPoolExecutor(max_workers=3) as pool:
        views = list(pool.map(lambda _: json.loads(request(owner, ENDPOINT)[1]), range(3)))
    time.sleep(1.05)
    views.append(json.loads(request(owner, ENDPOINT)[1]))
    assert all(v["status"] == "ACKNOWLEDGED" and v["cash"] == "943.968" for v in views)
    assert all(v["source_identity"] == views[0]["source_identity"] for v in views)
    assert financial_hashes(root) == before


def test_owned_host_restart_and_repeated_close(host):
    _, root = host
    owner = ownership.OwnedHost(root, (root / "fixture-sha256.txt").read_text())
    old = owner.ready
    owner.close(owner.identity)
    owner.close(owner.identity)
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", urlparse(old["url"]).port)) != 0
    restarted = ownership.OwnedHost(root, (root / "fixture-sha256.txt").read_text())
    try:
        assert restarted.ready["host_id"] != old["host_id"]
        assert request(restarted, "/health")[0] == 200
    finally:
        restarted.close(restarted.identity)


def test_bad_manifest_never_reaches_readiness(host):
    with pytest.raises(RuntimeError, match="HOST_READY_IDENTITY_MISMATCH"):
        ownership.OwnedHost(host[1], "0" * 64)


def test_native_observer_failure_closes_only_original_owned_pipe(host, monkeypatch):
    children = []
    original = ownership.subprocess.Popen
    def create(*args, **kwargs):
        child = original(*args, **kwargs)
        children.append(child)
        return child
    def denied(pid):
        raise PermissionError("TEST_OBSERVER_UNAVAILABLE")
    monkeypatch.setattr(ownership.subprocess, "Popen", create)
    monkeypatch.setattr(ownership, "observe_pid", denied)
    with pytest.raises(PermissionError):
        ownership.OwnedHost(host[1], (host[1] / "fixture-sha256.txt").read_text())
    assert len(children) == 1 and children[0].poll() == 0 and children[0].stdin.closed


def test_timeout_retains_ownership_and_retry_does_not_repeat_stdin_close():
    owner = ownership.OwnedHost.__new__(ownership.OwnedHost)
    owner.identity, owner.closed, owner.shutdown_requested = {"pid": 1, "created": 2, "image": "fixture"}, False, False
    calls = []
    active = [True]
    def wait(timeout):
        assert timeout == 12
        raise subprocess.TimeoutExpired("test-owned-fixture", timeout)
    owner.process = SimpleNamespace(stdin=SimpleNamespace(close=lambda: calls.append("close")),
                                    poll=lambda: None if active[0] else 0, wait=wait, returncode=0)
    owner.verify = lambda expected: calls.append("verified")
    with pytest.raises(subprocess.TimeoutExpired):
        owner.close(owner.identity)
    assert owner.process is not None and not owner.closed and owner.shutdown_requested
    with pytest.raises(subprocess.TimeoutExpired):
        owner.close(owner.identity)
    assert calls.count("close") == 1
    active[0] = False
    owner.process.wait = lambda timeout: 0
    owner.close(owner.identity)
    assert owner.closed and calls.count("close") == 1


def test_owner_refuses_foreign_root_before_process_or_log(host, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("FOREIGN_ROOT_ATTEMPTED_PROCESS_CREATION")
    monkeypatch.setattr(ownership.subprocess, "Popen", forbidden)
    foreign = host[1] / ("not-authorized-" + str(time.time_ns()))
    foreign.mkdir()
    with pytest.raises(ValueError, match="BEFORE_PROCESS_OR_LOG"):
        ownership.OwnedHost(foreign, "0" * 64)
    assert not list(foreign.iterdir())
