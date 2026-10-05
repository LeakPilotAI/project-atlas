from pathlib import Path

import pytest

from app.investment.quality_dips_paper import (
    PAPER_POLICY_VERSION,
    execute_broker_order,
    open_lot,
    open_lots,
    mirror_forward_observation,
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



def forward_observation(*, state="ACCUMULATION", reached=("L1",)):
    row = observation()
    row.update(
        {
            "strategy_version": "QUALITY_DIPS_V3",
            "policy_version": "quality-dips-v3-mos-15-20-25-30-v1",
            "prediction": {
                "entry_ladder": {
                    "ready": True,
                    "levels": [
                        {"level": level, "reached": level in reached}
                        for level in ("L1", "L2", "L3", "L4")
                    ],
                }
            },
            "classification": state,
        }
    )
    return row


def test_mirror_opens_only_levels_reached_in_frozen_forward_observation(tmp_path: Path):
    path = tmp_path / "quality_dips_paper.jsonl"
    row = forward_observation(reached=("L1", "L2"))
    result = mirror_forward_observation(row, path=path)
    assert [lot["level"] for lot in result["opened_lots"]] == ["L1", "L2"]
    assert all(lot["paper_notional_dollars"] == 100.0 for lot in result["opened_lots"])
    assert all(lot["fill_price"] == row["price"] for lot in result["opened_lots"])
    again = mirror_forward_observation(row, path=path)
    assert [lot["lot_id"] for lot in again["opened_lots"]] == [
        lot["lot_id"] for lot in result["opened_lots"]
    ]
    assert len(read_events(path)) == 3


def test_mirror_records_no_fill_without_inventing_position(tmp_path: Path):
    path = tmp_path / "quality_dips_paper.jsonl"
    row = forward_observation(state="WATCH", reached=())
    result = mirror_forward_observation(row, path=path)
    assert result["opened_lots"] == []
    assert result["decision"]["decision"] == "PAPER_NO_FILL"
    assert open_lots(read_events(path)) == []


def test_mirror_rejects_non_forward_or_wrong_policy_evidence(tmp_path: Path):
    path = tmp_path / "quality_dips_paper.jsonl"
    row = forward_observation()
    row["evidence_class"] = "HISTORICAL_IMMUTABLE"
    with pytest.raises(ValueError, match="FORWARD_COLLECTION"):
        mirror_forward_observation(row, path=path)
    row = forward_observation()
    row["policy_version"] = "future-policy"
    with pytest.raises(ValueError, match="policy_version"):
        mirror_forward_observation(row, path=path)
    assert read_events(path) == []
