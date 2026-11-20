from app.investment.freshness_proof import build_freshness_proof


def _readiness(ok=True):
    names = (
        "provider_reliability",
        "fundamental_completeness",
        "valuation_completeness",
        "historical_price_coverage",
        "point_in_time_integrity",
        "look_ahead",
    )
    return {
        "status": "READY FOR RESEARCH" if ok else "COLLECTING",
        "checks": {name: {"ok": ok, "detail": name} for name in names},
    }


def test_freshness_proof_projects_existing_quality_gates_without_live_unlock():
    proof = build_freshness_proof(_readiness(True))
    assert proof["domain"] == "EQUITY_INVESTMENT"
    assert proof["mode"] == "DATA_QUALITY_ONLY"
    assert proof["quality_gate_passed"] is True
    assert proof["failed_checks"] == []
    assert proof["strategy_frozen"] is True
    assert proof["live_capital_allowed"] is False


def test_freshness_proof_fails_closed_when_quality_check_is_missing():
    readiness = _readiness(True)
    del readiness["checks"]["valuation_completeness"]
    proof = build_freshness_proof(readiness)
    assert proof["quality_gate_passed"] is False
    assert "valuation_completeness" in proof["failed_checks"]
    assert proof["checks"]["valuation_completeness"]["detail"] == "check unavailable"


def test_freshness_proof_does_not_treat_dataset_readiness_as_edge():
    proof = build_freshness_proof(_readiness(True))
    assert "does not establish predictive edge" in proof["note"]
    assert proof["live_capital_allowed"] is False
