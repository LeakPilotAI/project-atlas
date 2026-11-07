"""Operator plan for reproducible representative BTC/ETH/SOL historical source acquisition.

This module does not fetch provider data itself and never stores credentials. It defines
exact source requirements and deterministic filenames so raw downloads can be acquired
outside Atlas and normalized/imported reproducibly.
"""
from __future__ import annotations

from dataclasses import asdict,dataclass
import json
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class HistoricalSourcePlan:
    symbol:str
    timeframe:str
    start_utc:str
    end_utc:str
    candles_source:str
    funding_source:str
    oi_source:str
    rolling_volume_source:str
    htf_source:str

    @property
    def stem(self)->str:
        return f"{self.symbol.upper()}-{self.timeframe}"

    def raw_paths(self,root:Path)->dict[str,str]:
        root=Path(root)
        return {
            "candles":str(root/f"{self.stem}.candles.json"),
            "funding":str(root/f"{self.stem}.funding.json"),
            "open_interest":str(root/f"{self.stem}.oi.json"),
            "rolling_volume":str(root/f"{self.stem}.volume.csv"),
            "htf_candles":str(root/f"{self.symbol.upper()}-1h.candles.json"),
            "htf_context":str(root/f"{self.stem}.htf.csv"),
            "merged_context":str(root/f"{self.stem}.context.csv"),
        }

    def validate(self)->None:
        if self.symbol.upper() not in {"BTC","ETH","SOL"}:raise ValueError("representative plan symbol must be BTC, ETH, or SOL")
        if self.timeframe!="5m":raise ValueError("representative plan timeframe must be 5m")
        if not self.start_utc.endswith("Z") or not self.end_utc.endswith("Z"):raise ValueError("plan timestamps must be explicit UTC Z timestamps")
        if self.start_utc>=self.end_utc:raise ValueError("plan start_utc must be before end_utc")
        for field in ("candles_source","funding_source","oi_source","rolling_volume_source","htf_source"):
            if not str(getattr(self,field)).strip():raise ValueError(f"missing source identity: {field}")


def representative_plans(*,start_utc:str,end_utc:str,symbols:Iterable[str]=("BTC","ETH","SOL"))->list[HistoricalSourcePlan]:
    plans=[]
    for symbol in symbols:
        plan=HistoricalSourcePlan(
            symbol=symbol.upper(),timeframe="5m",start_utc=start_utc,end_utc=end_utc,
            candles_source="hyperliquid:info/candleSnapshot:5m",
            funding_source="hyperliquid:info/fundingHistory",
            oi_source="0xarchive:hyperliquid/open-interest:5m",
            rolling_volume_source="atlas:derive-rolling-24h-notional-from-historical-5m-candles",
            htf_source="hyperliquid:info/candleSnapshot:1h",
        )
        plan.validate();plans.append(plan)
    return plans


def write_source_plan(path:Path,*,start_utc:str,end_utc:str,raw_root:Path=Path("backend/data/research/raw/historical"))->Path:
    plans=representative_plans(start_utc=start_utc,end_utc=end_utc)
    payload={
        "mode":"RESEARCH_HISTORICAL_SOURCE_ACQUISITION_PLAN",
        "live_capital_allowed":False,
        "automatic_real_money_execution":False,
        "requirements":{
            "oi_cadence":"5m",
            "rolling_volume":"trailing 24h notional derived point-in-time from historical records only",
            "htf":"1h candles; expose only completed bars to 5m decisions",
            "current_state_backfill_allowed":False,
        },
        "plans":[{**asdict(plan),"raw_paths":plan.raw_paths(raw_root)} for plan in plans],
    }
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8");return path


def main(argv:list[str]|None=None)->int:
    import argparse
    p=argparse.ArgumentParser(description="Emit reproducible Atlas BTC/ETH/SOL historical source acquisition plan")
    p.add_argument("--start",required=True);p.add_argument("--end",required=True);p.add_argument("--output",type=Path,default=Path("backend/data/research/historical/source-plan.json"));p.add_argument("--raw-root",type=Path,default=Path("backend/data/research/raw/historical"))
    a=p.parse_args(argv);out=write_source_plan(a.output,start_utc=a.start,end_utc=a.end,raw_root=a.raw_root);print(f"source_plan={out}");return 0


if __name__=="__main__":raise SystemExit(main())
