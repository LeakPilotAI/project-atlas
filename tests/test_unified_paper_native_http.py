"""Existing native fixture/read host with two read-only market observations."""

import asyncio
import json
import os
import time
from pathlib import Path

from app.services.unified_paper_runtime import UnifiedMarketReadCapability
from test_quality_dips_operational_read_service import capture, m, request
from test_unified_paper_runtime import runtime

pytest_plugins = ["test_quality_dips_operational_read_service"]


def test_unified_native_financial_reads_http_and_graceful_owned_close(composition):
    c = composition
    before = capture(c.n.source), capture(c.n.projection), capture(c.n.reports)
    r = runtime()
    r.clock = lambda: int(time.time())
    for lane in r.lanes.values():
        original = lane.observe

        async def current_observation(original=original):
            return {**await original(), "at": r.clock()}

        lane.observe = current_observation
    asyncio.run(r.poll())
    reader = UnifiedMarketReadCapability(r)
    host = m.OwnedReadHost(c.service, unified_reader=reader)
    ready = host.start()
    try:
        status, raw, _ = request(ready, m.SELECTED)
        view = json.loads(raw)
        assert status == 200 and view["status"] == "ACKNOWLEDGED"
        assert view["multi_market"]["lanes"]["QUALITY_DIPS"]["session"] == "CLOSED"
        assert view["multi_market"]["lanes"]["HYPERLIQUID"]["session"] == "OPEN"
        assert view["multi_market"]["total_cash"] is None
        assert request(ready, m.SELECTED + "/commands", "POST")[0] == 403
        assert request(ready, "/api/investments/quality-dips")[0] == 404
        assert all(not p.calls for p in r.lanes.values())
        # Optional real-browser observation of this exact disposable host, <=60s.
        evidence = os.environ.get("ATLAS_UNIFIED_BROWSER_EVIDENCE")
        if evidence:
            root = Path(evidence).absolute()
            diagnostics = Path(__file__).resolve().parents[1] / "logs/diagnostics"
            assert root.parent == diagnostics and root.name.startswith("unified-paper-")
            (root / "browser-ready.json").write_text(json.dumps(ready), encoding="utf-8")
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and not (root / "browser-release.txt").exists():
                asyncio.run(r.poll())
                time.sleep(.25)
        r.lanes["HYPERLIQUID"].failed = True
        asyncio.run(r.poll())
        view = json.loads(request(ready, m.SELECTED)[1])
        assert view["multi_market"]["lanes"]["HYPERLIQUID"]["connection"] == "UNAVAILABLE"
        assert view["multi_market"]["lanes"]["QUALITY_DIPS"]["connection"] == "CONNECTED"
        assert not view["startup_authorized"]
    finally:
        host.close(ready)
    assert host.close_read_only_session(ready) is True
    assert (capture(c.n.source), capture(c.n.projection), capture(c.n.reports)) == before
