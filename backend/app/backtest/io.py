"""Validated historical dataset IO for deterministic Atlas backtests."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.backtest.historical import HistoricalBar


@dataclass(frozen=True)
class HistoricalContext:
    bar: HistoricalBar
    open_interest_usd: float
    volume_24h_usd: float
    htf_regime_aligned: bool|None = None
    htf_trend: str|None = None


_REQUIRED=("timestamp","symbol","timeframe","open","high","low","close","volume","open_interest_usd","volume_24h_usd")
_VALID_HTF={"UP","DOWN","FLAT","UNKNOWN","OFF"}


def _bool(value:object)->bool:
    if isinstance(value,bool):return value
    text=str(value).strip().lower()
    if text in {"1","true","yes","y"}:return True
    if text in {"0","false","no","n"}:return False
    raise ValueError(f"invalid boolean value: {value!r}")


def _trend(value:object)->str:
    text=str(value).strip().upper()
    if text not in _VALID_HTF:raise ValueError(f"invalid htf_trend: {value!r}")
    return text


def _row_to_context(row:dict,source:str)->HistoricalContext:
    missing=[key for key in _REQUIRED if key not in row or row[key] in (None,"")]
    if missing:raise ValueError(f"{source}: missing required fields: {', '.join(missing)}")
    has_trend=row.get("htf_trend") not in (None,"")
    has_legacy=row.get("htf_regime_aligned") not in (None,"")
    if not has_trend and not has_legacy:raise ValueError(f"{source}: missing required HTF context: htf_trend")
    try:
        bar=HistoricalBar(
            timestamp=str(row["timestamp"]),symbol=str(row["symbol"]).upper(),timeframe=str(row["timeframe"]),
            open=float(row["open"]),high=float(row["high"]),low=float(row["low"]),close=float(row["close"]),volume=float(row["volume"]),
            funding_rate=float(row.get("funding_rate") or 0.0),
        )
        oi=float(row["open_interest_usd"]);vol24=float(row["volume_24h_usd"])
        trend=_trend(row["htf_trend"]) if has_trend else None
        aligned=_bool(row["htf_regime_aligned"]) if has_legacy else None
    except (TypeError,ValueError) as exc:raise ValueError(f"{source}: invalid field value: {exc}") from exc
    if oi<0 or vol24<0:raise ValueError(f"{source}: OI/24h volume cannot be negative")
    return HistoricalContext(bar,oi,vol24,aligned,trend)


def load_historical_contexts(path:Path)->list[HistoricalContext]:
    path=Path(path)
    if not path.is_file():raise FileNotFoundError(path)
    rows:list[dict]=[]
    suffix=path.suffix.lower()
    if suffix==".csv":
        with path.open("r",encoding="utf-8-sig",newline="") as fh:rows=list(csv.DictReader(fh))
    elif suffix in {".jsonl",".ndjson"}:
        with path.open("r",encoding="utf-8") as fh:
            for line_no,line in enumerate(fh,1):
                line=line.strip()
                if not line:continue
                value=json.loads(line)
                if not isinstance(value,dict):raise ValueError(f"{path}:{line_no}: JSONL row must be an object")
                rows.append(value)
    else:raise ValueError("historical dataset must be .csv, .jsonl, or .ndjson")
    if not rows:raise ValueError("historical dataset is empty")
    contexts=[_row_to_context(row,f"{path}:{idx}") for idx,row in enumerate(rows,2 if suffix==".csv" else 1)]
    timestamps=[x.bar.timestamp for x in contexts]
    if timestamps!=sorted(timestamps) or len(timestamps)!=len(set(timestamps)):raise ValueError("historical dataset timestamps must be unique and ascending")
    identities={(x.bar.symbol,x.bar.timeframe) for x in contexts}
    if len(identities)!=1:raise ValueError("historical dataset must contain exactly one symbol/timeframe")
    return contexts


def bars_only(contexts:Iterable[HistoricalContext])->list[HistoricalBar]:
    return [row.bar for row in contexts]
