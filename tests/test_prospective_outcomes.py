from datetime import datetime, timezone
from app.investment.bars import OhlcvBar
from app.investment.prospective_evidence import append_record, read_records
from app.investment.prospective_outcomes import outcome_for, refresh_outcomes


def observation():
    return {"observation_id": "one", "timestamp": "2026-01-01T15:00:00+00:00", "price": 100,
            "symbol": "ABC", "policy_version": "frozen", "execution_model_version": "no-fill",
            "evidence_class": "FORWARD_COLLECTION",
            "prediction": {"entry_ladder": {"levels": [{"level": "L1", "limit_price": 90}]}}}


def test_outcomes_exclude_observation_day_incomplete_and_future_bars():
    bars = [OhlcvBar("2026-01-01", high=999, low=1, close=900),
            OhlcvBar("2026-01-02", high=105, low=85, close=90),
            OhlcvBar("2026-01-03", high=999, low=1, close=900),
            OhlcvBar("2026-02-01", high=999, low=1, close=900)]
    row = outcome_for(observation(), bars, datetime(2026, 1, 3, tzinfo=timezone.utc))
    assert len(row["price_path"]) == 1
    assert round(row["measures"]["return_1d"], 5) == -0.1
    assert row["measures"]["return_5d"] is None
    assert row["target_interactions"][0]["status"] == "TOUCHED_NOT_ASSUMED_FILLED"
    assert row["result_r"] is None
    assert row["paper_fill"] == "UNKNOWN"


def test_outcome_revisions_preserve_observation_and_unknown_then_loss(tmp_path):
    observations = tmp_path / "observations.jsonl"
    outcomes = tmp_path / "outcomes.jsonl"
    append_record(observations, observation())
    before = observations.read_bytes()
    first = refresh_outcomes(observations, outcomes, lambda _: [])
    assert first[0]["status"] == "UNKNOWN"
    assert refresh_outcomes(observations, outcomes, lambda _: []) == []
    refresh_outcomes(observations, outcomes, lambda _: [OhlcvBar("2026-01-02", close=80, low=75, high=95)])
    assert len(read_records(outcomes)) == 2
    assert read_records(outcomes)[1]["measures"]["return_1d"] < 0
    assert observations.read_bytes() == before
