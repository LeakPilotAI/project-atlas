"""
Project Atlas — Discord bot

Professional slash commands for status, performance,
quality dips, opportunities, and subscriptions.
Alerts are delivered via DM to subscribers only.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.analytics.anomaly import AnomalySignal

logger = get_logger("discord")
settings = get_settings()

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

SUBSCRIBERS_KEY = "atlas:discord:subscribers"


# ──────────────────────────────────────────────
# Subscriber helpers
# ──────────────────────────────────────────────

async def get_subscriber_ids() -> list[int]:
    redis = await get_redis()
    raw = await redis.smembers(SUBSCRIBERS_KEY)
    ids: list[int] = []
    for item in raw:
        try:
            s = item.decode() if isinstance(item, bytes) else str(item)
            ids.append(int(s))
        except Exception:
            continue
    return ids


async def add_subscriber(user_id: int) -> None:
    redis = await get_redis()
    await redis.sadd(SUBSCRIBERS_KEY, str(user_id))


async def remove_subscriber(user_id: int) -> None:
    redis = await get_redis()
    await redis.srem(SUBSCRIBERS_KEY, str(user_id))


async def is_subscribed(user_id: int) -> bool:
    redis = await get_redis()
    return bool(await redis.sismember(SUBSCRIBERS_KEY, str(user_id)))


# ──────────────────────────────────────────────
# Bot lifecycle
# ──────────────────────────────────────────────

@bot.event
async def on_ready():
    logger.info("Discord bot ready", user=str(bot.user), id=bot.user.id if bot.user else None)
    try:
        synced = await bot.tree.sync()
        logger.info("Slash commands synced", count=len(synced))
    except Exception as e:
        logger.error("Failed to sync slash commands", error=str(e))


# ──────────────────────────────────────────────
# Alert delivery
# ──────────────────────────────────────────────

def _severity_color(severity: str) -> discord.Color:
    s = (severity or "").lower()
    if s in ("high", "critical"):
        return discord.Color.red()
    if s == "medium":
        return discord.Color.orange()
    return discord.Color.gold()


async def send_discord_alert(
    signal: AnomalySignal,
    chart_bytes: Optional[bytes] = None,
) -> None:
    """DM all subscribers with a professional embed."""
    if not bot.is_ready():
        logger.warning("Discord not ready — alert skipped", symbol=signal.symbol)
        return

    subscriber_ids = await get_subscriber_ids()
    if not subscriber_ids:
        logger.info("No Discord subscribers — alert skipped", symbol=signal.symbol)
        return

    embed = discord.Embed(
        title=signal.title or f"{signal.symbol} Alert",
        description=signal.message or "",
        color=_severity_color(signal.severity),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="Symbol", value=f"`{signal.symbol}`", inline=True)
    embed.add_field(name="Price", value=f"${signal.price:,.4f}" if signal.price else "—", inline=True)
    embed.add_field(name="Severity", value=(signal.severity or "—").upper(), inline=True)

    if signal.opportunity_score is not None:
        embed.add_field(name="Opportunity", value=f"{signal.opportunity_score:.0f}", inline=True)
    if signal.confidence_score is not None:
        embed.add_field(name="Confidence", value=f"{signal.confidence_score:.0f}", inline=True)
    if signal.risk_score is not None:
        embed.add_field(name="Risk", value=f"{signal.risk_score:.0f}", inline=True)

    embed.set_footer(text="Project Atlas • Market Intelligence")

    file = None
    if chart_bytes:
        file = discord.File(fp=__import__("io").BytesIO(chart_bytes), filename="chart.png")
        embed.set_image(url="attachment://chart.png")

    sent = 0
    for uid in subscriber_ids:
        try:
            user = await bot.fetch_user(uid)
            if file:
                # Re-create file object per send
                f = discord.File(fp=__import__("io").BytesIO(chart_bytes), filename="chart.png")
                await user.send(embed=embed, file=f)
            else:
                await user.send(embed=embed)
            sent += 1
            await asyncio.sleep(0.35)
        except Exception as e:
            logger.warning("Failed to DM user", user_id=uid, error=str(e))

    logger.info("Discord alert delivered", symbol=signal.symbol, recipients=sent)


# ──────────────────────────────────────────────
# Slash commands
# ──────────────────────────────────────────────

@bot.tree.command(name="help", description="Show all Atlas commands")
async def cmd_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Project Atlas — Commands",
        description="Professional market intelligence for Hyperliquid perps + quality stock dips.",
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="📡 Alerts",
        value=(
            "`/subscribe` — Receive DM alerts\n"
            "`/unsubscribe` — Stop DM alerts\n"
            "`/mystatus` — Your subscription status"
        ),
        inline=False,
    )
    embed.add_field(
        name="📊 System",
        value=(
            "`/status` — Bot health & scanners\n"
            "`/performance` — Paper trade stats\n"
            "`/opportunities` — Recent tracked setups"
        ),
        inline=False,
    )
    embed.add_field(
        name="🏦 Quality Dips (Stocks)",
        value=(
            "`/dips` — Watchlist discount status\n"
            "`/watchlist` — Current stock watchlist"
        ),
        inline=False,
    )
    embed.add_field(
        name="🔍 Research",
        value=(
            "`/whale <symbol>` — Hyperliquid whale flow\n"
            "`/regime <symbol>` — Market regime\n"
            "`/ticker <symbol>` — Quick market snapshot"
        ),
        inline=False,
    )
    embed.set_footer(text="Alerts are DM-only • No channel spam")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="subscribe", description="Start receiving Atlas alert DMs")
async def cmd_subscribe(interaction: discord.Interaction):
    await add_subscriber(interaction.user.id)
    embed = discord.Embed(
        title="Subscribed",
        description=(
            "You will now receive **private DMs** for:\n"
            "• High-quality Hyperliquid perp setups\n"
            "• Quality stock dip / generational discount alerts\n\n"
            "No channel spam."
        ),
        color=discord.Color.green(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="unsubscribe", description="Stop receiving Atlas alert DMs")
async def cmd_unsubscribe(interaction: discord.Interaction):
    await remove_subscriber(interaction.user.id)
    embed = discord.Embed(
        title="Unsubscribed",
        description="You will no longer receive Atlas DMs.",
        color=discord.Color.orange(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="mystatus", description="Check your subscription status")
async def cmd_mystatus(interaction: discord.Interaction):
    sub = await is_subscribed(interaction.user.id)
    embed = discord.Embed(
        title="Your Status",
        color=discord.Color.green() if sub else discord.Color.greyple(),
    )
    embed.add_field(name="Subscribed", value="Yes ✅" if sub else "No ❌", inline=True)
    embed.add_field(name="User ID", value=f"`{interaction.user.id}`", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="status", description="System health and scanner status")
async def cmd_status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get("http://127.0.0.1:8000/health")
            data = r.json()
    except Exception as e:
        await interaction.followup.send(f"Could not reach API: `{e}`", ephemeral=True)
        return

    def flag(v: bool) -> str:
        return "🟢 Running" if v else "🔴 Stopped"

    embed = discord.Embed(
        title="Atlas System Status",
        color=discord.Color.green() if data.get("status") == "ok" else discord.Color.red(),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="API", value=data.get("status", "—").upper(), inline=True)
    embed.add_field(name="Redis", value=data.get("redis", "—"), inline=True)
    embed.add_field(name="Discord", value="Ready" if data.get("discord_ready") else "Not ready", inline=True)
    embed.add_field(name="Hyperliquid Scanner", value=flag(data.get("scanner_running")), inline=True)
    embed.add_field(name="Opportunity Tracker", value=flag(data.get("opportunity_tracker_running")), inline=True)
    embed.add_field(name="Paper Trades", value=flag(data.get("paper_trade_tracker_running")), inline=True)
    embed.add_field(name="Weekly Summary", value=flag(data.get("weekly_summary_running")), inline=True)
    embed.add_field(name="Quality Dip Scanner", value=flag(data.get("quality_dip_running")), inline=True)
    adapters = data.get("adapters") or []
    embed.add_field(name="Adapters", value=", ".join(adapters) if adapters else "—", inline=True)
    embed.set_footer(text="Project Atlas")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="performance", description="Paper trade performance summary")
async def cmd_performance(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get("http://127.0.0.1:8000/api/performance")
            data = r.json()
    except Exception as e:
        await interaction.followup.send(f"Could not load performance: `{e}`", ephemeral=True)
        return

    embed = discord.Embed(
        title="Paper Trade Performance",
        color=discord.Color.teal(),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="Closed Trades", value=str(data.get("total_closed", 0)), inline=True)
    embed.add_field(name="Win Rate", value=f"{data.get('win_rate', 0)}%", inline=True)
    embed.add_field(name="Avg PnL", value=f"{data.get('avg_pnl', 0):+.2f}%", inline=True)
    embed.add_field(name="Best Trade", value=f"{data.get('best_trade', 0):+.2f}%", inline=True)
    embed.add_field(name="Worst Trade", value=f"{data.get('worst_trade', 0):+.2f}%", inline=True)
    embed.set_footer(text="Simulated results • Not financial advice")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="opportunities", description="Recent monitored / signaled opportunities")
async def cmd_opportunities(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get("http://127.0.0.1:8000/api/opportunities")
            rows = r.json()
    except Exception as e:
        await interaction.followup.send(f"Could not load opportunities: `{e}`", ephemeral=True)
        return

    if not rows:
        await interaction.followup.send("No recent opportunities.", ephemeral=True)
        return

    lines = []
    for o in rows[:12]:
        rec = o.get("recommendation") or "—"
        conf = o.get("confidence")
        conf_s = f"{conf:.0f}%" if conf is not None else "—"
        lines.append(
            f"**{o.get('symbol')}** · `{o.get('status')}` · {rec} · conf {conf_s}"
        )

    embed = discord.Embed(
        title="Recent Opportunities",
        description="\n".join(lines),
        color=discord.Color.dark_gold(),
        timestamp=discord.utils.utcnow(),
    )
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="dips", description="Quality stock dips currently in discount zone")
async def cmd_dips(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get("http://127.0.0.1:8000/api/quality-dips")
            data = r.json()
    except Exception as e:
        await interaction.followup.send(f"Could not load quality dips: `{e}`", ephemeral=True)
        return

    discounts = data.get("in_discount_zone") or []
    watchlist = data.get("watchlist") or []

    if not discounts:
        embed = discord.Embed(
            title="Quality Dips",
            description=(
                f"No names currently in the configured discount zone.\n"
                f"Watchlist: `{', '.join(watchlist)}`"
            ),
            color=discord.Color.greyple(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    lines = []
    for d in discounts:
        lines.append(
            f"**{d['symbol']}** ${d['price']:,.2f} · "
            f"**{d['pct_from_high']:.1f}%** below 52w high · "
            f"`{d['priority'].upper()}`"
        )

    embed = discord.Embed(
        title="Quality Dip Zone",
        description="\n".join(lines),
        color=discord.Color.red(),
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(text="Review before buying • No auto-buy")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="watchlist", description="Show the quality-dip stock watchlist")
async def cmd_watchlist(interaction: discord.Interaction):
    from app.services.quality_dip_scanner import _watchlist, _threshold_pct, _high_priority_pct

    wl = _watchlist()
    embed = discord.Embed(
        title="Quality Dip Watchlist",
        description=", ".join(f"`{t}`" for t in wl) if wl else "Empty",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Alert threshold", value=f"{_threshold_pct():.0f}% below 52w high", inline=True)
    embed.add_field(name="High priority", value=f"{_high_priority_pct():.0f}% below 52w high", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="whale", description="Hyperliquid whale flow for a symbol")
@app_commands.describe(symbol="Ticker e.g. BTC, SOL, ETH")
async def cmd_whale(interaction: discord.Interaction, symbol: str):
    await interaction.response.defer(ephemeral=True)
    symbol = symbol.upper().strip()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"http://127.0.0.1:8000/api/whale/{symbol}")
            data = r.json()
    except Exception as e:
        await interaction.followup.send(f"Whale lookup failed: `{e}`", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"Whale Flow — {symbol}",
        description=data.get("summary") or "—",
        color=discord.Color.purple(),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="Bias", value=str(data.get("bias", "—")).upper(), inline=True)
    embed.add_field(name="Net USD", value=f"${data.get('net_usd', 0):+,.0f}", inline=True)
    embed.add_field(name="Large trades", value=str(data.get("trade_count", 0)), inline=True)
    largest = data.get("largest_trade")
    if largest:
        embed.add_field(
            name="Largest",
            value=f"{largest.get('side', '').upper()} ${largest.get('size_usd', 0):,.0f} @ ${largest.get('price', 0)}",
            inline=False,
        )
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="regime", description="Market regime for a Hyperliquid symbol")
@app_commands.describe(symbol="Ticker e.g. BTC, SOL")
async def cmd_regime(interaction: discord.Interaction, symbol: str):
    await interaction.response.defer(ephemeral=True)
    symbol = symbol.upper().strip()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"http://127.0.0.1:8000/api/regime/{symbol}")
            data = r.json()
    except Exception as e:
        await interaction.followup.send(f"Regime lookup failed: `{e}`", ephemeral=True)
        return

    if data.get("error"):
        await interaction.followup.send(f"Error: {data['error']}", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"Regime — {symbol}",
        color=discord.Color.dark_teal(),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="Regime", value=str(data.get("regime", "—")), inline=True)
    embed.add_field(name="Direction", value=str(data.get("direction", "—")), inline=True)
    embed.add_field(name="Confidence", value=f"{data.get('confidence', 0):.0f}", inline=True)
    embed.add_field(name="Trend strength", value=str(data.get("trend_strength", "—")), inline=True)
    embed.add_field(name="Volatility", value=str(data.get("volatility", "—")), inline=True)
    if data.get("notes"):
        embed.add_field(name="Notes", value=str(data["notes"]), inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="ticker", description="Quick Hyperliquid ticker snapshot")
@app_commands.describe(symbol="Ticker e.g. BTC")
async def cmd_ticker(interaction: discord.Interaction, symbol: str):
    await interaction.response.defer(ephemeral=True)
    symbol = symbol.upper().strip()
    try:
        from app.adapters.registry import registry
        adapter = registry.get("hyperliquid")
        if not adapter:
            await interaction.followup.send("Hyperliquid adapter unavailable", ephemeral=True)
            return
        tickers = await adapter.get_all_tickers()
        match = next((t for t in tickers if t.symbol.upper() == symbol), None)
        if not match:
            await interaction.followup.send(f"No ticker found for `{symbol}`", ephemeral=True)
            return
        d = match.model_dump() if hasattr(match, "model_dump") else match.__dict__
        embed = discord.Embed(
            title=f"{symbol} — Hyperliquid",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Price", value=f"${d.get('price', 0):,.4f}", inline=True)
        embed.add_field(name="24h Volume", value=f"${d.get('volume_24h', 0):,.0f}", inline=True)
        embed.add_field(name="Open Interest", value=f"{d.get('open_interest', 0):,.2f}", inline=True)
        fr = d.get("funding_rate")
        if fr is not None:
            embed.add_field(name="Funding", value=f"{float(fr):.6f}", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Ticker failed: `{e}`", ephemeral=True)