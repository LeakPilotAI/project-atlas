import json
from app.services.v6_research_evidence_ui import research_evidence_ui

def test_ui_consolidates_durable_status_without_live_unlock(tmp_path):
    marker=tmp_path/"marker.json";members=tmp_path/"members.jsonl";cache=tmp_path/"cache.json";history=tmp_path/"history.jsonl"
    marker.write_text(json.dumps({"cohort":"v6_forward_only","started_at":"2026-09-15T00:00:00+00:00"}),encoding="utf-8")
    members.write_text(json.dumps({"event":"membership","trade_id":"t1","entry_timestamp":"2026-09-15T01:00:00+00:00","challengers":["trend_regime"],"pre_entry_snapshot":{"regime":"TREND_UP"}})+"\n",encoding="utf-8")
    cache.write_text(json.dumps({"forward_evidence":{"trend_regime":{"closed":25,"positive_expectancy":True}},"shadow_paper":{"prospective_nomination_count":1}}),encoding="utf-8")
    history.write_text(json.dumps({"event":"v6_forward_evidence_snapshot","timestamp":"2026-09-15T02:00:00+00:00","evidence":{"forward":{"trend_regime":{"closed":25,"expectancy":0.1,"uncertainty_supports_positive_edge":False}},"exit_replay":{"path_coverage":0.4},"shadow_paper":{"prospective_nomination_count":1}}})+"\n",encoding="utf-8")
    r=research_evidence_ui(history_path=history,marker_path=marker,membership_path=members,scorecard_cache_path=cache)
    assert r["mode"]=="LIGHTWEIGHT_DURABLE_READ_ONLY";assert r["readiness_progress"]["forward"]["trend_regime"]["closed"]==25;assert r["evidence"]["snapshot_count"]==1
    assert r["diversity"]["snapshot_available"] is True;assert r["longitudinal_diversity"]["candidates"]["trend_regime"]["snapshot_count"]==1
    assert r["fixed_window_diversity"]["method"]=="PREDECLARED_7_DAY_POINT_IN_TIME"
    mw=r["multi_window_diversity"];assert mw["method"]=="PREDECLARED_3D_7D_14D_POINT_IN_TIME";assert mw["all_windows_reported"] is True;assert mw["best_window_selection"] is False
    assert [x["days"] for x in mw["predeclared_windows"]]==[3,7,14]
    c=mw["candidates"]["trend_regime"];assert set(c["windows"])=={"3","7","14"};assert c["selected_best_window"] is None
    assert c["windows"]["3"]["minimum_window_memberships"]==10;assert c["windows"]["7"]["minimum_window_memberships"]==20;assert c["windows"]["14"]["minimum_window_memberships"]==30
    mh=r["multi_window_consistency_history"];assert mh["method"]=="PROSPECTIVE_NEW_EVIDENCE_ONLY_3D_7D_14D";assert mh["best_window_selection"] is False
    hc=mh["candidates"]["trend_regime"];assert hc["observation_count"]==1;assert hc["duplicate_refresh_resistant"] is True;assert hc["new_evidence_required"] is True
    assert set(hc["latest"]["windows"])=={"3","7","14"}
    ch=r["consistency_change_diagnostics"];assert ch["method"]=="DESCRIPTIVE_NEW_EVIDENCE_TRANSITIONS";assert ch["automatic_scoring"] is False;assert ch["best_window_selection"] is False
    cc=ch["candidates"]["trend_regime"];assert cc["observation_count"]==1;assert cc["transition_count"]==0;assert cc["new_evidence_only"] is True;assert cc["production_promoted"] is False
    assert r["heavy_research_recompute"] is False;assert r["separation"]["multi_window_diversity_is_trading_readiness"] is False;assert r["separation"]["multi_window_consistency_history_is_trading_readiness"] is False;assert r["separation"]["consistency_change_diagnostics_is_trading_readiness"] is False;assert r["trading_readiness"]=="NOT_READY";assert r["live_capital_allowed"] is False;assert r["automatic_real_money_execution"] is False

def test_ui_missing_durable_files_fails_closed(tmp_path):
    r=research_evidence_ui(history_path=tmp_path/"history.jsonl",marker_path=tmp_path/"marker.json",membership_path=tmp_path/"members.jsonl",scorecard_cache_path=tmp_path/"cache.json")
    assert r["evidence"]["snapshot_count"]==0;assert r["stability"]["human_review_eligible"]==[];assert r["diversity"]["snapshot_available"] is False;assert r["longitudinal_diversity"]["candidates"]=={};assert r["fixed_window_diversity"]["candidates"]=={};assert r["multi_window_diversity"]["snapshot_available"] is False;assert r["multi_window_diversity"]["candidates"]=={};assert r["multi_window_consistency_history"]["snapshot_count"]==0;assert r["multi_window_consistency_history"]["candidates"]=={};assert r["consistency_change_diagnostics"]["candidates"]=={};assert r["consistency_change_diagnostics"]["automatic_scoring"] is False;assert r["normal_command_center_recompute"] is False;assert r["automatic_promotion"] is False;assert r["live_capital_allowed"] is False
