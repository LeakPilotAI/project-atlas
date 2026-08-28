"""Phase 3 research engine: snapshot + history → scored, explainable record.

No alerts. No allocation. No orders. No ML. Not started from main.py.
Does not import the trading / paper stack.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from app.investment.bars import OhlcvBar
from app.investment.drawdown import DrawdownReport, analyze_drawdown, return_volatility
from app.investment.enums import (
    AssetType,
    DataQuality,
    EvidenceQuality,
    InvestmentAlertState,
    ThesisState,
)
from app.investment.history import load_bars
from app.investment.models import MeasuredValue
from app.investment.research_models import (
    SCORING_VERSION,
    ComponentScores,
    Explainability,
    ResearchRecord,
)
from app.investment.scoring import (
    combine_components,
    conflicting_in,
    score_balance_sheet,
    score_cash_flow,
    score_drawdown_context,
    score_evidence,
    score_growth,
    score_profitability,
    score_thesis,
    score_valuation,
)
from app.investment.snapshot import InvestmentSnapshot

PASSIVE_TYPES = {AssetType.ETF, AssetType.INDEX, AssetType.SECTOR_ETF}


def _usable(mv: Optional[MeasuredValue]) -> Optional[float]:
    if mv is None or not mv.is_usable():
        return None
    try:
        return float(mv.value)
    except (TypeError, ValueError):
        return None


def assess_thesis(
    funds: Dict[str, MeasuredValue],
    *,
    asset_type: AssetType = AssetType.UNKNOWN,
) -> Tuple[ThesisState, List[str], List[str]]:
    """Thesis from the *current* snapshot only. Trends are UNKNOWN without history."""
    notes: List[str] = []
    flags: List[str] = []
    earnings = _usable(funds.get("earnings"))
    fcf = _usable(funds.get("free_cash_flow"))
    ocf = _usable(funds.get("operating_cash_flow"))
    net_m = _usable(funds.get("net_margin"))
    cash = _usable(funds.get("cash"))
    debt = _usable(funds.get("total_debt"))
    mcap = _usable(funds.get("market_cap"))
    rev = _usable(funds.get("revenue"))

    usable_n = sum(
        1
        for v in (earnings, fcf, ocf, net_m, cash, debt, mcap, rev)
        if v is not None
    )
    notes.append("thesis uses the current fundamentals snapshot; trend/deterioration over time is UNKNOWN")

    if usable_n < 3:
        if asset_type in PASSIVE_TYPES:
            notes.append("passive vehicle: issuer-level thesis not inferred from thin ETF/index fields")
        else:
            notes.append("too few fundamental fields for a thesis call")
        return ThesisState.UNKNOWN, notes, flags

    if earnings is not None and earnings < 0:
        flags.append("negative_earnings")
    if fcf is not None and fcf < 0:
        flags.append("negative_fcf")
    if ocf is not None and ocf < 0:
        flags.append("negative_ocf")
    if net_m is not None and net_m < 0:
        flags.append("negative_margins")
    if cash is not None and debt is not None and cash > 0 and debt > 3 * cash:
        flags.append("high_leverage")
    elif debt is not None and mcap is not None and mcap > 0 and debt / mcap > 0.80:
        flags.append("high_leverage")

    severe = {"negative_earnings", "negative_fcf", "high_leverage", "negative_margins"}
    collapse = "negative_earnings" in flags and "negative_fcf" in flags
    if collapse and ("high_leverage" in flags or "negative_margins" in flags):
        notes.append("current snapshot shows earnings + cash-flow collapse with additional stress")
        return ThesisState.BROKEN, notes, flags
    if collapse:
        notes.append("earnings and free cash flow both not positive")
        return ThesisState.DAMAGED, notes, flags
    if len(flags) >= 2:
        notes.append("multiple current-state red flags")
        return ThesisState.UNDER_PRESSURE, notes, flags
    if len(flags) == 1:
        if flags[0] in severe:
            notes.append(f"single red flag: {flags[0]}")
            return ThesisState.UNDER_PRESSURE, notes, flags
        return ThesisState.INTACT, notes, flags

    profitable = earnings is not None and earnings > 0
    cash_ok = fcf is None or fcf > 0
    healthy_bs = "high_leverage" not in flags
    if profitable and cash_ok and healthy_bs and usable_n >= 5:
        notes.append("current profitability, cash generation, and leverage look intact")
        return ThesisState.STRONG, notes, flags
    notes.append("no severe current red flags")
    return ThesisState.INTACT, notes, flags


def assess_evidence(
    snap: InvestmentSnapshot,
    dd: DrawdownReport,
) -> Tuple[EvidenceQuality, List[str], List[str]]:
    notes: List[str] = []
    missing: List[str] = []
    price_ok = snap.price.is_usable()
    if not price_ok:
        missing.append("price")
        notes.append("usable price missing")

    fund_keys = [
        "revenue",
        "earnings",
        "eps",
        "free_cash_flow",
        "operating_cash_flow",
        "gross_margin",
        "operating_margin",
        "net_margin",
        "total_debt",
        "cash",
        "shares_outstanding",
        "market_cap",
    ]
    usable_funds = [k for k in fund_keys if _usable(snap.fundamentals.get(k)) is not None]
    for k in ("revenue", "earnings", "free_cash_flow", "shares_outstanding"):
        if k not in usable_funds:
            missing.append(k)

    val_keys = ["pe", "forward_pe", "ps", "pb", "ev_ebitda", "fcf_yield", "earnings_yield", "price_to_fcf"]
    usable_val = [k for k in val_keys if _usable(snap.valuation.get(k)) is not None]
    if not usable_val:
        missing.append("valuation")

    n_bars = dd.coverage_bars
    all_mvs = [snap.price, *snap.fundamentals.values(), *snap.valuation.values()]
    conflict = conflicting_in(all_mvs)
    if conflict:
        notes.append("conflicting values present — evidence reduced, values not repaired")
    if snap.failures:
        notes.append(f"provider failures: {len(snap.failures)}")
    stale_price = snap.price.quality is DataQuality.STALE
    if stale_price:
        notes.append("price is STALE")

    notes.append(
        f"fundamental fields usable {len(usable_funds)}/{len(fund_keys)}; "
        f"valuation fields usable {len(usable_val)}/{len(val_keys)}; "
        f"history {n_bars} bars"
    )

    if not price_ok:
        return EvidenceQuality.INSUFFICIENT, notes, missing

    is_passive = snap.asset.asset_type in PASSIVE_TYPES
    fund_n = len(usable_funds)
    val_n = len(usable_val)

    high = (
        not conflict
        and not snap.failures
        and snap.price.quality is DataQuality.FRESH
        and fund_n >= 8
        and val_n >= 3
        and n_bars >= 500
    )
    medium = (
        not conflict
        and fund_n >= (2 if is_passive else 5)
        and val_n >= 2
        and n_bars >= 252
        and snap.price.quality in (DataQuality.FRESH, DataQuality.STALE)
    )
    low = (fund_n >= 2 or val_n >= 1) and n_bars >= 60

    if high:
        q = EvidenceQuality.HIGH
    elif medium:
        q = EvidenceQuality.MEDIUM
        if conflict:
            q = EvidenceQuality.LOW
    elif low:
        q = EvidenceQuality.LOW
        if conflict:
            q = EvidenceQuality.INSUFFICIENT
    else:
        q = EvidenceQuality.INSUFFICIENT
        notes.append("coverage too thin for a high-conviction read")

    if is_passive and q is EvidenceQuality.HIGH:
        q = EvidenceQuality.MEDIUM
        notes.append("ETF/index evidence capped at MEDIUM (issuer fundamentals often not comparable)")

    return q, notes, missing


def assess_risk(
    *,
    dd: DrawdownReport,
    vol: Optional[float],
    thesis: ThesisState,
    evidence: EvidenceQuality,
    funds: Dict[str, MeasuredValue],
    bars: Sequence[OhlcvBar],
) -> Tuple[Optional[int], List[str], List[str], List[str]]:
    """Higher score = more acceptable risk (same direction as other components)."""
    market: List[str] = []
    fundamental: List[str] = []
    data: List[str] = []
    parts: List[float] = []

    if vol is None:
        market.append("volatility UNKNOWN (history too short)")
    else:
        market.append(f"annualized close-to-close vol ~ {vol:.0%} in-sample")
        if vol < 0.18:
            parts.append(82.0)
        elif vol < 0.28:
            parts.append(70.0)
        elif vol < 0.40:
            parts.append(52.0)
        elif vol < 0.55:
            parts.append(35.0)
        else:
            parts.append(18.0)
            market.append("very high realized volatility")

    if dd.current_drawdown is not None:
        mag = -dd.current_drawdown
        if mag >= 0.40:
            market.append(f"deep current drawdown ({dd.current_drawdown:.0%}) — path risk is elevated")
            parts.append(40.0)
        elif mag >= 0.20:
            market.append(f"material current drawdown ({dd.current_drawdown:.0%})")
            parts.append(58.0)
        else:
            parts.append(75.0)

    vols = [b.volume for b in bars[-20:] if b.volume is not None]
    if vols:
        avg_v = sum(vols) / len(vols)
        if avg_v <= 0:
            market.append("recent volume is zero/empty")
            parts.append(30.0)

    if thesis is ThesisState.BROKEN:
        fundamental.append("thesis BROKEN")
        parts.append(8.0)
    elif thesis is ThesisState.DAMAGED:
        fundamental.append("thesis DAMAGED")
        parts.append(22.0)
    elif thesis is ThesisState.UNDER_PRESSURE:
        fundamental.append("thesis UNDER_PRESSURE")
        parts.append(45.0)
    elif thesis is ThesisState.UNKNOWN:
        fundamental.append("thesis UNKNOWN")
    else:
        parts.append(78.0)

    debt = _usable(funds.get("total_debt"))
    cash = _usable(funds.get("cash"))
    if debt is not None and cash is not None and cash >= 0 and debt > 3 * max(cash, 1e-9):
        fundamental.append("leverage vs cash is high")
        parts.append(25.0)

    if evidence in (EvidenceQuality.INSUFFICIENT, EvidenceQuality.UNKNOWN):
        data.append("evidence insufficient — data risk dominates")
        parts.append(15.0)
    elif evidence is EvidenceQuality.LOW:
        data.append("evidence LOW")
        parts.append(40.0)
    elif evidence is EvidenceQuality.MEDIUM:
        data.append("evidence MEDIUM (Yahoo quote/fundamentals, not a paid feed)")
        parts.append(68.0)
    else:
        data.append("evidence HIGH within the Yahoo/sample limits")
        parts.append(80.0)

    if dd.coverage_bars < 252:
        data.append("history shorter than ~1 year")

    if not parts:
        return None, market, fundamental, data
    return int(round(max(0.0, min(100.0, sum(parts) / len(parts))))), market, fundamental, data


def generational_gate(
    *,
    thesis: ThesisState,
    evidence: EvidenceQuality,
    dd: DrawdownReport,
    valuation_score: Optional[int],
    fundamentals_score: Optional[int],
    balance_sheet_score: Optional[int],
    cash_flow_score: Optional[int],
    risk_score: Optional[int],
    opportunity_score: Optional[int],
) -> Tuple[bool, List[str]]:
    """Strict research-only gate. Drawdown alone never passes.

    False negatives preferred over 'buy every dip'.
    """
    blockers: List[str] = []
    if thesis not in (ThesisState.STRONG, ThesisState.INTACT):
        blockers.append(f"thesis is {thesis.value}; need STRONG or INTACT")
    if evidence not in (EvidenceQuality.HIGH, EvidenceQuality.MEDIUM):
        blockers.append(f"evidence is {evidence.value}; need HIGH or MEDIUM")
    if dd.current_drawdown is None or dd.current_drawdown > -0.45:
        blockers.append("drawdown is not large/unusual enough (need at least -45% from highest available)")
    if dd.drawdown_percentile is None:
        blockers.append("drawdown percentile UNKNOWN — cannot claim an unusual historical drawdown")
    elif dd.drawdown_percentile < 85:
        blockers.append(
            f"drawdown percentile {dd.drawdown_percentile:.0f} is not unusual in-sample (need ≥ 85)"
        )
    if dd.coverage_bars < 252:
        blockers.append("historical coverage under 252 bars")
    if valuation_score is None or valuation_score < 70:
        blockers.append("valuation missing or not attractive (need ≥ 70)")
    if fundamentals_score is None or fundamentals_score < 70:
        blockers.append("fundamentals missing or not strong (need ≥ 70)")
    if balance_sheet_score is not None and balance_sheet_score < 60:
        blockers.append("balance sheet not acceptable")
    if cash_flow_score is not None and cash_flow_score < 60:
        blockers.append("cash flow not acceptable")
    if risk_score is not None and risk_score < 50:
        blockers.append("risk not acceptable")
    if opportunity_score is None or opportunity_score < 75:
        blockers.append("opportunity score below 75")

    pillars = 0
    if dd.current_drawdown is not None and dd.current_drawdown <= -0.45:
        pillars += 1
    if valuation_score is not None and valuation_score >= 70:
        pillars += 1
    if (
        fundamentals_score is not None
        and fundamentals_score >= 70
        and thesis in (ThesisState.STRONG, ThesisState.INTACT)
    ):
        pillars += 1
    if pillars < 3:
        blockers.append(
            "need three independent pillars: large/unusual drawdown + attractive valuation + intact fundamentals"
        )
    return (len(blockers) == 0, blockers)


def classify_opportunity(
    *,
    thesis: ThesisState,
    evidence: EvidenceQuality,
    dd: DrawdownReport,
    valuation_score: Optional[int],
    fundamentals_score: Optional[int],
    opportunity_score: Optional[int],
    generational_ok: bool,
) -> InvestmentAlertState:
    if thesis is ThesisState.BROKEN:
        return InvestmentAlertState.THESIS_BROKEN
    if generational_ok:
        return InvestmentAlertState.GENERATIONAL_OPPORTUNITY
    if (
        thesis in (ThesisState.STRONG, ThesisState.INTACT)
        and evidence in (EvidenceQuality.HIGH, EvidenceQuality.MEDIUM)
        and valuation_score is not None
        and valuation_score >= 75
        and dd.current_drawdown is not None
        and dd.current_drawdown <= -0.20
        and opportunity_score is not None
        and opportunity_score >= 65
        and fundamentals_score is not None
        and fundamentals_score >= 60
    ):
        return InvestmentAlertState.DEEP_VALUE
    if (
        thesis in (ThesisState.STRONG, ThesisState.INTACT)
        and evidence not in (EvidenceQuality.INSUFFICIENT, EvidenceQuality.UNKNOWN)
        and opportunity_score is not None
        and opportunity_score >= 55
        and dd.current_drawdown is not None
        and dd.current_drawdown <= -0.15
        and (fundamentals_score is None or fundamentals_score >= 55)
    ):
        return InvestmentAlertState.ACCUMULATION
    if (
        thesis not in (ThesisState.BROKEN, ThesisState.DAMAGED)
        and evidence is not EvidenceQuality.INSUFFICIENT
        and opportunity_score is not None
        and opportunity_score >= 40
    ):
        return InvestmentAlertState.WATCH
    return InvestmentAlertState.NO_ACTION


def build_explain(
    *,
    snap: InvestmentSnapshot,
    dd: DrawdownReport,
    thesis: ThesisState,
    evidence: EvidenceQuality,
    classification: InvestmentAlertState,
    components: ComponentScores,
    missing: Sequence[str],
    thesis_flags: Sequence[str],
    val_notes: Sequence[str],
    market_risk: Sequence[str],
    fundamental_risk: Sequence[str],
    data_risk: Sequence[str],
    blockers: Sequence[str],
) -> Explainability:
    why_asset = [
        f"{snap.asset.symbol} ({snap.asset.asset_type.value}"
        + (f", {snap.asset.name}" if snap.asset.name else "")
        + ")"
    ]
    if snap.asset.sector:
        why_asset.append(f"sector tagged {snap.asset.sector} in the universe file")

    interesting: List[str] = []
    why_now: List[str] = []
    if dd.current_drawdown is not None:
        why_now.append(
            f"current drawdown is {dd.current_drawdown:.0%} from highest available "
            f"({dd.coverage_label})"
        )
        if dd.current_drawdown <= -0.20:
            interesting.append("price is a material distance from the sample high")
    if dd.drawdown_percentile is not None:
        why_now.append(
            f"in-sample drawdown percentile is {dd.drawdown_percentile:.0f}th "
            "(sample-relative, not a cycle claim)"
        )
    if components.valuation is not None and components.valuation >= 70:
        why_now.append(
            "current valuation bands look attractive vs rule-of-thumb multiples "
            "(not a historical percentile)"
        )
        interesting.append("valuation component is in the attractive band")
    elif components.valuation is None:
        why_now.append("no usable current valuation — historical valuation context UNKNOWN")
    if not why_now:
        why_now.append("no strong timing signal in drawdown or valuation context")

    supports: List[str] = []
    weakens: List[str] = []
    if thesis in (ThesisState.STRONG, ThesisState.INTACT):
        supports.append(f"thesis state {thesis.value} on the current snapshot")
    if components.cash_flow is not None and components.cash_flow >= 70:
        supports.append("cash generation looks positive on available figures")
    if components.balance_sheet is not None and components.balance_sheet >= 70:
        supports.append("balance sheet looks acceptable on available figures")
    if components.fundamentals is not None and components.fundamentals >= 70:
        supports.append("profitability looks acceptable on available figures")
    for f in thesis_flags:
        weakens.append(f.replace("_", " "))
    if thesis in (ThesisState.DAMAGED, ThesisState.BROKEN, ThesisState.UNDER_PRESSURE):
        weakens.append(f"thesis {thesis.value}")
    if thesis is ThesisState.UNKNOWN:
        weakens.append("thesis UNKNOWN — cannot claim business quality")

    invalidation = [
        "a later snapshot showing earnings and free cash flow both negative with rising leverage",
        "price data that cannot be reconciled (CONFLICTING OHLC) without a usable quote",
        "evidence quality falling to INSUFFICIENT",
    ]
    if classification is InvestmentAlertState.GENERATIONAL_OPPORTUNITY:
        invalidation.append("any generational blocker firing on a later scored snapshot")

    risks = list(market_risk) + list(fundamental_risk) + list(data_risk)
    if snap.asset.sector:
        risks.append(f"sector exposure: {snap.asset.sector} (not sized; allocation is not this phase)")

    dq = [
        f"evidence quality {evidence.value}",
        dd.coverage_label,
    ]
    dq.extend(val_notes[-2:])
    if blockers and classification is not InvestmentAlertState.GENERATIONAL_OPPORTUNITY:
        dq.append("generational gate blocked: " + blockers[0])

    missing_list = [m for m in missing]
    if components.growth is None:
        missing_list.append("fundamental growth history")

    return Explainability(
        why_this_asset=why_asset,
        why_interesting=interesting or ["limited standalone interest on current evidence"],
        why_now=why_now,
        supports_thesis=supports or ["no strong supporting fundamental evidence"],
        weakens_thesis=weakens or ["no specific current red flags listed"],
        missing_data=sorted(set(missing_list)),
        invalidation=invalidation,
        risks=risks,
        data_quality_notes=dq,
    )


class InvestmentResearch:
    """Score an InvestmentSnapshot plus OHLCV history. Does not call Yahoo."""

    version = SCORING_VERSION

    def score_snapshot(
        self,
        snap: InvestmentSnapshot,
        bars: Optional[Sequence[OhlcvBar]] = None,
        *,
        history_root=None,
    ) -> ResearchRecord:
        symbol = snap.asset.symbol
        if bars is None:
            bars = load_bars(symbol, root=history_root)
        dd = analyze_drawdown(bars, current_price=_usable(snap.price))
        vol = return_volatility(bars)

        val_score, val_notes = score_valuation(snap.valuation)
        fund_score, fund_notes = score_profitability(snap.fundamentals)
        cf_score, cf_notes = score_cash_flow(snap.fundamentals)
        bs_score, bs_notes = score_balance_sheet(snap.fundamentals)
        growth_score, growth_notes = score_growth(snap.fundamentals)
        dd_score, dd_notes = score_drawdown_context(dd)

        thesis, thesis_notes, thesis_flags = assess_thesis(
            snap.fundamentals, asset_type=snap.asset.asset_type
        )
        evidence, ev_notes, missing = assess_evidence(snap, dd)
        risk_score, market_r, fund_r, data_r = assess_risk(
            dd=dd,
            vol=vol,
            thesis=thesis,
            evidence=evidence,
            funds=snap.fundamentals,
            bars=bars,
        )

        components = ComponentScores(
            valuation=val_score,
            fundamentals=fund_score,
            drawdown=dd_score,
            balance_sheet=bs_score,
            growth=growth_score,
            cash_flow=cf_score,
            thesis_integrity=score_thesis(thesis),
            risk=risk_score,
            evidence_quality=score_evidence(evidence),
        )
        opp = combine_components(components)
        gen_ok, blockers = generational_gate(
            thesis=thesis,
            evidence=evidence,
            dd=dd,
            valuation_score=val_score,
            fundamentals_score=fund_score,
            balance_sheet_score=bs_score,
            cash_flow_score=cf_score,
            risk_score=risk_score,
            opportunity_score=opp,
        )
        classification = classify_opportunity(
            thesis=thesis,
            evidence=evidence,
            dd=dd,
            valuation_score=val_score,
            fundamentals_score=fund_score,
            opportunity_score=opp,
            generational_ok=gen_ok,
        )
        explain = build_explain(
            snap=snap,
            dd=dd,
            thesis=thesis,
            evidence=evidence,
            classification=classification,
            components=components,
            missing=missing,
            thesis_flags=thesis_flags,
            val_notes=val_notes,
            market_risk=market_r,
            fundamental_risk=fund_r,
            data_risk=data_r,
            blockers=blockers,
        )
        # Keep unused note lists referenced so methodology stays inspectable on the record.
        explain.data_quality_notes.extend(fund_notes[:1] + cf_notes[:1] + bs_notes[:1] + growth_notes[:1] + dd_notes[:1] + thesis_notes[:1] + ev_notes[:1])

        return ResearchRecord(
            scoring_version=SCORING_VERSION,
            symbol=symbol,
            asset_type=snap.asset.asset_type,
            name=snap.asset.name,
            price=_usable(snap.price),
            classification=classification,
            opportunity_score=opp,
            evidence_quality=evidence,
            thesis=thesis,
            components=components,
            drawdown=dd,
            market_risk=market_r,
            fundamental_risk=fund_r,
            data_risk=data_r,
            explain=explain,
            missing_critical=list(missing),
            generational_blockers=blockers,
            input_snapshot=snap.as_dict(),
            coverage_label=dd.coverage_label,
        )

    def score_many(
        self,
        snaps: Sequence[InvestmentSnapshot],
        *,
        history_root=None,
    ) -> List[ResearchRecord]:
        return [self.score_snapshot(s, history_root=history_root) for s in snaps]


def format_research_text(rec: ResearchRecord) -> str:
    c = rec.components.as_dict()

    def _fmt(v: Optional[int]) -> str:
        return "n/a" if v is None else str(v)

    dd = rec.drawdown
    pct = "UNKNOWN" if dd.drawdown_percentile is None else f"{dd.drawdown_percentile:.0f}th"
    cur = "UNKNOWN" if dd.current_drawdown is None else f"{dd.current_drawdown:.0%}"
    d52 = "UNKNOWN" if dd.drawdown_52w is None else f"{dd.drawdown_52w:.0%}"
    lines = [
        "**INVESTMENT RESEARCH**",
        f"scoring_version: `{rec.scoring_version}`",
        f"Asset: `{rec.symbol}` ({rec.asset_type.value})",
        f"Price: `{rec.price}`",
        f"Classification: `{rec.classification.value}`",
        f"Opportunity Score: `{_fmt(rec.opportunity_score)}/100`  _(ordinal ranking, not a probability)_",
        "",
        "Components:",
        f"  Valuation: `{_fmt(c['valuation'])}`",
        f"  Fundamentals: `{_fmt(c['fundamentals'])}`",
        f"  Drawdown: `{_fmt(c['drawdown'])}`",
        f"  Balance Sheet: `{_fmt(c['balance_sheet'])}`",
        f"  Growth: `{_fmt(c['growth'])}`",
        f"  Cash Flow: `{_fmt(c['cash_flow'])}`",
        f"  Thesis Integrity: `{_fmt(c['thesis_integrity'])}`",
        f"  Risk: `{_fmt(c['risk'])}`",
        f"  Evidence Quality: `{_fmt(c['evidence_quality'])}`",
        "",
        f"Current drawdown: `{cur}`",
        f"52-week drawdown: `{d52}`",
        f"Drawdown percentile: `{pct}`",
        f"Historical data coverage: `{dd.coverage_label}`",
        f"Thesis: `{rec.thesis.value}`",
        f"Evidence: `{rec.evidence_quality.value}`",
        "",
        "WHY THIS ASSET?",
        *[f"* {x}" for x in rec.explain.why_this_asset],
        "",
        "WHY IS IT INTERESTING?",
        *[f"* {x}" for x in rec.explain.why_interesting],
        "",
        "WHY NOW?",
        *[f"* {x}" for x in rec.explain.why_now],
        "",
        "WHAT SUPPORTS THE THESIS?",
        *[f"* {x}" for x in rec.explain.supports_thesis],
        "",
        "WHAT WEAKENS THE THESIS?",
        *[f"* {x}" for x in rec.explain.weakens_thesis],
        "",
        "WHAT DATA IS MISSING?",
        *([f"* {x}" for x in rec.explain.missing_data] or ["* none listed"]),
        "",
        "WHAT COULD INVALIDATE THE THESIS?",
        *[f"* {x}" for x in rec.explain.invalidation],
        "",
        "RISKS:",
        *[f"* {x}" for x in rec.explain.risks],
        "",
        f"DATA QUALITY: `{rec.evidence_quality.value}`",
        "",
        rec.disclaimer,
        "",
        "_Phase 3 research only. Not a recommendation. Not an alert._",
    ]
    return "\n".join(lines)
