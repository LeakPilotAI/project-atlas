"""Disposable simulated journal integration; never production authority."""
from datetime import UTC, datetime

import pytest

from app.investment.quality_dips_paper import (
    accounting_snapshot, close_lot, initialize_paper_account, open_lot, read_events,
)
from app.services.personal_paper_price_evidence import (
    PriceEvidenceRejected, preview_current_stock_order,
    preview_quality_dips_account_capacity,
)


def _quote(now):
    return {"symbol": "MSFT", "state": "FRESH", "bid": "99.99", "ask": "100",
            "bid_lots": 10, "ask_lots": 10, "timestamp": now.isoformat(),
            "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP"}


def test_disposable_forward_journal_entry_exit_restart_and_idempotency(tmp_path):
    """Exercise existing journal writer only under explicit disposable test fixtures."""
    path = tmp_path / "disposable-paper.jsonl"
    initialize_paper_account(account_id="isolated-test", opening_cash=1000,
                             fee_bps_per_side=2, max_open_positions=1,
                             data_provenance="FORWARD_COLLECTION", path=path)
    now = datetime(2026, 11, 6, 20, tzinfo=UTC)
    proposal = preview_current_stock_order(_quote(now), symbol="MSFT", now=now,
                                           side="BUY", quantity="0.5", max_notional="100")
    capacity = preview_quality_dips_account_capacity(
        proposal, journal_events=read_events(path), account_id="isolated-test")
    assert capacity["blockers"] == []
    # The disposable fixture explicitly invokes the existing journal writer;
    # the preview itself does not and cannot grant that authority.
    observation = {"observation_id": "test-obs", "symbol": "MSFT",
                   "evidence_class": "FORWARD_COLLECTION"}
    entry = open_lot(observation, level="L1", paper_notional_dollars=50,
                     fill_price=proposal["reference_price"], account_id="isolated-test",
                     fee_bps_per_side=2, path=path)
    assert open_lot(observation, level="L1", paper_notional_dollars=50,
                    fill_price=proposal["reference_price"], account_id="isolated-test",
                    fee_bps_per_side=2, path=path)["lot_id"] == entry["lot_id"]
    snapshot = accounting_snapshot(read_events(path), account_id="isolated-test")
    assert snapshot["open_positions"] == 1
    assert snapshot["available_cash"] < 950
    capacity = preview_quality_dips_account_capacity(
        proposal, journal_events=read_events(path), account_id="isolated-test")
    assert "PAPER_POSITION_LIMIT" in capacity["blockers"]
    with pytest.raises(ValueError, match="open-position limit"):
        open_lot({**observation, "observation_id": "another"}, level="L1",
                 paper_notional_dollars=50, fill_price=100,
                 account_id="isolated-test", fee_bps_per_side=2, path=path)
    closed = close_lot(entry["lot_id"], exit_price=101, reason="DISPOSABLE_TEST", path=path)
    assert close_lot(entry["lot_id"], exit_price=101, reason="DISPOSABLE_TEST",
                     path=path)["event_id"] == closed["event_id"]
    # Re-read from disk as a fresh process would, then reconcile the ledger.
    recovered = accounting_snapshot(read_events(path), account_id="isolated-test")
    assert recovered["open_positions"] == 0
    assert recovered["cash_reconciled"] is True
    assert recovered["net_realized_pnl"] > 0
    assert len([e for e in read_events(path) if e["event"] == "open_lot"]) == 1
    assert len([e for e in read_events(path) if e["event"] == "close_lot"]) == 1


def test_disposable_journal_rejects_wrong_account_provenance(tmp_path):
    path = tmp_path / "isolated.jsonl"
    initialize_paper_account(account_id="paper-a", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="FORWARD_COLLECTION", path=path)
    with pytest.raises(ValueError):
        open_lot({"observation_id": "test", "symbol": "MSFT", "evidence_class": "TEST_DATA"},
                 level="L1", paper_notional_dollars=50, fill_price=100,
                 account_id="paper-a", fee_bps_per_side=2, path=path)
    assert accounting_snapshot(read_events(path), account_id="paper-a")["open_positions"] == 0
