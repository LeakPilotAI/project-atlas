"""Recommendation-only allocation + accumulation ladder. No brokerage."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal
from typing import List, Optional, Sequence
from uuid import uuid4

from app.investment.enums import (
    EvidenceQuality,
    InvestmentAlertState,
    RiskTolerance,
    ThesisState,
)
from app.investment.models import AllocationPlan, AllocationTier, PortfolioInput
from app.investment.portfolio import existing_position_value, exposure_percent, sector_value
from app.investment.research_models import ResearchRecord
from app.investment.storage import PLANS_PATH, ensure_dirs

ALLOCATION_VERSION = "atlas-alloc-4.0"
TWOPLACES = Decimal("0.01")
SIXPLACES = Decimal("0.000001")

ACTIONABLE = {
    InvestmentAlertState.ACCUMULATION,
    InvestmentAlertState.DEEP_VALUE,
    InvestmentAlertState.GENERATIONAL_OPPORTUNITY,
}


def D(x) -> Decimal:
    return Decimal(str(x))


def money(x) -> Decimal:
    return D(x).quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)


def _shares(allocation: Decimal, price: Decimal, *, fractional: bool) -> Decimal:
    if price <= 0:
        return Decimal("0")
    if fractional:
        return (allocation / price).quantize(SIXPLACES, rounding=ROUND_DOWN)
    return (allocation / price).to_integral_value(rounding=ROUND_DOWN)


def _score_mult(score: Optional[int]) -> Decimal:
    if score is None:
        return Decimal("0")
    if score >= 85:
        return Decimal("0.70")
    if score >= 70:
        return Decimal("0.50")
    if score >= 55:
        return Decimal("0.35")
    return Decimal("0")


def _evidence_mult(q: EvidenceQuality) -> Decimal:
    if q is EvidenceQuality.HIGH:
        return Decimal("1.0")
    if q is EvidenceQuality.MEDIUM:
        return Decimal("0.75")
    return Decimal("0")


def _thesis_mult(t: ThesisState) -> Decimal:
    if t is ThesisState.STRONG:
        return Decimal("1.0")
    if t is ThesisState.INTACT:
        return Decimal("0.85")
    if t is ThesisState.UNDER_PRESSURE:
        return Decimal("0.40")
    return Decimal("0")


def _vol_mult(vol: Optional[float]) -> Decimal:
    if vol is None:
        return Decimal("0.80")
    if vol > 0.50:
        return Decimal("0.50")
    if vol > 0.35:
        return Decimal("0.75")
    return Decimal("1.0")


def _risk_tol_mult(rt: RiskTolerance) -> Decimal:
    if rt is RiskTolerance.CONSERVATIVE:
        return Decimal("0.60")
    if rt is RiskTolerance.MODERATE:
        return Decimal("0.85")
    if rt is RiskTolerance.AGGRESSIVE:
        return Decimal("1.00")
    return Decimal("0.70")


def _n_tiers(cls: InvestmentAlertState) -> int:
    if cls is InvestmentAlertState.GENERATIONAL_OPPORTUNITY:
        return 4
    if cls in (InvestmentAlertState.DEEP_VALUE, InvestmentAlertState.ACCUMULATION):
        return 3
    return 0


def _step_size(rec: ResearchRecord) -> tuple[Decimal, str]:
    """Tier spacing from vol / drawdown — not a fixed 5% grid."""
    vol = None
    for note in rec.market_risk:
        if "vol ~" in note:
            # "annualized close-to-close vol ~ 26% in-sample"
            try:
                pct = note.split("vol ~")[1].split("%")[0].strip()
                vol = float(pct) / 100.0
            except Exception:
                vol = None
    dd = rec.drawdown.current_drawdown
    if vol is not None and vol > 0:
        monthly = vol / (12 ** 0.5)
        step = max(0.03, min(0.12, 0.75 * monthly))
        return D(step), f"spacing {step:.1%} from in-sample vol {vol:.0%} (0.75× monthly vol, clipped 3–12%)"
    if dd is not None and abs(dd) > 0:
        step = max(0.04, min(0.10, abs(dd) * 0.25))
        return D(step), f"spacing {step:.1%} from |drawdown| (vol unavailable)"
    return D("0.06"), "spacing 6% (vol and drawdown unavailable; conservative labeled default)"


def maximum_recommended_allocation(
    rec: ResearchRecord,
    portfolio: PortfolioInput,
    *,
    mark: Optional[float] = None,
    previous_max: Optional[float] = None,
    price_fell: bool = False,
    score_improved: bool = False,
) -> tuple[Decimal, List[str], str]:
    """Dollar cap. Never spends the reserve. Never exceeds max position / sector."""
    notes: List[str] = []
    if not portfolio.is_complete_for_personalized_plan():
        return Decimal("0"), notes, "portfolio profile incomplete (need value, cash, and cash reserve)"
    if rec.classification not in ACTIONABLE:
        return Decimal("0"), notes, f"{rec.classification.value} is not an allocation state"
    if rec.evidence_quality in (EvidenceQuality.INSUFFICIENT, EvidenceQuality.UNKNOWN):
        return Decimal("0"), notes, "evidence insufficient — pause personalized allocation"
    if rec.thesis in (ThesisState.BROKEN, ThesisState.DAMAGED, ThesisState.UNKNOWN):
        return Decimal("0"), notes, f"thesis {rec.thesis.value} — no personalized allocation"

    pv = D(portfolio.portfolio_value)
    cash = money(portfolio.available_cash)
    reserve = money(portfolio.minimum_cash_reserve or 0)
    if cash < reserve:
        return Decimal("0"), notes, "available cash is below the configured reserve"
    usable = cash - reserve
    notes.append(f"usable buying power {usable} after reserve {reserve}")

    px = mark if mark is not None else rec.price
    existing = D(existing_position_value(portfolio, rec.symbol, px))
    max_pos = pv * D(portfolio.maximum_position_percent) / D(100)
    headroom = max(Decimal("0"), max_pos - existing)
    exp = exposure_percent(float(existing), float(pv))
    notes.append(
        f"existing {rec.symbol} {money(existing)} ({0 if exp is None else exp:.1f}%); "
        f"max position {portfolio.maximum_position_percent}% = {money(max_pos)}; headroom {money(headroom)}"
    )
    if headroom <= 0:
        return Decimal("0"), notes, "existing exposure exceeds the configured position limit"

    sector = ""
    for h in portfolio.holdings:
        if h.symbol == rec.symbol and h.sector:
            sector = h.sector
            break
    if not sector:
        sector = rec.input_snapshot.get("asset", {}).get("sector") or ""
    if sector and portfolio.maximum_sector_exposure_percent is not None:
        sv = D(sector_value(portfolio, sector))
        cap_s = pv * D(portfolio.maximum_sector_exposure_percent) / D(100)
        sector_headroom = max(Decimal("0"), cap_s - sv)
        notes.append(f"sector {sector} {money(sv)} / cap {money(cap_s)}")
        if sector_headroom <= 0:
            return Decimal("0"), notes, "sector exposure exceeds the configured sector limit"
        headroom = min(headroom, sector_headroom)

    sm = _score_mult(rec.opportunity_score)
    em = _evidence_mult(rec.evidence_quality)
    tm = _thesis_mult(rec.thesis)
    vm = _vol_mult(None)  # refined below if vol parsed
    for note in rec.market_risk:
        if "vol ~" in note:
            try:
                vm = _vol_mult(float(note.split("vol ~")[1].split("%")[0].strip()) / 100.0)
            except Exception:
                pass
            break
    rm = _risk_tol_mult(portfolio.risk_tolerance)
    if sm == 0:
        return Decimal("0"), notes, "opportunity score too low for allocation"
    if em == 0:
        return Decimal("0"), notes, "evidence quality too low for allocation"
    if tm == 0:
        return Decimal("0"), notes, "thesis does not support allocation"

    raw = min(usable, headroom) * sm * em * tm * vm * rm
    cap = money(raw)
    notes.append(
        f"multipliers score={sm} evidence={em} thesis={tm} vol={vm} risk_tol={rm}"
    )
    if price_fell and not score_improved and previous_max is not None:
        prev = money(previous_max)
        if cap > prev:
            notes.append("price fell without score/thesis improvement — not increasing allocation")
            cap = prev
    if cap <= 0:
        return Decimal("0"), notes, "computed allocation is zero"
    return cap, notes, ""


def build_ladder(
    rec: ResearchRecord,
    portfolio: PortfolioInput,
    *,
    max_alloc: Decimal,
    starting_cash: Decimal,
    reserve: Decimal,
) -> tuple[List[AllocationTier], Decimal, List[str]]:
    reasons: List[str] = []
    n = _n_tiers(rec.classification)
    if n <= 0 or max_alloc <= 0 or rec.price in (None, 0):
        return [], starting_cash, reasons
    px = D(rec.price)
    step, step_why = _step_size(rec)
    reasons.append(step_why)
    # Limits below last: 0.5×, 1.5×, 2.75×, 4× step
    coeffs = [Decimal("0.50"), Decimal("1.50"), Decimal("2.75"), Decimal("4.00")][:n]
    prices = [money(px * (Decimal("1") - c * step)) for c in coeffs]
    for i, p in enumerate(prices):
        if p <= 0:
            prices[i] = money(px * Decimal("0.50"))

    # Split max_alloc across tiers; last tier gets remainder cents.
    cents = int(max_alloc * 100)
    base, rem = divmod(cents, n)
    targets = [money(Decimal(base) / 100)] * n
    targets[-1] = money(targets[-1] + Decimal(rem) / 100)

    remaining = money(starting_cash)
    floor = money(reserve)
    tiers: List[AllocationTier] = []
    fractional = bool(portfolio.allow_fractional_shares)
    for i, (limit_px, target) in enumerate(zip(prices, targets), start=1):
        spendable = remaining - floor
        if spendable <= 0:
            break
        budget = min(target, spendable)
        qty = _shares(budget, limit_px, fractional=fractional)
        spent = money(qty * limit_px)
        if qty <= 0 or spent <= 0:
            reasons.append(f"tier {i}: budget {budget} at {limit_px} bought 0 shares")
            continue
        remaining = money(remaining - spent)
        why = (
            f"limit {limit_px} is {(1 - float(limit_px / px)):.1%} below last price "
            f"using {step_why.split(' from ')[0] if ' from ' in step_why else step_why}"
        )
        tiers.append(
            AllocationTier(
                index=i,
                price=float(limit_px),
                dollar_amount=float(spent),
                share_quantity=float(qty) if fractional else int(qty),
                reason=why,
                remaining_cash_after=float(remaining),
            )
        )
    return tiers, remaining, reasons


def build_plan(
    rec: ResearchRecord,
    portfolio: PortfolioInput,
    *,
    previous: Optional[AllocationPlan] = None,
    now: Optional[datetime] = None,
) -> AllocationPlan:
    now = now or datetime.now(timezone.utc)
    notes: List[str] = []
    reasoning: List[str] = []

    def blocked(reason: str, status: str = "BLOCKED") -> AllocationPlan:
        return AllocationPlan(
            symbol=rec.symbol,
            blocked_reason=reason,
            status=status,
            plan_id=_plan_id(rec.symbol, now),
            allocation_version=ALLOCATION_VERSION,
            scoring_version=rec.scoring_version,
            evidence_quality=rec.evidence_quality.value,
            thesis=rec.thesis.value,
            classification=rec.classification.value,
            notes=list(notes),
            reasoning=list(reasoning) + [reason],
            parent_plan_id=previous.plan_id if previous else "",
            version=(previous.version + 1) if previous else 1,
            starting_buying_power=portfolio.available_cash,
            available_buying_power=portfolio.available_cash,
            reserve_cash=portfolio.minimum_cash_reserve,
        )

    if rec.thesis is ThesisState.BROKEN:
        return blocked("THESIS BROKEN — STOP ACCUMULATING.", status="CANCELLED_THESIS_BROKEN")
    if rec.evidence_quality in (EvidenceQuality.INSUFFICIENT, EvidenceQuality.UNKNOWN):
        return blocked("evidence quality insufficient — pause personalized allocation", status="PAUSED_EVIDENCE")
    if not portfolio.is_complete_for_personalized_plan():
        return blocked("portfolio information required")
    if rec.classification not in ACTIONABLE:
        return blocked(f"{rec.classification.value} is research-only; no personalized accumulation plan")

    price_fell = bool(
        previous
        and previous.tiers
        and rec.price is not None
        and previous.tiers[0].price
        and rec.price < (previous.tiers[0].price or rec.price)
    )
    score_improved = bool(
        previous
        and previous.notes
        and rec.opportunity_score is not None
        # previous score not stored on plan; use parent classification upgrade as proxy
    )
    if previous and rec.opportunity_score is not None:
        # if previous was lower conviction, treat as improvement
        score_improved = rec.classification.value != previous.classification and rec.classification in ACTIONABLE

    cap, cap_notes, err = maximum_recommended_allocation(
        rec,
        portfolio,
        mark=rec.price,
        previous_max=previous.maximum_target_allocation if previous else None,
        price_fell=price_fell,
        score_improved=score_improved,
    )
    notes.extend(cap_notes)
    if err:
        return blocked(err)

    start = money(portfolio.available_cash)
    reserve = money(portfolio.minimum_cash_reserve or 0)
    tiers, remaining, ladder_notes = build_ladder(
        rec, portfolio, max_alloc=cap, starting_cash=start, reserve=reserve
    )
    reasoning.extend(ladder_notes)
    spent = money(sum(D(t.dollar_amount or 0) for t in tiers))
    if money(start) != money(spent + remaining):
        return blocked("internal rounding error — plan not issued")
    if remaining < reserve:
        return blocked("plan would breach cash reserve")
    if not tiers:
        return blocked("no executable whole-share tiers at current prices")

    reasoning.append(f"starting buying power {start}")
    reasoning.append(f"maximum planned allocation {spent}")
    for t in tiers:
        reasoning.append(
            f"TIER {t.index}  ${t.price}  ${t.dollar_amount}  {t.share_quantity} shares  ({t.reason})"
        )
    reasoning.append(f"remaining reserve {remaining}")
    reasoning.append("This is a recommendation, not an order. No brokerage execution.")

    return AllocationPlan(
        symbol=rec.symbol,
        available_buying_power=float(start),
        starting_buying_power=float(start),
        maximum_target_allocation=float(spent),
        reserve_cash=float(reserve),
        number_of_tiers=len(tiers),
        tiers=tiers,
        remaining_buying_power=float(remaining),
        remaining_reserve=float(remaining),
        blocked_reason="",
        plan_id=_plan_id(rec.symbol, now),
        allocation_version=ALLOCATION_VERSION,
        version=(previous.version + 1) if previous else 1,
        status="ACTIVE",
        notes=notes,
        reasoning=reasoning,
        parent_plan_id=previous.plan_id if previous else "",
        scoring_version=rec.scoring_version,
        evidence_quality=rec.evidence_quality.value,
        thesis=rec.thesis.value,
        classification=rec.classification.value,
    )


def _plan_id(symbol: str, now: datetime) -> str:
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    return f"{symbol}-{ts}-{uuid4().hex[:8]}"


def persist_plan(plan: AllocationPlan, path=None) -> None:
    """Append-only. Never overwrite a historical plan."""
    import json

    ensure_dirs()
    p = path or PLANS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "plan_id": plan.plan_id,
        "parent_plan_id": plan.parent_plan_id,
        "version": plan.version,
        "allocation_version": plan.allocation_version,
        "scoring_version": plan.scoring_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": plan.symbol,
        "status": plan.status,
        "classification": plan.classification,
        "thesis": plan.thesis,
        "evidence_quality": plan.evidence_quality,
        "starting_buying_power": plan.starting_buying_power,
        "maximum_target_allocation": plan.maximum_target_allocation,
        "reserve_cash": plan.reserve_cash,
        "remaining_reserve": plan.remaining_reserve,
        "blocked_reason": plan.blocked_reason,
        "notes": plan.notes,
        "reasoning": plan.reasoning,
        "tiers": [
            {
                "index": t.index,
                "price": t.price,
                "dollar_amount": t.dollar_amount,
                "share_quantity": t.share_quantity,
                "reason": t.reason,
                "remaining_cash_after": t.remaining_cash_after,
            }
            for t in plan.tiers
        ],
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def load_plans(path=None) -> List[dict]:
    p = path or PLANS_PATH
    if not p.exists():
        return []
    import json

    out: List[dict] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def format_plan(plan: AllocationPlan) -> str:
    lines = [
        f"**ACCUMULATION PLAN** `{plan.plan_id}`",
        f"Asset: `{plan.symbol}`",
        f"Status: `{plan.status}`",
        f"Classification: `{plan.classification}`",
        f"allocation_version: `{plan.allocation_version}`",
        f"scoring_version: `{plan.scoring_version}`",
        "",
        f"Starting buying power: `{plan.starting_buying_power}`",
        f"Maximum planned allocation: `{plan.maximum_target_allocation}`",
        f"Configured reserve: `{plan.reserve_cash}`",
    ]
    if plan.blocked_reason:
        lines += ["", f"BLOCKED: {plan.blocked_reason}"]
    for t in plan.tiers:
        lines += [
            "",
            f"TIER {t.index}",
            f"${t.price}",
            f"${t.dollar_amount}",
            f"{t.share_quantity} shares",
            f"WHY THIS PRICE? {t.reason}",
            f"Cash after tier: `{t.remaining_cash_after}`",
        ]
    lines += [
        "",
        f"Remaining reserve: `{plan.remaining_reserve}`",
        "",
        "_Recommendation only. No brokerage order. Not a guarantee._",
    ]
    return "\n".join(lines)
