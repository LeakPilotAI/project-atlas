"""Locked representative UTC windows for Atlas historical research.

These windows are research fixtures, not claims that any period is representative of
future performance. They are deliberately separated into development and holdout
periods so candidate tuning cannot silently consume every evaluation interval.
"""
from __future__ import annotations

from dataclasses import asdict,dataclass
import json
from pathlib import Path
from typing import Literal

WindowRole=Literal["DEVELOPMENT","HOLDOUT"]

@dataclass(frozen=True)
class RepresentativeWindow:
    window_id:str
    start_utc:str
    end_utc:str
    role:WindowRole
    purpose:str

    def validate(self)->None:
        if not self.window_id.strip():raise ValueError("window_id required")
        if not self.start_utc.endswith("Z") or not self.end_utc.endswith("Z"):raise ValueError("window timestamps must be UTC Z")
        if self.start_utc>=self.end_utc:raise ValueError("window start must precede end")
        if self.role not in {"DEVELOPMENT","HOLDOUT"}:raise ValueError("invalid window role")
        if not self.purpose.strip():raise ValueError("window purpose required")


def locked_representative_windows()->tuple[RepresentativeWindow,...]:
    """Return immutable research windows.

    Windows are calendar-selected and role-separated before observing Atlas strategy
    results. HOLDOUT windows must not be used for candidate parameter tuning.
    """
    rows=(
        RepresentativeWindow("dev-2024-h2","2024-07-01T00:00:00Z","2025-01-01T00:00:00Z","DEVELOPMENT","first broad development interval"),
        RepresentativeWindow("dev-2025-h1","2025-01-01T00:00:00Z","2025-07-01T00:00:00Z","DEVELOPMENT","second broad development interval"),
        RepresentativeWindow("holdout-2025-h2","2025-07-01T00:00:00Z","2026-01-01T00:00:00Z","HOLDOUT","untouched temporal holdout"),
        RepresentativeWindow("holdout-2026-h1","2026-01-01T00:00:00Z","2026-07-01T00:00:00Z","HOLDOUT","recent untouched temporal holdout"),
    )
    for row in rows:row.validate()
    return rows


def write_windows(path:Path)->Path:
    rows=locked_representative_windows()
    payload={
        "mode":"RESEARCH_ONLY_HISTORICAL_WINDOWS",
        "selection_basis":"calendar-selected before Atlas strategy-result inspection",
        "holdout_policy":"HOLDOUT windows are evaluation-only and must not be used for candidate parameter tuning",
        "live_capital_allowed":False,
        "automatic_real_money_execution":False,
        "windows":[asdict(row) for row in rows],
    }
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return path


def main(argv:list[str]|None=None)->int:
    import argparse
    p=argparse.ArgumentParser(description="Emit locked Atlas representative historical research windows")
    p.add_argument("--output",type=Path,default=Path("backend/data/research/historical/representative-windows.json"))
    a=p.parse_args(argv);out=write_windows(a.output);print(f"representative_windows={out}");return 0

if __name__=="__main__":raise SystemExit(main())
