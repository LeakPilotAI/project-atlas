"""Deterministic accounting tests; every journal write is a temporary fixture."""
import asyncio
import json
from datetime import datetime, timezone

import pytest
from app.api.archive import _eligible_paper_close, _paper_trade_r
from app.services import paper_journal as journal_mod
from app.services.day_trading_cohort_diagnostics import (
    build_day_trading_cohort_diagnostics,
)
from app.services.e29_forward_scorecard import build_scorecard
from app.services.edge_diagnostics import load_paper_closes_safe
from app.services.outcome_research import load_paper_closes, paper_performance
from app.services.paper_accounting import is_administrative, recorded_net_r
from app.services.paper_attribution import build_scorecards
from app.services.paper_execution_cohorts import execution_model_cohorts
from app.services.paper_risk_window import utc_day_risk_snapshot


@pytest.fixture
def journal(tmp_path, monkeypatch):
    path = tmp_path / "paper.jsonl"
    monkeypatch.setattr(journal_mod, "JOURNAL_PATH", path)
    monkeypatch.setattr(journal_mod, "CANDIDATE_PATH", tmp_path / "candidates.jsonl")
    return journal_mod.PaperJournal(), path


def run(coro):
    return asyncio.run(coro)


def opened(j, **kwargs):
    return run(j.open_trade(symbol="BTC", side="LONG", entry=100, stop=95,
                           tp1=105, tp2=110, fees_bps=2, slippage_bps=1,
                           **kwargs))


@pytest.mark.parametrize("reason,exit_price,gross", [
    ("TP", 105, 1), ("STOP", 95, -1), ("BE", 100, 0), ("SCRATCH", 100, 0),
    ("BE", 100.5, .1), ("SCRATCH", 99.5, -.1), ("SCRATCH", 101, .2),
])
def test_costs_once_independent_of_exit_label(journal, reason, exit_price, gross):
    j, path = journal
    tid = opened(j)
    original = path.read_bytes()
    row = run(j.close_trade(tid, exit_price=exit_price, result=reason))
    assert row["gross_pnl_r"] == pytest.approx(gross)
    assert row["R_multiple"] == pytest.approx(gross)
    assert row["net_pnl_r"] == pytest.approx(gross - .012)
    assert row["exit_reason"] == reason
    assert row["scratch"] == (reason in {"BE", "SCRATCH"})
    assert row["win"] == (gross - .012 > 0)
    assert row["counts_for_live"] is True  # Eligibility metadata, not order authority.
    assert path.read_bytes().startswith(original)
    after = path.read_bytes()
    assert run(j.close_trade(tid, exit_price=900, result="TP")) == row
    assert path.read_bytes() == after
    stats = run(j.stats())
    assert stats["closed"] == stats["all_time"]["closed"] == 1
    assert stats["sum_r"] == row["net_pnl_r"]


@pytest.mark.parametrize("net,expected", [(0., 0.), (-.1, -.1), (.1, .1), (None, 2.)])
def test_zero_and_null_contract(net, expected):
    row = {"net_pnl_r": net, "R_multiple": 2.}
    assert recorded_net_r(row) == expected
    assert journal_mod.PaperJournal._tally([row])["sum_r"] == expected
    assert _paper_trade_r(row) == expected


def test_legacy_missing_net():
    assert recorded_net_r({"R_multiple": 2.}) == 2.
    assert journal_mod.PaperJournal._tally([{"R_multiple": 2.}])["sum_r"] == 2.


@pytest.mark.parametrize("bad", ["bad", "", float("nan"), float("inf"), -float("inf"), True, [], {}])
def test_invalid_net_cannot_fall_back_to_profitable_gross(bad):
    row = {"event": "close", "net_pnl_r": bad, "R_multiple": 99}
    assert recorded_net_r(row) is None
    stats = journal_mod.PaperJournal._tally([row])
    assert stats["closed"] == 0
    assert stats["invalid_results"] == 1
    assert not _eligible_paper_close(row)


@pytest.mark.parametrize("admin", [
    {"result": "SESSION_ROLL"}, {"result": "INTERRUPTED"},
    {"session_roll": True}, {"interrupted": True}, {"status": "interrupted"},
    {"exit_reason": "atlas_shutdown"}, {"exit_reason": "session_reset"},
])
def test_administrative_rows_excluded_from_all_performance_consumers(journal, admin):
    j, path = journal
    base = {"event": "close", "trade_id": "real", "strategy": "a",
            "entry_timestamp": "2026-10-13T00:00:00+00:00",
            "exit_timestamp": "2026-10-13T01:00:00+00:00", "net_pnl_r": 1.}
    excluded = {**base, "trade_id": "admin", "net_pnl_r": 99., **admin}
    rows = [base, excluded]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    original = path.read_bytes()
    assert is_administrative(excluded)
    assert run(j.stats())["all_time"]["closed"] == 1
    assert journal_mod.PaperJournal._tally(rows)["sum_r"] == 1
    assert load_paper_closes(path) == [base]
    assert load_paper_closes_safe(path)[0] == [base]
    assert paper_performance(rows)["total_r"] == 1
    assert build_scorecards(rows)["closed_performance_records"] == 1
    assert build_day_trading_cohort_diagnostics(rows)["overall"]["total_r"] == 1
    memberships = {r["trade_id"]: {"baseline_member": True, "challenger_member": True} for r in rows}
    assert build_scorecard(rows, memberships)["baseline"]["closed_trades"] == 1
    assert execution_model_cohorts(rows)["cohorts"][0]["resolved_count"] == 1
    assert not _eligible_paper_close(excluded)
    risk = utc_day_risk_snapshot(path, now=datetime(2026, 10, 13, 12, tzinfo=timezone.utc))
    assert risk["closed"] == 1 and risk["net_r"] == 1
    assert path.read_bytes() == original


@pytest.mark.parametrize("method", ["roll_open_for_session", "interrupt_open_for_shutdown"])
def test_administrative_creation_and_recovery_are_idempotent(journal, method):
    j, path = journal
    tid = opened(j)
    prefix = path.read_bytes()
    assert getattr(j, method)() == [tid]
    assert getattr(j, method)() == []
    assert path.read_bytes().startswith(prefix)
    row = json.loads(path.read_text().splitlines()[-1])
    assert row["net_pnl_r"] == row["gross_pnl_r"] == 0
    assert row["counts_for_live"] is False
    assert row["scratch"] is True
    assert run(j.stats())["closed"] == 0
    before = path.read_bytes()
    recovered = journal_mod.PaperJournal()
    assert recovered.list_open() == []
    assert recovered.reconcile_from_disk()["added"] == 0
    assert path.read_bytes() == before
    assert recovered.bootstrap_session(session_id="new", label="new")["prior_closed_archived"] == 0


def test_session_roll_through_close_keeps_administrative_contract(journal):
    j, _ = journal
    row = run(j.close_trade(opened(j), exit_price=105, result="SESSION_ROLL"))
    assert row["gross_pnl_r"] == 1
    assert row["net_pnl_r"] == 0
    assert row["counts_for_live"] is False
    assert run(j.stats())["closed"] == 0


def test_recovery_reconciliation_and_normal_close_once(journal):
    j, path = journal
    tid = opened(j)
    j.update_excursion(tid, 102, force=True)
    j.note_be_armed(tid, 100)
    before = path.read_bytes()
    recovered = journal_mod.PaperJournal()
    assert recovered.list_open()[0]["be_armed"] is True
    recovered.reconcile_from_disk()
    recovered.reconcile_from_disk()
    assert path.read_bytes() == before
    row = run(recovered.close_trade(tid, exit_price=100, result="BE"))
    assert row["net_pnl_r"] == -.012
    j.reconcile_from_disk()
    assert j.list_open() == []
    assert run(j.stats())["closed"] == 1
    assert sum(json.loads(l).get("event") == "close" for l in path.read_text().splitlines()) == 1


def test_economic_results_and_scratch_labels_remain_distinct():
    rows = [{"net_pnl_r": 1, "strategy": "a"},
            {"net_pnl_r": -.1, "result": "BE", "scratch": True, "strategy": "b"},
            {"net_pnl_r": 0., "R_multiple": 99, "strategy": "b"},
            {"net_pnl_r": -1, "strategy": "a"}]
    result = journal_mod.PaperJournal._tally(rows)
    assert (result["wins"], result["losses"], result["scratches"]) == (1, 1, 2)
    assert result["sum_r"] == -.1
    cohorts = build_day_trading_cohort_diagnostics(rows)
    assert {r["cohort"]: r["total_r"] for r in cohorts["by_strategy"]} == {"a": 0., "b": -.1}


@pytest.mark.parametrize("module", ["day_trading_cohort_diagnostics", "e26_attribution",
                                    "v2_setup_attribution", "e29_forward_scorecard"])
def test_research_readers_preserve_zero_and_fallback_only_on_null(module):
    import importlib
    reader = importlib.import_module("app.services." + module)._r
    assert reader({"net_pnl_r": 0., "R_multiple": 99}) == 0.
    assert reader({"net_pnl_r": None, "R_multiple": -.5}) == -.5
    with pytest.raises(ValueError):
        reader({"net_pnl_r": "invalid", "R_multiple": 99})
