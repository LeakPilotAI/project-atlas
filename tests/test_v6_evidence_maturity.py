import json
from app.services.v6_evidence_maturity import research_evidence_maturity


def test_maturity_summary_is_descriptive_and_fail_closed(tmp_path):
    marker=tmp_path/"marker.json";members=tmp_path/"members.jsonl";cache=tmp_path/"cache.json";history=tmp_path/"history.jsonl"
    marker.write_text(json.dumps({"cohort":"v6_forward_only","started_at":"2026-09-15T00:00:00+00:00"}),encoding="utf-8")
    members.write_text(json.dumps({"event":"membership","trade_id":"t1","entry_timestamp":"2026-09-15T01:00:00+00:00","challengers":["trend_regime"],"pre_entry_snapshot":{"regime":"TREND_UP"}})+"\n",encoding="utf-8")
    cache.write_text(json.dumps({"forward_evidence":{"trend_regime":{"closed":25,"positive_expectancy":True}},"shadow_paper":{"prospective_nomination_count":1}}),encoding="utf-8")
    history.write_text(json.dumps({"event":"v6_forward_evidence_snapshot","timestamp":"2026-09-15T02:00:00+00:00","evidence":{"forward":{"trend_regime":{"closed":25,"expectancy":0.1,"uncertainty_supports_positive_edge":False}},"exit_replay":{"path_coverage":0.4},"shadow_paper":{"prospective_nomination_count":1}}})+"\n",encoding="utf-8")
    r=research_evidence_maturity(history_path=history,marker_path=marker,membership_path=members,scorecard_cache_path=cache)
    assert r["mode"]=="DESCRIPTIVE_MATURITY_PRESENCE_MISSING"
    c=r["candidates"]["trend_regime"]
    assert set(c["dimensions"])=={"forward_sample","uncertainty_support","stability","diversity","longitudinal_history","multi_window_evidence","confirmation_depth","gap_closure"}
    assert c["dimensions"]["forward_sample"]["state"]=="PRESENT"
    assert c["dimensions"]["uncertainty_support"]["state"]=="MISSING"
    assert c["dimensions"]["multi_window_evidence"]["state"]=="PRESENT"
    assert c["dimensions"]["confirmation_depth"]["state"]=="MISSING"
    assert c["dimensions"]["gap_closure"]["state"]=="MISSING"
    assert c["aggregate_score"] is None;assert c["readiness_percentage"] is None
    assert r["automatic_scoring"] is False;assert r["weighted_scoring"] is False;assert r["best_window_selection"] is False;assert r["automatic_promotion"] is False
    assert r["trading_readiness"]=="NOT_READY";assert r["live_capital_allowed"] is False;assert r["automatic_real_money_execution"] is False


def test_maturity_missing_files_returns_no_candidates(tmp_path):
    r=research_evidence_maturity(history_path=tmp_path/"history.jsonl",marker_path=tmp_path/"marker.json",membership_path=tmp_path/"members.jsonl",scorecard_cache_path=tmp_path/"cache.json")
    assert r["candidates"]=={}
    assert r["automatic_scoring"] is False
    assert r["weighted_scoring"] is False
    assert r["live_capital_allowed"] is False
