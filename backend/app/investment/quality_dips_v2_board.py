"""Quality Dips V2 read-only board projection.

Adds patient-capital research fields to legacy Quality Dips rows without changing
legacy scoring, persistence, or brokerage behavior. Phase 9 exposes the V2 policy to
the API/dashboard while execution remains manual-only.
"""
from __future__ import annotations

from typing import Any, Iterable

from app.investment.quality_dips_v2_evidence import adapt_research_row
from app.investment.quality_dips_v2_entries import build_entry_ladder
from app.investment.quality_dips_v2_gate import evaluate_v2_gate
from app.investment.quality_dips_v2_valuation import from_research_row as valuation_from_research_row


def _merge_valuation(row: dict[str, Any]) -> dict[str, Any]:
    merged = dict(row)
    valuation = valuation_from_research_row(row)
    if valuation.get("valuation_window_complete"):
        merged["normalization_value"] = dict(valuation.get("normalization_value") or {})
    return merged


def build_v2_projection(row: dict[str, Any]) -> dict[str, Any]:
    """Return a read-only V2 projection for one investment research row."""
    merged = _merge_valuation(row)
    evidence = adapt_research_row(merged)
    gate = evaluate_v2_gate(evidence)

    ladder = build_entry_ladder(
        conservative_value=(evidence.get("normalization_value") or {}).get("conservative"),
        current_price=evidence.get("price"),
        valuation_complete=not bool(evidence.get("missing_v2_evidence")),
    )

    return {
        "symbol": evidence.get("symbol"),
        "patient_state": evidence.get("patient_state"),
        "state_reasons": list(evidence.get("state_reasons") or []),
        "evidence_gate": gate,
        "normalization_value": dict(evidence.get("normalization_value") or {}),
        "conservative_upside_pct": evidence.get("conservative_upside_pct"),
        "base_upside_pct": evidence.get("base_upside_pct"),
        "optimistic_upside_pct": evidence.get("optimistic_upside_pct"),
        "trend": dict(evidence.get("trend") or {}),
        "entry_ladder": ladder,
        "missing_v2_evidence": list(evidence.get("missing_v2_evidence") or []),
        "policy": {
            "minimum_upside_hurdle_pct": 29.0,
            "generational_upside_hurdle_pct": 50.0,
            "levels": {"L1": 29.0, "L2": 35.0, "L3": 40.0, "L4": 50.0},
            "price_alone_breaks_thesis": False,
        },
        "execution": "MANUAL_ONLY",
        "read_only": True,
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


def attach_v2_board(
    board: Iterable[dict[str, Any]], research_rows: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in research_rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").upper().strip()
        if not symbol:
            continue
        prev = latest.get(symbol)
        if prev is None or str(row.get("timestamp") or "") >= str(prev.get("timestamp") or ""):
            latest[symbol] = row

    out: list[dict[str, Any]] = []
    for item in board:
        row = dict(item)
        symbol = str(row.get("symbol") or "").upper().strip()
        source = latest.get(symbol)
        row["quality_dips_v2"] = build_v2_projection(source) if source else {
            "symbol": symbol,
            "patient_state": "WATCH",
            "state_reasons": ["no source research row available"],
            "evidence_gate": {"allowed": False, "status": "BLOCKED", "reasons": ["missing source research"]},
            "normalization_value": {},
            "entry_ladder": {"active": False, "levels": []},
            "missing_v2_evidence": ["source_research"],
            "execution": "MANUAL_ONLY",
            "read_only": True,
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        }
        out.append(row)
    return out
