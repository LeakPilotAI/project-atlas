"""Append-safe prospective crypto research evidence store. No trading authority."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any

READINESS_POLICY={"policy_version":"E62_PRE_OUTCOME_V1","minimum_total_observations":30,"minimum_distinct_observation_days":14,"minimum_valid_fraction":0.90}
ZERO_AUTHORITY={"scoring_active":False,"dip_state_active":False,"can_emit_signal":False,"paper_entry_authority":False,"execution_authority":False,"strategy_selection_authority":False,"threshold_mutation_authority":False,"promotion_authority":False,"live_capital_allowed":False}

def observation_identity(record: dict[str, Any]) -> str:
    material={"asset_class":record.get("asset_class"),"symbol":record.get("symbol"),"observed_at":record.get("observed_at"),"evidence":record.get("evidence")}
    raw=json.dumps(material,sort_keys=True,separators=(",",":"),default=str).encode()
    return hashlib.sha256(raw).hexdigest()

class CryptoProspectiveEvidenceStore:
    def __init__(self,path):
        self.path=Path(path); self.records=[]; self._ids=set()
        self.integrity={"ok":True,"malformed_lines":0,"duplicate_lines":0,"identity_mismatch_lines":0}
        self.reload()
    def reload(self):
        self.records=[]; self._ids=set()
        self.integrity={"ok":True,"malformed_lines":0,"duplicate_lines":0,"identity_mismatch_lines":0}
        if not self.path.exists(): return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            try:
                row=json.loads(line); oid=str(row["observation_id"])
            except (json.JSONDecodeError,KeyError,TypeError,ValueError):
                self.integrity["ok"]=False; self.integrity["malformed_lines"]+=1
                continue
            if oid != observation_identity(row):
                self.integrity["ok"]=False; self.integrity["identity_mismatch_lines"]+=1
                continue
            if oid in self._ids:
                self.integrity["duplicate_lines"]+=1
                continue
            self.records.append(row); self._ids.add(oid)
    def append(self,record: dict[str,Any]) -> bool:
        if not self.integrity["ok"]:
            raise ValueError("EVIDENCE_STORE_INTEGRITY_FAILED")
        row=dict(record); oid=observation_identity(row)
        if oid in self._ids: return False
        row["observation_id"]=oid; self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.open("a",encoding="utf-8") as fh:
            fh.write(json.dumps(row,sort_keys=True,separators=(",",":"),default=str)+"\n")
        self.records.append(row); self._ids.add(oid); return True

def evidence_summary(records):
    rows=list(records); total=len(rows)
    valid=sum(bool(x.get("evidence_valid")) for x in rows)
    days={str(x.get("observed_at",""))[:10] for x in rows if x.get("observed_at")}
    reasons={}
    for row in rows:
        for item in (row.get("evidence") or {}).values():
            for reason in item.get("reasons",[]):
                reasons[reason]=reasons.get(reason,0)+1
    fraction=(valid/total) if total else 0.0
    gates={"total_observations":total>=READINESS_POLICY["minimum_total_observations"],"distinct_days":len(days)>=READINESS_POLICY["minimum_distinct_observation_days"],"valid_fraction":fraction>=READINESS_POLICY["minimum_valid_fraction"]}
    result={"total_observations":total,"valid_observations":valid,"valid_fraction":fraction,"distinct_observation_days":len(days),"failure_reasons":reasons}
    result.update({"predeclared_readiness_policy":dict(READINESS_POLICY),"readiness_gates_met":all(gates.values()),"gate_checks":gates})
    result.update(ZERO_AUTHORITY)
    return result
