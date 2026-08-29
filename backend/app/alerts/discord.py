"""Discord alerts + slash commands. DM-only. Paper from journal; research from shadow."""

from __future__ import annotations

import asyncio
from typing import Any, List, Optional, Set

import discord
from discord import app_commands
import structlog

from app.core.config import get_settings

log = structlog.get_logger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

_ready = False
_subscribers: Set[int] = set()
_start_lock = asyncio.Lock()
_bot_task: Optional[asyncio.Task] = None


def is_discord_ready() -> bool:
    return _ready and bot.is_ready()


def get_subscriber_ids() -> List[int]:
    return list(_subscribers)


def _owner_ids() -> Set[int]:
    settings = get_settings()
    raw = getattr(settings, "discord_owner_ids", None) or ""
    if isinstance(raw, (list, tuple, set)):
        out = set()
        for x in raw:
            try:
                out.add(int(x))
            except (TypeError, ValueError):
                pass
        return out
    out: Set[int] = set()
    for part in str(raw).replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


def _seed_subscribers() -> None:
    global _subscribers
    owners = _owner_ids()
    if owners:
        _subscribers |= owners
        for uid in owners:
            log.info("Seeded Discord subscriber", user_id=uid)


async def send_discord_alert(
    *args: Any,
    symbol: str = "",
    title: str = "",
    description: str = "",
    price: float = 0.0,
    severity: str = "MEDIUM",
    opportunity: int = 50,
    confidence: int = 50,
    risk: int = 50,
    **kwargs: Any,
) -> bool:
    if args:
        if len(args) >= 1 and not symbol:
            symbol = str(args[0])
        if len(args) >= 2 and not title:
            title = str(args[1])
        if len(args) >= 3 and not description:
            description = str(args[2])
        if len(args) >= 4 and not price:
            try:
                price = float(args[3])
            except (TypeError, ValueError):
                pass

    symbol = kwargs.get("symbol", symbol) or symbol
    title = kwargs.get("title", title) or title
    description = kwargs.get("description", description) or description
    price = float(kwargs.get("price", price) or price or 0)
    severity = str(kwargs.get("severity", severity) or severity)
    opportunity = int(kwargs.get("opportunity", opportunity) or opportunity)
    confidence = int(kwargs.get("confidence", confidence) or confidence)
    risk = int(kwargs.get("risk", risk) or risk)

    if not is_discord_ready():
        log.warning("Discord not ready — alert skipped", symbol=symbol, title=title)
        return False

    color = discord.Color.orange()
    sev = severity.upper()
    if sev in ("HIGH", "CRITICAL"):
        color = discord.Color.red()
    elif sev in ("LOW",):
        color = discord.Color.green()
    elif sev in ("INFO",):
        color = discord.Color.blurple()

    embed = discord.Embed(
        title=(title or f"{symbol} alert")[:256],
        description=(description or "")[:4096],
        color=color,
    )
    if symbol:
        embed.add_field(name="Symbol", value=str(symbol)[:64], inline=True)
    if price:
        embed.add_field(name="Price", value=f"${price:,.4f}", inline=True)
    embed.add_field(name="Severity", value=sev[:32], inline=True)
    embed.add_field(name="Opportunity", value=str(opportunity), inline=True)
    embed.add_field(name="Confidence", value=str(confidence), inline=True)
    embed.add_field(name="Risk", value=str(risk), inline=True)
    embed.set_footer(text="Project Atlas • Market Intelligence")

    delivered = 0
    targets = list(_subscribers) or list(_owner_ids())
    for uid in targets:
        try:
            user = await bot.fetch_user(int(uid))
            if user is None:
                continue
            await user.send(embed=embed)
            delivered += 1
        except Exception as e:
            log.warning("DM failed", user_id=uid, error=str(e)[:200])

    log.info("Discord alert delivered", recipients=delivered, symbol=symbol or title)
    return delivered > 0


@bot.event
async def on_ready() -> None:
    global _ready
    _seed_subscribers()
    try:
        synced = await tree.sync()
        log.info("Slash commands synced", count=len(synced))
    except Exception as e:
        log.warning("Slash sync failed", error=str(e)[:200])
    _ready = True
    log.info(
        "Discord bot ready",
        id=bot.user.id if bot.user else None,
        user=str(bot.user) if bot.user else None,
        subscribers=len(_subscribers),
    )


@tree.command(name="subscribe", description="Subscribe to Atlas DMs")
async def subscribe_cmd(interaction: discord.Interaction) -> None:
    _subscribers.add(interaction.user.id)
    await interaction.response.send_message(
        "Subscribed. You will receive Atlas DMs.", ephemeral=True
    )
    log.info("Subscriber added", user_id=interaction.user.id)


@tree.command(name="unsubscribe", description="Stop Atlas DMs")
async def unsubscribe_cmd(interaction: discord.Interaction) -> None:
    _subscribers.discard(interaction.user.id)
    await interaction.response.send_message("Unsubscribed.", ephemeral=True)


@tree.command(name="status", description="Atlas bot status")
async def status_cmd(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(
        f"**Atlas Discord** ready=`{is_discord_ready()}` · "
        f"subscribers=`{len(_subscribers)}` · user=`{bot.user}`",
        ephemeral=True,
    )


@tree.command(name="paper", description="Paper trade stats (journal only)")
async def paper_cmd(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        from app.services.outcome_research import paper_text
        from app.services.paper_journal import paper_journal
        from app.services.perp_micro_coach import perp_micro_coach

        ready = await perp_micro_coach.live_readiness()
        opens = paper_journal.list_open()
        text = paper_text(open_n=len(opens), readiness=ready)
        if opens:
            extra = ["", "**Open positions**"]
            for o in opens[:6]:
                extra.append(
                    f"• `{o.get('symbol')}` {o.get('side')} entry "
                    f"`{o.get('actual_entry_price')}` "
                    f"MFE `{float(o.get('mfe_r') or 0):+.2f}R` "
                    f"MAE `{float(o.get('mae_r') or 0):+.2f}R`"
                )
            text = text.replace("_Paper only.", "\n".join(extra) + "\n_Paper only.")
        if len(text) > 1900:
            text = text[:1900] + "…"
        await interaction.followup.send(text, ephemeral=True)
    except Exception as e:
        log.warning("paper_cmd failed", error=str(e), exc_info=True)
        await interaction.followup.send(f"Paper stats error: `{e}`", ephemeral=True)


@tree.command(name="research", description="24h funnel, independent gates, distributions (not paper PnL)")
async def research_cmd(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        from app.services.funnel_research import funnel_research

        text = funnel_research.research_summary_text()
        await interaction.followup.send(text, ephemeral=True)
    except Exception as e:
        log.warning("research_cmd failed", error=str(e), exc_info=True)
        await interaction.followup.send(f"Research error: `{e}`", ephemeral=True)


@tree.command(name="diagnostics", description="Why no paper trades — bottleneck + funnel")
async def diagnostics_cmd(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        from app.services.funnel_research import funnel_research

        text = funnel_research.diagnostics_text()
        await interaction.followup.send(text, ephemeral=True)
    except Exception as e:
        log.warning("diagnostics_cmd failed", error=str(e), exc_info=True)
        await interaction.followup.send(f"Diagnostics error: `{e}`", ephemeral=True)


@tree.command(name="papertest", description="Run isolated TEST paper path (not counted)")
async def papertest_cmd(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        from app.api.diagnostics import diagnostics_paper_test

        result = await diagnostics_paper_test()
        await interaction.followup.send(
            f"**Paper pipeline TEST**\n"
            f"open `{result.get('open_worked')}` · close `{result.get('close_worked')}`\n"
            f"MFE `{result.get('mfe_r')}` · MAE `{result.get('mae_r')}`\n"
            f"Discord `{result.get('discord_delivered')}`\n"
            f"trade_type=TEST · does not count in /paper",
            ephemeral=True,
        )
    except Exception as e:
        log.warning("papertest_cmd failed", error=str(e), exc_info=True)
        await interaction.followup.send(f"Paper test error: `{e}`", ephemeral=True)


@tree.command(name="investhealth", description="Investment data health (not /paper, not trading)")
async def investhealth_cmd(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        from app.investment.diagnostics import format_full_health
        from app.investment.scan import investment_scanner

        text = format_full_health(running=bool(investment_scanner.running))
        if len(text) > 1900:
            text = text[:1900] + "…"
        await interaction.followup.send(text, ephemeral=True)
    except Exception as e:
        log.warning("investhealth_cmd failed", error=str(e), exc_info=True)
        await interaction.followup.send(
            f"Investment health error: `{e}`\n_Trading /paper is unrelated._",
            ephemeral=True,
        )


@tree.command(name="help", description="Atlas command list")
async def help_cmd(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(
        "**Atlas commands**\n"
        "`/subscribe` — receive DMs\n"
        "`/unsubscribe` — stop DMs\n"
        "`/status` — bot status\n"
        "`/paper` — real paper journal (MFE/MAE)\n"
        "`/research` — 24h funnel + independent gates + distributions (not PnL)\n"
        "`/diagnostics` — WHY NO PAPER TRADES / bottleneck\n"
        "`/papertest` — isolated TEST open/close (not counted)\n"
        "`/investhealth` — investment dataset/scanner health (not trading)\n"
        "`/help` — this message\n\n"
        "_Alerts are research only. Manual execution. Not financial advice._",
        ephemeral=True,
    )


async def start_discord_bot() -> None:
    global _bot_task
    async with _start_lock:
        settings = get_settings()
        token = (settings.discord_token or "").strip()
        if not token:
            log.warning("DISCORD_TOKEN missing — Discord disabled")
            return
        if _bot_task and not _bot_task.done():
            log.info("Discord bot already running")
            return

        _seed_subscribers()

        async def _runner() -> None:
            try:
                log.info("Discord bot starting...")
                await bot.start(token)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error("Discord bot crashed", error=str(e), exc_info=True)

        _bot_task = asyncio.create_task(_runner(), name="discord_bot")
        log.info("Discord bot task scheduled (DM-only alerts)")


async def stop_discord_bot() -> None:
    global _ready, _bot_task
    _ready = False
    try:
        if bot.is_ready():
            await bot.close()
    except Exception as e:
        log.warning("Discord close error", error=str(e)[:200])
    if _bot_task and not _bot_task.done():
        _bot_task.cancel()
        try:
            await _bot_task
        except asyncio.CancelledError:
            pass
    _bot_task = None
    log.info("Discord bot stopped")
