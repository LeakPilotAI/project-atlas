from app.investment.integrity import audit_observation, is_validation_eligible


def _row():
    return {
        "observation_id": "o1",
        "symbol": "MSFT",
        "as_of": "2026-09-10T14:00:00+00:00",
        "timestamp": "2026-09-10T14:00:00+00:00",
        "look_ahead_protected": True,
        "known_at": {
            "price_effective": "2026-09-10T13:59:00+00:00",
            "price_retrieved": "2026-09-10T13:59:30+00:00",
            "fundamentals_retrieved": "2026-09-10T13:00:00+00:00",
            "valuation_retrieved": "2026-09-10T13:00:00+00:00",
            "history_cutoff": "2026-09-10",
        },
        "outcomes": {"1d": None, "5d": None, "20d": None, "60d": None, "252d": None},
    }


def test_clean_point_in_time_row_is_validation_eligible():
    row = _row()
    audit = audit_observation(row)
    assert audit["validation_eligible"] is True
    assert audit["lookahead"] is False
    assert is_validation_eligible(row) is True


def test_future_retrieval_timestamp_is_quarantined_not_rewritten():
    row = _row()
    original = row["known_at"]["price_retrieved"]
    row["known_at"]["price_retrieved"] = "2026-09-10T14:01:00+00:00"
    audit = audit_observation(row)
    assert audit["validation_eligible"] is False
    assert audit["lookahead"] is True
    assert is_validation_eligible(row) is False
    assert row["known_at"]["price_retrieved"] == "2026-09-10T14:01:00+00:00"
    assert original != row["known_at"]["price_retrieved"]


def test_missing_lineage_is_quarantined_instead_of_assumed_safe():
    row = _row()
    row["known_at"] = {}
    audit = audit_observation(row)
    assert audit["validation_eligible"] is False
    assert audit["reconstructable"] is False
    assert is_validation_eligible(row) is False
