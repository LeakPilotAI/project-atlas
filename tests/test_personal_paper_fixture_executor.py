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


def test_rule_driven_disposable_session_takes_profit_and_reconciles(tmp_path):
    from datetime import UTC, datetime, timedelta
    from app.services.personal_paper_fixture_executor import rehearse_disposable_rule_driven_session as run
    start = datetime(2026, 11, 7, tzinfo=UTC)
    times = [start + timedelta(seconds=i) for i in range(5)]
    def q(t, bid, ask):
        return {"symbol": "MSFT", "state": "FRESH", "bid": bid, "ask": ask,
                "bid_lots": 5, "ask_lots": 5, "timestamp": t.isoformat(),
                "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP"}
    quotes = [q(t, b, a) for t, b, a in zip(times,
        (99.9, 99.9, 101, 104, 105), (100, 100, 101.1, 104.1, 105.1))]
    path = tmp_path / "rules.jsonl"
    initialize_paper_account(account_id="rules", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="TEST_DATA", path=path)
    obs = {"observation_id": "rules-1", "symbol": "MSFT", "evidence_class": "TEST_DATA"}
    args = dict(path=path, account_id="rules", observation=obs, quotes=quotes,
                times=times, entry_signals=[False, True, False, False, True])
    result = run(**args)
    assert [x["action"] for x in result["actions"]] == ["WAIT", "ENTER", "MARK", "EXIT", "WAIT"]
    assert result["actions"][3]["reason"] == "SYNTHETIC_TAKE_PROFIT"
    assert result["net_realized_pnl"] > 0
    assert result["open_positions"] == 0 and result["cash_reconciled"]
    assert result["forward_trading_authorized"] is False
    assert len([e for e in read_events(path) if e["event"] == "open_lot"]) == 1
    before = path.read_bytes()
    with pytest.raises(ValueError, match="REPLAYED_QUOTE"):
        run(**{**args, "quotes": [quotes[0], quotes[1], quotes[1], quotes[3], quotes[4]]})
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="TEST_DATA_BOUNDED_REQUIRED"):
        run(**{**args, "entry_signals": [True]})
    assert path.read_bytes() == before
    forward = tmp_path / "forward-rules.jsonl"
    initialize_paper_account(account_id="forward", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="FORWARD_COLLECTION", path=forward)
    before_forward = forward.read_bytes()
    with pytest.raises(ValueError, match="REFUSES_FORWARD_ACCOUNT"):
        run(**{**args, "path": forward, "account_id": "forward"})
    assert forward.read_bytes() == before_forward

def test_rule_driven_disposable_session_stop_loss_and_end_flat(tmp_path):
    from datetime import UTC, datetime, timedelta
    from app.services.personal_paper_fixture_executor import rehearse_disposable_rule_driven_session as run
    start = datetime(2026, 11, 7, tzinfo=UTC)
    times = [start + timedelta(seconds=i) for i in range(3)]
    def q(t, bid):
        return {"symbol": "MSFT", "state": "FRESH", "bid": bid, "ask": bid+0.1,
                "bid_lots": 5, "ask_lots": 5, "timestamp": t.isoformat(),
                "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP"}
    obs = {"observation_id": "risk-1", "symbol": "MSFT", "evidence_class": "TEST_DATA"}
    for name, prices, reason in (("stop", [100, 97, 96], "SYNTHETIC_STOP_LOSS"),
                                 ("end", [100, 100, 100], "SYNTHETIC_SESSION_END")):
        path = tmp_path / (name+".jsonl")
        initialize_paper_account(account_id=name, opening_cash=1000,
                                 fee_bps_per_side=2, data_provenance="TEST_DATA", path=path)
        result = run(path=path, account_id=name, observation=obs,
                     quotes=[q(t, b) for t, b in zip(times, prices)], times=times,
                     entry_signals=[True, False, False])
        assert result["actions"][-1]["reason"] == ("SESSION_ALREADY_CLOSED" if name == "stop" else reason)
        assert result["open_positions"] == 0
        assert result["net_realized_pnl"] < 0
