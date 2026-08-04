"""
Project Atlas — Discord bot

Slash commands for system status, quality dips, performance,
research helpers, and DM subscriptions.
"""

from __future__ import annotations

import asyncio
import io
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
# Lifecycle
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
    if not bot.is_ready():
        logger.warning("Discord not ready — alert skipped", symbol=getattr(signal, "symbol", None))
        return

    subscriber_ids = await get_subscriber_ids()
    if not subscriber_ids:
        logger.info("No Discord subscribers — alert skipped", symbol=getattr(signal, "symbol", None))
        return

    embed = discord.Embed(
        title=signal.title or f"{signal.symbol} Alert",
        description=signal.message or "",
        color=_severity_color(signal.severity),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="Symbol", value=f"`{signal.symbol}`", inline=True)
    price = getattr(signal, "price", None)
    embed.add_field(
        name="Price",
        value=f"${price:,.4f}" if price is not None else "—",
        inline=True,
    )
    embed.add_field(name="Severity", value=(signal.severity or "—").upper(), inline=True)

    if signal.opportunity_score is not None:
        embed.add_field(name="Opportunity", value=f"{signal.opportunity_score:.0f}", inline=True)
    if signal.confidence_score is not None:
        embed.add_field(name="Confidence", value=f"{signal.confidence_score:.0f}", inline=True)
    if signal.risk_score is not None:
        embed.add_field(name="Risk", value=f"{signal.risk_score:.0f}", inline=True)

    embed.set_footer(text="Project Atlas • Market Intelligence")

    for uid in subscriber_ids:
        try:
            user = await bot.fetch_user(uid)
            if chart_bytes:
                f = discord.File(fp=io.BytesIO(chart_bytes), filename="chart.png")
                embed_copy = embed.copy()
                embed_copy.set_image(url="attachment://chart.png")
                await user.send(embed=embed_copy, file=f)
            else:
                await user.send(embed=embed)
            await asyncio.sleep(0.35)
        except Exception as e:
            logger.warning("Failed to DM user", user_id=uid, error=str(e))

    logger.info("Discord alert delivered", symbol=signal.symbol, recipients=len(subscriber_ids))


async def _api_get(path: str, timeout: float = 30.0) -> dict | list:
    import httpx
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(f"http://127.0.0.1:8000{path}")
        r.raise_for_status()
        return r.json()


# ──────────────────────────────────────────────
# Slash commands
# ──────────────────────────────────────────────

@bot.tree.command(name="help", description="Show all Atlas commands")
async def cmd_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Project Atlas — Command Center",
        description="Hyperliquid perp scanner + quality equity/metals dip intelligence.",
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="📡 Alerts",
        value=(
            "`/subscribe` — Receive DM alerts + batch briefings\n"
            "`/unsubscribe` — Stop all DMs\n"
            "`/mystatus` — Your subscription status"
        ),
        inline=False,
    )
    embed.add_field(
        name="🖥️ System",
        value=(
            "`/status` — Full system health\n"
            "`/performance` — Paper trade stats\n"
            "`/opportunities` — Recent perp setups"
        ),
        inline=False,
    )
    embed.add_field(
        name="🏦 Quality Dips",
        value=(
            "`/dips` — Ranked names in discount zone\n"
            "`/watchlist` — Full equity/metals list + thresholds\n"
            "`/briefing` — Fresh analysis priority list now"
        ),
        inline=False,
    )
    embed.add_field(
        name="🔍 Research",
        value=(
            "`/ticker <symbol>` — Hyperliquid snapshot\n"
            "`/whale <symbol>` — Whale flow\n"
            "`/regime <symbol>` — Market regime"
        ),
        inline=False,
    )
    embed.set_footer(text="Alerts are DM-only • No channel spam")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="subscribe", description="Receive Atlas DM alerts and batch briefings")
async def cmd_subscribe(interaction: discord.Interaction):
    await add_subscriber(interaction.user.id)
    embed = discord.Embed(
        title="Subscribed",
        description=(
            "You will receive **private DMs** for:\n"
            "• High-quality Hyperliquid setups\n"
            "• Quality stock / metals dip alerts\n"
            "• Post-scan ranked analysis briefings\n\n"
            "No server channel spam."
        ),
        color=discord.Color.green(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="unsubscribe", description="Stop receiving Atlas DMs")
async def cmd_unsubscribe(interaction: discord.Interaction):
    await remove_subscriber(interaction.user.id)
    embed = discord.Embed(
        title="Unsubscribed",
        description="You will no longer receive Atlas DMs.",
        color=discord.Color.orange(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="mystatus", description="Your subscription status")
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
        data = await _api_get("/health", timeout=8.0)
    except Exception as e:
        await interaction.followup.send(f"API unreachable: `{e}`", ephemeral=True)
        return

    def flag(v) -> str:
        return "🟢 Running" if v else "🔴 Stopped"

    embed = discord.Embed(
        title="Atlas System Status",
        color=discord.Color.green() if data.get("status") == "ok" else discord.Color.red(),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="API", value=str(data.get("status", "—")).upper(), inline=True)
    embed.add_field(name="Redis", value=str(data.get("redis", "—")), inline=True)
    embed.add_field(
        name="Discord",
        value="Ready" if data.get("discord_ready") else "Not ready",
        inline=True,
    )
    embed.add_field(name="Perp Scanner", value=flag(data.get("scanner_running")), inline=True)
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
        data = await _api_get("/api/performance", timeout=12.0)
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


@bot.tree.command(name="opportunities", description="Recent monitored / signaled perp opportunities")
async def cmd_opportunities(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        rows = await _api_get("/api/opportunities", timeout=12.0)
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
        conf_s = f"{conf:.0f}" if conf is not None else "—"
        lines.append(f"**{o.get('symbol')}** · `{o.get('status')}` · {rec} · conf {conf_s}")

    embed = discord.Embed(
        title="Recent Opportunities",
        description="\n".join(lines),
        color=discord.Color.dark_gold(),
        timestamp=discord.utils.utcnow(),
    )
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="dips", description="Ranked quality dips currently in discount zone")
async def cmd_dips(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        data = await _api_get("/api/quality-dips", timeout=90.0)
    except Exception as e:
        await interaction.followup.send(f"Could not load quality dips: `{e}`", ephemeral=True)
        return

    discounts = data.get("in_discount_zone") or []
    watchlist = data.get("watchlist") or []

    if not discounts:
        embed = discord.Embed(
            title="Quality Dips",
            description=(
                "No names currently in the configured discount zone.\n"
                f"Watchlist size: **{len(watchlist)}**"
            ),
            color=discord.Color.greyple(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    # Prefer review_score if present
    discounts = sorted(
        discounts,
        key=lambda d: d.get("review_score", d.get("pct_from_high", 0)),
        reverse=True,
    )

    lines = []
    for i, d in enumerate(discounts[:15], 1):
        score = d.get("review_score")
        score_s = f" · score {score:.0f}" if score is not None else ""
        cat = (d.get("category") or "stock").upper()
        lines.append(
            f"**{i}. {d['symbol']}** (${d['price']:,.2f}) — "
            f"**{d['pct_from_high']:.1f}%** off high · `{cat}`{score_s}"
        )

    embed = discord.Embed(
        title=f"Quality Dip Zone — {len(discounts)} names",
        description="\n".join(lines),
        color=discord.Color.red(),
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(text="Review before buying • Use /briefing for analysis order")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="briefing", description="Run ranked deep-analysis priority list now")
async def cmd_briefing(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        data = await _api_get("/api/quality-dips", timeout=90.0)
    except Exception as e:
        await interaction.followup.send(f"Briefing failed: `{e}`", ephemeral=True)
        return

    discounts = data.get("in_discount_zone") or []
    if not discounts:
        await interaction.followup.send("No discount-zone names to brief right now.", ephemeral=True)
        return

    discounts = sorted(
        discounts,
        key=lambda d: d.get("review_score", d.get("pct_from_high", 0)),
        reverse=True,
    )
    top = discounts[:6]
    metals = [d for d in discounts if (d.get("category") or "") == "metal"]

    lines = [
        f"**{len(discounts)} candidates** in discount zone.",
        "Research priority only — not buy advice. Confirm prices on your broker.",
        "",
        "**Start deep analysis here:**",
    ]
    for i, d in enumerate(top, 1):
        note = d.get("review_note") or ""
        score = d.get("review_score")
        score_s = f"{score:.0f}/100" if score is not None else "—"
        lines.append(
            f"{i}. **{d['symbol']}** — {d['pct_from_high']:.1f}% off high · score {score_s}"
        )
        if note:
            lines.append(f"   _{note}_")

    lines.append("")
    lines.append("**Approach**")
    lines.append(f"• Open charts for **{top[0]['symbol']}**, **{top[1]['symbol'] if len(top)>1 else '—'}**, "
                 f"**{top[2]['symbol'] if len(top)>2 else '—'}** only.")
    if metals:
        lines.append(
            f"• Metals theme active: {', '.join(m['symbol'] for m in metals[:5])} — one thesis, not five trades."
        )
    lines.append("• Verify live price → thesis → size small if acting.")
    lines.append("")
    lines.append("_Atlas ranks research time. You decide capital._")

    embed = discord.Embed(
        title="📋 Quality Dip Briefing",
        description="\n".join(lines),
        color=discord.Color.dark_gold(),
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(text="Project Atlas • Not financial advice")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="watchlist", description="Quality-dip watchlist and thresholds")
async def cmd_watchlist(interaction: discord.Interaction):
    from app.services.quality_dip_scanner import _watchlist, METALS_SYMBOLS

    wl = _watchlist()
    metals = [t for t in wl if t in METALS_SYMBOLS]
    stocks = [t for t in wl if t not in METALS_SYMBOLS]

    embed = discord.Embed(
        title="Quality Dip Watchlist",
        color=discord.Color.blurple(),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(
        name=f"Stocks ({len(stocks)})",
        value=", ".join(f"`{t}`" for t in stocks) or "—",
        inline=False,
    )
    embed.add_field(
        name=f"Metals ({len(metals)})",
        value=", ".join(f"`{t}`" for t in metals) or "—",
        inline=False,
    )
    embed.add_field(
        name="Stock thresholds",
        value=f"{settings.quality_dip_threshold_pct:.0f}% / {settings.quality_dip_high_priority_pct:.0f}% high",
        inline=True,
    )
    embed.add_field(
        name="Metals thresholds",
        value=f"{settings.quality_dip_metals_threshold_pct:.0f}% / {settings.quality_dip_metals_high_priority_pct:.0f}% high",
        inline=True,
    )
    embed.add_field(
        name="Adaptive",
        value="ON" if settings.quality_dip_adaptive else "OFF",
        inline=True,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="whale", description="Hyperliquid whale flow for a symbol")
@app_commands.describe(symbol="Ticker e.g. BTC, SOL, ETH")
async def cmd_whale(interaction: discord.Interaction, symbol: str):
    await interaction.response.defer(ephemeral=True)
    symbol = symbol.upper().strip()
    try:
        data = await _api_get(f"/api/whale/{symbol}", timeout=15.0)
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
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="regime", description="Market regime for a Hyperliquid symbol")
@app_commands.describe(symbol="Ticker e.g. BTC, SOL")
async def cmd_regime(interaction: discord.Interaction, symbol: str):
    await interaction.response.defer(ephemeral=True)
    symbol = symbol.upper().strip()
    try:
        data = await _api_get(f"/api/regime/{symbol}", timeout=15.0)
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