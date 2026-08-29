"""Dataset readiness for later historical research. Not a profitability claim."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.investment.integrity import pit_audit
from app.investment.monitor import collection_monitor
from app.investment.quality import asset_quality_breakdown
from app.investment.scan_store import load_observations
from app.investment.storage import OBSERVATIONS_PATH

# Gates for READY FOR RESEARCH (dataset trust, not strategy success).
READY_MIN_VALID = 500
READY_MIN_ASSETS = 15
READY_MIN_SESSIONS = 10
READY_MIN_SECTORS = 4
READY_MIN_ASSET_TYPES = 2
READY_MIN_PROVIDER_SUCCESS = 0.60
READY_MIN_PIT_RATE = 0.95
READY_MAX_LOOKAHEAD = 0
READY_MIN_FUND_FRESH_ASSETS = 8
READY_MIN_HIST_FRESH_ASSETS = 10
COLLECTING_MIN_VALID = 1


def _pass(ok: bool, detail: str) -> Dict[str, Any]:
    return {"ok": ok, "detail": detail}


def _fund_val_hist_counts(observations_path: Optional[Path]) -> Tuple[int, int, int, int]:
    q = asset_quality_breakdown(observations_path)
    assets = q.get("assets") or []
    fund = sum(1 for a in assets if (a.get("groups") or {}).get("fundamentals") in ("FRESH", "STALE"))
    val = sum(1 for a in assets if (a.get("groups") or {}).get("valuation") in ("FRESH", "STALE"))
    hist = sum(1 for a in assets if (a.get("groups") or {}).get("history") in ("FRESH", "STALE"))
    return len(assets), fund, val, hist


def dataset_readiness(
    observations_path: Optional[Path] = None,
    **monitor_kwargs,
) -> Dict[str, Any]:
    path = observations_path or OBSERVATIONS_PATH
    mon = collection_monitor(path, **monitor_kwargs)
    audit = pit_audit(path)
    n_assets, fund_n, val_n, hist_n = _fund_val_hist_counts(path)
    checks: Dict[str, Dict[str, Any]] = {}

    valid = int(mon["valid_observations"])
    checks["valid_observations"] = _pass(
        valid >= READY_MIN_VALID,
        f"{valid} / {READY_MIN_VALID} VALID+VALID_NO_ACTION",
    )
    assets = int(mon["unique_assets"])
    checks["unique_assets"] = _pass(assets >= READY_MIN_ASSETS, f"{assets} / {READY_MIN_ASSETS}")
    sessions = int(mon["session_dates"])
    checks["market_sessions"] = _pass(
        sessions >= READY_MIN_SESSIONS, f"{sessions} distinct dates / {READY_MIN_SESSIONS}"
    )
    sectors = [s for s in (mon.get("by_sector") or {}) if s and s != "UNKNOWN"]
    checks["sector_diversity"] = _pass(
        len(sectors) >= READY_MIN_SECTORS, f"{len(sectors)} named sectors / {READY_MIN_SECTORS}"
    )
    types = [t for t in (mon.get("by_asset_type") or {}) if t and t != "UNKNOWN"]
    stock_etf = {"STOCK", "ETF"} & set(types)
    checks["asset_diversity"] = _pass(
        len(stock_etf) >= READY_MIN_ASSET_TYPES or len(types) >= READY_MIN_ASSET_TYPES,
        f"types={sorted(types)} (want STOCK and ETF)",
    )
    sr = mon.get("provider_success_rate")
    checks["provider_reliability"] = _pass(
        isinstance(sr, float) and sr >= READY_MIN_PROVIDER_SUCCESS,
        f"success_rate={sr if sr is not None else 'n/a'} (need ≥ {READY_MIN_PROVIDER_SUCCESS:.0%})",
    )
    checks["fundamental_completeness"] = _pass(
        fund_n >= READY_MIN_FUND_FRESH_ASSETS,
        f"{fund_n} assets with usable fundamentals / {READY_MIN_FUND_FRESH_ASSETS}",
    )
    checks["valuation_completeness"] = _pass(
        val_n >= READY_MIN_FUND_FRESH_ASSETS,
        f"{val_n} assets with usable valuation / {READY_MIN_FUND_FRESH_ASSETS}",
    )
    checks["historical_price_coverage"] = _pass(
        hist_n >= READY_MIN_HIST_FRESH_ASSETS,
        f"{hist_n} assets with history / {READY_MIN_HIST_FRESH_ASSETS}",
    )
    pit_rate = audit.get("reconstructable_rate")
    checks["point_in_time_integrity"] = _pass(
        isinstance(pit_rate, float) and pit_rate >= READY_MIN_PIT_RATE and audit["observations"] > 0,
        f"reconstructable {audit['reconstructable']} / {audit['observations']}",
    )
    checks["look_ahead"] = _pass(
        audit["lookahead_violations"] <= READY_MAX_LOOKAHEAD,
        f"{audit['lookahead_violations']} look-ahead flags (need 0)",
    )

    all_ok = all(c["ok"] for c in checks.values())
    lookahead_fail = not checks["look_ahead"]["ok"]
    if all_ok:
        status = "READY FOR RESEARCH"
    elif valid >= COLLECTING_MIN_VALID and not lookahead_fail:
        status = "COLLECTING"
    else:
        status = "NOT READY"

    blockers = [f"{k}: {v['detail']}" for k, v in checks.items() if not v["ok"]]
    return {
        "status": status,
        "checks": checks,
        "blockers": blockers,
        "monitor": mon,
        "audit": {
            "lookahead_violations": audit["lookahead_violations"],
            "reconstructable": audit["reconstructable"],
            "flagged": audit["flagged"],
            "clean": audit["clean"],
        },
        "disclaimer": (
            "READY FOR RESEARCH means the dataset is trustworthy enough to study later. "
            "It does not mean the strategy is profitable, has alpha, or has a win rate. "
            "Do not loosen filters because GENERATIONAL is rare."
        ),
    }


def format_readiness(report: Optional[Dict[str, Any]] = None, **kwargs) -> str:
    r = report or dataset_readiness(**kwargs)
    lines = [
        "**DATASET READINESS**",
        f"DATASET STATUS: {r['status']}",
        "",
    ]
    for k, v in (r.get("checks") or {}).items():
        mark = "PASS" if v.get("ok") else "FAIL"
        lines.append(f"{mark}  {k}: {v.get('detail')}")
    lines += ["", "Blockers:"]
    blockers = r.get("blockers") or []
    if not blockers:
        lines.append("(none)")
    else:
        for b in blockers:
            lines.append(f"  • {b}")
    lines += ["", r.get("disclaimer") or ""]
    return "\n".join(lines)
