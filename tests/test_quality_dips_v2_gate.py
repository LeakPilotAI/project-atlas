from datetime import datetime, timezone

from app.investment.quality_dips_v2_gate import evaluate_v2_gate

NOW = datetime(2026, 9, 17, tzinfo=timezone.utc)


def _base():
    return {
        "symbol": "MSFT",
        "timestamp": "2026-09-10T00:00:00+00:00",
        "evidence_quality": "HIGH",
        "thesis": "INTACT",
        "thesis_intact": True,
        "value_trap": False,
        "missing_v2_evidence": [],
        "trend": {
            "short_term": "UP",
            "intermediate_term": "UP",
            "long_term": "UP",
            "as_of": "2026-09-16T00:00:00+00:00",
        },
    }


def test_passes_fresh_intact_evidence():
    out = evaluate_v2_gate(_base(), now=NOW)
    assert out["gate_passed"] is True
    assert out["status"] == "ELIGIBLE_FOR_V2_CLASSIFICATION"
    assert out["execution"] == "MANUAL_ONLY"
    assert out["live_capital_allowed"] is False
    assert out["automatic_real_money_execution"] is False


def test_broken_thesis_blocks():
    row = _base()
    row["thesis"] = "BROKEN"
    row["thesis_intact"] = False
    out = evaluate_v2_gate(row, now=NOW)
    assert out["gate_passed"] is False
    assert any("thesis integrity failed" in x for x in out["blockers"])


def test_value_trap_blocks():
    row = _base()
    row["value_trap"] = True
    out = evaluate_v2_gate(row, now=NOW)
    assert out["gate_passed"] is False
    assert any("value-trap" in x for x in out["blockers"])


def test_missing_required_evidence_blocks():
    row = _base()
    row["missing_v2_evidence"] = ["base_normalization_value"]
    out = evaluate_v2_gate(row, now=NOW)
    assert out["gate_passed"] is False
    assert any("required V2 evidence missing" in x for x in out["blockers"])


def test_stale_research_blocks():
    row = _base()
    row["timestamp"] = "2026-06-01T00:00:00+00:00"
    out = evaluate_v2_gate(row, now=NOW)
    assert out["gate_passed"] is False
    assert any("research evidence stale" in x for x in out["blockers"])


def test_missing_research_timestamp_blocks():
    row = _base()
    row["timestamp"] = None
    out = evaluate_v2_gate(row, now=NOW)
    assert out["gate_passed"] is False
    assert "research timestamp unavailable" in out["blockers"]


def test_stale_trend_is_caution_not_thesis_breaker():
    row = _base()
    row["trend"]["as_of"] = "2026-08-01T00:00:00+00:00"
    out = evaluate_v2_gate(row, now=NOW)
    assert out["gate_passed"] is True
    assert any("trend evidence older" in x for x in out["cautions"])


def test_bearish_trend_alone_does_not_break_thesis():
    row = _base()
    row["trend"]["short_term"] = "DOWN"
    row["trend"]["intermediate_term"] = "BEARISH"
    out = evaluate_v2_gate(row, now=NOW)
    assert out["gate_passed"] is True
    assert any("trend alone is not thesis failure" in x for x in out["cautions"])
