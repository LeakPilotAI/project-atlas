"""Fail-closed readiness audit for real historical Atlas source bundles."""
from __future__ import annotations

from dataclasses import asdict,dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable

from app.backtest.manifest import load_manifest


@dataclass(frozen=True)
class DatasetReadiness:
    symbol:str
    dataset:str
    manifest:str
    ready:bool
    reasons:tuple[str,...]
    manifest_id:str|None=None


def audit_dataset(symbol:str,dataset:Path,manifest:Path)->DatasetReadiness:
    reasons=[];payload=None
    if not dataset.is_file():reasons.append("canonical dataset missing")
    if not manifest.is_file():reasons.append("provenance manifest missing")
    if not reasons:
        try:payload=load_manifest(manifest,dataset)
        except Exception as exc:reasons.append(f"manifest verification failed: {exc}")
    if payload is not None:
        if str(payload.get("symbol","")).upper()!=symbol.upper():reasons.append("manifest symbol mismatch")
        for field in ("candles_source","funding_source","oi_source","rolling_volume_source","htf_context_source"):
            if not str(payload.get(field,"")).strip():reasons.append(f"missing provenance: {field}")
        if payload.get("pit_aligned") is not True:reasons.append("dataset is not PIT aligned")
        if payload.get("current_state_backfill_used") is not False:reasons.append("current-state backfill is forbidden")
        notes=str(payload.get("notes", ""))
        if "raw_sha256=" not in notes:reasons.append("raw source checksums missing from manifest notes")
    return DatasetReadiness(symbol.upper(),str(dataset),str(manifest),not reasons,tuple(reasons),str(payload.get("manifest_id")) if payload else None)


def audit_representative_bundle(root:Path,symbols:Iterable[str]=("BTC","ETH","SOL"),timeframe:str="5m")->dict:
    root=Path(root);items=[]
    for symbol in symbols:
        dataset=root/f"{symbol.upper()}-{timeframe}.csv";manifest=dataset.with_suffix(dataset.suffix+".manifest.json")
        items.append(audit_dataset(symbol,dataset,manifest))
    payload={"mode":"RESEARCH_HISTORICAL_SOURCE_READINESS","timeframe":timeframe,"datasets":[asdict(x) for x in items],"ready_for_locked_baseline_batch":all(x.ready for x in items),"live_capital_allowed":False,"automatic_real_money_execution":False}
    canonical=json.dumps(payload,sort_keys=True,separators=(",",":"));payload["audit_id"]=sha256(canonical.encode()).hexdigest()[:20]
    return payload


def main(argv:list[str]|None=None)->int:
    import argparse
    p=argparse.ArgumentParser(description="Audit BTC/ETH/SOL canonical historical datasets before locked-baseline research")
    p.add_argument("--root",type=Path,default=Path("backend/data/research/historical"));p.add_argument("--timeframe",default="5m")
    a=p.parse_args(argv);result=audit_representative_bundle(a.root,timeframe=a.timeframe);print(json.dumps(result,indent=2,sort_keys=True));return 0 if result["ready_for_locked_baseline_batch"] else 2


if __name__=="__main__":raise SystemExit(main())
