"""Read-only Quality Dips board projection for the Atlas dashboard.

Consumes persisted investment research/allocation rows only. Never reads Hyperliquid
state and never places orders. Scores are ordinal research rankings, not probabilities.
"""

from __future__ import annotations

from typing import Any, Iterable

_ALLOWED_TYPES = {"STOCK", "ETF", "SECTOR_ETF"}
_ACTIONABLE = {"ACCUMULATION", "DEEP_VALUE", "GENERATIONAL_OPPORTUNITY"}


def _readiness(row: dict[str, Any]) -> tuple[str, list[str], list[str], bool]:
    blockers: list[str] = []
    reasons: list[str] = []
    asset_type = str(row.get("asset_type") or "UNKNOWN").upper()
    thesis = str(row.get("thesis") or "UNKNOWN").upper()
    evidence = str(row.get("evidence_quality") or "UNKNOWN").upper()
    classification = str(row.get("classification") or "NO_ACTION").upper()
    missing_critical = list(row.get("missing_critical") or [])
    components = dict(row.get("components") or {})

    if asset_type not in _ALLOWED_TYPES:
        blockers.append("Quality Dips accepts stocks and ETFs only")
    if thesis == "BROKEN" or classification == "THESIS_BROKEN":
        blockers.append("investment thesis is broken")
    if thesis == "UNKNOWN":
        blockers.append("investment thesis is unknown")
    if evidence in {"INSUFFICIENT", "UNKNOWN"}:
        blockers.append("evidence quality is insufficient")
    if missing_critical:
        blockers.append("critical evidence is missing")

    if blockers:
        hard = asset_type not in _ALLOWED_TYPES or thesis == "BROKEN" or classification == "THESIS_BROKEN"
        return ("STAND_DOWN" if hard else "WATCH", blockers, reasons, False)

    if classification not in _ACTIONABLE:
        reasons.append("research classification is not an accumulation state")
        return "WATCH", blockers, reasons, False
    if evidence == "LOW":
        reasons.append("low evidence quality requires confirmation")
        return "PREPARE", blockers, reasons, False
    if thesis in {"DAMAGED", "UNDER_PRESSURE"}:
        reasons.append("thesis is under pressure; do not accumulate yet")
        return "PREPARE", blockers, reasons, False

    required = ["valuation", "fundamentals", "drawdown", "thesis_integrity"]
    missing = [name for name in required if components.get(name) is None]
    if missing:
        reasons.append("missing scored components: " + ", ".join(missing))
        return "PREPARE", blockers, reasons, False

    reasons.append("sufficient evidence with intact thesis and complete core scoring")
    return "ACCUMULATE", blockers, reasons, True


def _latest_by_symbol(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").upper().strip()
        if not symbol:
            continue
        prev = latest.get(symbol)
        if prev is None or str(row.get("timestamp") or "") >= str(prev.get("timestamp") or ""):
            latest[symbol] = row
    return list(latest.values())


def build_quality_dips_board(
    research_rows: Iterable[dict[str, Any]],
    plan_rows: Iterable[dict[str, Any]] = (),
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    latest_plans: dict[str, dict[str, Any]] = {}
    for plan in plan_rows:
        if not isinstance(plan, dict):
            continue
        symbol = str(plan.get("symbol") or "").upper().strip()
        if symbol:
            latest_plans[symbol] = plan

    board: list[dict[str, Any]] = []
    for row in _latest_by_symbol(research_rows):
        asset_type = str(row.get("asset_type") or "UNKNOWN").upper()
        if asset_type not in _ALLOWED_TYPES:
            continue
        stance, blockers, reasons, ladder_eligible = _readiness(row)
        plan = latest_plans.get(str(row.get("symbol") or "").upper()) or {}
        tiers = list(plan.get("tiers") or []) if ladder_eligible and str(plan.get("status") or "") == "ACTIVE" else []
        drawdown = dict(row.get("drawdown") or {})
        board.append({
            "symbol": str(row.get("symbol") or "").upper(),
            "name": row.get("name") or "",
            "asset_type": asset_type,
            "price": row.get("price"),
            "timestamp": row.get("timestamp"),
            "classification": row.get("classification") or "NO_ACTION",
            "stance": stance,
            "ladder_eligible": ladder_eligible,
            "opportunity_score": row.get("opportunity_score"),
            "evidence_quality": row.get("evidence_quality") or "UNKNOWN",
            "thesis": row.get("thesis") or "UNKNOWN",
            "components": dict(row.get("components") or {}),
            "current_drawdown": drawdown.get("current_drawdown"),
            "drawdown_percentile": drawdown.get("percentile") or drawdown.get("historical_percentile"),
            "coverage_label": row.get("coverage_label") or "",
            "blockers": blockers,
            "reasons": reasons,
            "missing_critical": list(row.get("missing_critical") or []),
            "invalidation": list((row.get("explain") or {}).get("invalidation") or []),
            "risks": list((row.get("explain") or {}).get("risks") or []),
            "plan_status": plan.get("status") or "NONE",
            "maximum_target_allocation": plan.get("maximum_target_allocation"),
            "reserve_cash": plan.get("reserve_cash"),
            "tiers": tiers,
            "domain": "EQUITY_INVESTMENT",
            "execution": "MANUAL_ONLY",
        })

    rank = {"ACCUMULATE": 0, "PREPARE": 1, "WATCH": 2, "STAND_DOWN": 3}
    board.sort(key=lambda r: (rank.get(str(r["stance"]), 9), -(float(r.get("opportunity_score") or 0))))
    return board[: max(1, int(limit))]
