"""E126 admission evidence and race regressions; temporary journals only."""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import app.services.paper_journal as journal_mod
import app.services.perp_setup_paper_mirror as mirror_mod
import pytest
from app.core.config import Settings
from app.services.paper_risk import check_paper_risk
from app.services.paper_risk_controls import PaperRiskControlStore
from app.services.paper_risk_window import (
    risk_snapshot_is_current,
    utc_day_risk_snapshot,
)

NOW = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)


def close(**overrides):
    return {"event": "close", "trade_id": "one", "exit_timestamp": "2026-10-14T01:00:00Z",
            "net_pnl_r": -1, **overrides}


def snapshot(tmp_path, rows):
    path = tmp_path / "journal.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    before = path.read_bytes()
    result = utc_day_risk_snapshot(path, now=NOW)
    assert path.read_bytes() == before
    return result


@pytest.mark.parametrize("value,allowed", [(0, True), (-3, False), (-3.01, False), (-2.99999, True)])
def test_exact_loss_boundary(tmp_path, value, allowed):
    s = snapshot(tmp_path, [close(net_pnl_r=value)])
    assert s["reliable"]
    assert check_paper_risk(open_positions=[], requested_risk_usd=1,
                            session_net_r=s["net_r"], accounting_reliable=s["reliable"])["allowed"] is allowed


@pytest.mark.parametrize("field", ["session_net_r", "requested_risk_usd"])
@pytest.mark.parametrize("bad", [None, "bad", float("nan"), float("inf"), float("-inf"), True, [], {}])
def test_invalid_risk_input(field, bad):
    args = {"open_positions": [], "requested_risk_usd": 1, "session_net_r": 0}
    args[field] = bad
    assert not check_paper_risk(**args)["allowed"]


@pytest.mark.parametrize("bad", [None, "bad", float("nan"), float("inf"), True])
def test_unknown_today_net_is_not_zero(tmp_path, bad):
    s = snapshot(tmp_path, [close(net_pnl_r=bad)])
    assert not s["reliable"] and s["net_r"] is None


@pytest.mark.parametrize("stamp", [None, "bad", "2026-10-14", "2026-13-14T01:00:00Z"])
def test_unknown_timestamp_blocks(tmp_path, stamp):
    assert not snapshot(tmp_path, [close(exit_timestamp=stamp)])["reliable"]


def test_legacy_zero_rollover_strategies_and_exclusions(tmp_path):
    rows = [close(trade_id="old", exit_timestamp="2026-10-13T23:59:59Z", net_pnl_r=-50),
            close(trade_id="micro", strategy="rsi_extension_v1", net_pnl_r=0, R_multiple=10),
            close(trade_id="equity", strategy="equity_daytrade_manual_limit_v1", net_pnl_r=None,
                  R_multiple=-1, exit_timestamp=None, timestamp="2026-10-14 00:00:00"),
            close(trade_id="mirror", strategy="perp_setup_auto_v2_resting_limit", net_pnl_r=0.5),
            close(trade_id="test", trade_type="TEST", exit_timestamp=None, net_pnl_r=None),
            close(trade_id="admin", result="INTERRUPTED", exit_timestamp=None, net_pnl_r=None)]
    s = snapshot(tmp_path, rows)
    assert s["reliable"] and s["closed"] == 3 and s["net_r"] == -0.5
    s = snapshot(tmp_path, [close(exit_timestamp="2026-10-13T20:00:00-05:00")])
    assert s["reliable"] and s["closed"] == 1


def test_missing_empty_unreadable(tmp_path, monkeypatch):
    p = tmp_path / "journal.jsonl"
    assert not utc_day_risk_snapshot(p)["reliable"]
    p.touch()
    assert utc_day_risk_snapshot(p)["net_r"] == 0
    original = Path.open

    def denied(self, *args, **kwargs):
        if self == p:
            raise PermissionError("test")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", denied)
    assert not utc_day_risk_snapshot(p)["reliable"]


@pytest.mark.parametrize("raw", [b'{"event":"close"', b'bad\n', b'[]\n', b'{}\n', b'\xff\n'])
def test_malformed_partial_unreadable_bytes(tmp_path, raw):
    p = tmp_path / "journal.jsonl"
    p.write_bytes(raw)
    assert not utc_day_risk_snapshot(p)["reliable"]
    assert p.read_bytes() == raw


def test_duplicate_identity_and_legacy_ambiguity(tmp_path):
    s = snapshot(tmp_path, [close(), close()])
    assert s["reliable"] and s["net_r"] == -1 and s["duplicate_closes"] == 1
    assert not snapshot(tmp_path, [close(), close(net_pnl_r=2)])["reliable"]
    assert snapshot(tmp_path, [close(trade_id=None)])["reliable"]
    assert not snapshot(tmp_path, [close(trade_id=None), close(trade_id=None)])["reliable"]


def test_snapshot_rejects_append_and_rollover(tmp_path):
    p = tmp_path / "journal.jsonl"
    p.touch()
    s = utc_day_risk_snapshot(p)
    assert risk_snapshot_is_current(s)
    with p.open("a") as handle:
        handle.write('{"event":"open"}\n')
    assert not risk_snapshot_is_current(s)
    s = utc_day_risk_snapshot(p, now=datetime(2020, 1, 1, tzinfo=timezone.utc))
    assert not risk_snapshot_is_current(s)


def test_recovered_positions_preserved_and_counted(tmp_path, monkeypatch):
    p = tmp_path / "journal.jsonl"
    rows = [{"event": "open", "trade_id": str(i), "symbol": str(i), "side": "LONG"} for i in range(3)]
    p.write_text("".join(json.dumps(row) + "\n" for row in rows))
    before = p.read_bytes()
    monkeypatch.setattr(journal_mod, "JOURNAL_PATH", p)
    monkeypatch.setattr(journal_mod, "CANDIDATE_PATH", tmp_path / "candidates.jsonl")
    journal = journal_mod.PaperJournal()
    assert len(journal.list_open()) == 3
    assert not check_paper_risk(open_positions=journal.list_open(), requested_risk_usd=1)["allowed"]
    assert p.read_bytes() == before


def test_strategy_specific_concurrency_unchanged():
    assert Settings(_env_file=None, perp_micro_max_open=0).effective_max_open == 80
    assert Settings(_env_file=None, perp_micro_max_open=6).effective_max_open == 6


@pytest.mark.parametrize("raw", ['bad', '[]', '{}', '{"kill_switch":"false"}'])
def test_corrupt_controls_fail_closed(tmp_path, raw):
    p = tmp_path / "controls.json"
    p.write_text(raw)
    store = PaperRiskControlStore(p)
    assert not store.reliable
    assert not check_paper_risk(open_positions=[], requested_risk_usd=1,
                                controls_reliable=store.reliable)["allowed"]
    assert p.read_text() == raw


def admission(tmp_path, monkeypatch):
    p = tmp_path / "journal.jsonl"
    p.touch()
    monkeypatch.setattr(journal_mod, "JOURNAL_PATH", p)
    monkeypatch.setattr(journal_mod, "CANDIDATE_PATH", tmp_path / "candidates.jsonl")
    journal = journal_mod.PaperJournal()
    monkeypatch.setattr(mirror_mod, "paper_journal", journal)
    controls = PaperRiskControlStore(tmp_path / "controls.json")
    monkeypatch.setattr(mirror_mod, "paper_risk_controls", controls)
    monkeypatch.setattr(mirror_mod, "utc_day_risk_snapshot", lambda: utc_day_risk_snapshot(p))
    mirror = mirror_mod.PerpSetupPaperMirror(pending_path=tmp_path / "pending.jsonl")
    mirror._seeded = True
    mirror._terminal_cache_hydrated = True
    for symbol in ["BTC", "ETH", "SOL", "AVAX"]:
        mirror._pending[symbol] = {"symbol": symbol, "side": "LONG", "limit_price": 99,
                                   "stop": 95, "tp1": 105, "tp2": 110}
    return mirror, journal, controls, p


def test_serialized_concurrent_fills_cannot_exceed_cap(tmp_path, monkeypatch):
    mirror, journal, _, _ = admission(tmp_path, monkeypatch)

    async def run():
        return await asyncio.gather(*(mirror._fill_pending(s, mark=98.98, setup={"mark_timestamp": datetime.now(timezone.utc).isoformat()}) for s in list(mirror._pending)))

    results = asyncio.run(run())
    assert results.count(True) == 3
    assert len(journal.list_open()) == 3
    assert not asyncio.run(mirror._fill_pending("BTC", mark=98.98, setup={"mark_timestamp": datetime.now(timezone.utc).isoformat()}))


@pytest.mark.parametrize("failure", ["exception", "kill", "append", "missing", "cancel"])
def test_no_open_when_state_changes_during_worker(tmp_path, monkeypatch, failure):
    mirror, journal, controls, p = admission(tmp_path, monkeypatch)
    controls.session_net_r = 100  # Stored PnL cannot rescue a failed snapshot.
    before = p.read_bytes()

    async def worker(func):
        if failure == "exception":
            raise OSError("test snapshot failure")
        s = func()
        if failure == "kill":
            controls.kill_switch = True
        elif failure == "append":
            with p.open("a") as handle:
                handle.write(json.dumps(close(exit_timestamp=datetime.now(timezone.utc).isoformat())) + "\n")
        elif failure == "missing":
            s = {"net_r": 0}
        elif failure == "cancel":
            mirror._pending.clear()
        return s

    monkeypatch.setattr(mirror_mod.asyncio, "to_thread", worker)
    assert not asyncio.run(mirror._fill_pending("BTC", mark=98.98, setup={"mark_timestamp": datetime.now(timezone.utc).isoformat()}))
    assert not journal.list_open()
    assert not any(json.loads(line).get("event") == "open" for line in p.read_text().splitlines())
    if failure != "append":
        assert p.read_bytes() == before


def test_api_snapshot_failure_never_uses_stored_profit(monkeypatch):
    import app.api.perp_manual as api

    async def failed(func):
        raise OSError("test")

    monkeypatch.setattr(api.asyncio, "to_thread", failed)
    monkeypatch.setattr(api.paper_risk_controls, "session_net_r", 100)
    result = asyncio.run(api.paper_risk_status())
    assert result["session_net_r"] is None
    assert not result["standard_auto_mirror_probe"]["allowed"]
    assert not result["live_capital_allowed"]


def test_change_during_read_is_unreliable(tmp_path, monkeypatch):
    import app.services.paper_risk_window as window
    p = tmp_path / "journal.jsonl"
    p.touch()
    original = window._version
    calls = 0

    def changing(path):
        nonlocal calls
        calls += 1
        version = original(path)
        if calls == 2:
            version[2] += 1
        return version

    monkeypatch.setattr(window, "_version", changing)
    s = window.utc_day_risk_snapshot(p)
    assert not s["reliable"] and "journal changed during snapshot" in s["issues"]


def test_positions_rechecked_after_worker(tmp_path, monkeypatch):
    mirror, journal, _, p = admission(tmp_path, monkeypatch)

    async def worker(func):
        s = func()
        journal._open = {str(i): {"symbol": str(i), "side": "LONG"} for i in range(3)}
        return s

    monkeypatch.setattr(mirror_mod.asyncio, "to_thread", worker)
    assert not asyncio.run(mirror._fill_pending("BTC", mark=98.98, setup={"mark_timestamp": datetime.now(timezone.utc).isoformat()}))
    assert len(journal.list_open()) == 3 and p.read_bytes() == b""


def test_new_control_store_default_and_corrupt_evidence_refusal(tmp_path):
    p = tmp_path / "controls.json"

    fresh = PaperRiskControlStore(p)
    assert fresh.reliable

    p.write_text("bad", encoding="utf-8")
    original_bytes = p.read_bytes()

    store = PaperRiskControlStore(p)
    assert not store.reliable

    store.kill_switch = True

    try:
        store.save()
    except RuntimeError as exc:
        assert "independent reconciliation" in str(exc)
    else:
        raise AssertionError(
            "Corrupt PAPER control evidence must refuse persistence"
        )

    assert p.read_bytes() == original_bytes

    restored = PaperRiskControlStore(p)
    assert not restored.reliable


@pytest.mark.parametrize("row", [{"event": []}, {"event": "mystery"}, close(trade_type="unknown")])
def test_invalid_record_contract(tmp_path, row):
    assert not snapshot(tmp_path, [row])["reliable"]


def test_unrounded_small_losses_are_not_a_stop(tmp_path):
    s = snapshot(tmp_path, [close(net_pnl_r=-2.99999)])
    assert s["net_r"] == -2.99999


def test_finite_values_cannot_overflow_total(tmp_path):
    s = snapshot(tmp_path, [close(net_pnl_r=1e308), close(trade_id="two", net_pnl_r=1e308)])
    assert not s["reliable"] and s["net_r"] is None


def test_risk_ui_preserves_unknown_instead_of_showing_zero():
    import shutil
    import subprocess
    root = Path(__file__).resolve().parents[1]
    page = (root / "backend/app/static/command_center_risk.html").read_text(encoding="utf-8")
    prefixes = ("const $=", "const num=", "let DATA=", "function renderMetrics()", "function renderHeadroom()")
    code = "\n".join(line for line in page.splitlines() if line.startswith(prefixes))
    probe = r"""
const assert=require('node:assert/strict');
const nodes={};const document={getElementById:id=>nodes[id]||(nodes[id]={})};
""" + code + r"""
DATA={risk:{session_net_r:null,limits:{max_session_loss_r:3}}};
renderMetrics();renderHeadroom();
assert.equal(nodes.mNet.textContent,'—');assert.equal(nodes.mHeadroom.textContent,'—');
assert.ok(nodes.headroom.innerHTML.includes('Accounting unavailable'));
DATA.risk.session_net_r=0;renderMetrics();renderHeadroom();
assert.equal(nodes.mNet.textContent,'0.00R');assert.equal(nodes.mHeadroom.textContent,'+3.00R');
assert.ok(nodes.headroom.innerHTML.includes('3.00R to stop'));
"""
    node = shutil.which("node")
    assert node, "Node is required for the dashboard contract"
    subprocess.run([node, "-e", probe], check=True, capture_output=True, text=True, encoding="utf-8")


def test_perp_r_formatter_preserves_unknown():
    import shutil
    import subprocess
    page = (Path(__file__).resolve().parents[1] / "backend/app/static/dashboard_shell.html").read_text(encoding="utf-8")
    code = next(line for line in page.splitlines() if line.startswith("const rtxt="))
    probe = "const assert=require('node:assert/strict');" + code
    probe += "assert.equal(rtxt(null),'—');assert.equal(rtxt(undefined),'—');assert.equal(rtxt(0),'0.00R');"
    node = shutil.which("node")
    assert node
    subprocess.run([node, "-e", probe], check=True, capture_output=True, text=True, encoding="utf-8")
