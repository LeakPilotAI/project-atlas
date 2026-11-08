"""One continuous disposable source/ledger/report/HTTP runtime, not checkpoints."""
import hashlib
import importlib.util
import json
import os
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runtime_owner", REPO / "scripts/observation_runtime/disposable_host_owner.py")
owner_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner_module)
ENDPOINT = "/api/investments/quality-dips/selected-paper"


def request(owner, path=ENDPOINT, method="GET", headers=None):
    req = urllib.request.Request(owner.ready["url"] + path, method=method,
        headers={"Content-Type": "application/json", **(headers or {})}, data=b"{}" if method == "POST" else None)
    try:
        response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response: return response.status, response.read()


def wait_view(owner, predicate):
    deadline = time.monotonic() + 12
    last = None
    while time.monotonic() < deadline:
        code, raw = request(owner)
        last = json.loads(raw)
        if code == 200 and predicate(last): return last
        time.sleep(.03)
    raise AssertionError(last)


@pytest.fixture
def host(tmp_path):
    parent = os.environ.get("ATLAS_AUTO_RUNTIME_HTTP_PARENT")
    if not parent: pytest.skip("NOT EXECUTED: explicit runtime HTTP confinement required")
    parent = Path(parent)
    assert parent.parent == REPO / "logs/diagnostics" and parent.name.startswith("qd-auto-runtime-")
    assert tmp_path.is_relative_to(parent)
    # Owner requires its unique top-level confined diagnostics root.
    root = REPO / "logs/diagnostics" / ("qd-http-browser-runtime-" + os.urandom(12).hex())
    root.mkdir()
    with (parent / "continuous-http-roots.txt").open("a") as log:
        log.write(str(root) + "\n")
    raw = json.dumps({"schema": "QD_AUTO_CONTINUOUS_FIXTURE_V3", "interval_seconds": .35}).encode()
    (root / "fixture.json").write_bytes(raw)
    owner = owner_module.OwnedHost(root, hashlib.sha256(raw).hexdigest(), runtime_fixture=True)
    try:
        yield owner, root
    finally:
        owner.close(owner.identity)
        with socket.socket() as s: assert s.connect_ex(("127.0.0.1", urlparse(owner.ready["url"]).port)) != 0


def test_continuous_http_session_changes_native_state_without_trade_commands(host):
    owner, root = host
    assert request(owner)[0] == 200
    assert json.loads(request(owner)[1])["status"] == "UNAVAILABLE"  # Not started/no report.
    assert owner.runtime_control("start")["runtime"]["state"] == "RUNNING"
    entry = wait_view(owner, lambda v: v.get("source_revision") == 1)
    partial = wait_view(owner, lambda v: v.get("source_revision") == 2)
    final = wait_view(owner, lambda v: v.get("source_revision") == 3)
    assert entry["cash"] == "899.96"
    assert next(iter(partial["positions"].values()))["remaining"] == "0.6"
    assert final["cash"] == "1015.9136" and not final["positions"]
    assert final["realized"]["net"] == "15.9136"
    assert entry["source_identity"]["root"] == partial["source_identity"]["root"] == final["source_identity"]["root"]
    assert request(owner, ENDPOINT + "/commands", "POST")[0] == 403
    assert request(owner, "/api/investments/quality-dips")[0] == 404
    assert request(owner, headers={"Host": "foreign.invalid"})[0] == 403
    assert owner.runtime_control("stop")["runtime"]["state"] == "STOPPED"
    before = {str(p.relative_to(root)): p.read_bytes() for p in (root / "account").rglob("*") if p.is_file()}
    for _ in range(4): assert json.loads(request(owner)[1])["autonomous"]["session_state"] == "STOPPED"
    assert before == {str(p.relative_to(root)): p.read_bytes() for p in (root / "account").rglob("*") if p.is_file()}
    assert "refused" in owner.runtime_control("start")["runtime"]


def test_continuous_pause_preserves_position_and_allows_protective_management(host):
    owner, _ = host
    owner.runtime_control("start")
    wait_view(owner, lambda v: v.get("source_revision") == 1)
    assert owner.runtime_control("pause")["runtime"]["state"] == "PAUSED"
    final = wait_view(owner, lambda v: v.get("source_revision") == 3)
    assert final["autonomous"]["session_state"] == "PAUSED"
    assert owner.runtime_control("stop")["runtime"]["state"] == "STOPPED"


def test_disconnection_stops_dispatch_and_refuses_restart_recovery(host):
    owner, _ = host
    owner.runtime_control("start")
    entry = wait_view(owner, lambda v: v.get("source_revision") == 1)
    assert entry["cash"] == "899.96"
    owner.runtime_control("disconnect")
    failed = wait_view(owner, lambda v: v.get("autonomous", {}).get("session_state") == "STOP_INCOMPLETE")
    assert failed["source_revision"] == 1 and len(failed["positions"]) == 1
    assert "refused" in owner.runtime_control("start")["runtime"]
