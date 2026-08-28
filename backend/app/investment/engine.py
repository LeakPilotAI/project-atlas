"""Phase 4 orchestrator. Opt-in. Not started from main.py. No real orders."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Sequence

from app.investment.alerts import AlertDecision, AlertStore, commit_alert, evaluate_alert
from app.investment.allocation import build_plan, format_plan, persist_plan
from app.investment.enums import InvestmentAlertState, ThesisState
from app.investment.market_hours import session_status
from app.investment.models import AllocationPlan, PortfolioInput
from app.investment.notify import format_investment_alert
from app.investment.paper_book import PaperBook
from app.investment.research_models import ResearchRecord


def can_personalize(rec: ResearchRecord, portfolio: PortfolioInput) -> bool:
    if not portfolio.is_complete_for_personalized_plan():
        return False
    if rec.thesis in (ThesisState.BROKEN, ThesisState.UNKNOWN):
        return False
    if rec.classification in (
        InvestmentAlertState.NO_ACTION,
        InvestmentAlertState.WATCH,
        InvestmentAlertState.THESIS_BROKEN,
    ):
        return False
    return True


def process_research(
    rec: ResearchRecord,
    *,
    portfolio: Optional[PortfolioInput] = None,
    store: Optional[AlertStore] = None,
    previous_plan: Optional[AllocationPlan] = None,
    paper: Optional[PaperBook] = None,
    now: Optional[datetime] = None,
    system_ok: bool = True,
    persist: bool = False,
    spy_price: Optional[float] = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    session = session_status(now, system_ok=system_ok)
    store = store or AlertStore(persist=False)
    decision = evaluate_alert(rec, store, now=now)
    commit_alert(rec, decision, store, now=now)

    plan: Optional[AllocationPlan] = None
    port = portfolio or PortfolioInput()
    if rec.thesis is ThesisState.BROKEN:
        plan = build_plan(rec, port, previous=previous_plan, now=now)
        if paper:
            paper.cancel_open(rec.symbol, reason="THESIS BROKEN — STOP ACCUMULATING")
    elif can_personalize(rec, port):
        plan = build_plan(rec, port, previous=previous_plan, now=now)
        if paper and plan and plan.is_actionable():
            paper.submit_from_plan(plan)
        elif paper and plan and plan.status == "PAUSED_EVIDENCE":
            paper.cancel_open(rec.symbol, reason="evidence insufficient")
    elif rec.classification in (InvestmentAlertState.WATCH, InvestmentAlertState.NO_ACTION):
        plan = None

    if persist and plan is not None:
        persist_plan(plan)

    if paper and rec.price and session == "MARKET_OPEN":
        paper.try_fill(rec.symbol, rec.price, session=session)
        paper.mark({rec.symbol: rec.price})
        if spy_price:
            paper.seed_benchmark(spy_price)

    alert_text = format_investment_alert(rec, decision, plan=plan) if decision.emit else ""
    return {
        "session": session,
        "decision": decision,
        "plan": plan,
        "alert_text": alert_text,
        "research": rec,
    }


def format_dashboard(
    records: Sequence[ResearchRecord],
    plans: Sequence[AllocationPlan],
    paper: Optional[PaperBook] = None,
    *,
    session: str = "MARKET_CLOSED",
    spy_price: Optional[float] = None,
) -> str:
    lines = [
        "**ATLAS INVESTMENT RESEARCH**",
        f"Session: `{session}`",
        "_Separate from Hyperliquid paper / /paper / /research._",
        "",
        "INVESTMENT OPPORTUNITIES",
        "Asset | Classification | Price | Drawdown | Score | Evidence | Thesis | Risk",
    ]
    for r in records:
        dd = "n/a" if r.drawdown.current_drawdown is None else f"{r.drawdown.current_drawdown:.0%}"
        lines.append(
            f"{r.symbol} | {r.classification.value} | {r.price} | {dd} | "
            f"{r.opportunity_score}/100 | {r.evidence_quality.value} | {r.thesis.value} | {r.components.risk}"
        )
    lines += ["", "ACTIVE ACCUMULATION PLANS"]
    active = [p for p in plans if p.status == "ACTIVE" and p.is_actionable()]
    if not active:
        lines.append("(none)")
    for p in active:
        lines.append(
            f"{p.symbol} | max ${p.maximum_target_allocation} | tiers {p.number_of_tiers} | "
            f"reserve ${p.remaining_reserve}"
        )
    counts = {
        "STRONG": 0,
        "INTACT": 0,
        "UNDER_PRESSURE": 0,
        "DAMAGED": 0,
        "BROKEN": 0,
        "UNKNOWN": 0,
    }
    for r in records:
        counts[r.thesis.value] = counts.get(r.thesis.value, 0) + 1
    lines += ["", "THESIS HEALTH"]
    for k, v in counts.items():
        lines.append(f"{k}: {v}")
    lines += ["", "PAPER INVESTMENT"]
    if paper:
        snap = paper.snapshot(spy_price=spy_price)
        lines += [
            f"Cash: {snap['cash']}",
            f"Invested: {snap['invested']}",
            f"Portfolio Value: {snap['portfolio_value']}",
            f"PnL (unrealized): {snap['unrealized_pnl']}",
            f"Drawdown: {snap['drawdown']}",
            f"Benchmark: {snap['benchmark']}"
            + (f" value={snap['benchmark_value']}" if snap["benchmark_value"] is not None else " (no alpha claim)"),
        ]
    else:
        lines.append("(no paper book)")
    if session == "MARKET_CLOSED":
        lines += ["", "Market is CLOSED. Research may update; paper fills wait for the cash session."]
    elif session == "SYSTEM_OFFLINE":
        lines += ["", "SYSTEM OFFLINE — not the same as a closed market."]
    lines += ["", "Research rankings are not probabilities. No real orders."]
    return "\n".join(lines)
