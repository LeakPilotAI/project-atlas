"""Disposable simulated journal integration; never production authority."""
from datetime import UTC, datetime

import pytest

from app.investment.quality_dips_paper import (
    accounting_snapshot, close_lot, initialize_paper_account, mark_lot, open_lot, read_events,
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


@pytest.mark.parametrize("fault", ["wrong_account", "wrong_provenance", "duplicate_entry", "orphan_close"])
def test_restarted_forward_account_rejects_corrupted_financial_journal(tmp_path, fault):
    """Restart must refuse contradictory durable events, never silently recover."""
    import json
    path = tmp_path / "corrupt.jsonl"
    initialize_paper_account(account_id="isolated-test", opening_cash=1000,
                             fee_bps_per_side=2, max_open_positions=1,
                             data_provenance="FORWARD_COLLECTION", path=path)
    obs = {"observation_id": "obs", "symbol": "MSFT", "evidence_class": "FORWARD_COLLECTION"}
    entry = open_lot(obs, level="L1", paper_notional_dollars=50,
                     fill_price=100, account_id="isolated-test", fee_bps_per_side=2, path=path)
    if fault == "wrong_account":
        entry = {**entry, "account_id": "another-account"}
    elif fault == "wrong_provenance":
        entry = {**entry, "data_provenance": "TEST_DATA"}
    elif fault == "orphan_close":
        entry = {"event": "close_lot", "lot_id": "missing-lot",
                 "account_id": "isolated-test", "data_provenance": "FORWARD_COLLECTION"}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry) + "\n")
    with pytest.raises(ValueError):
        accounting_snapshot(read_events(path), account_id="isolated-test")


def test_restarted_forward_account_rejects_truncated_journal(tmp_path):
    import json
    path = tmp_path / "truncated.jsonl"
    initialize_paper_account(account_id="isolated-test", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="FORWARD_COLLECTION", path=path)
    with path.open("a", encoding="utf-8") as stream:
        stream.write('{"event": "open_lot", "lot_id":')
    with pytest.raises(json.JSONDecodeError):
        read_events(path)


class _DisposableLease:
    snapshot = {"test": "proof"}
    def __init__(self, valid=True):
        self.valid = valid
    def check(self, proof):
        return self.valid
    def check_components(self, components):
        return self.valid


class _DisposableInstallation:
    def __init__(self, lease):
        self.test_lease = lease
    def lease(self, request):
        from contextlib import nullcontext
        return nullcontext(self.test_lease)


def test_lease_held_forward_journal_reconciliation_is_read_only(tmp_path, monkeypatch):
    from app.services import personal_paper_runtime
    from app.services.personal_paper_price_evidence import inspect_forward_paper_journal_under_lease
    monkeypatch.setattr(personal_paper_runtime, "checked_personal_installation",
                        lambda lease, request: lease.snapshot)
    path = tmp_path / "forward.jsonl"
    initialize_paper_account(account_id="forward", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="FORWARD_COLLECTION", path=path)
    original = path.read_bytes()
    result = inspect_forward_paper_journal_under_lease(
        installation=_DisposableInstallation(_DisposableLease()), request={"action": "AUTO_PAPER"},
        components=(), journal_path=path, account_id="forward")
    assert result["available_cash"] == 1000
    assert result["paper_fill_authorized"] is False
    assert path.read_bytes() == original


def test_lease_held_forward_journal_refuses_revoked_or_missing_account(tmp_path, monkeypatch):
    from app.services import personal_paper_runtime
    from app.services.personal_paper_price_evidence import (
        PriceEvidenceRejected, inspect_forward_paper_journal_under_lease,
    )
    monkeypatch.setattr(personal_paper_runtime, "checked_personal_installation",
                        lambda lease, request: lease.snapshot)
    path = tmp_path / "forward.jsonl"
    initialize_paper_account(account_id="forward", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="FORWARD_COLLECTION", path=path)
    for lease, account in [(_DisposableLease(False), "forward"),
                           (_DisposableLease(), "another")]:
        with pytest.raises(PriceEvidenceRejected):
            inspect_forward_paper_journal_under_lease(
                installation=_DisposableInstallation(lease), request={"action": "AUTO_PAPER"},
                components=(), journal_path=path, account_id=account)


def test_concurrent_same_process_open_lot_cannot_oversubscribe_account(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    path = tmp_path / "concurrent.jsonl"
    initialize_paper_account(account_id="forward", opening_cash=1000,
                             fee_bps_per_side=2, max_open_positions=1,
                             data_provenance="FORWARD_COLLECTION", path=path)
    barrier = Barrier(2)
    def attempt(index):
        barrier.wait(timeout=5)
        try:
            open_lot({"observation_id": f"obs-{index}", "symbol": "MSFT",
                      "evidence_class": "FORWARD_COLLECTION"},
                     level="L1", paper_notional_dollars=50, fill_price=100,
                     account_id="forward", fee_bps_per_side=2, path=path)
            return "opened"
        except ValueError as exc:
            return str(exc)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, range(2)))
    assert outcomes.count("opened") == 1
    assert any("open-position limit" in outcome for outcome in outcomes)
    assert accounting_snapshot(read_events(path), account_id="forward")["open_positions"] == 1


def test_exclusive_writer_refuses_second_process_and_recovers_after_exit(tmp_path):
    import os
    import subprocess
    import sys
    import time
    from app.investment.quality_dips_paper import _exclusive_journal_writer
    path = tmp_path / "multi-process.jsonl"
    ready = tmp_path / "ready.flag"
    child = ("from pathlib import Path; import time; "
             "from app.investment.quality_dips_paper import _exclusive_journal_writer; "
             f"p=Path({str(path)!r}); ready=Path({str(ready)!r}); "
             "\nwith _exclusive_journal_writer(p):\n ready.write_text('locked')\n time.sleep(8)\n")
    env = {**os.environ, "PYTHONPATH": str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'backend')}
    proc = subprocess.Popen([sys.executable, "-c", child], env=env)
    try:
        for _ in range(100):
            if ready.exists():
                break
            if proc.poll() is not None:
                pytest.fail("lock holder exited before ready")
            time.sleep(0.03)
        assert ready.exists(), "child failed to acquire writer lock"
        with pytest.raises(ValueError, match="WRITER_OWNED_BY_ANOTHER_PROCESS"):
            with _exclusive_journal_writer(path):
                pass
    finally:
        proc.kill()
        proc.wait(timeout=5)
    for attempt in range(50):
        try:
            with _exclusive_journal_writer(path):
                break  # Windows may briefly delay lock release after termination
        except ValueError:
            if attempt == 49:
                raise
            time.sleep(0.02)


def test_concurrent_account_initialization_has_one_durable_open(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    path = tmp_path / "account-init.jsonl"
    barrier = Barrier(2)
    def initialize(_):
        barrier.wait(timeout=5)
        return initialize_paper_account(account_id="forward", opening_cash=1000,
                                        fee_bps_per_side=2, max_open_positions=1,
                                        data_provenance="FORWARD_COLLECTION", path=path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(initialize, range(2)))
    assert records[0] == records[1]
    assert len([row for row in read_events(path) if row["event"] == "account_opened"]) == 1


def test_concurrent_mark_and_close_preserves_journal_order(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    path = tmp_path / "mark-close.jsonl"
    initialize_paper_account(account_id="forward", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="FORWARD_COLLECTION", path=path)
    opened = open_lot({"observation_id": "obs", "symbol": "MSFT",
                       "evidence_class": "FORWARD_COLLECTION"}, level="L1",
                      paper_notional_dollars=50, fill_price=100,
                      account_id="forward", fee_bps_per_side=2, path=path)
    barrier = Barrier(2)
    def act(action):
        barrier.wait(timeout=5)
        try:
            if action == "mark":
                mark_lot(opened["lot_id"], market_price=101, path=path)
            else:
                close_lot(opened["lot_id"], exit_price=102, reason="test", path=path)
            return "ok"
        except ValueError as exc:
            return str(exc)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(act, ("mark", "close")))
    assert outcomes[1] == "ok"
    events = read_events(path)
    close_idx = next(i for i, row in enumerate(events) if row["event"] == "close_lot")
    assert all(row["event"] != "mark_lot" for row in events[close_idx + 1:])
    assert accounting_snapshot(events, account_id="forward")["open_positions"] == 0
