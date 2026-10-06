"""E43 operational cadence evidence."""
import json
from pathlib import Path
DATA_NAME="e43_alpha_cadence.jsonl"
MAX_ROWS=240

def default_path():
    return Path(__file__).resolve().parents[2]/"data"/DATA_NAME

def append_observation(alpha_ms,cycle_ms,path=None):
    a=float(alpha_ms);c=float(cycle_ms)
    if a<0 or c<=0 or a>c:raise ValueError("invalid cadence timing")
    row={"alpha_ms":round(a,3),"cycle_ms":round(c,3),"execution_authority":False}
    p=Path(path) if path else default_path();p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("a",encoding="utf-8") as f:f.write(json.dumps(row,separators=(",",":"))+"\n")
    return row

def history(path=None,limit=MAX_ROWS):
    p=Path(path) if path else default_path();rows=[];invalid=0
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():continue
            try:r=json.loads(line);a=float(r["alpha_ms"]);c=float(r["cycle_ms"])
            except Exception:invalid+=1;continue
            if a<0 or c<=0 or a>c or r.get("execution_authority") is not False:invalid+=1;continue
            rows.append({"alpha_ms":a,"cycle_ms":c})
    cap=max(1,min(int(limit),MAX_ROWS))
    return {"rows":rows[-cap:],"valid_count":len(rows),"invalid_count":invalid,"integrity_ok":invalid==0,"retention_limit":MAX_ROWS,"execution_authority":False}
