"""E42 preregistered Alpha cadence policy."""
POLICY={"version":"e42-alpha-cadence-policy-v1","min_observations":30,"alpha_p95_ms_threshold":50.0,"alpha_cycle_share_p95_threshold":0.20}

def decision(rows):
    rows=[x for x in rows if float(x.get("cycle_ms") or 0)>0]
    def p95(v):
        if not v:return None
        s=sorted(v);return s[min(len(s)-1,int((len(s)-1)*0.95))]
    a=p95([float(x.get("alpha_ms") or 0) for x in rows]);q=p95([float(x.get("alpha_ms") or 0)/float(x["cycle_ms"]) for x in rows]);ready=len(rows)>=POLICY["min_observations"]
    return {"policy":POLICY,"observations":len(rows),"alpha_p95_ms":a,"alpha_cycle_share_p95":q,"evidence_ready":ready,"decouple_recommended":bool(ready and ((a or 0)>50 or (q or 0)>.20))}
