"""Investment Discord / text alerts. Separate from trading embeds and slash commands."""

from __future__ import annotations

from typing import Optional

from app.investment.alerts import AlertDecision
from app.investment.enums import InvestmentAlertState
from app.investment.models import AllocationPlan
from app.investment.research_models import ResearchRecord

DISCLAIMER = (
    "This is an investment research signal, not a guarantee of recovery or profit. "
    "Not a brokerage order."
)


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
    if decision.classification is InvestmentAlertState.THESIS_BROKEN:
        title = "ATLAS INVESTMENT — THESIS BROKEN"
        extra = ["STOP ACCUMULATING.", "Cancel remaining paper limit tiers.", ""]
    elif decision.classification is InvestmentAlertState.GENERATIONAL_OPPORTUNITY:
        title = "ATLAS INVESTMENT OPPORTUNITY"
        extra = ["Classification is GENERATIONAL_OPPORTUNITY (research-only, extremely selective).", ""]
    else:
        title = "ATLAS INVESTMENT OPPORTUNITY"
        extra = []
    why = rec.explain.why_now or rec.explain.why_interesting
    risks = rec.explain.risks[:6]
    inv = rec.explain.invalidation
    lines = [
        title,
        "━━━━━━━━━━━━━━━━━━",
        "ASSET:",
        rec.symbol,
        "CLASSIFICATION:",
        decision.classification.value.replace("_", " "),
        "CURRENT PRICE:",
        _px(rec),
        "DRAWDOWN:",
        _dd(rec),
        "OPPORTUNITY SCORE:",
        f"{rec.opportunity_score if rec.opportunity_score is not None else 'n/a'}/100",
        "EVIDENCE QUALITY:",
        rec.evidence_quality.value,
        "THESIS:",
        rec.thesis.value,
        "━━━━━━━━━━━━━━━━━━",
        "WHY NOW?",
        *[f"• {x}" for x in why],
        "",
        "RISKS:",
        *([f"• {x}" for x in risks] or ["• none listed"]),
        "",
        "WHAT WOULD INVALIDATE THE THESIS?",
        *[f"• {x}" for x in inv],
        "━━━━━━━━━━━━━━━━━━",
        *extra,
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


async def deliver_investment_alert(text: str, *, symbol: str, priority: str = "NORMAL") -> bool:
    """DM via the existing Discord client. Does not add slash commands or mix /paper stats."""
    try:
        import discord

        from app.alerts.discord import bot, get_subscriber_ids, is_discord_ready
    except Exception:
        return False
    if not is_discord_ready():
        return False
    color = discord.Color.dark_gold()
    if priority == "HIGH":
        color = discord.Color.red()
    embed = discord.Embed(
        title="ATLAS INVESTMENT",
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
