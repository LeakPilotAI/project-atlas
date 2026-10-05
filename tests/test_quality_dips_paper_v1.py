from pathlib import Path

import pytest

from app.investment.quality_dips_paper import (
    PAPER_POLICY_VERSION,
    execute_broker_order,
    open_lot,
    open_lots,
    read_events,
    record_decision,
)


def observation():
    return {
        "observation_id": "obs-2026-10-05-MSFT",
        "symbol": "MSFT",
        "price": 500.0,
        "source_timestamp": "2026-10-05T14:00:00+00:00",
        "classification": "ACCUMULATION",
        "evidence_class": "FORWARD_COLLECTION",
    }


def test_decision_and_lot_are_append_only_and_idempotent(tmp_path: Path):
    path = tmp_path / "quality_dips_paper.jsonl"
    first = record_decision(observation(), decision="PAPER_OPEN_L1", path=path)
    second = record_decision(observation(), decision="PAPER_OPEN_L1", path=path)
    assert first["event_id"] == second["event_id"]

    lot1 = open_lot(observation(), level="L1", paper_notional_dollars=100, path=path)
    lot2 = open_lot(observation(), level="L1", paper_notional_dollars=100, path=path)
    assert lot1["lot_id"] == lot2["lot_id"]
    assert lot1["side"] == "LONG"
    assert lot1["paper_policy_version"] == PAPER_POLICY_VERSION
    assert lot1["broker_order_created"] is False
    assert lot1["live_capital_allowed"] is False
    assert len(read_events(path)) == 2
    assert len(open_lots(read_events(path))) == 1


def test_paper_notional_is_required_and_never_inferred(tmp_path: Path):
    path = tmp_path / "quality_dips_paper.jsonl"
    with pytest.raises(ValueError):
        open_lot(observation(), level="L1", paper_notional_dollars=0, path=path)
    with pytest.raises(ValueError):
        open_lot(observation(), level="L1", paper_notional_dollars=None, path=path)
    assert read_events(path) == []


def test_only_quality_dips_levels_are_accepted(tmp_path: Path):
    with pytest.raises(ValueError):
        open_lot(
            observation(),
            level="SHORT",
            paper_notional_dollars=100,
            path=tmp_path / "journal.jsonl",
        )


def test_broker_execution_is_impossible():
    with pytest.raises(RuntimeError, match="PAPER ONLY"):
        execute_broker_order("MSFT", 1)
