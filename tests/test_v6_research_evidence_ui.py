import json
from app.services.v6_research_evidence_ui import research_evidence_ui

def test_ui_consolidates_durable_status_without_live_unlock(tmp_path):
    marker=tmp_path/"marker.json";members=tmp_path/"members.jsonl";cache=tmp_path/"cache.json";history=tmp_path/"history.jsonl"
    marker.write_text(json.dumps({"cohort":"v6_forward_only","started_at":"2026-09-15T00:00:00+00:00"}),encoding="utf-8")
    members.write_text(json.dumps({"event":"membership","trade_id":"t1","entry_timestamp":"2026-09-15T01:00:00+00:00","challengers":["trend_regime"],"pre_entry_snapshot":{"regime":"TREND_UP"}})+"\n",encoding="utf-8")
    cache.write_text(json.dumps({"forward_evidence":{"trend_regime":{"closed":25,"positive_expectancy":True}},"shadow_paper":{"prospective_nomination_count":1}}),encoding="utf-8")
    history.write_text(json.dumps({"event":"v6_forward_evidence_snapshot","timestamp":"2026-09-15T02:00:00+00:00","evidence":{"forward":{"trend_regime":{"closed":25,"expectancy":0.1,"uncertainty_supports_positive_edge":False}},"exit_replay":{"path_coverage":0.4},"shadow_paper":{"prospective_nomination_count":1}}})+"\n",encoding="utf-8")
    r=research_evidence_ui(history_path=history,marker_path=marker,membership_path=members,scorecard_cache_path=cache)
    assert r["mode"]=="LIGHTWEIGHT_DURABLE_READ_ONLY"
    assert r["readiness_progress"]["forward"]["trend_regime"]["closed"]==25
    assert r["evidence"]["snapshot_count"]==1
    assert r["candidate_state"]["research_nominations_cached"]==1
    assert r["stability"]["human_review_eligible"]==[]
    assert r["diversity"]["snapshot_available"] is True
    assert r["diversity"]["candidates"]["trend_regime"]["membership_count"]==1
    assert r["longitudinal_diversity"]["candidates"]["trend_regime"]["snapshot_count"]==1
    assert r["longitudinal_diversity"]["candidates"]["trend_regime"]["trend"]=="INSUFFICIENT_LONGITUDINAL_EVIDENCE"
    assert r["longitudinal_diversity"]["method"]=="CUMULATIVE_POINT_IN_TIME"
    assert r["longitudinal_diversity"]["fixed_duration_windows_evaluated"] is True
    assert r["fixed_window_diversity"]["method"]=="PREDECLARED_7_DAY_POINT_IN_TIME"
    assert r["fixed_window_diversity"]["minimum_window_memberships"]==20
    assert r["fixed_window_diversity"]["candidates"]["trend_regime"]["comparison"]=="INSUFFICIENT_RECENT_WINDOW_EVIDENCE"
    assert r["fixed_window_diversity"]["candidates"]["trend_regime"]["recent_window_evidence_sufficient"] is False
    assert r["heavy_research_recompute"] is False
    assert r["separation"]["research_nomination_is_production_approval"] is False
    assert r["separation"]["fixed_window_diversity_is_trading_readiness"] is False
    assert r["trading_readiness"]=="NOT_READY"
    assert r["live_capital_allowed"] is False
    assert r["automatic_real_money_execution"] is False

def test_ui_missing_durable_files_fails_closed(tmp_path):
    r=research_evidence_ui(history_path=tmp_path/"history.jsonl",marker_path=tmp_path/"marker.json",membership_path=tmp_path/"members.jsonl",scorecard_cache_path=tmp_path/"cache.json")
    assert r["evidence"]["snapshot_count"]==0
    assert r["stability"]["human_review_eligible"]==[]
    assert r["diversity"]["snapshot_available"] is False
    assert r["diversity"]["established"]==[]
    assert r["longitudinal_diversity"]["candidates"]=={}
    assert r["fixed_window_diversity"]["snapshot_available"] is False
    assert r["fixed_window_diversity"]["candidates"]=={}
    assert r["normal_command_center_recompute"] is False
    assert r["automatic_promotion"] is False
    assert r["live_capital_allowed"] is False
