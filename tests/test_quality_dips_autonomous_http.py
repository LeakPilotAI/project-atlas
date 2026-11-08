"""Real loopback HTTP over automatically generated disposable native records."""
import importlib.util
import json
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import pytest
from qd_autonomous_native_fixture import REPO, build_http_fixture
from qd_http_fixture import financial_hashes

spec = importlib.util.spec_from_file_location("auto_owned_host", REPO / "scripts/observation_runtime/disposable_host_owner.py")
ownership = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ownership)
ENDPOINT = "/api/investments/quality-dips/selected-paper"


@pytest.fixture(scope="module")
def host():
    path = os.environ.get("ATLAS_AUTO_HTTP_ROOT")
    if not path:
        pytest.skip("NOT EXECUTED: explicit confined HTTP root required")
    root = Path(path)
    assert root.parent == REPO / "logs/diagnostics" and root.name.startswith("qd-http-browser-auto-")
    assert root.is_dir() and not any(p.is_symlink() or p.is_junction() for p in [root, *root.parents])
    sha = build_http_fixture(root)
    (root / "fixture-sha256.txt").write_text(sha)
    before = financial_hashes(root)
    (root / "financial-hashes-before.json").write_text(json.dumps(before, sort_keys=True))
    owner = ownership.OwnedHost(root, sha)
    try:
        yield owner, root
    finally:
        owner.close(owner.identity)
        after = financial_hashes(root)
        (root / "financial-hashes-after.json").write_text(json.dumps(after, sort_keys=True))
        assert before == after
        with socket.socket() as probe:
            assert probe.connect_ex(("127.0.0.1", urlparse(owner.ready["url"]).port)) != 0


def request(owner, path=ENDPOINT, method="GET", headers=None):
    req = urllib.request.Request(owner.ready["url"] + path, method=method, headers={**({"Content-Type": "application/json"} if method == "POST" else {}), **(headers or {})},
        data=b"{}" if method == "POST" else None)
    try:
        response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.read()


@pytest.mark.parametrize("phase,cash,remaining,net", [
    ("entry", "899.96", "1", "0"), ("partial", "943.9424", "0.6", "3.9664"),
    ("final", "1015.9136", None, "15.9136")])
def test_actual_automatic_trade_native_to_http(host, phase, cash, remaining, net):
    owner, _ = host
    owner.control(phase=phase)
    status, raw = request(owner)
    v = json.loads(raw)
    assert status == 200 and v["status"] == "ACKNOWLEDGED", v
    assert v["account_id"] == "synthetic-auto" and v["epoch"] == "synthetic-auto"
    assert v["cash"] == cash and v["realized"]["net"] == net
    assert v["autonomous"]["session_state"] == "STOPPED"
    assert v["autonomous"]["execution"] == "SIMULATED"
    assert v["autonomous"]["l1_state"] == "STALE"  # Historical synthetic market evidence.
    assert v["valuation"] is None and v["report_status"] == "INCOMPLETE"
    if remaining:
        assert next(iter(v["positions"].values()))["remaining"] == remaining
    else:
        assert not v["positions"] and v["realized"]["fees"] == "0.0432"


@pytest.mark.parametrize("mode", ["unknown", "stale", "unavailable"])
def test_actual_http_refusal_clears_financial_values(host, mode):
    owner, _ = host
    owner.control(phase="final", mode=mode)
    status, raw = request(owner)
    v = json.loads(raw)
    assert status == 200 and v["status"] in ("UNKNOWN", "UNAVAILABLE")
    assert v["cash"] is None and v["positions"] is None


def test_actual_host_boundary_and_owned_identity(host):
    owner, _ = host
    owner.control(phase="final")
    assert request(owner, "/health")[0] == 200
    assert request(owner, ENDPOINT + "/commands", method="POST")[0] == 403
    assert request(owner, "/api/investments/quality-dips")[0] == 404
    assert request(owner, headers={"Host": "foreign.invalid"})[0] == 403
    assert request(owner, headers={"Origin": "https://foreign.invalid"})[0] == 403
    assert request(owner, "/quality_dips.html?mode=selected-paper")[0] == 200
    with pytest.raises(ValueError): owner.close({**owner.identity, "created": owner.identity["created"] + 1})
    owner.verify(owner.identity)


def test_actual_network_failure_is_not_a_successful_financial_read(host):
    owner, _ = host
    owner.control(phase="final", mode="network_failure")
    assert request(owner)[0] == 503
