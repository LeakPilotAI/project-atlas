from app.investment.quality_dips_v3_alerts import freeze_v3_entry_snapshot, format_v3_alert


def test_freeze_v3_entry_snapshot_is_manual_and_deep_copies():
    plan = {"symbol":"MSFT","patient_state":"ACCUMULATION","entry_ladder":{"levels":[{"level":"L1","limit_price":100}]}}
    snap = freeze_v3_entry_snapshot(
        symbol="MSFT",
        event={"event_type":"ENTRY_LEVEL_REACHED","level":"L1","limit_price":100},
        plan=plan,
    )
    plan["patient_state"] = "WATCH"
    assert snap["v3_plan_snapshot"]["patient_state"] == "ACCUMULATION"
    assert snap["level"] == "L1"
    assert snap["entry_limit_price"] == 100
    assert snap["execution"] == "MANUAL_ONLY"
    assert snap["automatic_real_money_execution"] is False


def test_format_v3_alert_is_explicitly_non_executional():
    msg = format_v3_alert(
        {"event_type":"ENTRY_LEVEL_REACHED","symbol":"MSFT","level":"L1","limit_price":100},
        {"symbol":"MSFT","patient_state":"ACCUMULATION","fair_value_anchor":120,"discount_to_fair_value_pct":16.7},
    )
    assert "ENTRY_LEVEL_REACHED" in msg
    assert "MANUAL RESEARCH ONLY" in msg
    assert "No brokerage order was placed" in msg
