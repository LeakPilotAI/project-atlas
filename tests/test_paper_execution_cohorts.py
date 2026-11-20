from app.services.paper_execution_cohorts import execution_model_cohorts


def event(tid, kind, version=None, **values):
    return {"trade_id": tid, "event": kind, "timestamp": "2026-09-20T12:00:00Z",
            "features": {"paper_execution_model_version": version} if version else {}, **values}


def test_versions_legacy_zero_losses_and_unknown_are_separate():
    rows = [event("a", "open", "v2"), event("a", "close", net_pnl_r=-2),
            event("b", "close", "v2", net_pnl_r=1),
            event("c", "close", "v2", net_pnl_r=0, R_multiple=99, result="BE"),
            event("d", "open", "v1"), event("old", "close", net_pnl_r=-9),
            event("e", "close", "v2"), event("f", "close", "v2", result="INTERRUPTED", net_pnl_r=0)]
    report = execution_model_cohorts(rows)
    cohorts = {row["paper_execution_model_version"]: row for row in report["cohorts"]}
    current = cohorts["v2"]
    assert current["trade_count"] == 5
    assert current["closed_count"] == 5
    assert current["resolved_count"] == 3
    assert current["unknown_result_count"] == current["interrupted_count"] == 1
    assert current["wins"] == current["losses"] == current["scratches"] == 1
    assert current["total_r"] == -1
    assert current["median_r"] == 0
    assert current["max_drawdown_r"] == 2
    assert cohorts["UNKNOWN/legacy"]["total_r"] == -9
    assert cohorts["v1"]["open_count"] == 1
    assert cohorts["v1"]["total_r"] is None


def test_test_diagnostic_duplicates_and_conflicts_stay_out_of_results():
    close = event("real", "close", "v2", net_pnl_r=-1)
    rows = [event("test", "open", "v2", trade_type="TEST"), event("test", "close", "v2", net_pnl_r=500),
            event("diag", "close", "v2", evidence_class="DIAGNOSTIC", net_pnl_r=500),
            close, close.copy(), event("conflict", "close", "v2", net_pnl_r=1),
            event("conflict", "close", "v2", net_pnl_r=-1)]
    result = execution_model_cohorts(rows)
    assert result["excluded_test_diagnostic_trades"] == 2
    cohort = result["cohorts"][0]
    assert cohort["trade_count"] == 2
    assert cohort["total_r"] == -1
    assert cohort["conflicting_close_count"] == 1
    assert cohort["unknown_result_count"] == 1


def test_missing_dates_and_nonfinite_results_are_unknown():
    result = execution_model_cohorts([event("x", "close", net_pnl_r=1, timestamp=None),
                                      event("y", "close", net_pnl_r=float("nan"))])
    assert result["cohorts"][0]["max_drawdown_r"] is None
    assert result["cohorts"][0]["unknown_result_count"] == 1
