"""Asset-class-neutral Quality Dips research envelope.

E60 scaffolding only. It cannot score, schedule, emit alerts, enter PAPER, mutate
Quality Dips V3 stock state, or authorize execution.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

ASSET_CLASSES = {"STOCK", "CRYPTO"}
CRYPTO_EVIDENCE_DIMENSIONS = (
    "liquidity_depth", "market_structure", "drawdown_regime",
    "supply_unlocks", "venue_custody_contract_risk",
    "network_activity", "manipulation_rug_risk",
)

@dataclass(frozen=True)
class QualityDipsResearchEnvelope:
    asset_class: str
    symbol: str
    universe_eligible: bool
    evidence: dict[str, Any]
    provenance: tuple[str, ...]
    freshness: dict[str, str]
    risk_flags: tuple[str, ...]
    active: bool = False
    can_emit_signal: bool = False
    can_schedule: bool = False
    paper_entry_authority: bool = False
    execution_authority: bool = False
    strategy_selection_authority: bool = False
    threshold_mutation_authority: bool = False
    promotion_authority: bool = False
    live_capital_allowed: bool = False

def build_crypto_research_envelope(*, symbol: str, allowlisted: bool,
                                   liquidity_qualified: bool,
                                   evidence: dict[str, Any],
                                   provenance=(), freshness=None,
                                   risk_flags=()) -> QualityDipsResearchEnvelope:
    sym=str(symbol or "").upper().strip()
    ev=dict(evidence or {})
    missing=[key for key in CRYPTO_EVIDENCE_DIMENSIONS if key not in ev]
    flags=tuple(str(x) for x in risk_flags if str(x))
    if missing:
        flags=flags + tuple(f"MISSING:{key}" for key in missing)
    return QualityDipsResearchEnvelope(
        asset_class="CRYPTO", symbol=sym,
        universe_eligible=bool(sym and allowlisted and liquidity_qualified),
        evidence=ev, provenance=tuple(str(x) for x in provenance if str(x)),
        freshness=dict(freshness or {}), risk_flags=flags,
    )
