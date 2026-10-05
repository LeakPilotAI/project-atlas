from datetime import datetime, timedelta, timezone
import json

from app.services.evidence_checkpoint_history import MAX_HISTORY, history_view, load_history, persist, previous_lanes
from app.services.cross_strategy_scorecard import build_cross_strategy_scorecard


def _report(sample=1):
    rows=[{"net_pnl_r": 0.5, "exit_timestamp": "2026-10-05T10:00:00+00:00"}] * sample
    return build_cross_strategy_scorecard(
        day_rows=rows,
        investment_snapshot={"summary": {"open_lots": 0, "closed_lots": 0}, "closed_lots": [], "timeline": []},
        prediction_snapshot={"summary": {"open_positions": 0, "closed_trades": 0}, "events": []},
    )


def test_checkpoint_history_is_telemetry_only_and_drives_movement_not_performance(tmp_path):
    path=tmp_path / "checkpoints.jsonl"
    first=_report(1)
    t0=datetime(2026,10,5,10,tzinfo=timezone.utc)
    assert persist(first,path=path,now=t0)["persisted"] is True
    history=load_history(path)
    assert history[0]["telemetry_only"] is True
    assert history[0]["performance_interpretation"] is None
    assert history[0]["strategy_action"] is None
    prior=previous_lanes(history)
    second=build_cross_strategy_scorecard(
        day_rows=[{"net_pnl_r":0.5,"exit_timestamp":"2026-10-05T10:00:00+00:00"},{"net_pnl_r":-0.25,"exit_timestamp":"2026-10-05T11:00:00+00:00"}],
        investment_snapshot={"summary":{},"closed_lots":[],"timeline":[]},
        prediction_snapshot={"summary":{},"events":[]},
        previous_checkpoints=prior,
    )
    day={x["lane"]:x for x in second["lanes"]}["DAY_TRADING"]
    assert day["evidence_checkpoint"]["movement"] == "GROWING"
    assert day["evidence_checkpoint"]["performance_interpretation"] is None
    assert second["comparison_rules"]["thresholds_modified"] is False
    assert second["comparison_rules"]["production_strategy_modified"] is False


def test_unchanged_checkpoint_is_deduped_inside_one_hour(tmp_path):
    path=tmp_path / "checkpoints.jsonl"
    report=_report(1)
    t0=datetime(2026,10,5,10,tzinfo=timezone.utc)
    assert persist(report,path=path,now=t0)["persisted"] is True
    result=persist(report,path=path,now=t0+timedelta(minutes=30))
    assert result == {"persisted": False, "reason": "UNCHANGED_WITHIN_INTERVAL"}
    assert len(load_history(path)) == 1


def test_history_reader_ignores_malformed_and_view_is_bounded(tmp_path):
    path=tmp_path / "checkpoints.jsonl"
    path.write_text("not-json\n" + json.dumps({"telemetry_only":False}) + "\n",encoding="utf-8")
    base=datetime(2026,10,5,10,tzinfo=timezone.utc)
    for i in range(55):
        persist(_report(1 if i % 2 == 0 else 2),path=path,now=base+timedelta(hours=i))
    view=history_view(path,limit=50)
    assert view["telemetry_only"] is True
    assert view["performance_interpretation"] is None
    assert view["strategy_action"] is None
    assert view["retention_max"] == MAX_HISTORY
    assert view["returned"] == 50
    assert len(view["checkpoints"]) == 50


def test_transition_summary_is_adjacent_telemetry_not_performance():
    from app.services.evidence_checkpoint_history import transition_summary
    history=[
        {"observed_at":"2026-10-05T10:00:00+00:00","lanes":{"DAY_TRADING":{"sample_size":10,"latest_evidence_at":"2026-10-05T09:00:00+00:00","integrity_status":"OK","reconstruction_status":"OK","evidence_health_band":"THIN"}}},
        {"observed_at":"2026-10-05T11:00:00+00:00","lanes":{"DAY_TRADING":{"sample_size":12,"latest_evidence_at":"2026-10-05T10:30:00+00:00","integrity_status":"PARTIAL","reconstruction_status":"PARTIAL","evidence_health_band":"THIN"}}},
    ]
    result=transition_summary(history)
    lane=result["lanes"]["DAY_TRADING"]
    assert result["telemetry_only"] is True
    assert result["performance_interpretation"] is None
    assert result["strategy_action"] is None
    assert lane["sample_delta"] == 2
    assert lane["freshness_delta_hours"] == 1.5
    assert lane["integrity_transition"] == "OK->PARTIAL"
    assert lane["reconstruction_transition"] == "OK->PARTIAL"
    assert lane["health_transition"] == "THIN->THIN"
    assert lane["performance_interpretation"] is None
    assert lane["strategy_action"] is None


def test_transition_summary_baseline_has_no_invented_delta():
    from app.services.evidence_checkpoint_history import transition_summary
    result=transition_summary([{"observed_at":"2026-10-05T10:00:00+00:00","lanes":{}}])
    assert result["status"] == "BASELINE"
    assert result["lanes"] == {}
    assert result["performance_interpretation"] is None


def test_capture_status_exposes_dedup_cadence_without_strategy_action():
    from datetime import datetime, timezone
    from app.services.evidence_checkpoint_history import capture_status
    history=[{"observed_at":"2026-10-05T10:00:00+00:00","telemetry_only":True}]
    result=capture_status(history, datetime(2026,10,5,10,30,tzinfo=timezone.utc))
    assert result["status"] == "DEDUP_WINDOW"
    assert result["seconds_until_eligible"] == 1800
    assert result["minimum_unchanged_interval_seconds"] == 3600
    assert result["telemetry_only"] is True
    assert result["strategy_action"] is None


def test_diagnostic_alerts_are_non_actionable_and_lane_scoped():
    from app.services.evidence_checkpoint_history import diagnostic_alerts
    transitions={"lanes":{"DAY_TRADING":{"integrity_transition":"OK->OK","reconstruction_transition":"OK->OK"},"INVESTMENT_QUALITY_DIPS_V1":{"integrity_transition":"OK->PARTIAL","reconstruction_transition":"OK->FAILED_ISOLATED"}}}
    alerts=diagnostic_alerts(transitions)
    assert len(alerts) == 1
    assert alerts[0]["lane"] == "INVESTMENT_QUALITY_DIPS_V1"
    assert alerts[0]["severity"] == "DIAGNOSTIC"
    assert alerts[0]["telemetry_only"] is True
    assert alerts[0]["performance_interpretation"] is None
    assert alerts[0]["strategy_action"] is None
    assert alerts[0]["automatic_response"] is None


def test_checkpoint_journal_integrity_reports_malformed_without_losing_valid_rows(tmp_path):
    from app.services.evidence_checkpoint_history import journal_integrity
    path=tmp_path / "checkpoints.jsonl"
    valid={"observed_at":"2026-10-05T10:00:00+00:00","scorecard_version":"cross-strategy-evidence-health-v3","telemetry_only":True,"lanes":{}}
    path.write_text(json.dumps(valid)+"\nnot-json\n"+json.dumps({"telemetry_only":False})+"\n",encoding="utf-8")
    result=journal_integrity(path)
    assert result["status"] == "PARTIAL"
    assert result["readable_rows"] == 1
    assert result["malformed_rows"] == 1
    assert result["ignored_non_telemetry_rows"] == 1
    assert result["newest_valid_checkpoint"] == valid["observed_at"]
    assert result["retention_status"] == "WITHIN_LIMIT"
    assert result["strategy_action"] is None
    assert result["automatic_response"] is None
    assert len(load_history(path)) == 1


def test_checkpoint_corruption_does_not_change_native_scorecard_evidence(tmp_path):
    from app.services.evidence_checkpoint_history import journal_integrity
    path=tmp_path / "checkpoints.jsonl"
    path.write_text("broken\n",encoding="utf-8")
    before=_report(2)
    integrity=journal_integrity(path)
    after=_report(2)
    assert integrity["status"] == "PARTIAL"
    assert integrity["readable_rows"] == 0
    assert before["lanes"] == after["lanes"]
    assert before["comparison_rules"] == after["comparison_rules"]
    assert before["live_capital_allowed"] is False
    assert after["automatic_real_money_execution"] is False


def test_unknown_checkpoint_version_is_diagnostic_only_and_excluded_from_current_history(tmp_path):
    from app.services.evidence_checkpoint_history import schema_compatibility
    path=tmp_path / "checkpoints.jsonl"
    supported={"observed_at":"2026-10-05T10:00:00+00:00","scorecard_version":"cross-strategy-evidence-health-v3","telemetry_only":True,"lanes":{"DAY_TRADING":{"sample_size":2}}}
    unknown={"observed_at":"2026-10-05T11:00:00+00:00","scorecard_version":"future-v99","telemetry_only":True,"lanes":{"DAY_TRADING":{"sample_size":999999}}}
    path.write_text(json.dumps(supported)+"\n"+json.dumps(unknown)+"\n",encoding="utf-8")
    history=load_history(path)
    compat=schema_compatibility(path)
    assert len(history) == 1
    assert history[0]["scorecard_version"] == "cross-strategy-evidence-health-v3"
    assert previous_lanes(history)["DAY_TRADING"]["sample_size"] == 2
    assert compat["status"] == "UNKNOWN_VERSION_PRESENT"
    assert compat["supported_rows"] == 1
    assert compat["unknown_version_rows"] == 1
    assert compat["unknown_versions"] == ["future-v99"]
    assert compat["unknown_rows_used_as_current_evidence"] is False
    assert compat["strategy_action"] is None


def test_unknown_version_cannot_change_native_scorecard_or_live_permissions(tmp_path):
    path=tmp_path / "checkpoints.jsonl"
    path.write_text(json.dumps({"scorecard_version":"future-v99","telemetry_only":True,"lanes":{"DAY_TRADING":{"sample_size":999999}}})+"\n",encoding="utf-8")
    assert load_history(path) == []
    before=_report(2)
    after=_report(2)
    assert before["lanes"] == after["lanes"]
    assert before["comparison_rules"] == after["comparison_rules"]
    assert after["live_capital_allowed"] is False
    assert after["automatic_real_money_execution"] is False
