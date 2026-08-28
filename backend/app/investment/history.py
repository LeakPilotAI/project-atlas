"""Isolated daily OHLCV store. Dedupes by symbol+date. Never writes trading journals."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from app.investment.bars import OhlcvBar
from app.investment.storage import HISTORY_DIR, ensure_dirs
from app.investment.validate import find_duplicate_dates, validate_ohlc


def _parse_dt(raw: object) -> Optional[datetime]:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def _path(symbol: str, root: Path | None = None) -> Path:
    ensure_dirs()
    base = root or HISTORY_DIR
    base.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch for ch in symbol.upper() if ch.isalnum() or ch in ".-^")
    return base / f"{safe}.jsonl"


def load_dates(symbol: str, root: Path | None = None) -> Set[str]:
    p = _path(symbol, root)
    dates: Set[str] = set()
    if not p.exists():
        return dates
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            d = row.get("date")
            if d:
                dates.add(str(d)[:10])
    return dates


def append_bars(
    symbol: str,
    bars: Iterable[OhlcvBar],
    root: Path | None = None,
) -> Dict[str, int]:
    """Append new dates only. Duplicate dates are skipped and counted.

    Questionable bars are stored with issues attached — never repaired.
    """
    existing = load_dates(symbol, root)
    incoming = [b for b in bars]
    in_dates = [b.session_date for b in incoming]
    dups_in_batch = find_duplicate_dates(in_dates)
    written = skipped_dup = flagged = 0
    p = _path(symbol, root)
    with p.open("a", encoding="utf-8") as f:
        seen_batch: Set[str] = set()
        for bar in incoming:
            d = bar.session_date
            if not d or d in existing or d in seen_batch:
                skipped_dup += 1
                continue
            issues = validate_ohlc(
                session_date=bar.session_date,
                open_=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
            )
            bar.issues = [i.code for i in issues]
            if issues:
                flagged += 1
            f.write(json.dumps(bar.as_dict(), default=str) + "\n")
            existing.add(d)
            seen_batch.add(d)
            written += 1
    return {
        "written": written,
        "skipped_duplicate": skipped_dup,
        "flagged": flagged,
        "batch_internal_duplicates": len(dups_in_batch),
    }


def load_bars(symbol: str, root: Path | None = None) -> List[OhlcvBar]:
    p = _path(symbol, root)
    out: List[OhlcvBar] = []
    if not p.exists():
        return out
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            out.append(
                OhlcvBar(
                    session_date=str(row.get("date") or ""),
                    open=row.get("open"),
                    high=row.get("high"),
                    low=row.get("low"),
                    close=row.get("close"),
                    volume=row.get("volume"),
                    adjusted_close=row.get("adjusted_close"),
                    source=str(row.get("source") or ""),
                    retrieved_at=_parse_dt(row.get("retrieved_at")),
                    effective_timestamp=_parse_dt(row.get("effective_timestamp")),
                    quality=str(row.get("quality") or "UNKNOWN"),
                    issues=list(row.get("issues") or []),
                )
            )
    return out
