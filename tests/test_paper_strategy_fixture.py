import asyncio
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from app.investment.quality_dips_paper import close_lot, open_lot
from app.services.paper_epoch_fixture import EpochFixture, create_epoch_fixture
from app.services.paper_strategy_fixture import (
    NativeProjectionFixture,
    exit_command,
    quality_entry,
    quality_terminal_exit,
)
from app.trading_core.perp_manual_state_store import ManualPerpStateStore
from test_hyperliquid_paper_handoff import actual_journal
from test_hyperliquid_store_integration import manual_plan
from test_paper_epoch_fixture import STAMP, entry, manifest, quote


def observation(stamp=STAMP, price="100"):
    return {"symbol": "MSFT", "observation_id": "fixture-observation", "classification": "ACCUMULATION",
            "strategy_version": "QUALITY_DIPS_V3", "policy_version": "quality-dips-v3-mos-15-20-25-30-v1",
            "evidence_class": "FORWARD_COLLECTION", "reached_levels": ["L1"], "quote": quote(price, "MSFT", stamp)}


def test_quality_native_source_and_versioned_cash_cost_report(tmp_path):
    m = manifest("quality", "QUALITY_DIPS")
    s = create_epoch_fixture(tmp_path / "epoch.sqlite", m)
    obs = observation()
    c = quality_entry(s, obs, level="L1", notional="100", operation_id="entry", timestamp=STAMP, manual=True)
    receipt = s.execute(c)
    path = tmp_path / "native-quality.jsonl"
    lot = open_lot({"symbol": "MSFT", "observation_id": obs["observation_id"], "price": 100},
                   level="L1", paper_notional_dollars=100, path=path)
    retained = path.read_bytes()
    assert Decimal(s.snapshot()["cash"]) == 900
    partial = exit_command(s, operation_id="partial", position_id=receipt["position_id"], quantity="0.25",
                           quote=quote("110", "MSFT"), timestamp=STAMP, manual=True)
    s.execute(partial)
    assert s.daily_report("2026-10-23")["state"] == "INCOMPLETE"
    assert path.read_bytes() == retained  # Native V1 cannot truthfully project partial exits.
    with pytest.raises(ValueError, match="Price-only"):
        quality_terminal_exit(s, position_id=receipt["position_id"], operation_id="bad",
                              terminal_observation={}, quote=quote("110", "MSFT"), timestamp=STAMP, manual=True)
    final = quality_terminal_exit(s, position_id=receipt["position_id"], operation_id="final",
                                  terminal_observation={"classification": "THESIS_BROKEN"},
                                  quote=quote("110", "MSFT"), timestamp=STAMP, manual=True)
    s.execute(final)
    report = s.daily_report("2026-10-23")
    assert Decimal(report["closing_cash"]) == Decimal("1009.92")
    assert Decimal(report["realized_net"]) == Decimal("9.92")
    assert Decimal(report["costs"]) == Decimal("0.08")
    # Same-price legs can be compared to V1 full gross closure,not a general
    # mapping of different-price partial fills to a fabricated V1 exit.
    native_close = close_lot(lot["lot_id"], exit_price=110, reason="THESIS_BROKEN", path=path)
    assert Decimal(str(native_close["realized_pnl"])) == Decimal(report["realized_gross"])
    assert not report["shutdown_authorized"]
    assert EpochFixture(s.path, expected_manifest=m).execute(final) == s.execute(final)


@pytest.mark.parametrize("bad", ["version", "future-class", "not-reached", "not-manual", "cash"])
def test_quality_refuses_unapproved_evidence_and_cash(tmp_path, bad):
    s = create_epoch_fixture(tmp_path / "epoch.sqlite", manifest("quality", "QUALITY_DIPS"))
    obs = observation()
    if bad == "version": obs["strategy_version"] = "V2"
    if bad == "future-class": obs["evidence_class"] = "BACKTEST"
    if bad == "not-reached": obs["reached_levels"] = []
    with pytest.raises(ValueError):
        s.execute(quality_entry(s, obs, level="L1", notional="1001" if bad == "cash" else "100",
                                operation_id="entry", timestamp=STAMP, manual=bad != "not-manual"))
    assert s.snapshot()["revision"] == 0


def native_bridge(tmp_path):
    s = create_epoch_fixture(tmp_path / "epoch.sqlite", manifest())
    module, journal = actual_journal(tmp_path)
    manual = ManualPerpStateStore(tmp_path / "manual.json")
    manual.save(plans=[], setup_history=[])
    def publish(state, receipt):
        plans = manual.load()["plans"]
        by_id = {p["canonical_fixture_id"]: p for p in plans}
        new = []
        for ident, position in state["positions"].items():
            plan = by_id.get(ident)
            if plan is None:
                tid = asyncio.run(journal.open_trade(symbol=position["symbol"], side=position["side"],
                    entry=float(position["entry"]), stop=98, tp1=104, tp2=106, risk_usd=1,
                    counts_for_live=False, fees_bps=2, slippage_bps=2,
                    source="fixture-manual-only", features={"canonical_fixture_id": ident}))
                plan = {**manual_plan(position["symbol"], position["side"]),
                        "canonical_fixture_id": ident, "fixture_journal_trade_id": tid}
            new.append({**plan, "fixture_projection": {**position, "source_revision": state["revision"]}})
        manual.save(plans=new, setup_history=[])
    def observe():
        return {"journal": module.JOURNAL_PATH.read_bytes().hex(), "manual": manual.load()}
    return s, NativeProjectionFixture(s, publish=publish, observe=observe), module, manual


def test_hyperliquid_actual_native_entry_and_truthful_partial_projection(tmp_path):
    s, bridge, module, manual = native_bridge(tmp_path)
    c = entry(s)
    ack = bridge.apply(c)
    assert bridge.apply(c) == ack
    pos = ack["evidence"]["canonical_receipt"]["position_id"]
    original = module.JOURNAL_PATH.read_bytes()
    for ident, qty in [("partial", "0.125"), ("final", "0.375")]:
        command = exit_command(s, operation_id=ident, position_id=pos, quantity=qty,
                               quote=quote("104"), timestamp=STAMP, manual=True)
        assert bridge.apply(command) == bridge.apply(command)
    assert bridge.apply(c) == ack  # Old acknowledged retry after newer projections.
    p = manual.load()["plans"][0]
    assert p["status"] == "ENTERED" and Decimal(p["fixture_projection"]["remaining"]) == 0
    assert module.JOURNAL_PATH.read_bytes() == original
    native = module.PaperJournal().list_open()[0]
    assert native["features"]["canonical_fixture_id"] == pos
    assert native["position_size"] == 0.5 and native["fees_bps"] == native["slippage_bps"] == 2
    assert bridge.snapshot()["report_state"] == "RECONCILED_FIXTURE_ONLY"
    assert not bridge.daily_report("2026-10-23")["shutdown_authorized"]


@pytest.mark.parametrize("phase", ["after_commit", "before_projection", "after_projection", "before_projection_ack", "after_projection_ack"])
def test_projection_interruption_never_replays_unknown_callback(tmp_path, phase):
    s, bridge, _, _ = native_bridge(tmp_path)
    c = entry(s)
    def fault(point):
        if point == phase:
            raise RuntimeError("fixture interruption")
    with pytest.raises(RuntimeError): bridge.apply(c, fault=fault)
    if phase == "after_projection_ack":
        assert bridge.apply(c)["evidence"]["canonical_receipt"]["source_revision"] == 1
    else:
        with pytest.raises(ValueError, match="UNKNOWN"):
            bridge.apply(c)
        with pytest.raises(ValueError): bridge.daily_report("2026-10-23")
    assert s.snapshot()["revision"] == 1


def test_native_projection_corruption_and_concurrent_retry(tmp_path):
    s, bridge, _, manual = native_bridge(tmp_path)
    c = entry(s)
    def attempt(_):
        try:
            return bridge.apply(c)
        except ValueError:
            return "REFUSED_PENDING"
    with ThreadPoolExecutor(3) as pool:
        result = list(pool.map(attempt, range(3)))
    assert any(isinstance(r, dict) for r in result)
    assert s.snapshot()["revision"] == 1
    assert len(manual.load()["plans"]) == 1
    manual.save(plans=[], setup_history=[])
    with pytest.raises(ValueError, match="Changed native"):
        bridge.snapshot()
    with pytest.raises(ValueError): bridge.daily_report("2026-10-23")


@pytest.mark.parametrize("observation", [None, {}])
def test_missing_projection_observation_preserves_unknown(tmp_path, observation):
    s = create_epoch_fixture(tmp_path / "epoch.sqlite", manifest())
    bridge = NativeProjectionFixture(s, publish=lambda *_: None, observe=lambda: observation)
    c = entry(s)
    with pytest.raises(ValueError, match="Missing"):
        bridge.apply(c)
    with pytest.raises(ValueError, match="UNKNOWN"):
        bridge.apply(c)
    with pytest.raises(ValueError): bridge.daily_report("2026-10-23")


def test_day_boundary_report_does_not_use_future_closure(tmp_path):
    from datetime import datetime

    s = create_epoch_fixture(tmp_path / "epoch.sqlite", manifest("quality", "QUALITY_DIPS"))
    c = quality_entry(s, observation(), level="L1", notional="100", operation_id="entry", timestamp=STAMP, manual=True)
    pos = s.execute(c)["position_id"]
    tomorrow = int(datetime.fromisoformat("2026-10-24T04:00:01+00:00").timestamp())
    s.execute(exit_command(s, operation_id="close", position_id=pos, quantity="1", quote=quote("110", "MSFT", tomorrow),
                           timestamp=tomorrow, manual=True))
    first, second = s.daily_report("2026-10-23"), s.daily_report("2026-10-24")
    assert first["state"] == "INCOMPLETE" and Decimal(first["closing_cash"]) == 900
    assert second["state"] == "RECONCILED_FIXTURE_ONLY" and Decimal(second["opening_cash"]) == 900
    assert Decimal(first["realized_net"]) == 0 and Decimal(second["realized_net"]) == Decimal("9.92")


def test_no_operational_module_imports_the_new_prototypes():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "backend/app"
    for path in root.rglob("*.py"):
        if path.name in ("paper_epoch_fixture.py", "paper_strategy_fixture.py"):
            continue
        text = path.read_text(encoding="utf-8-sig")
        assert "import paper_epoch_fixture" not in text and "services.paper_epoch_fixture" not in text
        assert "import paper_strategy_fixture" not in text and "services.paper_strategy_fixture" not in text


@pytest.mark.parametrize("phase", ["after_projection", "after_projection_ack"])
def test_abrupt_projection_child_restart(tmp_path, phase):
    from pathlib import Path

    s = create_epoch_fixture(tmp_path / "epoch.sqlite", manifest())
    c = entry(s)
    output, config = tmp_path / "projection.json", tmp_path / "config.json"
    config.write_text(json.dumps([str(s.path), manifest(), c, str(output), phase]), encoding="utf-8")
    code = '''import json,os,sys
from pathlib import Path
from app.services.paper_epoch_fixture import EpochFixture
from app.services.paper_strategy_fixture import NativeProjectionFixture
p,m,c,out,phase=json.load(open(sys.argv[1],encoding="utf-8"))
def publish(state,receipt):
 with open(out,"x",encoding="utf-8") as f:
  json.dump(state,f);f.flush();os.fsync(f.fileno())
def observe():return json.loads(Path(out).read_text(encoding="utf-8"))
def fault(point):
 if point==phase:os._exit(74)
NativeProjectionFixture(EpochFixture(p,expected_manifest=m),publish=publish,observe=observe).apply(c,fault=fault)
'''
    child = subprocess.run([sys.executable, "-c", code, str(config)], cwd=Path(__file__).resolve().parents[1],
                           env={**os.environ, "PYTHONPATH": "backend"}, timeout=15, capture_output=True, check=False)
    assert child.returncode == 74, child.stderr
    def never_publish(*_args):
        pytest.fail("Callback must not replay after crash")
    bridge = NativeProjectionFixture(EpochFixture(s.path, expected_manifest=manifest()), publish=never_publish,
                                     observe=lambda: json.loads(output.read_text(encoding="utf-8")))
    if phase == "after_projection":
        with pytest.raises(ValueError, match="UNKNOWN"): bridge.apply(c)
    else:
        assert bridge.apply(c)["evidence"]["canonical_receipt"]["source_revision"] == 1
    assert s.snapshot()["revision"] == 1


@pytest.mark.parametrize("start,end,day", [
    ("2026-03-08T06:30:00+00:00", "2026-03-08T07:30:00+00:00", "2026-03-08"),
    ("2026-11-01T05:30:00+00:00", "2026-11-01T06:30:00+00:00", "2026-11-01"),
])
def test_quality_day_report_dst_and_immutable_revisions(tmp_path, start, end, day):
    from datetime import datetime

    a, b = int(datetime.fromisoformat(start).timestamp()), int(datetime.fromisoformat(end).timestamp())
    m = manifest("quality", "QUALITY_DIPS"); m["opened_at"] = a
    s = create_epoch_fixture(tmp_path / "epoch.sqlite", m)
    c = quality_entry(s, observation(a), level="L1", notional="100", operation_id="entry", timestamp=a, manual=True)
    pos = s.execute(c)["position_id"]
    first = s.daily_report(day)
    s.execute(quality_terminal_exit(s, position_id=pos, operation_id="close",
        terminal_observation={"classification": "THESIS_BROKEN"}, quote=quote("110", "MSFT", b), timestamp=b, manual=True))
    second = s.daily_report(day)
    assert first["state"] == "INCOMPLETE" and second["state"] == "RECONCILED_FIXTURE_ONLY"
    assert Decimal(second["realized_net"]) == Decimal("9.92")
    with s.connect() as db:
        rows = db.execute("SELECT body FROM daily ORDER BY revision").fetchall()
        assert len(rows) == 2 and json.loads(rows[0][0]) == first
        db.execute("UPDATE daily SET parent='wrong' WHERE revision=1")
    with pytest.raises(ValueError, match="report history"): s.daily_report(day)
