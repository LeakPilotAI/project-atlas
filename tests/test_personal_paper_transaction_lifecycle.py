"""Disposable end-to-end journal transaction tests; never runtime fill authority."""
from datetime import UTC, datetime

import pytest

from app.investment.quality_dips_paper import (
    accounting_snapshot, close_lot, initialize_paper_account,
    journal_mutation_transaction, mark_lot, open_lot, read_events,
)
from app.services.personal_paper_price_evidence import validate_stock_iex_quote


def _quote(now, bid, ask):
    return {"symbol": "MSFT", "state": "FRESH", "bid": bid, "ask": ask,
            "bid_lots": 5, "ask_lots": 5, "timestamp": now.isoformat(),
            "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP"}


def test_disposable_quote_entry_mark_exit_restart_under_single_transaction(tmp_path):
    path = tmp_path / "isolated-forward.jsonl"
    now = datetime(2026, 11, 6, 20, tzinfo=UTC)
    observation = {"observation_id": "synthetic-fixture-1", "symbol": "MSFT",
                   "evidence_class": "FORWARD_COLLECTION"}
    with journal_mutation_transaction(path):
        initialize_paper_account(account_id="fixture-forward", opening_cash=1000,
                                 fee_bps_per_side=2, max_open_positions=1,
                                 data_provenance="FORWARD_COLLECTION", path=path)
        buy = validate_stock_iex_quote(_quote(now, "99.99", "100"), symbol="MSFT", now=now)
        entry = open_lot(observation, level="L1", paper_notional_dollars=50,
                         fill_price=buy["ask"], account_id="fixture-forward",
                         fee_bps_per_side=2, path=path)
        assert entry["broker_order_created"] is False
        assert accounting_snapshot(read_events(path), account_id="fixture-forward")["open_positions"] == 1
    # A separate journal transaction models the next forward collection tick.
    with journal_mutation_transaction(path):
        sell = validate_stock_iex_quote(_quote(now, "102", "102.01"), symbol="MSFT", now=now)
        mark_lot(entry["lot_id"], market_price=sell["bid"], path=path)
        close = close_lot(entry["lot_id"], exit_price=sell["bid"],
                          reason="DISPOSABLE_FIXTURE_EXIT", path=path)
        assert close["live_capital_allowed"] is False
    # Fresh disk replay: no in-memory state is trusted after restart.
    recovered = accounting_snapshot(read_events(path), account_id="fixture-forward")
    assert recovered["open_positions"] == 0
    assert recovered["cash_reconciled"] is True
    assert recovered["net_realized_pnl"] > 0
    assert len([r for r in read_events(path) if r["event"] == "open_lot"]) == 1
    assert len([r for r in read_events(path) if r["event"] == "close_lot"]) == 1
    with journal_mutation_transaction(path):
        assert open_lot(observation, level="L1", paper_notional_dollars=50,
                        fill_price=buy["ask"], account_id="fixture-forward",
                        fee_bps_per_side=2, path=path)["lot_id"] == entry["lot_id"]
        assert close_lot(entry["lot_id"], exit_price=sell["bid"],
                         reason="DISPOSABLE_FIXTURE_EXIT", path=path)["event_id"] == close["event_id"]
    assert len([r for r in read_events(path) if r["event"] == "open_lot"]) == 1


def test_disposable_transaction_rejects_stale_quote_before_journal_write(tmp_path):
    path = tmp_path / "isolated-forward.jsonl"
    now = datetime(2026, 11, 6, 20, tzinfo=UTC)
    with journal_mutation_transaction(path):
        initialize_paper_account(account_id="fixture-forward", opening_cash=1000,
                                 fee_bps_per_side=2, data_provenance="FORWARD_COLLECTION", path=path)
        before = path.read_bytes()
        with pytest.raises(ValueError, match="PROVIDER_QUOTE_STALE_OR_FUTURE"):
            validate_stock_iex_quote(_quote(datetime(2026, 11, 6, 19, tzinfo=UTC),
                                            "99.99", "100"), symbol="MSFT", now=now)
        assert path.read_bytes() == before
