from pathlib import Path

from app.investment.quality_dips_v3_forward_store import append_v3_forward_observation


def test_forward_v3_observation_persists_full_shadow_evidence(tmp_path):
    path=tmp_path/"v3_forward.jsonl"
    plan={
        "patient_state":"ACCUMULATION",
        "fair_value_anchor":120.0,
        "discount_to_fair_value_pct":20.0,
        "blockers":[],
        "entry_ladder":{"ready":True,"levels":[{"level":"L1","limit_price":102.0,"reached":True}]},
        "policy":{"level_margins_pct":{"L1":15.0}},
    }
    row=append_v3_forward_observation(symbol="msft",price=100,plan=plan,source_timestamp="2026-09-18T12:00:00Z",path=path)
    assert row["symbol"]=="MSFT"
    assert row["patient_state"]=="ACCUMULATION"
    assert row["entry_ladder"]["levels"][0]["reached"] is True
    text=path.read_text(encoding="utf-8")
    assert "automatic_real_money_execution" in text
