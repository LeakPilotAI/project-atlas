import json
from pathlib import Path
from app.services.v6_window_diversity import diversity_report


def _append(path:Path,row):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as f:f.write(json.dumps(row)+"\n")


def test_diversity_requires_days_and_multiple_regimes(tmp_path):
    history=tmp_path/"history.jsonl"; members=tmp_path/"members.jsonl"
    _append(history,{"event":"v6_forward_evidence_snapshot","timestamp":"2026-09-16T00:00:00+00:00","evidence":{"forward":{"trend_regime":{"closed":120}}}})
    for day in range(1,4):
        for regime in ("TREND_UP","TREND_DOWN"):
            for i in range(10):
                _append(members,{"event":"membership","trade_id":f"{day}-{regime}-{i}","entry_timestamp":f"2026-09-{day:02d}T12:00:00+00:00","challengers":["trend_regime"],"pre_entry_snapshot":{"regime":regime}})
    r=diversity_report(membership_path=members,history_path=history)
    c=r["candidates"]["trend_regime"]
    assert c["temporal_diversity_established"] is True
    assert c["regime_diversity_established"] is True
    assert c["diversity_established"] is True
    assert r["live_capital_allowed"] is False
    assert r["automatic_real_money_execution"] is False


def test_diversity_fails_closed_for_clustered_or_single_regime(tmp_path):
    history=tmp_path/"history.jsonl"; members=tmp_path/"members.jsonl"
    _append(history,{"event":"v6_forward_evidence_snapshot","evidence":{"forward":{"quality_85":{"closed":120}}}})
    for i in range(30):
        _append(members,{"event":"membership","trade_id":str(i),"entry_timestamp":"2026-09-16T12:00:00+00:00","challengers":["quality_85"],"pre_entry_snapshot":{"regime":"TREND_UP"}})
    c=diversity_report(membership_path=members,history_path=history)["candidates"]["quality_85"]
    assert c["temporal_diversity_established"] is False
    assert c["regime_diversity_established"] is False
    assert c["diversity_established"] is False


def test_no_snapshot_has_no_candidate_diversity(tmp_path):
    r=diversity_report(membership_path=tmp_path/"missing-members.jsonl",history_path=tmp_path/"missing-history.jsonl")
    assert r["snapshot_available"] is False
    assert r["candidates"] == {}
    assert r["diversity_established"] == []
    assert r["trading_readiness"] == "NOT_READY"
