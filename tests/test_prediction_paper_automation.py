from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import app.prediction.prediction_paper_automation as automation_module
from app.prediction.kalshi_public import normalize_market
from app.prediction.paper_engine import PredictionPaperJournal, evaluate_pre_event_repricing
from app.prediction.prediction_paper_automation import (
    PredictionAutomationConfig,
    PredictionPaperAutomation,
)


def _market(now, *, volume="500", oi="300"):
    return normalize_market({
        "ticker": "KXTEST-A", "event_ticker": "KXTEST-E", "market_type": "binary",
        "title": "Test", "status": "open", "yes_bid_dollars": "0.40",
        "yes_ask_dollars": "0.42", "no_bid_dollars": "0.58",
        "no_ask_dollars": "0.60", "volume_fp": volume, "volume_24h_fp": volume,
        "open_interest_fp": oi, "occurrence_datetime": (now + timedelta(hours=3)).isoformat(),
        "is_provisional": False, "mve_collection_ticker": "", "mve_selected_legs": [],
    })


def _book():
    return {
        "yes": {"bids": [{"price_dollars": "0.50", "quantity_contracts": "100"}],
                "asks": [{"price_dollars": "0.42", "quantity_contracts": "100"}],
                "best_bid_dollars": "0.50", "best_ask_dollars": "0.42", "spread_dollars": "0.02"},
        "no": {"bids": [{"price_dollars": "0.50", "quantity_contracts": "100"}],
               "asks": [{"price_dollars": "0.42", "quantity_contracts": "100"}],
               "best_bid_dollars": "0.50", "best_ask_dollars": "0.42", "spread_dollars": "0.02"},
    }


def _candles():
    return [{"yes_bid": {"close_dollars": "0.50", "high_dollars": "0.60"},
             "yes_ask": {"close_dollars": "0.52", "low_dollars": "0.40"}} for _ in range(6)]


def _journal(tmp_path):
    return PredictionPaperJournal(
        journal_path=tmp_path / "paper.jsonl",
        candidate_path=tmp_path / "candidates.jsonl",
    )


def _open(journal, now, flat_minutes=0):
    return journal.open_from_evaluation({
        "eligible": True, "ticker": "KXTEST-A", "side": "YES",
        "quantity_contracts": "10",
        "occurrence_datetime": (now + timedelta(minutes=30)).isoformat(),
        "flat_deadline": (now + timedelta(minutes=flat_minutes)).isoformat(),
        "strategy": "PRE_EVENT_RECENT_RECLAIM_V1", "score": 90,
        "engine_version": "prediction-paper-reprice-v1",
        "entry_fill": {"fillable": True, "vwap_dollars": "0.42",
                       "notional_dollars": "4.20", "estimated_taker_fee_dollars": "0.17",
                       "depth_slippage_dollars_per_contract": "0",
                       "levels": [{"price_dollars": "0.42", "quantity_contracts": "10"}]},
    })


def test_scanner_prefilters_before_expensive_reads_and_never_opens(monkeypatch, tmp_path):
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    journal = _journal(tmp_path)
    monkeypatch.setattr(automation_module, "prediction_paper_journal", journal)
    calls = {"book": 0, "candles": 0}

    async def markets(**kwargs):
        return {"markets": [_market(now, volume="1", oi="1")]}
    async def book(*args, **kwargs):
        calls["book"] += 1
        return {"orderbook": _book()}
    async def candles(*args, **kwargs):
        calls["candles"] += 1
        return {"candlesticks": _candles()}

    monkeypatch.setattr(automation_module.kalshi_public, "get_markets", markets)
    monkeypatch.setattr(automation_module.kalshi_public, "get_orderbook", book)
    monkeypatch.setattr(automation_module.kalshi_public, "get_candlesticks", candles)

    service = PredictionPaperAutomation()
    state = asyncio.run(service.run_scan_once(now=now))
    assert state["markets_prefilter_rejected"] == 1
    assert calls == {"book": 0, "candles": 0}
    assert journal.open_trade() is None
    rows = journal._rows(journal.candidate_path)
    assert {row["side"] for row in rows} == {"YES", "NO"}
    status = service.status()
    assert status["unattended_paper_open_enabled"] is False
    assert status["automatic_paper_position_opening"] is False
    assert status["unattended_paper_open_block_reasons"] == ["AUTO_FLAT_LIVE_VALIDATION_REQUIRED"]


def test_scanner_paginates_metadata_pool_and_prioritizes_viable_market(monkeypatch, tmp_path):
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    journal = _journal(tmp_path)
    monkeypatch.setattr(automation_module, "prediction_paper_journal", journal)
    low_a = _market(now, volume="1", oi="1")
    low_a["ticker"] = "KXTEST-LOW-A"
    low_b = _market(now, volume="2", oi="2")
    low_b["ticker"] = "KXTEST-LOW-B"
    good = _market(now, volume="500", oi="300")
    good["ticker"] = "KXTEST-GOOD"
    calls = {"markets": [], "book": [], "candles": []}

    async def markets(**kwargs):
        calls["markets"].append(dict(kwargs))
        if not kwargs.get("cursor"):
            return {"markets": [low_a, low_b], "cursor": "NEXT"}
        return {"markets": [good], "cursor": None}

    async def book(ticker, **kwargs):
        calls["book"].append(ticker)
        return {"orderbook": _book()}

    async def candles(*args, **kwargs):
        calls["candles"].append(kwargs["ticker"])
        return {"candlesticks": _candles()}

    monkeypatch.setattr(automation_module.kalshi_public, "get_markets", markets)
    monkeypatch.setattr(automation_module.kalshi_public, "get_orderbook", book)
    monkeypatch.setattr(automation_module.kalshi_public, "get_candlesticks", candles)

    service = PredictionPaperAutomation(config=PredictionAutomationConfig(
        discovery_limit=1,
        discovery_pool_limit=3,
        discovery_page_size=2,
    ))
    state = asyncio.run(service.run_scan_once(now=now))
    assert state["metadata_markets_seen"] == 3
    assert state["markets_selected"] == 1
    assert state["selection_viable_count"] == 1
    assert state["selection_activity_qualified_count"] == 1
    assert state["markets_fully_evaluated"] == 1
    assert calls["markets"][0]["cursor"] is None
    assert calls["markets"][1]["cursor"] == "NEXT"
    assert calls["book"] == ["KXTEST-GOOD"]
    assert calls["candles"] == ["KXTEST-GOOD"]
    rows = journal._rows(journal.candidate_path)
    assert {row["ticker"] for row in rows} == {"KXTEST-GOOD"}


def test_scanner_accepts_provider_active_status_from_open_discovery(monkeypatch, tmp_path):
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    journal = _journal(tmp_path)
    monkeypatch.setattr(automation_module, "prediction_paper_journal", journal)
    market = _market(now)
    market["status"] = "active"

    async def markets(**kwargs):
        return {"markets": [market]}
    async def book(*args, **kwargs):
        return {"orderbook": _book()}
    async def candles(*args, **kwargs):
        return {"candlesticks": _candles()}

    monkeypatch.setattr(automation_module.kalshi_public, "get_markets", markets)
    monkeypatch.setattr(automation_module.kalshi_public, "get_orderbook", book)
    monkeypatch.setattr(automation_module.kalshi_public, "get_candlesticks", candles)

    state = asyncio.run(PredictionPaperAutomation().run_scan_once(now=now))
    assert state["markets_prefilter_rejected"] == 0
    assert state["markets_fully_evaluated"] == 1
    assert state["yes_evaluations"] == 1
    assert state["no_evaluations"] == 1


def test_scanner_evaluates_yes_and_no_with_one_market_data_read(monkeypatch, tmp_path):
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    journal = _journal(tmp_path)
    monkeypatch.setattr(automation_module, "prediction_paper_journal", journal)
    calls = {"book": 0, "candles": 0}

    async def markets(**kwargs):
        assert kwargs["limit"] <= 200
        return {"markets": [_market(now)]}
    async def book(*args, **kwargs):
        calls["book"] += 1
        return {"orderbook": _book()}
    async def candles(*args, **kwargs):
        calls["candles"] += 1
        return {"candlesticks": _candles()}

    monkeypatch.setattr(automation_module.kalshi_public, "get_markets", markets)
    monkeypatch.setattr(automation_module.kalshi_public, "get_orderbook", book)
    monkeypatch.setattr(automation_module.kalshi_public, "get_candlesticks", candles)

    state = asyncio.run(PredictionPaperAutomation().run_scan_once(now=now))
    assert state["markets_fully_evaluated"] == 1
    assert state["yes_evaluations"] == 1 and state["no_evaluations"] == 1
    assert calls == {"book": 1, "candles": 1}
    assert journal.open_trade() is None


def test_scanner_notifies_eligible_candidates_without_opening(monkeypatch, tmp_path):
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    journal = _journal(tmp_path)
    monkeypatch.setattr(automation_module, "prediction_paper_journal", journal)
    notified = []

    async def markets(**kwargs):
        return {"markets": [_market(now)], "cursor": None}

    async def book(*args, **kwargs):
        return {"orderbook": _book()}

    async def candles(*args, **kwargs):
        return {"candlesticks": _candles()}

    def eligible_eval(*, market, side, quantity, **kwargs):
        return {
            "eligible": True,
            "ticker": market["ticker"],
            "side": side,
            "score": 91,
            "quantity_contracts": str(quantity),
            "occurrence_datetime": market["timing"]["occurrence_datetime"],
            "flat_deadline": (now + timedelta(hours=2, minutes=30)).isoformat(),
            "strategy": "PRE_EVENT_RECENT_RECLAIM_V1",
            "projected": {"net_edge_dollars_per_contract": "0.04"},
            "entry_fill": {"fillable": True, "vwap_dollars": "0.42"},
        }

    async def notify(candidates):
        notified.extend(candidates)
        return {
            "attempted": len(candidates),
            "delivered": len(candidates),
            "deduped": 0,
            "failed": 0,
            "last_alert_key": "synthetic",
            "last_error": None,
        }

    monkeypatch.setattr(automation_module.kalshi_public, "get_markets", markets)
    monkeypatch.setattr(automation_module.kalshi_public, "get_orderbook", book)
    monkeypatch.setattr(automation_module.kalshi_public, "get_candlesticks", candles)
    monkeypatch.setattr(automation_module, "evaluate_pre_event_repricing", eligible_eval)
    monkeypatch.setattr(automation_module, "deliver_prediction_eligible_alerts", notify)

    state = asyncio.run(PredictionPaperAutomation().run_scan_once(now=now))
    assert state["eligible_count"] == 2
    assert state["eligible_alerts_attempted"] == 2
    assert state["eligible_alerts_delivered"] == 2
    assert {row["side"] for row in notified} == {"YES", "NO"}
    assert journal.open_trade() is None


def test_auto_flat_waits_before_deadline(monkeypatch, tmp_path):
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    journal = _journal(tmp_path)
    _open(journal, now, flat_minutes=11)
    monkeypatch.setattr(automation_module, "prediction_paper_journal", journal)

    async def forbidden(*args, **kwargs):
        raise AssertionError("no early orderbook read")
    monkeypatch.setattr(automation_module.kalshi_public, "get_orderbook", forbidden)

    state = asyncio.run(PredictionPaperAutomation().run_auto_flat_once(now=now))
    assert state["last_action"] == "WAITING_FOR_FLAT_DEADLINE"
    assert journal.open_trade() is not None


def test_candidate_requires_full_executable_exit_depth_at_entry():
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    market = _market(now)
    book_data = _book()
    # Entry asks remain deep enough for 10 contracts, but only two contracts can
    # currently be sold. A mandatory-flat strategy must reject this asymmetry.
    book_data["yes"]["bids"] = [
        {"price_dollars": "0.50", "quantity_contracts": "2"}
    ]
    evaluation = evaluate_pre_event_repricing(
        market=market,
        orderbook=book_data,
        candles=_candles(),
        side="YES",
        quantity=Decimal("10"),
        now=now,
    )
    assert evaluation["eligible"] is False
    assert "INSUFFICIENT_EXECUTABLE_EXIT_DEPTH_AT_ENTRY" in evaluation["rejection_reasons"]
    assert evaluation["exit_liquidity_at_entry"]["required_for_eligibility"] is True
    assert evaluation["exit_liquidity_at_entry"]["fillable"] is False


def test_auto_flat_begins_retry_window_ten_minutes_before_flat_deadline(monkeypatch, tmp_path):
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    journal = _journal(tmp_path)
    _open(journal, now, flat_minutes=10)
    monkeypatch.setattr(automation_module, "prediction_paper_journal", journal)
    calls = {"book": 0}
    book_data = _book()
    book_data["yes"]["bids"] = []

    async def book(*args, **kwargs):
        calls["book"] += 1
        return {"orderbook": book_data}

    monkeypatch.setattr(automation_module.kalshi_public, "get_orderbook", book)
    service = PredictionPaperAutomation()
    state = asyncio.run(service.run_auto_flat_once(now=now))
    assert calls["book"] == 1
    assert state["last_reason"] == "AUTO_FLAT_BLOCKED_NO_DEPTH"
    assert state["blocked"] is True
    assert journal.open_trade() is not None


def test_auto_flat_uses_multilevel_bid_vwap_and_closes_once(monkeypatch, tmp_path):
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    journal = _journal(tmp_path)
    opened = _open(journal, now)
    monkeypatch.setattr(automation_module, "prediction_paper_journal", journal)
    book_data = _book()
    book_data["yes"]["bids"] = [
        {"price_dollars": "0.50", "quantity_contracts": "4"},
        {"price_dollars": "0.48", "quantity_contracts": "6"},
    ]

    async def book(*args, **kwargs):
        return {"orderbook": book_data}
    monkeypatch.setattr(automation_module.kalshi_public, "get_orderbook", book)

    service = PredictionPaperAutomation()
    first = asyncio.run(service.run_auto_flat_once(now=now))
    second = asyncio.run(service.run_auto_flat_once(now=now))
    assert first["last_action"] == "AUTO_FLAT_EXECUTED"
    assert second["last_action"] == "IDLE"
    closes = [r for r in journal._rows(journal.journal_path) if r.get("event") == "close"]
    assert len(closes) == 1 and closes[0]["trade_id"] == opened["trade_id"]
    assert Decimal(closes[0]["actual_exit_price"]) == Decimal("0.488")
    assert len(closes[0]["exit_fill_levels"]) == 2


def test_auto_flat_insufficient_depth_records_block_not_fake_close(monkeypatch, tmp_path):
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    journal = _journal(tmp_path)
    _open(journal, now)
    monkeypatch.setattr(automation_module, "prediction_paper_journal", journal)
    book_data = _book()
    book_data["yes"]["bids"] = [{"price_dollars": "0.50", "quantity_contracts": "2"}]

    async def book(*args, **kwargs):
        return {"orderbook": book_data}
    monkeypatch.setattr(automation_module.kalshi_public, "get_orderbook", book)

    service = PredictionPaperAutomation()
    state = asyncio.run(service.run_auto_flat_once(now=now))
    assert state["last_reason"] == "AUTO_FLAT_BLOCKED_INSUFFICIENT_DEPTH"
    assert journal.open_trade() is not None
    rows = journal._rows(journal.journal_path)
    assert not [r for r in rows if r.get("event") == "close"]
    assert len([r for r in rows if r.get("event") == "auto_flat_blocked"]) == 1
    assert "AUTO_FLAT_SAFETY_BLOCKED" in service.status()["unattended_paper_open_block_reasons"]


def test_scanner_isolates_market_failure_and_persists_error_candidates(monkeypatch, tmp_path):
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    journal = _journal(tmp_path)
    monkeypatch.setattr(automation_module, "prediction_paper_journal", journal)
    good = _market(now)
    good["ticker"] = "KXTEST-GOOD"
    bad = _market(now)
    bad["ticker"] = "KXTEST-BAD"

    async def markets(**kwargs):
        return {"markets": [bad, good]}
    async def book(ticker, **kwargs):
        if ticker == "KXTEST-BAD":
            raise RuntimeError("synthetic provider failure")
        return {"orderbook": _book()}
    async def candles(*args, **kwargs):
        return {"candlesticks": _candles()}

    monkeypatch.setattr(automation_module.kalshi_public, "get_markets", markets)
    monkeypatch.setattr(automation_module.kalshi_public, "get_orderbook", book)
    monkeypatch.setattr(automation_module.kalshi_public, "get_candlesticks", candles)

    state = asyncio.run(PredictionPaperAutomation().run_scan_once(now=now))
    assert state["error_count"] == 1
    assert state["markets_fully_evaluated"] == 1
    rows = journal._rows(journal.candidate_path)
    bad_rows = [row for row in rows if row.get("ticker") == "KXTEST-BAD"]
    good_rows = [row for row in rows if row.get("ticker") == "KXTEST-GOOD"]
    assert {row["side"] for row in bad_rows} == {"YES", "NO"}
    assert all(row["rejection_reasons"] == ["SCANNER_EVALUATION_ERROR"] for row in bad_rows)
    assert {row["side"] for row in good_rows} == {"YES", "NO"}


def test_auto_flat_provider_failure_preserves_open_position(monkeypatch, tmp_path):
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    journal = _journal(tmp_path)
    _open(journal, now)
    monkeypatch.setattr(automation_module, "prediction_paper_journal", journal)

    async def book(*args, **kwargs):
        raise automation_module.PredictionProviderError("synthetic provider failure")
    monkeypatch.setattr(automation_module.kalshi_public, "get_orderbook", book)

    service = PredictionPaperAutomation()
    state = asyncio.run(service.run_auto_flat_once(now=now))
    assert state["last_reason"] == "AUTO_FLAT_PROVIDER_ERROR"
    assert state["blocked"] is True
    assert journal.open_trade() is not None
    assert not [r for r in journal._rows(journal.journal_path) if r.get("event") == "close"]


def test_auto_flat_event_start_violation_never_manufactures_settlement_fill(monkeypatch, tmp_path):
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    journal = _journal(tmp_path)
    opened = journal.open_from_evaluation({
        "eligible": True, "ticker": "KXTEST-A", "side": "YES",
        "quantity_contracts": "10",
        "occurrence_datetime": (now - timedelta(seconds=1)).isoformat(),
        "flat_deadline": (now - timedelta(minutes=30)).isoformat(),
        "strategy": "PRE_EVENT_RECENT_RECLAIM_V1", "score": 90,
        "engine_version": "prediction-paper-reprice-v1",
        "entry_fill": {"fillable": True, "vwap_dollars": "0.42",
                       "notional_dollars": "4.20", "estimated_taker_fee_dollars": "0.17",
                       "depth_slippage_dollars_per_contract": "0",
                       "levels": [{"price_dollars": "0.42", "quantity_contracts": "10"}]},
    })
    monkeypatch.setattr(automation_module, "prediction_paper_journal", journal)

    async def forbidden(*args, **kwargs):
        raise AssertionError("event-start violation must not manufacture a provider exit")
    monkeypatch.setattr(automation_module.kalshi_public, "get_orderbook", forbidden)

    service = PredictionPaperAutomation()
    state = asyncio.run(service.run_auto_flat_once(now=now))
    assert state["last_action"] == "TERMINAL_UNCLOSED"
    assert state["last_reason"] == "EXIT_FAILED_BEFORE_EVENT_START"
    assert state["deadline_violation"] is True
    assert journal.open_trade() is None
    terminal = journal.latest_expired_unclosed()
    assert terminal["trade_id"] == opened["trade_id"]
    assert terminal["status"] == "EXPIRED_UNCLOSED"
    assert terminal["actual_exit_price"] is None
    assert terminal["net_pnl_dollars"] is None
    assert terminal["counts_as_closed_trade"] is False
    assert not [r for r in journal._rows(journal.journal_path) if r.get("event") == "close"]

    # Repeated checks are idempotent and preserve the durable safety block.
    again = asyncio.run(service.run_auto_flat_once(now=now + timedelta(seconds=5)))
    assert again["last_action"] == "TERMINAL_UNCLOSED"
    terminals = [
        r for r in journal._rows(journal.journal_path)
        if r.get("event") == "expired_unclosed"
    ]
    assert len(terminals) == 1
    assert "AUTO_FLAT_SAFETY_BLOCKED" in service.status()["unattended_paper_open_block_reasons"]


def test_expired_unclosed_preserves_no_liquidity_failure_without_fake_pnl(monkeypatch, tmp_path):
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    journal = _journal(tmp_path)
    opened = journal.open_from_evaluation({
        "eligible": True, "ticker": "KXTEST-A", "side": "YES",
        "quantity_contracts": "10",
        "occurrence_datetime": (now + timedelta(seconds=1)).isoformat(),
        "flat_deadline": (now - timedelta(minutes=30)).isoformat(),
        "strategy": "PRE_EVENT_RECENT_RECLAIM_V1", "score": 90,
        "engine_version": "prediction-paper-reprice-v1",
        "entry_fill": {"fillable": True, "vwap_dollars": "0.42",
                       "notional_dollars": "4.20", "estimated_taker_fee_dollars": "0.17",
                       "depth_slippage_dollars_per_contract": "0",
                       "levels": [{"price_dollars": "0.42", "quantity_contracts": "10"}]},
    })
    journal.log_event({
        "event": "auto_flat_blocked",
        "trade_id": opened["trade_id"],
        "reason": "AUTO_FLAT_BLOCKED_NO_DEPTH",
        "error": "NO_EXECUTABLE_DEPTH",
    })
    monkeypatch.setattr(automation_module, "prediction_paper_journal", journal)

    service = PredictionPaperAutomation()
    state = asyncio.run(
        service.run_auto_flat_once(now=now + timedelta(seconds=2))
    )
    assert state["last_reason"] == "EXIT_FAILED_NO_LIQUIDITY"
    terminal = journal.latest_expired_unclosed()
    assert terminal["status"] == "EXPIRED_UNCLOSED"
    assert terminal["terminal_reason"] == "EXIT_FAILED_NO_LIQUIDITY"
    assert terminal["last_pre_event_block_reason"] == "AUTO_FLAT_BLOCKED_NO_DEPTH"
    assert terminal["actual_exit_price"] is None
    assert terminal["gross_pnl_dollars"] is None
    assert terminal["net_pnl_dollars"] is None
    assert journal.open_trade() is None
    snapshot = journal.snapshot()
    assert snapshot["summary"]["open_positions"] == 0
    assert snapshot["summary"]["expired_unclosed_trades"] == 1
    assert snapshot["summary"]["closed_trades"] == 0



def test_terminal_unclosed_is_not_counted_as_active_or_closed_trade(tmp_path):
    journal = _journal(tmp_path)
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    opened = journal.open_from_evaluation({
        "eligible": True, "ticker": "KXTEST-TERMINAL", "side": "YES",
        "quantity_contracts": "10",
        "occurrence_datetime": (now + timedelta(hours=2)).isoformat(),
        "flat_deadline": (now + timedelta(hours=1)).isoformat(),
        "strategy": "PRE_EVENT_RECENT_RECLAIM_V1", "score": 90,
        "engine_version": "prediction-paper-reprice-v1",
        "entry_fill": {"fillable": True, "vwap_dollars": "0.42",
                       "notional_dollars": "4.20", "estimated_taker_fee_dollars": "0.17",
                       "depth_slippage_dollars_per_contract": "0",
                       "levels": [{"price_dollars": "0.42", "quantity_contracts": "10"}]},
    })
    terminal = journal.expire_unclosed(opened=opened, now=now + timedelta(hours=2))
    snapshot = journal.snapshot()
    assert terminal["status"] == "EXPIRED_UNCLOSED"
    assert terminal["counts_as_closed_trade"] is False
    assert terminal["counts_for_live"] is False
    assert journal.open_trade() is None
    assert snapshot["summary"]["open_positions"] == 0
    assert snapshot["summary"]["expired_unclosed_trades"] == 1
    assert snapshot["summary"]["closed_trades"] == 0
    assert snapshot["summary"]["net_pnl_dollars"] == "0"
