from app.services.v6_maturity_sequence_stability import _classify,maturity_sequence_stability_diagnostics


def test_classify_sequence_patterns():
    assert _classify([])=="INSUFFICIENT_HISTORY"
    assert _classify(["PERSISTED"] )=="INSUFFICIENT_HISTORY"
    assert _classify(["PERSISTED","PERSISTED"])=="REPEATED_OUTCOME"
    assert _classify(["PERSISTED","REVERSED","PERSISTED"])=="ALTERNATING_PATTERN"
    assert _classify(["PERSISTED","REVERSED","REVERSED"])=="MIXED_SEQUENCE"


def test_maturity_sequence_stability_missing_files_fail_closed(tmp_path):
    r=maturity_sequence_stability_diagnostics(membership_path=tmp_path/"m",history_path=tmp_path/"h")
    assert r["candidates"]=={}
    assert r["duplicate_refreshes_skipped"]==0
    assert r["automatic_scoring"] is False
    assert r["weighted_scoring"] is False
    assert r["readiness_percentage"] is None
    assert r["trading_readiness"]=="NOT_READY"
    assert r["live_capital_allowed"] is False
    assert r["automatic_real_money_execution"] is False
