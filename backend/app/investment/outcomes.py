"""Future outcome measurement — separate from scoring.

These fields stay NULL on the original observation at timestamp T.
A later process may fill them using prices *after* T. That write goes to
`data/investment/outcomes.jsonl` and never overwrites the research record.

Do not import this module from `research.py` / `scoring.py`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from app.investment.bars import OhlcvBar
from app.investment.lookahead import as_of_date, filter_bars_as_of
from app.investment.storage import OUTCOMES_PATH, ensure_dirs

HORIZONS = {"1d": 1, "5d": 5, "20d": 20, "60d": 60, "252d": 252}


def empty_outcomes() -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {}
    for h in HORIZONS:
        out[f"price_{h}"] = None
        out[f"return_{h}"] = None
    out["max_adverse_excursion"] = None
    out["max_favorable_excursion"] = None
    out["time_to_recovery"] = None
    return out


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def sessions_after(bars: Iterable[OhlcvBar], as_of: datetime) -> List[OhlcvBar]:
    """Bars strictly after T. Used only by enrichment, never by scoring."""
    cutoff = as_of_date(as_of)
    later = [b for b in bars if b.session_date and b.session_date > cutoff and b.close is not None]
    later.sort(key=lambda b: b.session_date)
    return later


def measure_outcomes(
    *,
    price_at_t: Optional[float],
    as_of: datetime,
    bars: Iterable[OhlcvBar],
    now: datetime,
) -> Dict[str, Optional[float]]:
    """Fill horizons that have already elapsed. Leave the rest NULL.

    `bars` may include the full history; future-of-*now* is dropped so we
    do not peek past the enrichment clock either.
    """
    result = empty_outcomes()
    if price_at_t in (None, 0):
        return result
    px = float(price_at_t)
    known = filter_bars_as_of(bars, now)
    later = sessions_after(known, as_of)
    if not later:
        return result

    elapsed = {h: later[n - 1] if len(later) >= n else None for h, n in HORIZONS.items()}
    for h, bar in elapsed.items():
        if bar is None or bar.close is None:
            continue
        result[f"price_{h}"] = float(bar.close)
        result[f"return_{h}"] = (float(bar.close) / px) - 1.0

    # MAE / MFE from subsequent highs/lows once at least 1 session exists.
    lows = [b.low for b in later if b.low is not None]
    highs = [b.high for b in later if b.high is not None]
    if lows:
        result["max_adverse_excursion"] = (min(lows) / px) - 1.0
    if highs:
        result["max_favorable_excursion"] = (max(highs) / px) - 1.0

    dipped = any(b.close is not None and b.close < px for b in later)
    if dipped:
        recov = next((i for i, b in enumerate(later, start=1) if b.close is not None and b.close >= px), None)
        result["time_to_recovery"] = None if recov is None else float(recov)
    elif len(later) >= HORIZONS["252d"]:
        result["time_to_recovery"] = 0.0
    return result


def persist_outcome(
    *,
    observation_id: str,
    symbol: str,
    as_of: datetime,
    outcomes: Dict[str, Optional[float]],
    path: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> None:
    ensure_dirs()
    p = path or OUTCOMES_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now(timezone.utc)
    row = {
        "observation_id": observation_id,
        "symbol": symbol,
        "as_of": _iso(as_of),
        "enriched_at": _iso(now),
        "look_ahead_protected": True,
        **outcomes,
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def load_outcomes(path: Optional[Path] = None) -> List[dict]:
    p = path or OUTCOMES_PATH
    if not p.exists():
        return []
    out: List[dict] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def enrich_observation(
    obs: dict,
    bars: Iterable[OhlcvBar],
    *,
    now: Optional[datetime] = None,
    outcomes_path: Optional[Path] = None,
) -> Optional[dict]:
    """Read-only on `obs`. Writes a new outcomes row. Returns the row or None."""
    now = now or datetime.now(timezone.utc)
    as_of_raw = obs.get("as_of") or obs.get("timestamp")
    if not as_of_raw:
        return None
    try:
        as_of = datetime.fromisoformat(str(as_of_raw).replace("Z", "+00:00"))
    except Exception:
        return None
    research = obs.get("research") if isinstance(obs.get("research"), dict) else obs
    price = research.get("price") if isinstance(research, dict) else obs.get("price")
    outcomes = measure_outcomes(price_at_t=price, as_of=as_of, bars=bars, now=now)
    if all(v is None for v in outcomes.values()):
        return None
    persist_outcome(
        observation_id=str(obs.get("observation_id") or ""),
        symbol=str(obs.get("symbol") or research.get("symbol") or ""),
        as_of=as_of,
        outcomes=outcomes,
        path=outcomes_path,
        now=now,
    )
    return outcomes
