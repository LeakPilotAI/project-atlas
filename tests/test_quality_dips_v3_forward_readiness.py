from datetime import datetime, timedelta, timezone
import json

from app.investment.quality_dips_v3_forward_readiness import forward_readiness


def test_forward_readiness_blocks_insufficient_coverage(tmp_path):
    path=tmp_path/"v3.jsonl"
    path.write_text(json.dumps({"timestamp":datetime.now(timezone.utc).isoformat(),"symbol":"MSFT","patient_state":"WATCH"})+"\n",encoding="utf-8")
    out=forward_readiness(path)
    assert out["ready"] is False
    assert len(out["blockers"]) == 3


def test_forward_readiness_passes_thresholds(tmp_path):
    path=tmp_path/"v3.jsonl"
    rows=[]
    start=datetime(2026,9,1,tzinfo=timezone.utc)
    symbols=[f"S{i}" for i in range(10)]
    for d in range(20):
        for s in symbols:
            rows.append({"timestamp":(start+timedelta(days=d)).isoformat(),"symbol":s,"patient_state":"WATCH"})
    path.write_text("\n".join(json.dumps(r) for r in rows)+"\n",encoding="utf-8")
    out=forward_readiness(path)
    assert out["ready"] is True
    assert out["evaluations"] == 200
    assert out["symbols"] == 10
    assert out["unique_days"] == 20
