"""Investment Discord / text alerts. Separate from trading embeds and slash commands."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.investment.alerts import AlertDecision
from app.investment.enums import InvestmentAlertState
from app.investment.models import AllocationPlan
from app.investment.research_models import ResearchRecord

DISCLAIMER = (
    "This is an investment research signal, not a guarantee of recovery or profit. "
    "Not a brokerage order."
)

ACTION_LINE = {
    InvestmentAlertState.WATCH: "WATCH — on the radar. Not a buy yet.",
    InvestmentAlertState.ACCUMULATION: "PREPARE TO BUY — accumulation zone. Research a scale-in. You place any order.",
    InvestmentAlertState.DEEP_VALUE: "PREPARE TO BUY — deep value zone. A dip can keep falling. Size small.",
    InvestmentAlertState.GENERATIONAL_OPPORTUNITY: "REVIEW CAREFULLY — generational gate passed. Not permission to size large.",
    InvestmentAlertState.THESIS_BROKEN: "STAND DOWN — do not buy this dip.",
    InvestmentAlertState.NO_ACTION: "NO ACTION — not a setup.",
}


def _dd(rec: ResearchRecord) -> str:
    d = rec.drawdown.current_drawdown
    return "UNKNOWN" if d is None else f"{d:.0%}"


def _px(rec: ResearchRecord) -> str:
    return "UNKNOWN" if rec.price is None else f"${rec.price:,.2f}"


def format_investment_alert(
    rec: ResearchRecord,
    decision: AlertDecision,
    *,
    plan: Optional[AllocationPlan] = None,
) -> str:
    cls_label = decision.classification.value.replace("_", " ")
    action = ACTION_LINE.get(decision.classification, "Research only.")
    if decision.classification is InvestmentAlertState.THESIS_BROKEN:
        title = "ATLAS INVESTMENT — THESIS BROKEN"
        extra = ["STAND DOWN.", "STOP ACCUMULATING.", "Cancel remaining paper limit tiers.", ""]
    else:
        title = f"ATLAS INVESTMENT — {cls_label}"
        extra = []
    why = rec.explain.why_now or rec.explain.why_interesting
    risks = rec.explain.risks[:6]
    lines = [
        title,
        rec.symbol,
        f"ACTION: {action}",
        f"Price: {_px(rec)}",
        f"Drawdown: {_dd(rec)}",
        f"Score: {rec.opportunity_score if rec.opportunity_score is not None else 'n/a'}/100",
        f"Evidence: {rec.evidence_quality.value}",
        f"Thesis: {rec.thesis.value}",
        "",
        "WHY NOW:",
        *[f"• {x}" for x in why],
        "",
        "RISKS:",
        *([f"• {x}" for x in risks] or ["• none listed"]),
        "",
        "WHAT WOULD INVALIDATE THE THESIS?",
        *[f"• {x}" for x in rec.explain.invalidation],
        "",
        *extra,
        "Research only:",
        "No real order has been placed.",
        DISCLAIMER,
    ]
    if plan is None:
        lines.append("No personalized allocation (no valid portfolio profile, or not an allocation state).")
    elif plan.blocked_reason:
        lines.append(f"Allocation: {plan.blocked_reason}")
    else:
        lines.append(
            f"Suggested max allocation ${plan.maximum_target_allocation} "
            f"across {plan.number_of_tiers} limit tiers. Remaining reserve ${plan.remaining_reserve}."
        )
    return "\n".join(lines)


def _pct(v: Optional[float]) -> str:
    if v is None:
        return "UNKNOWN"
    return f"{v*100:+.1f}%"


def format_equity_move_alert(
    *,
    symbol: str,
    tape_row: Dict[str, Any],
    plan: Optional[AllocationPlan] = None,
    review: Optional[Dict[str, Any]] = None,
    why: Optional[list] = None,
    risks: Optional[list] = None,
) -> str:
    cls = str(tape_row.get("classification") or "UNKNOWN")
    cause = tape_row.get("cause") or {}
    headline = cause.get("headline")
    src = cause.get("source")
    cause_line = (
        f"{cause.get('category', 'UNKNOWN')} — {headline} ({src})"
        if headline and src
        else "UNKNOWN"
    )
    ladder = "not issued (thesis/evidence/capital block)"
    if plan is not None and plan.is_actionable():
        bits = []
        for t in plan.tiers:
            bits.append(f"T{t.index}: ${t.price} · ${t.dollar_amount} · {t.share_quantity} sh · {t.reason}")
        ladder = "\n".join(bits)
    rv = review or (plan.review_levels if plan else {}) or {}
    lines = [
        "ATLAS EQUITY ALERT",
        f"{symbol} — {cls.replace('_', ' ')}",
        f"Price: {tape_row.get('price')}",
        f"1D: {_pct(tape_row.get('ret_1d'))}",
        f"5D: {_pct(tape_row.get('ret_5d'))}",
        f"Drawdown: {_pct(tape_row.get('drawdown'))}",
        f"Volume vs 20d: {tape_row.get('rel_volume') if tape_row.get('rel_volume') is not None else 'UNKNOWN'}",
        f"Move Score: {tape_row.get('move_score')}/100",
        "",
        "RELATIVE:",
        f"vs SPY: {_pct(tape_row.get('vs_spy'))}",
        f"vs QQQ: {_pct(tape_row.get('vs_qqq'))}",
        f"vs sector: {_pct(tape_row.get('vs_sector'))}",
        "",
        f"THESIS: {tape_row.get('thesis')}",
        f"Evidence: {tape_row.get('evidence')}",
        f"Valuation component: {tape_row.get('valuation')}",
        f"CAUSE: {cause_line}",
        "",
        f"ATLAS CLASSIFICATION: {cls}",
        "",
        "MANUAL RESEARCH BUY LADDER:",
        ladder,
        "",
        "REVIEW LEVELS:",
        f"Recovery: {rv.get('recovery', 'n/a')}",
        f"Fair Value: {rv.get('fair_value', 'n/a')}",
        f"Overvaluation: {rv.get('overvaluation', 'n/a')}",
        f"Thesis Review: {rv.get('thesis_review', 'n/a')}",
        "",
        "WHY:",
        *[f"• {x}" for x in (why or ["unusual move vs history/peers"])],
        "",
        "RISKS:",
        *[f"• {x}" for x in (risks or ["thesis can break", "drawdowns can continue"])],
        "",
        "MANUAL ACTION:",
        "Review on your broker. Atlas does not place the buy.",
        "No real order has been placed.",
        DISCLAIMER,
    ]
    return "\n".join(lines)


async def deliver_investment_alert(
    text: str,
    *,
    symbol: str,
    priority: str = "NORMAL",
    title: str = "ATLAS INVESTMENT",
) -> bool:
    """DM via the existing Discord client. Does not add slash commands or mix /paper stats."""
    try:
        import discord

        from app.alerts.discord import bot, get_subscriber_ids, is_discord_ready
    except Exception:
        return False
    if not is_discord_ready():
        return False
    color = discord.Color.dark_teal()
    if priority == "HIGH":
        color = discord.Color.red()
    elif "QUALITY DIP" in title.upper() or "PREPARE" in text.upper()[:80]:
        color = discord.Color.dark_gold()
    embed = discord.Embed(
        title=title[:256],
        description=text[:4096],
        color=color,
    )
    embed.set_footer(text="Investment research • not trading paper • not a guarantee")
    delivered = 0
    for uid in get_subscriber_ids():
        try:
            user = await bot.fetch_user(int(uid))
            if user is None:
                continue
            await user.send(embed=embed)
            delivered += 1
        except Exception:
            continue
    return delivered > 0
