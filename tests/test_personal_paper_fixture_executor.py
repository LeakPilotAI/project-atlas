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


def test_disposable_validated_quote_to_journal_spread_slippage_and_restart(tmp_path):
    from datetime import UTC, datetime, timedelta
    from app.services.personal_paper_fixture_executor import execute_disposable_validated_quote_step
    now = datetime(2026, 11, 7, tzinfo=UTC)
    path = tmp_path / "quote-test.jsonl"
    initialize_paper_account(account_id="quote", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="TEST_DATA", path=path)
    observation = {"observation_id": "quote-1", "symbol": "MSFT",
                   "evidence_class": "TEST_DATA"}
    args = dict(path=path, account_id="quote", observation=observation, now=now)
    def quote(bid, ask, stamp=now):
        return {"symbol": "MSFT", "state": "FRESH", "bid": bid, "ask": ask,
                "bid_lots": 5, "ask_lots": 5, "timestamp": stamp.isoformat(),
                "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP"}
    before = path.read_bytes()
    with pytest.raises(ValueError, match="PROVIDER_QUOTE_STALE_OR_FUTURE"):
        execute_disposable_validated_quote_step(**args, action="ENTER",
            quote=quote("99.99", "100", now-timedelta(minutes=1)))
    assert path.read_bytes() == before
    entry = execute_disposable_validated_quote_step(**args, action="ENTER",
        quote=quote("99.99", "100"), slippage_bps=10)
    assert entry["simulated_execution_price"] == 100.1
    assert entry["provider_authenticated"] is False
    mark = execute_disposable_validated_quote_step(**args, action="MARK",
        quote=quote("99.99", "100"), slippage_bps=10)
    assert mark["simulated_execution_price"] == 99.89001
    close = execute_disposable_validated_quote_step(**args, action="EXIT",
        quote=quote("99.99", "100"), slippage_bps=10)
    assert close["simulated_execution_price"] == 99.89001
    assert close["net_realized_pnl"] < 0
    assert accounting_snapshot(read_events(path), account_id="quote")["open_positions"] == 0
    forward_observation = {**observation, "evidence_class": "FORWARD_COLLECTION"}
    after = path.read_bytes()
    with pytest.raises(ValueError, match="TEST_DATA_ONLY"):
        execute_disposable_validated_quote_step(**{**args, "observation": forward_observation},
            action="ENTER", quote=quote("99.99", "100"))
    assert path.read_bytes() == after


def test_bounded_disposable_quote_lifecycle_validates_sequence_before_writes(tmp_path):
    from datetime import UTC, datetime, timedelta
    from app.services.personal_paper_fixture_executor import rehearse_disposable_quote_lifecycle
    path = tmp_path / "lifecycle.jsonl"
    initialize_paper_account(account_id="life", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="TEST_DATA", path=path)
    observation = {"observation_id": "life-1", "symbol": "MSFT",
                   "evidence_class": "TEST_DATA"}
    start = datetime(2026, 11, 7, tzinfo=UTC)
    times = [start + timedelta(seconds=i) for i in range(3)]
    def quote(stamp, bid, ask):
        return {"symbol": "MSFT", "state": "FRESH", "bid": bid, "ask": ask,
                "bid_lots": 5, "ask_lots": 5, "timestamp": stamp.isoformat(),
                "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP"}
    quotes = [quote(times[0], "99.99", "100"),
              quote(times[1], "100.99", "101"),
              quote(times[2], "101.99", "102")]
    args = dict(path=path, account_id="life", observation=observation,
                times=times, slippage_bps=10)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="REPLAYED_QUOTE"):
        rehearse_disposable_quote_lifecycle(**args, quotes=[quotes[0], quotes[0], quotes[2]])
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="REPLAYED_QUOTE"):
        rehearse_disposable_quote_lifecycle(**args, quotes=[quotes[0], quotes[1], quote(times[0], "101.99", "102")])
    assert path.read_bytes() == before
    result = rehearse_disposable_quote_lifecycle(**args, quotes=quotes)
    assert result["completed"] == 3
    assert [r["action"] for r in result["steps"]] == ["ENTER", "MARK", "EXIT"]
    assert result["steps"][-1]["net_realized_pnl"] > 0
    assert accounting_snapshot(read_events(path), account_id="life")["open_positions"] == 0
    assert len([r for r in read_events(path) if r["event"] == "open_lot"]) == 1
    assert len([r for r in read_events(path) if r["event"] == "close_lot"]) == 1
