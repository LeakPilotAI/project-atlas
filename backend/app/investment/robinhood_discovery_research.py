"""Bounded broad-universe investment research.

This is intentionally separate from the normal Quality Dips scan.  It evaluates
only a small rotating batch, then promotes a symbol into a research lane using
the same point-in-time scoring engine.  It never submits a brokerage order.
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.core.logging import get_logger
from app.investment.enums import AssetType, EvidenceQuality, InvestmentAlertState, ThesisState
from app.investment.history import load_bars
from app.investment.ingest import InvestmentIngest
from app.investment.research import InvestmentResearch
from app.investment.robinhood_universe_registry import (
    mark_research_failed,
    research_candidates,
    set_research_lane,
)
from app.investment.universe import InvestmentUniverse, UniverseEntry

log = get_logger("robinhood_discovery_research")


class ProviderResearchDataError(RuntimeError):
    def __init__(self, failure_codes: tuple[str, ...]) -> None:
        self.failure_codes = failure_codes
        super().__init__("Provider research data is incomplete")


def classify_lane(rec: Any) -> tuple[str, str]:
    """Conservative lane classifier; drawdown alone can never create QUALITY_DIPS."""
    evidence = rec.evidence_quality
    thesis = rec.thesis
    score = rec.opportunity_score
    components = rec.components
    classification = rec.classification

    if thesis is ThesisState.BROKEN:
        return "EXCLUDED", "current scored thesis is BROKEN"
    if evidence in {EvidenceQuality.INSUFFICIENT, EvidenceQuality.UNKNOWN}:
        return "FRONTIER_RESEARCH", f"evidence is {evidence.value}"

    quality_ok = (
        thesis in {ThesisState.STRONG, ThesisState.INTACT}
        and components.fundamentals is not None
        and components.fundamentals >= 60
        and components.valuation is not None
        and components.valuation >= 55
    )
    if quality_ok and classification in {
        InvestmentAlertState.ACCUMULATION,
        InvestmentAlertState.DEEP_VALUE,
        InvestmentAlertState.GENERATIONAL_OPPORTUNITY,
    }:
        return "QUALITY_DIPS", f"existing Quality Dips action gate classification={classification.value}"

    compounder_ok = (
        thesis in {ThesisState.STRONG, ThesisState.INTACT}
        and components.fundamentals is not None
        and components.fundamentals >= 70
        and components.cash_flow is not None
        and components.cash_flow >= 60
        and score is not None
        and score >= 55
    )
    if compounder_ok:
        return "ESTABLISHED_COMPOUNDER", "strong/intact thesis with supported fundamentals and cash flow"

    if thesis not in {ThesisState.BROKEN, ThesisState.DAMAGED} and score is not None and score >= 40:
        return "EMERGING_COMPOUNDER", "promising scored evidence; not yet a Quality Dip"

    return "FRONTIER_RESEARCH", "does not yet satisfy compounder or Quality Dips evidence gates"


async def research_batch(*, limit: int = 4) -> dict[str, Any]:
    """Research a deliberately tiny rotating batch to protect API/runtime health."""
    candidates = await asyncio.to_thread(research_candidates, limit=max(1, min(int(limit), 8)))
    results: list[dict[str, Any]] = []
    research = InvestmentResearch()
    for row in candidates:
        symbol = str(row.get("symbol") or "").upper().strip()
        if not symbol:
            continue
        entry = UniverseEntry(
            symbol=symbol,
            name=str(row.get("name") or ""),
            asset_type=AssetType.STOCK,
            active=True,
            groups=["robinhood_discovery"],
        )
        try:
            ingest = InvestmentIngest(universe=InvestmentUniverse([entry]), persist=True)
            snap = await ingest.ingest_symbol(entry, history_period="5y")
            if snap.failures:
                failure_codes = tuple(
                    sorted(
                        {
                            str(failure.get("code") or "UNKNOWN")
                            for failure in snap.failures
                            if isinstance(failure, dict)
                        }
                    )
                )
                raise ProviderResearchDataError(failure_codes or ("UNKNOWN",))
            bars = await asyncio.to_thread(load_bars, symbol)
            rec = await asyncio.to_thread(research.score_snapshot, snap, bars)
            lane, reason = classify_lane(rec)
            await asyncio.to_thread(set_research_lane, symbol, lane, reason=reason)
            results.append({
                "symbol": symbol,
                "research_lane": lane,
                "research_status": "SUCCEEDED",
                "classification": rec.classification.value,
                "opportunity_score": rec.opportunity_score,
                "evidence_quality": rec.evidence_quality.value,
                "thesis": rec.thesis.value,
            })
        except Exception as exc:
            error_type = (
                f"ProviderDataUnavailable:{','.join(exc.failure_codes)}"
                if isinstance(exc, ProviderResearchDataError)
                else type(exc).__name__
            )
            await asyncio.to_thread(mark_research_failed, symbol, error_type)
            log.warning(
                "Robinhood universe research failed",
                symbol=symbol,
                error_type=error_type,
            )
            results.append({
                "symbol": symbol,
                "research_lane": str(row.get("research_lane") or "UNCLASSIFIED").upper(),
                "research_status": "FAILED",
                "error": error_type,
            })
        await asyncio.sleep(0.75)
    return {
        "researched": len(results),
        "results": results,
        "execution": "RESEARCH_ONLY_MANUAL",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
