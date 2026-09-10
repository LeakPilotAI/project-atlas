"""Read-only cross-domain summary for Project Atlas.

This module may observe both product domains, but it never merges their symbols,
capital assumptions, scores, performance, or action logic. It places no orders.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from app.investment.board import build_quality_dips_board
from app.investment.storage import OPPORTUNITIES_PATH, PLANS_PATH


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _perp_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    setups = list(snapshot.get("setups") or [])
    plans = list(snapshot.get("plans") or [])
    actionable_states = {"PREPARE", "L1_ACTIVE", "L2_ACTIVE", "L3_ACTIVE"}
    top = setups[0] if setups else None
    return {
        "domain": "HYPERLIQUID_PERPS",
        "source": "hyperliquid",
        "execution": "MANUAL_ONLY",
        "running": bool(snapshot.get("running")),
        "updated_at": snapshot.get("updated_at") or snapshot.get("last_refresh_at"),
        "market_count": int(snapshot.get("market_count") or 0),
        "setup_count": len(setups),
        "prime_count": sum(1 for x in setups if str(x.get("tier") or "") == "PRIME"),
        "qualified_count": sum(1 for x in setups if str(x.get("tier") or "") == "QUALIFIED"),
        "actionable_count": sum(1 for x in setups if str(x.get("state") or "") in actionable_states),
        "entered_count": sum(1 for x in plans if str(x.get("status") or "") == "ENTERED"),
        "alert_candidate_count": len(snapshot.get("alert_candidates") or []),
        "top_setup": None if top is None else {
            "symbol": top.get("symbol"),
            "side": top.get("side"),
            "tier": top.get("tier"),
            "state": top.get("state"),
            "score": top.get("score"),
            "next_action": top.get("next_action"),
        },
        "last_error": snapshot.get("last_error"),
        "note": "Hyperliquid-only manual trading guidance. No investment capital assumptions are included.",
    }


def _investment_summary(board: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(board)
    counts = {"ACCUMULATE": 0, "PREPARE": 0, "WATCH": 0, "STAND_DOWN": 0}
    for row in rows:
        stance = str(row.get("stance") or "WATCH")
        counts[stance] = counts.get(stance, 0) + 1
    top = rows[0] if rows else None
    return {
        "domain": "EQUITY_INVESTMENT",
        "source": "investment_research_store",
        "execution": "MANUAL_ONLY",
        "asset_count": len(rows),
        "counts": counts,
        "top_opportunity": None if top is None else {
            "symbol": top.get("symbol"),
            "asset_type": top.get("asset_type"),
            "stance": top.get("stance"),
            "classification": top.get("classification"),
            "opportunity_score": top.get("opportunity_score"),
            "evidence_quality": top.get("evidence_quality"),
            "thesis": top.get("thesis"),
            "ladder_eligible": bool(top.get("ladder_eligible")),
        },
        "note": "Stock/ETF-only investment research. No perp symbols, leverage, or trading state are included.",
    }


def build_command_center_summary(
    perp_snapshot: dict[str, Any],
    research_rows: Iterable[dict[str, Any]],
    plan_rows: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    board = build_quality_dips_board(research_rows, plan_rows, limit=100)
    return {
        "domain": "ORCHESTRATION",
        "mode": "READ_ONLY",
        "execution": "NO_ORDER_ACTIONS",
        "perps": _perp_summary(perp_snapshot),
        "investments": _investment_summary(board),
        "guardrails": {
            "shared_symbols": False,
            "shared_capital_assumptions": False,
            "shared_performance": False,
            "shared_action_logic": False,
        },
        "note": "Command Center observes both domains but never combines their risk, capital, scores, or execution logic.",
    }


def live_command_center_summary(perp_snapshot: dict[str, Any]) -> dict[str, Any]:
    return build_command_center_summary(
        perp_snapshot,
        _load_jsonl(OPPORTUNITIES_PATH),
        _load_jsonl(PLANS_PATH),
    )
