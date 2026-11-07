"""Incremental TEST_DATA execution against the actual durable journal."""
from datetime import UTC, datetime, timedelta

import pytest

from app.investment.quality_dips_paper import initialize_paper_account
from app.services.disposable_v3_incremental import (
    execute_incremental_test_v3_tick, inspect_incremental_test_v3_recovery)


def test_incremental_v3_entry_mark_exit_restarts_from_journal(tmp_path):
    path = tmp_path / "paper.jsonl"
    initialize_paper_account(account_id="demo", opening_cash=1000,
                             fee_bps_per_side=2, max_open_positions=1,
                             data_provenance="TEST_DATA", path=path)
    start = datetime(2026, 11, 7, tzinfo=UTC)
    research = {"symbol": "MSFT", "source_verified": True,
                "timestamp": start.isoformat(),
                "normalization_value": {"conservative": 95, "base": 100, "optimistic": 105},
                "quality_score": 80, "fundamentals_score": 80,
                "valuation_score": 70, "drawdown_percentile": 80,
                "evidence_quality": "HIGH", "thesis": "INTACT", "value_trap": False}
    observation = {"observation_id": "incremental-test", "symbol": "MSFT",
                   "evidence_class": "TEST_DATA"}
    actions = []
    for i, (bid, ask) in enumerate([(101, 101.1), (79.9, 80), (80.9, 81), (84, 84.1)]):
        now = start + timedelta(seconds=i)
        quote = {"symbol": "MSFT", "state": "FRESH", "bid": bid, "ask": ask,
                 "bid_lots": 5, "ask_lots": 5, "timestamp": now.isoformat(),
                 "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP"}
        # Once a position is open, risk management must continue even if
        # the research input becomes stale or loses its entry provenance.
        tick_research = research if i < 2 else {**research, "source_verified": False}
        result = execute_incremental_test_v3_tick(
            path=path, account_id="demo", observation=observation,
            research=tick_research, quote=quote, now=now)
        actions.append(result["action"])
        assert result["cash_reconciled"] is True
        assert result["forward_trading_authorized"] is False
    assert actions == ["WAIT", "ENTER", "MARK", "EXIT"]
    assert result["open_positions"] == 0
    assert result["net_realized_pnl"] > 0
    from app.investment.quality_dips_paper import read_events
    ticks = [e for e in read_events(path) if e.get("event") == "v3_tick_completed"]
    assert len(ticks) == 4
    report = inspect_incremental_test_v3_recovery(path=path, account_id="demo")
    assert report["recovery_status"] == "CLEAN"
    assert report["completed_ticks"] == 4
    assert report["journal_mutated"] is False
    with pytest.raises(ValueError, match="REPLAYED_OR_OLDER_TICK"):
        execute_incremental_test_v3_tick(path=path, account_id="demo",
            observation=observation, research=research, quote=quote, now=now)



def test_incremental_v3_refuses_forward_evidence(tmp_path):
    with pytest.raises(ValueError, match="TEST_DATA_ONLY"):
        execute_incremental_test_v3_tick(path=tmp_path / "none", account_id="x",
                                         observation={"symbol": "MSFT", "evidence_class": "FORWARD_COLLECTION"},
                                         research={"symbol": "MSFT"}, quote={}, now=datetime.now(UTC))


def test_incremental_v3_interrupted_tick_blocks_unsafe_recovery(tmp_path):
    from app.investment.quality_dips_paper import _append
    path = tmp_path / "interrupted.jsonl"
    initialize_paper_account(account_id="demo", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="TEST_DATA", path=path)
    start = datetime(2026, 11, 7, tzinfo=UTC)
    _append({"event": "v3_tick_started", "event_id": "start-interrupted",
             "provider_timestamp": start.isoformat(), "account_id": "demo"}, path)
    research = {"symbol": "MSFT", "source_verified": True,
                "timestamp": start.isoformat(),
                "normalization_value": {"conservative": 95, "base": 100, "optimistic": 105},
                "quality_score": 80, "fundamentals_score": 80,
                "valuation_score": 70, "drawdown_percentile": 80,
                "evidence_quality": "HIGH", "thesis": "INTACT", "value_trap": False}
    quote = {"symbol": "MSFT", "state": "FRESH", "bid": 101, "ask": 101.1,
             "bid_lots": 5, "ask_lots": 5,
             "timestamp": (start + timedelta(seconds=1)).isoformat(),
             "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP"}
    with pytest.raises(ValueError, match="INTERRUPTED_TICK_REQUIRES_RECONCILIATION"):
        execute_incremental_test_v3_tick(path=path, account_id="demo",
            observation={"observation_id": "test", "symbol": "MSFT",
                         "evidence_class": "TEST_DATA"},
            research=research, quote=quote, now=start + timedelta(seconds=1))


def test_recovery_report_does_not_modify_interrupted_journal(tmp_path):
    from app.investment.quality_dips_paper import _append
    path = tmp_path / "interrupted.jsonl"
    initialize_paper_account(account_id="demo", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="TEST_DATA", path=path)
    _append({"event": "v3_tick_started", "event_id": "start-test",
             "provider_timestamp": "2026-11-07T00:00:00+00:00",
             "account_id": "demo"}, path)
    before = path.read_bytes()
    report = inspect_incremental_test_v3_recovery(path=path, account_id="demo")
    assert report["recovery_status"] == "BLOCKED_MANUAL_REVIEW"
    assert report["pending_tick_count"] == 1
    assert "INCOMPLETE_TICK" in report["anomalies"]
    assert report["automatic_recovery_authorized"] is False
    assert path.read_bytes() == before


def test_recovery_report_detects_orphan_completion(tmp_path):
    from app.investment.quality_dips_paper import _append
    path = tmp_path / "orphan.jsonl"
    initialize_paper_account(account_id="demo", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="TEST_DATA", path=path)
    _append({"event": "v3_tick_completed", "event_id": "done-orphan",
             "provider_timestamp": "2026-11-07T00:00:00+00:00",
             "account_id": "demo"}, path)
    report = inspect_incremental_test_v3_recovery(path=path, account_id="demo")
    assert "UNMATCHED_COMPLETION" in report["anomalies"]
    assert report["recovery_status"] == "BLOCKED_MANUAL_REVIEW"


def test_recovery_accepts_equivalent_timezone_instants(tmp_path):
    from app.investment.quality_dips_paper import _append
    path = tmp_path / "timezone.jsonl"
    initialize_paper_account(account_id="demo", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="TEST_DATA", path=path)
    _append({"event": "v3_tick_started", "event_id": "start-abc",
             "provider_timestamp": "2026-11-07T12:00:00+00:00",
             "account_id": "demo"}, path)
    _append({"event": "v3_tick_completed", "event_id": "done-abc",
             "provider_timestamp": "2026-11-07T06:00:00-06:00",
             "account_id": "demo", "action": "WAIT", "simulated_event_id": None}, path)
    report = inspect_incremental_test_v3_recovery(path=path, account_id="demo")
    assert report["recovery_status"] == "CLEAN"
    assert report["completed_ticks"] == 1


def test_recovery_detects_nonmonotonic_timestamps_across_offsets(tmp_path):
    from app.investment.quality_dips_paper import _append
    path = tmp_path / "order.jsonl"
    initialize_paper_account(account_id="demo", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="TEST_DATA", path=path)
    for digest, stamp in (("a", "2026-11-07T12:00:00+00:00"),
                          ("b", "2026-11-07T05:59:00-06:00")):
        _append({"event": "v3_tick_started", "event_id": "start-" + digest,
                 "provider_timestamp": stamp, "account_id": "demo"}, path)
        _append({"event": "v3_tick_completed", "event_id": "done-" + digest,
                 "provider_timestamp": stamp, "account_id": "demo"}, path)
    report = inspect_incremental_test_v3_recovery(path=path, account_id="demo")
    assert "DUPLICATE_OR_NONMONOTONIC_START" in report["anomalies"]
    assert report["recovery_status"] == "BLOCKED_MANUAL_REVIEW"


def test_incremental_v3_refuses_entry_when_research_not_verified(tmp_path):
    path = tmp_path / "unverified.jsonl"
    initialize_paper_account(account_id="demo", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="TEST_DATA", path=path)
    now = datetime(2026, 11, 7, tzinfo=UTC)
    research = {"symbol": "MSFT", "source_verified": False,
                "timestamp": now.isoformat(),
                "normalization_value": {"conservative": 95, "base": 100, "optimistic": 105},
                "quality_score": 80, "fundamentals_score": 80,
                "valuation_score": 70, "drawdown_percentile": 80,
                "evidence_quality": "HIGH", "thesis": "INTACT", "value_trap": False}
    quote = {"symbol": "MSFT", "state": "FRESH", "bid": 79.9, "ask": 80,
             "bid_lots": 5, "ask_lots": 5, "timestamp": now.isoformat(),
             "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP"}
    with pytest.raises(ValueError):
        execute_incremental_test_v3_tick(path=path, account_id="demo",
            observation={"observation_id": "test", "symbol": "MSFT",
                         "evidence_class": "TEST_DATA"},
            research=research, quote=quote, now=now)
    assert inspect_incremental_test_v3_recovery(path=path, account_id="demo")["completed_ticks"] == 0


def test_explicit_session_end_flattens_position_without_reentry(tmp_path):
    from scripts.observation_runtime.disposable_v3_incremental_demo import run_incremental_demo
    from app.investment.quality_dips_paper import read_events
    path = tmp_path / "session_end.jsonl"
    initialize_paper_account(account_id="demo", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="TEST_DATA", path=path)
    start = datetime(2026, 11, 7, tzinfo=UTC)
    research = {"symbol": "MSFT", "source_verified": True,
                "timestamp": start.isoformat(),
                "normalization_value": {"conservative": 95, "base": 100, "optimistic": 105},
                "quality_score": 80, "fundamentals_score": 80,
                "valuation_score": 70, "drawdown_percentile": 80,
                "evidence_quality": "HIGH", "thesis": "INTACT", "value_trap": False}
    observation = {"observation_id": "session-end", "symbol": "MSFT",
                   "evidence_class": "TEST_DATA"}
    actions = []
    for index, (bid, ask) in enumerate([(79.9, 80), (80, 80.1), (80, 80.1)]):
        now = start + timedelta(seconds=index)
        quote = {"symbol": "MSFT", "state": "FRESH", "bid": bid,
                 "ask": ask, "bid_lots": 5, "ask_lots": 5,
                 "timestamp": now.isoformat(),
                 "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP"}
        result = execute_incremental_test_v3_tick(
            path=path, account_id="demo", observation=observation,
            research=research, quote=quote, now=now,
            flatten_at_session_end=(index == 1))
        actions.append(result["action"])
    assert actions == ["ENTER", "EXIT", "WAIT"]
    assert result["open_positions"] == 0
    assert inspect_incremental_test_v3_recovery(path=path, account_id="demo")["recovery_status"] == "CLEAN"


def test_session_end_flag_must_be_explicit_boolean(tmp_path):
    with pytest.raises(ValueError, match="SESSION_END_FLAG_INVALID"):
        execute_incremental_test_v3_tick(path=tmp_path / "none", account_id="demo",
            observation={"symbol": "MSFT", "evidence_class": "TEST_DATA"},
            research={"symbol": "MSFT"}, quote={}, now=datetime.now(UTC),
            flatten_at_session_end="yes")


def test_incremental_refuses_completed_tick_without_matching_financial_write(tmp_path):
    from app.investment.quality_dips_paper import _append
    path = tmp_path / "tampered.jsonl"
    initialize_paper_account(account_id="demo", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="TEST_DATA", path=path)
    start = datetime(2026, 11, 7, tzinfo=UTC)
    for kind, ident in (("v3_tick_started", "start-abc"),
                        ("v3_tick_completed", "done-abc")):
        row = {"event": kind, "event_id": ident,
               "provider_timestamp": start.isoformat(), "account_id": "demo"}
        if kind == "v3_tick_completed":
            row.update(action="ENTER", simulated_event_id="missing")
        _append(row, path)
    research = {"symbol": "MSFT", "source_verified": True,
                "timestamp": start.isoformat(),
                "normalization_value": {"conservative": 95, "base": 100, "optimistic": 105},
                "quality_score": 80, "fundamentals_score": 80,
                "valuation_score": 70, "drawdown_percentile": 80,
                "evidence_quality": "HIGH", "thesis": "INTACT", "value_trap": False}
    now = start + timedelta(seconds=1)
    quote = {"symbol": "MSFT", "state": "FRESH", "bid": 79.9, "ask": 80,
             "bid_lots": 5, "ask_lots": 5, "timestamp": now.isoformat(),
             "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP"}
    before = path.read_bytes()
    report = inspect_incremental_test_v3_recovery(path=path, account_id="demo")
    assert "FINANCIAL_TICK_HISTORY_MISMATCH" in report["anomalies"]
    assert report["recovery_status"] == "BLOCKED_MANUAL_REVIEW"
    with pytest.raises(ValueError, match="FINANCIAL_TICK_HISTORY_MISMATCH"):
        execute_incremental_test_v3_tick(path=path, account_id="demo",
            observation={"observation_id": "test", "symbol": "MSFT",
                         "evidence_class": "TEST_DATA"},
            research=research, quote=quote, now=now)
    assert path.read_bytes() == before


def test_incremental_refuses_orphan_financial_write_after_completed_tick(tmp_path):
    from app.investment.quality_dips_paper import _append
    path = tmp_path / "orphan.jsonl"
    initialize_paper_account(account_id="demo", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="TEST_DATA", path=path)
    start = datetime(2026, 11, 7, tzinfo=UTC)
    _append({"event": "v3_tick_started", "event_id": "start-abc",
             "provider_timestamp": start.isoformat(), "account_id": "demo"}, path)
    _append({"event": "v3_tick_completed", "event_id": "done-abc",
             "provider_timestamp": start.isoformat(), "account_id": "demo",
             "action": "WAIT", "simulated_event_id": None}, path)
    _append({"event": "mark_lot", "event_id": "orphan",
             "account_id": "demo"}, path)
    research = {"symbol": "MSFT", "source_verified": True,
                "timestamp": start.isoformat(),
                "normalization_value": {"conservative": 95, "base": 100, "optimistic": 105},
                "quality_score": 80, "fundamentals_score": 80,
                "valuation_score": 70, "drawdown_percentile": 80,
                "evidence_quality": "HIGH", "thesis": "INTACT", "value_trap": False}
    now = start + timedelta(seconds=1)
    quote = {"symbol": "MSFT", "state": "FRESH", "bid": 79.9, "ask": 80,
             "bid_lots": 5, "ask_lots": 5, "timestamp": now.isoformat(),
             "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP"}
    before = path.read_bytes()
    report = inspect_incremental_test_v3_recovery(path=path, account_id="demo")
    assert "ACCOUNTING_REPLAY_REFUSED" in report["anomalies"]
    assert report["recovery_status"] == "BLOCKED_MANUAL_REVIEW"
    with pytest.raises(ValueError, match="ORPHAN_FINANCIAL_EVENT"):
        execute_incremental_test_v3_tick(path=path, account_id="demo",
            observation={"observation_id": "test", "symbol": "MSFT",
                         "evidence_class": "TEST_DATA"},
            research=research, quote=quote, now=now)
    assert path.read_bytes() == before
