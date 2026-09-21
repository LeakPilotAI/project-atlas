from app.investment.prospective_evidence import append_record
from app.investment.prospective_report import evidence_report


def test_report_uses_original_matched_benchmark_and_preserves_loss(
    tmp_path, monkeypatch
):
    import app.investment.prospective_report as module

    monkeypatch.setattr(module, "FREEZES", tmp_path / "freezes.jsonl")
    observations = tmp_path / "obs.jsonl"
    outcomes = tmp_path / "out.jsonl"
    base = {
        "timestamp": "2026-01-01T12:00:00+00:00",
        "source_timestamp": "2026-01-01T11:00:00+00:00",
        "price": 100,
        "policy_version": "frozen",
        "execution_model_version": "no-fill",
        "evidence_class": "FORWARD_COLLECTION",
        "valuation": {},
        "classification": "WATCH",
    }
    for symbol, close in [("ABC", 90), ("SPY", 110)]:
        append_record(
            observations, {**base, "symbol": symbol, "observation_id": symbol}
        )
        append_record(
            outcomes,
            {
                "observation_id": symbol,
                "price_path": [{"date": "2026-01-02", "close": close}],
                "measures": {"return_1d": close / 100 - 1},
                "target_interactions": [],
            },
        )
    before = observations.read_bytes()
    report = evidence_report(observations, outcomes, benchmark_symbol="SPY")
    result = report["benchmark"]["comparisons"][0]
    assert not result["outperformed"]
    assert result["status"] == "THE_STRATEGY_DID_NOT_OUTPERFORM_THE_BENCHMARK"
    assert report["readiness"]["evidence"]["mature_20_session_outcomes"] == 0
    assert report["readiness"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert observations.read_bytes() == before


def test_report_does_not_pool_test_or_unmatched_benchmark(tmp_path, monkeypatch):
    import app.investment.prospective_report as module

    monkeypatch.setattr(module, "FREEZES", tmp_path / "freezes.jsonl")
    observations = tmp_path / "obs.jsonl"
    outcomes = tmp_path / "out.jsonl"
    append_record(observations, {"evidence_class": "TEST", "symbol": "ABC"})
    report = evidence_report(observations, outcomes)
    assert report["observation_count"] == 0
    assert report["benchmark"]["comparisons"] == []
