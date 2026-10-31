"""Read-only PAPER/SHADOW operational checkpoint.

Inspects durability/recovery and shadow-isolation state without creating orders,
opening trades, changing legacy PAPER state, or enabling live capital.
"""
from __future__ import annotations

import argparse,json
from pathlib import Path
from typing import Any

from app.trading_core.event_store import EventStoreCorruption, JsonlEventStore
from app.trading_core.shadow_coordinator import V4ShadowCoordinator


def inspect(*,event_path:Path)->dict[str,Any]:
    path=Path(event_path)
    corruption=None
    event_count=0
    try:
        events=JsonlEventStore(path).load()
        event_count=len(events)
    except EventStoreCorruption as exc:
        corruption=str(exc)
    coordinator=V4ShadowCoordinator(path)
    recovered_open=coordinator.recover() if corruption is None else 0
    snapshot=coordinator.snapshot() if corruption is None else {
        "enabled":True,"mode":"SHADOW_ONLY","open":0,"closed":0,
        "last_error":f"event_store_corruption: {corruption}",
    }
    healthy=corruption is None and snapshot.get("mode")=="SHADOW_ONLY"
    return {
        "mode":"PAPER_SHADOW_OPERATIONAL_CHECKPOINT",
        "event_path":str(path),
        "event_store_exists":path.exists(),
        "event_count":event_count,
        "event_store_corruption":corruption,
        "recovered_open":recovered_open,
        "shadow_snapshot":snapshot,
        "persistent_recovery_ready":healthy,
        "shadow_isolation_ready":snapshot.get("mode")=="SHADOW_ONLY",
        "legacy_state_mutated":False,
        "real_order_actions":False,
        "live_capital_allowed":False,
        "automatic_real_money_execution":False,
        "status":"PAPER_SHADOW_CHECKPOINT_GREEN" if healthy else "PAPER_SHADOW_CHECKPOINT_BLOCKED",
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Read-only Atlas PAPER/SHADOW operational checkpoint")
    p.add_argument("--event-path",type=Path,default=Path("backend/data/trading_v4_shadow.jsonl"))
    p.add_argument("--output",type=Path)
    a=p.parse_args(argv);result=inspect(event_path=a.event_path)
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result["status"]=="PAPER_SHADOW_CHECKPOINT_GREEN" else 2

if __name__=="__main__":raise SystemExit(main())
