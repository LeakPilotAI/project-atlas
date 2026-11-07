"""Real disposable journal entry/mark/exit orchestration; never forward trading."""
import pytest

from app.investment.quality_dips_paper import (
    initialize_paper_account, read_events, accounting_snapshot,
)
from app.services.personal_paper_fixture_executor import execute_disposable_test_paper_step as step


def test_disposable_execution_entry_mark_exit_restart_and_forward_refusal(tmp_path):
    path = tmp_path / "test-only.jsonl"
    account_id = "disposable"
    observation = {"observation_id": "fixture-1", "symbol": "MSFT",
                   "evidence_class": "TEST_DATA"}
    initialize_paper_account(account_id=account_id, opening_cash=1000,
                             fee_bps_per_side=2, max_open_positions=1,
                             data_provenance="TEST_DATA", path=path)
    args = dict(path=path, account_id=account_id, observation=observation)
    entry = step(**args, action="ENTER", price=100)
    assert entry["open_positions"] == 1
    assert entry["simulated_execution_price"] == 100.02
    assert entry["slippage_bps"] == 2
    assert entry["forward_trading_authorized"] is False
    with pytest.raises(ValueError, match="POSITION_ALREADY_OPEN"):
        step(**args, action="ENTER", price=100)
    mark = step(**args, action="MARK", price=102)
    assert mark["open_positions"] == 1
    assert mark["simulated_execution_price"] == 101.9796
    exit_event = step(**args, action="EXIT", price=102)
    assert exit_event["open_positions"] == 0
    assert exit_event["simulated_execution_price"] == 101.9796
    assert exit_event["net_realized_pnl"] > 0
    assert len([r for r in read_events(path) if r["event"] == "open_lot"]) == 1
    assert len([r for r in read_events(path) if r["event"] == "close_lot"]) == 1
    assert accounting_snapshot(read_events(path), account_id=account_id)["cash_reconciled"]
    with pytest.raises(ValueError, match="SINGLE_POSITION_REQUIRED"):
        step(**args, action="EXIT", price=102)
    forward = tmp_path / "forward.jsonl"
    initialize_paper_account(account_id="forward", opening_cash=1000,
                             fee_bps_per_side=2, max_open_positions=1,
                             data_provenance="FORWARD_COLLECTION", path=forward)
    before = forward.read_bytes()
    with pytest.raises(ValueError, match="REFUSES_FORWARD_ACCOUNT"):
        step(path=forward, account_id="forward", observation=observation,
             action="ENTER", price=100)
    assert forward.read_bytes() == before


def test_disposable_slippage_refuses_invalid_and_never_improves_execution(tmp_path):
    path = tmp_path / "slippage.jsonl"
    initialize_paper_account(account_id="cost", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="TEST_DATA", path=path)
    observation = {"observation_id": "cost-fixture", "symbol": "MSFT",
                   "evidence_class": "TEST_DATA"}
    args = dict(path=path, account_id="cost", observation=observation)
    before = path.read_bytes()
    for bad in (-1, 101, "nan", "Infinity", "oops"):
        with pytest.raises(ValueError, match="SLIPPAGE_INVALID"):
            step(**args, action="ENTER", price=100, slippage_bps=bad)
    assert path.read_bytes() == before
    entry = step(**args, action="ENTER", price=100, slippage_bps=10)
    assert entry["simulated_execution_price"] == 100.1
    closed = step(**args, action="EXIT", price=100, slippage_bps=10)
    assert closed["simulated_execution_price"] == 99.9
    assert closed["net_realized_pnl"] < 0
