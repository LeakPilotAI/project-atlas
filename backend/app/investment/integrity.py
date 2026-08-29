"""Point-in-time integrity audit. Flags rows that cannot be reconstructed at T."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.investment.lookahead import as_of_date
from app.investment.scan_store import load_observations
from app.investment.storage import OBSERVATIONS_PATH


def _parse(raw: object) -> Optional[datetime]:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def _date_only(raw: object) -> Optional[str]:
    if not raw:
        return None
    s = str(raw)
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    dt = _parse(raw)
    return dt.date().isoformat() if dt else None


def audit_observation(row: dict) -> Dict[str, Any]:
    flags: List[str] = []
    as_of_raw = row.get("as_of") or row.get("timestamp")
    as_of = _parse(as_of_raw)
    if as_of is None:
        flags.append("missing as_of timestamp")
    known = row.get("known_at") if isinstance(row.get("known_at"), dict) else {}
    if not known:
        flags.append("missing known_at — cannot reconstruct what Atlas knew at T")

    cutoff_as_of = as_of_date(as_of) if as_of else _date_only(as_of_raw)

    hist = _date_only(known.get("history_cutoff"))
    if hist and cutoff_as_of and hist > cutoff_as_of:
        flags.append(f"look-ahead: history_cutoff {hist} after as_of {cutoff_as_of}")

    for key in ("price_effective", "price_retrieved", "fundamentals_retrieved", "valuation_retrieved"):
        dt = _parse(known.get(key))
        if dt and as_of and dt > as_of:
            flags.append(f"look-ahead: {key} {dt.isoformat()} after as_of")

    if row.get("look_ahead_protected") is False:
        flags.append("look_ahead_protected is false")

    outcomes = row.get("outcomes") if isinstance(row.get("outcomes"), dict) else {}
    leaked = [k for k, v in outcomes.items() if v is not None]
    if leaked:
        flags.append(f"outcome fields populated on observation at T: {', '.join(leaked[:6])}")

    reconstructable = not any(
        f.startswith("missing") or "cannot reconstruct" in f for f in flags
    ) and "missing as_of timestamp" not in flags
    lookahead = any("look-ahead" in f or "look_ahead_protected is false" in f for f in flags)
    return {
        "observation_id": row.get("observation_id"),
        "symbol": row.get("symbol"),
        "as_of": str(as_of_raw) if as_of_raw else None,
        "flags": flags,
        "ok": not flags,
        "reconstructable": reconstructable and not lookahead,
        "lookahead": lookahead,
    }


def pit_audit(observations_path: Optional[Path] = None) -> Dict[str, Any]:
    rows = load_observations(observations_path or OBSERVATIONS_PATH)
    results = [audit_observation(r) for r in rows]
    flagged = [r for r in results if not r["ok"]]
    lookahead_n = sum(1 for r in results if r["lookahead"])
    recon_n = sum(1 for r in results if r["reconstructable"])
    n = len(results)
    return {
        "observations": n,
        "ok": n - len(flagged),
        "flagged": len(flagged),
        "lookahead_violations": lookahead_n,
        "reconstructable": recon_n,
        "reconstructable_rate": (recon_n / n) if n else None,
        "flags": flagged[:50],
        "clean": lookahead_n == 0,
        "note": "Audit only. Does not change scores. Future prices must not sit on the T observation.",
    }


def format_pit_audit(report: Optional[Dict[str, Any]] = None, **kwargs) -> str:
    r = report or pit_audit(**kwargs)
    lines = [
        "**POINT-IN-TIME INTEGRITY AUDIT**",
        f"Observations: {r['observations']}",
        f"Reconstructable: {r['reconstructable']}",
        f"Flagged: {r['flagged']}",
        f"Look-ahead violations: {r['lookahead_violations']}",
        f"Clean: {'YES' if r['clean'] else 'NO'}",
        "",
    ]
    flags = r.get("flags") or []
    if not flags:
        lines.append("No integrity flags.")
    else:
        lines.append("Flagged rows:")
        for f in flags[:20]:
            reasons = "; ".join(f.get("flags") or [])
            lines.append(f"  {f.get('symbol')} {f.get('observation_id')}: {reasons}")
    lines += ["", str(r.get("note") or "")]
    return "\n".join(lines)
