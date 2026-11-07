"""Current QD analyst targets must not inherit collection timestamps."""
from app.investment.quality_dips_v2_runtime import _valuation_sources


def test_current_targets_refuse_collection_time_as_publication_time():
    row = {"symbol": "AVGO", "input_snapshot": {"valuation": {
        key: {"availability": True, "quality": "FRESH", "value": value,
              "retrieved_at": "2026-11-07T20:00:00+00:00"}
        for key, value in (("target_low_price", 400), ("target_mean_price", 500), ("target_high_price", 600))}}}
    assert _valuation_sources(row, current_only=True, allow_stored_evidence=False) == []
    for value in row["input_snapshot"]["valuation"].values():
        value["original_target_as_of_verified"] = True
        value["original_target_as_of"] = "2026-11-06"
    sources = _valuation_sources(row, current_only=True, allow_stored_evidence=False)
    assert len(sources) == 3
    assert all(s["as_of"] == "2026-11-06" for s in sources)
    row["input_snapshot"]["valuation"]["target_low_price"]["original_target_as_of_verified"] = False
    assert len(_valuation_sources(row, current_only=True, allow_stored_evidence=False)) == 2
