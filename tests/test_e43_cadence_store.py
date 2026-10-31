import json
from app.services.e43_cadence_store import append_observation,history
from app.services.e42_alpha_policy import decision

def test_restart_continuity_and_bounded_read(tmp_path):
 p=tmp_path/"c.jsonl"
 for i in range(35):append_observation(10+i/10,200,p)
 a=history(p,30);b=history(p,30)
 assert a==b and a["valid_count"]==35 and len(a["rows"])==30
 assert decision(a["rows"])["evidence_ready"] is True

def test_malformed_rows_fail_integrity_not_valid_history(tmp_path):
 p=tmp_path/"c.jsonl";append_observation(5,100,p)
 with p.open("a",encoding="utf-8") as f:f.write("{bad\n")
 h=history(p)
 assert h["valid_count"]==1 and h["invalid_count"]==1 and h["integrity_ok"] is False

def test_threshold_histories():
 low=[{"alpha_ms":10,"cycle_ms":200}]*30
 high=[{"alpha_ms":60,"cycle_ms":200}]*30
 assert decision(low)["decouple_recommended"] is False
 assert decision(high)["decouple_recommended"] is True
