"""Discord bot — DM alerts + slash commands."""

from __future__ import annotations

import asyncio
from typing import Any, Optional, Set

import discord
from discord.ext import commands

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("discord")

_bot: Optional[commands.Bot] = None
bot: Optional[commands.Bot] = None
_ready = asyncio.Event()
_subscribers: Set[int] = set()


def is_discord_ready() -> bool:
    return _bot is not None and _bot.is_ready()


def get_subscriber_ids() -> list[int]:
    return sorted(_subscribers)


async def _load_subscribers_from_redis() -> None:
    global _subscribers
    try:
        from app.core.redis import get_redis_client

        r = await get_redis_client()
        if r is None:
            return
        members = await r.smembers("atlas:discord:subscribers")
        for m in members or []:
            try:
                _subscribers.add(int(m))
            except ValueError:
                continue
    except Exception as e:
        log.warning("load subscribers failed", error=str(e))


async def _save_subscriber(user_id: int) -> None:
    _subscribers.add(user_id)
    try:
        from app.core.redis import get_redis_client

        r = await get_redis_client()
        if r is not None:
            await r.sadd("atlas:discord:subscribers", str(user_id))
    except Exception as e:
        log.warning("save subscriber failed", error=str(e))


async def _remove_subscriber(user_id: int) -> None:
    _subscribers.discard(user_id)
    try:
        from app.core.redis import get_redis_client

        r = await get_redis_client()
        if r is not None:
            await r.srem("atlas:discord:subscribers", str(user_id))
    except Exception as e:
        log.warning("remove subscriber failed", error=str(e))


def _build_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    client = commands.Bot(command_prefix="!", intents=intents)

    @client.event
    async def on_ready() -> None:
        settings = get_settings()
        await _load_subscribers_from_redis()
        for oid in settings.discord_owner_id_list:
            _subscribers.add(oid)
            try:
                await _save_subscriber(oid)
                log.info("Seeded Discord subscriber", user_id=oid)
            except Exception:
                pass
        try:
            synced = await client.tree.sync()
            log.info("Slash commands synced", count=len(synced))
        except Exception as e:
            log.warning("Slash sync failed", error=str(e))
        log.info(
            "Discord bot ready",
            id=client.user.id if client.user else None,
            subscribers=len(_subscribers),
            user=str(client.user) if client.user else None,
        )
        _ready.set()

    @client.tree.command(name="subscribe", description="Receive Atlas DM alerts")
    async def subscribe_cmd(interaction: discord.Interaction) -> None:
        await _save_subscriber(interaction.user.id)
        await interaction.response.send_message(
            "Subscribed to Atlas DMs (paper, dips, day-trade, heartbeats).",
            ephemeral=True,
        )

    @client.tree.command(name="unsubscribe", description="Stop Atlas DM alerts")
    async def unsubscribe_cmd(interaction: discord.Interaction) -> None:
        await _remove_subscriber(interaction.user.id)
        await interaction.response.send_message("Unsubscribed.", ephemeral=True)

    @client.tree.command(name="status", description="Atlas bot status")
    async def status_cmd(interaction: discord.Interaction) -> None:
        settings = get_settings()
        try:
            from app.services.perp_micro_coach import perp_micro_coach

            liquid = perp_micro_coach.liquid_count
        except Exception:
            liquid = 0
        await interaction.response.send_message(
            f"**{settings.app_name}** · `{settings.app_env}`\n"
            f"Subscribers: **{len(_subscribers)}**\n"
            f"Micro paper: **{settings.perp_micro_paper_enabled}** · "
            f"liquid **{liquid}** · risk ${settings.perp_micro_risk_usd:.2f}\n"
            f"_Research / paper only. No auto-execution._",
            ephemeral=True,
        )

    @client.tree.command(
        name="paper",
        description="Paper trades: open + recent history + stats",
    )
    async def paper_cmd(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            from app.services.paper_journal import paper_journal
            from app.services.perp_micro_coach import perp_micro_coach

            stats = await paper_journal.stats()
            opens = await paper_journal.list_open(15)
            closed = await paper_journal.list_closed(10)
            live = {}
            try:
                for t in await perp_micro_coach.list_open_papers():
                    live[str(t.get("id"))] = t
            except Exception:
                pass

            lines = [
                f"**Stats:** {stats['wins']}W / {stats['losses']}L · "
                f"WR **{stats['win_rate_pct']}%** · sum R **{stats['sum_r']:+.2f}** · "
                f"open **{stats['open']}**",
                "",
                "**Open:**",
            ]
            if not opens:
                lines.append("_None_")
            else:
                for t in opens:
                    mark = live.get(t["id"], {})
                    ur = mark.get("unrealized_r")
                    extra = f" · uR **{ur:+.2f}**" if ur is not None else ""
                    lines.append(
                        f"• `{t['id']}` **{t['symbol']}** {t['side']} @ `{t['entry']}`"
                        f"{extra} · stop `{t.get('stop')}` tp1 `{t.get('tp1')}`"
                    )
            lines.append("")
            lines.append("**Recent closes:**")
            if not closed:
                lines.append("_None yet — strict filters_")
            else:
                for t in closed:
                    lines.append(
                        f"• `{t['symbol']}` {t['side']} → {t.get('result')} "
                        f"**{(t.get('pnl_r') or 0):+.2f}R**"
                    )
            lines.append("\n_Paper only. No live execution._")
            text = "\n".join(lines)
            if len(text) > 1900:
                text = text[:1900] + "\n…"
            await interaction.followup.send(text, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Paper error: `{e}`", ephemeral=True)

    return client


async def start_discord_bot() -> None:
    global _bot, bot
    settings = get_settings()
    token = (settings.discord_token or "").strip()
    if not token:
        log.warning("DISCORD_TOKEN missing — Discord disabled")
        return
    if _bot is not None and _bot.is_ready():
        bot = _bot
        return
    log.info("Discord bot starting...")
    _bot = _build_bot()
    bot = _bot
    try:
        await _bot.start(token)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.error("Discord bot crashed", error=str(e))
        _bot = None
        bot = None


async def stop_discord_bot() -> None:
    global _bot, bot
    if _bot is not None:
        try:
            await _bot.close()
        except Exception as e:
            log.warning("Discord close failed", error=str(e))
        _bot = None
        bot = None
    _ready.clear()


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
        if len(args) >= 4 and price == 0.0:
            try:
                price = float(args[3])
            except Exception:
                pass

    symbol = kwargs.get("symbol", symbol) or symbol
    title = kwargs.get("title", title) or title
    description = kwargs.get("description", description) or description
    if "price" in kwargs:
        try:
            price = float(kwargs["price"])
        except Exception:
            pass
    severity = str(kwargs.get("severity", severity) or severity).upper()
    opportunity = int(kwargs.get("opportunity", opportunity) or opportunity)
    confidence = int(kwargs.get("confidence", confidence) or confidence)
    risk = int(kwargs.get("risk", risk) or risk)

    if _bot is None or not _bot.is_ready():
        log.warning("Discord not ready — alert skipped", symbol=symbol, title=title)
        return False

    color = discord.Color.gold()
    if severity == "HIGH":
        color = discord.Color.red()
    elif severity == "LOW":
        color = discord.Color.blue()
    elif severity == "MEDIUM":
        color = discord.Color.orange()

    embed = discord.Embed(
        title=(title or f"{symbol} alert")[:256],
        description=(description or "")[:4000],
        color=color,
    )
    if symbol:
        embed.add_field(name="Symbol", value=str(symbol)[:64], inline=True)
    if price:
        price_str = f"${price:.6g}" if price < 1 else (f"${price:.4f}" if price < 1000 else f"${price:,.2f}")
        embed.add_field(name="Price", value=price_str, inline=True)
    embed.add_field(name="Severity", value=severity, inline=True)
    embed.add_field(name="Opportunity", value=str(opportunity), inline=True)
    embed.add_field(name="Confidence", value=str(confidence), inline=True)
    embed.add_field(name="Risk", value=str(risk), inline=True)
    embed.set_footer(text="Project Atlas · Market Intelligence")

    recipients = list(_subscribers)
    if not recipients:
        for oid in get_settings().discord_owner_id_list:
            recipients.append(oid)
    if not recipients:
        log.warning("No Discord subscribers for alert", symbol=symbol)
        return False

    ok = 0
    for uid in recipients:
        try:
            user = await _bot.fetch_user(int(uid))
            await user.send(embed=embed)
            ok += 1
        except Exception as e:
            log.warning("DM failed", user_id=uid, error=str(e))
    if ok:
        log.info("Discord alert delivered", recipients=ok, symbol=symbol)
    return ok > 0