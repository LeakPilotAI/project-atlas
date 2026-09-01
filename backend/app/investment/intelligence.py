"""Compose move + relative + cause + review for one symbol. Investment-only."""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from app.investment.bars import OhlcvBar
from app.investment.cause import CauseRecord, infer_cause
from app.investment.enums import EvidenceQuality, MoveClassification, ThesisState
from app.investment.history import load_bars
from app.investment.moves import (
    MoveReport,
    apply_thesis_safety,
    is_actionable_dislocation,
    score_move,
)
from app.investment.relative import RelativeReport, relative_report
from app.investment.research_models import ResearchRecord
from app.investment.review_levels import ReviewLevels, build_review_levels
from app.investment.universe import InvestmentUniverse, UniverseEntry


def _bars(symbol: str, root) -> Sequence[OhlcvBar]:
    if not symbol:
        return []
    return load_bars(symbol, root=root)


def evaluate_equity_move(
    entry: UniverseEntry,
    rec: ResearchRecord,
    *,
    universe: InvestmentUniverse,
    history_root=None,
    headlines: Optional[list] = None,
    deteriorating: bool = False,
) -> Dict[str, Any]:
    asset_bars = _bars(entry.symbol, history_root)
    spy_sym = universe.spy_symbol()
    qqq_sym = universe.qqq_symbol()
    sector_sym = universe.sector_etf_for(entry)
    rel: RelativeReport = relative_report(
        symbol=entry.symbol,
        asset_bars=asset_bars,
        spy_bars=_bars(spy_sym, history_root) if spy_sym else (),
        qqq_bars=_bars(qqq_sym, history_root) if qqq_sym else (),
        sector_bars=_bars(sector_sym, history_root) if sector_sym else (),
        spy_symbol=spy_sym,
        qqq_symbol=qqq_sym,
        sector_symbol=sector_sym,
    )
    move: MoveReport = score_move(
        symbol=entry.symbol,
        bars=asset_bars,
        relative=rel,
        current_price=rec.price,
    )
    move.classification = apply_thesis_safety(
        move,
        thesis=rec.thesis,
        evidence=rec.evidence_quality,
        deteriorating=deteriorating,
    )
    cause: CauseRecord = infer_cause(headlines=headlines, relative=rel)
    actionable = is_actionable_dislocation(
        move.classification,
        thesis=rec.thesis,
        evidence=rec.evidence_quality,
    )
    reviews: Optional[ReviewLevels] = None
    if actionable or move.classification in (
        MoveClassification.MAJOR_DISLOCATION,
        MoveClassification.EXTREME_DISLOCATION,
    ):
        if rec.thesis not in (ThesisState.BROKEN, ThesisState.DAMAGED) and rec.evidence_quality not in (
            EvidenceQuality.INSUFFICIENT,
            EvidenceQuality.UNKNOWN,
        ):
            reviews = build_review_levels(
                price=rec.price,
                atr=move.atr,
                drawdown=move.drawdown,
                vol_ann=move.vol_ann,
                thesis=rec.thesis,
                move=move,
            )
        else:
            reviews = ReviewLevels(
                invalidation=["thesis/evidence block accumulation — no recovery ladder"],
            )
    tape_row = {
        "symbol": entry.symbol,
        "name": entry.name or rec.name,
        "price": rec.price,
        "ret_1d": move.ret_1d,
        "ret_5d": move.ret_5d,
        "ret_20d": move.ret_20d,
        "drawdown": move.drawdown,
        "rel_volume": move.rel_volume,
        "atr_norm": move.atr_norm,
        "vs_spy": rel.vs_spy_1d,
        "vs_qqq": rel.vs_qqq_1d,
        "vs_sector": rel.vs_sector_1d,
        "sector": entry.sector,
        "sector_etf": sector_sym,
        "move_score": move.score,
        "breakdown": move.breakdown.as_dict(),
        "thesis": rec.thesis.value,
        "evidence": rec.evidence_quality.value,
        "valuation": rec.components.valuation,
        "classification": move.classification.value,
        "cause": cause.as_dict(),
        "opportunity_score": rec.opportunity_score,
        "investment_class": rec.classification.value,
        "actionable": actionable,
    }
    return {
        "move": move,
        "relative": rel,
        "cause": cause,
        "review": reviews,
        "actionable": actionable,
        "tape_row": tape_row,
    }
