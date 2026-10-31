"""Read-only, fail-closed UTC-day evidence for Perp mirror admission.

This is not a portfolio-wide strategy policy. Never repair the source journal.
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.paper_accounting import is_administrative, recorded_net_r
from app.services.paper_journal import JOURNAL_PATH


def _version(path: Path) -> list[int]:
    stat = path.stat()
    return [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns]


def unavailable_risk_snapshot(reason: str = "snapshot computation failed") -> dict[str, Any]:
    return {
        "net_r": None, "closed": 0, "reliable": False, "issues": [reason],
        "window": "UTC_DAY", "window_date": datetime.now(UTC).date().isoformat(),
        "source": "PAPER_JOURNAL_REALIZED_CLOSES",
    }


def risk_snapshot_is_current(snapshot: dict[str, Any]) -> bool:
    """Recheck after the worker yields: a new close or UTC rollover invalidates it."""
    if snapshot.get("reliable") is not True:
        return False
    if snapshot.get("window_date") != datetime.now(UTC).date().isoformat():
        return False
    try:
        return _version(Path(snapshot["journal_path"])) == snapshot["journal_version"]
    except (OSError, KeyError, TypeError, ValueError):
        return False


def utc_day_risk_snapshot(path: Path = JOURNAL_PATH, *, now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    current = current.astimezone(UTC)
    snapshot = unavailable_risk_snapshot()
    snapshot.update(window_date=current.date().isoformat(), issues=[], journal_path=str(path.resolve()))
    issues: set[str] = set()
    seen: dict[str, tuple[Any, ...]] = {}
    legacy_seen: set[str] = set()
    values: list[float] = []
    duplicates = 0
    try:
        before = _version(path)
        # Bound the read to the captured file size; appends during parsing are
        # detected below and again on the event loop before authorizing entry.
        with path.open("rb") as handle:
            raw = handle.read(before[2])
        if raw and not raw.endswith(b"\n"):
            issues.add("unterminated journal record")
        for line in raw.decode("utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except (ValueError, TypeError):
                issues.add("malformed journal record")
                continue
            if not isinstance(row, dict) or not isinstance(row.get("event"), str):
                issues.add("invalid journal record")
                continue
            if row["event"] not in {"open", "mark", "close", "session_start"}:
                issues.add("unknown journal event")
                continue
            trade_type = str(row.get("trade_type") or "PAPER").upper()
            if trade_type == "TEST":
                continue
            if trade_type != "PAPER":
                issues.add("unknown journal trade type")
                continue
            if row["event"] != "close" or is_administrative(row):
                continue
            stamp = row.get("exit_timestamp") or row.get("timestamp")
            try:
                # Historical naive timestamps mean UTC; date-only is not a close time.
                if not isinstance(stamp, str) or len(stamp) < 19:
                    raise ValueError("missing close timestamp")
                ts = datetime.fromisoformat(stamp)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                ts = ts.astimezone(UTC)
            except (ValueError, TypeError, OverflowError):
                issues.add("unknown close timestamp")
                continue
            value = recorded_net_r(row)
            tid = str(row.get("trade_id") or "")
            signature = (ts.isoformat(), value, row.get("symbol"), row.get("side"), row.get("strategy"))
            if tid:
                if tid in seen:
                    duplicates += 1
                    if seen[tid] != signature:
                        issues.add("conflicting duplicate close")
                    continue
                seen[tid] = signature
            else:
                # Valid legacy id-less closes remain supported. Identical repeats
                # lack enough identity to decide whether there were two fills.
                identity = json.dumps(row, sort_keys=True)
                if identity in legacy_seen:
                    issues.add("ambiguous duplicate legacy close")
                    continue
                legacy_seen.add(identity)
            if ts > current:
                issues.add("future close timestamp")
                continue
            if ts.date() != current.date():
                continue
            if value is None:
                issues.add("unknown current-day net R")
                continue
            values.append(value)
        if _version(path) != before or len(raw) != before[2]:
            issues.add("journal changed during snapshot")
        snapshot["journal_version"] = before
    except (OSError, UnicodeError):
        issues.add("journal missing or unreadable")
    try:
        total = math.fsum(values)
        if not math.isfinite(total):
            raise OverflowError
    except (OverflowError, ValueError):
        total = None
        issues.add("nonfinite realized total")
    snapshot.update(
        net_r=total if not issues else None, closed=len(values),
        reliable=not issues, issues=sorted(issues), duplicate_closes=duplicates,
    )
    return snapshot
