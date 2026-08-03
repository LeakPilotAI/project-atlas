import asyncio
import csv
import io
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.core.redis import get_redis, close_redis
from app.adapters.registry import registry
from app.adapters.hyperliquid import HyperliquidAdapter
from app.services.scanner import scanner
from app.services.opportunity_tracker import opportunity_tracker
from app.services.paper_trade_tracker import paper_trade_tracker
from app.services.weekly_summary import weekly_summary_service
from app.services.quality_dip_scanner import quality_dip_scanner
from app.alerts.discord import bot as discord_bot

setup_logging()
logger = get_logger("main")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Project Atlas starting", env=settings.app_env)
    logger.info("Database URL host check", database_url=settings.database_url.split("@")[-1])

    try:
        r = await get_redis()
        await r.ping()
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.warning("Redis connection failed", error=str(e))

    from app.db.session import engine, Base
    from app.models import Market, Alert, Candle, Opportunity, PaperTrade  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")

    registry.register(HyperliquidAdapter())
    await registry.connect_all()

    await scanner.start()
    await opportunity_tracker.start()
    await paper_trade_tracker.start()
    await weekly_summary_service.start()
    await quality_dip_scanner.start()

    if settings.discord_token:
        asyncio.create_task(discord_bot.start(settings.discord_token))
        logger.info("Discord bot starting...")
    else:
        logger.warning("No DISCORD_TOKEN found – Discord alerts disabled")

    yield

    await scanner.stop()
    await opportunity_tracker.stop()
    await paper_trade_tracker.stop()
    await weekly_summary_service.stop()
    await quality_dip_scanner.stop()
    await registry.disconnect_all()
    await close_redis()

    if discord_bot.is_ready():
        await discord_bot.close()

    logger.info("Project Atlas shutting down")


app = FastAPI(
    title="Project Atlas",
    description="Advanced Trading & Liquidity Analysis System",
    version="0.10.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    redis_status = "unknown"
    try:
        r = await get_redis()
        await r.ping()
        redis_status = "ok"
    except Exception:
        redis_status = "unavailable"

    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.app_env,
        "redis": redis_status,
        "adapters": [a.name for a in registry.all()],
        "scanner_running": scanner._running,
        "opportunity_tracker_running": opportunity_tracker._running,
        "paper_trade_tracker_running": paper_trade_tracker._running,
        "weekly_summary_running": weekly_summary_service._running,
        "quality_dip_running": quality_dip_scanner._running,
        "discord_ready": discord_bot.is_ready() if settings.discord_token else False,
    }


@app.get("/")
async def root():
    return {"message": "Project Atlas is online"}


@app.get("/markets/tickers")
async def get_tickers():
    adapter = registry.get("hyperliquid")
    if not adapter:
        return {"error": "Hyperliquid adapter not available"}
    tickers = await adapter.get_all_tickers()
    return {
        "count": len(tickers),
        "tickers": [t.model_dump() for t in tickers[:50]],
    }


@app.get("/api/performance")
async def api_performance():
    from sqlalchemy import select, func
    from app.db.session import AsyncSessionLocal
    from app.models.paper_trade import PaperTrade

    async with AsyncSessionLocal() as session:
        total = await session.scalar(
            select(func.count()).select_from(PaperTrade).where(PaperTrade.status == "closed")
        ) or 0
        winners = await session.scalar(
            select(func.count()).select_from(PaperTrade).where(
                PaperTrade.status == "closed", PaperTrade.is_winner == True
            )
        ) or 0
        avg_pnl = await session.scalar(
            select(func.avg(PaperTrade.pnl_pct)).where(PaperTrade.status == "closed")
        ) or 0
        best = await session.scalar(
            select(func.max(PaperTrade.pnl_pct)).where(PaperTrade.status == "closed")
        ) or 0
        worst = await session.scalar(
            select(func.min(PaperTrade.pnl_pct)).where(PaperTrade.status == "closed")
        ) or 0

    return {
        "total_closed": total,
        "win_rate": round((winners / total * 100) if total > 0 else 0, 1),
        "avg_pnl": round(float(avg_pnl), 2),
        "best_trade": round(float(best), 2),
        "worst_trade": round(float(worst), 2),
    }


@app.get("/api/opportunities")
async def api_opportunities():
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.models.opportunity import Opportunity

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Opportunity).order_by(Opportunity.fired_at.desc()).limit(20)
        )
        opps = result.scalars().all()

    return [
        {
            "symbol": o.symbol,
            "status": o.status,
            "recommendation": o.recommendation,
            "confidence": o.recommendation_confidence,
            "entry_price": o.initial_price,
            "fired_at": o.fired_at.isoformat() if o.fired_at else None,
        }
        for o in opps
    ]


@app.get("/api/backtest/{symbol}")
async def api_backtest(symbol: str, lookforward: int = 12):
    from app.adapters.registry import registry
    from app.backtest.engine import run_simple_backtest
    from app.core.logging import get_logger

    log = get_logger("api.backtest")
    symbol = symbol.upper().strip()

    try:
        adapter = registry.get("hyperliquid")
        if not adapter:
            return {"error": "Hyperliquid adapter not available", "symbol": symbol}

        log.info("Fetching candles for backtest", symbol=symbol)
        candles_5m = await adapter.get_candles(symbol, interval="5m", limit=300)
        candles_15m = await adapter.get_candles(symbol, interval="15m", limit=120)

        log.info(
            "Candles received",
            symbol=symbol,
            count_5m=len(candles_5m),
            count_15m=len(candles_15m),
        )

        if len(candles_5m) < 50:
            return {
                "error": f"Not enough 5m data for {symbol} (got {len(candles_5m)} candles)",
                "symbol": symbol,
                "total_trades": 0,
            }

        result = run_simple_backtest(
            symbol, candles_5m, candles_15m, lookforward_bars=lookforward
        )

        return {
            "symbol": symbol,
            "total_trades": result.total_trades,
            "win_rate": result.win_rate,
            "avg_pnl": result.avg_pnl,
            "total_pnl": result.total_pnl,
            "best_trade": result.best_trade,
            "worst_trade": result.worst_trade,
            "avg_mfe": result.avg_mfe,
            "avg_mae": result.avg_mae,
            "expectancy": result.expectancy,
            "sample_trades": [
                {
                    "side": t.side,
                    "entry": t.entry_price,
                    "exit": t.exit_price,
                    "pnl_pct": t.pnl_pct,
                    "confidence": t.confidence,
                }
                for t in result.trades[:10]
            ],
        }

    except Exception as e:
        log.error("Backtest failed", symbol=symbol, error=str(e))
        return {
            "error": f"Backtest failed: {str(e)}",
            "symbol": symbol,
            "total_trades": 0,
        }


@app.get("/api/analytics/performance")
async def api_full_performance():
    from app.analytics.performance import get_full_performance_report
    from dataclasses import asdict

    report = await get_full_performance_report()
    return {
        "overall": asdict(report.overall),
        "by_side": {k: asdict(v) for k, v in report.by_side.items()},
        "by_symbol": [asdict(s) for s in report.by_symbol],
        "last_7_days": asdict(report.last_7_days),
        "last_30_days": asdict(report.last_30_days),
    }


@app.get("/api/profiles")
async def api_list_profiles():
    from app.analytics.profiles import list_profiles
    return {"profiles": list_profiles()}


@app.get("/api/profiles/active")
async def api_active_profile():
    return {"active": "balanced"}


@app.get("/api/regime/{symbol}")
async def api_regime(symbol: str):
    from app.adapters.registry import registry
    from app.analytics.regime import detect_regime

    symbol = symbol.upper().strip()
    adapter = registry.get("hyperliquid")
    if not adapter:
        return {"error": "Adapter not available"}

    candles = await adapter.get_candles(symbol, interval="5m", limit=60)
    if len(candles) < 30:
        return {"error": "Not enough data", "symbol": symbol}

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]

    regime = detect_regime(closes, highs, lows)
    return {
        "symbol": symbol,
        "regime": regime.regime,
        "trend_strength": regime.trend_strength,
        "volatility": regime.volatility,
        "direction": regime.direction,
        "confidence": regime.confidence,
        "notes": regime.notes,
    }


@app.get("/api/replay/{symbol}")
async def api_replay(symbol: str, max_steps: int = 60):
    from app.adapters.registry import registry
    from app.services.replay import run_replay
    from app.core.logging import get_logger

    log = get_logger("api.replay")
    symbol = symbol.upper().strip()

    try:
        adapter = registry.get("hyperliquid")
        if not adapter:
            return {"error": "Hyperliquid adapter not available"}

        candles_5m = await adapter.get_candles(symbol, interval="5m", limit=250)
        candles_15m = await adapter.get_candles(symbol, interval="15m", limit=100)

        if len(candles_5m) < 60:
            return {
                "error": f"Not enough data for replay (got {len(candles_5m)} candles)",
                "symbol": symbol,
            }

        result = run_replay(
            symbol=symbol,
            candles_5m=candles_5m,
            candles_15m=candles_15m,
            start_index=40,
            max_steps=max_steps,
        )

        steps_out = []
        for s in result.steps:
            if s.decision or s.anomalies:
                steps_out.append(
                    {
                        "index": s.index,
                        "timestamp": s.timestamp.isoformat(),
                        "price": s.price,
                        "volume": s.volume,
                        "regime": s.regime,
                        "anomalies": [
                            {
                                "title": a.title,
                                "severity": a.severity,
                                "opportunity_score": a.opportunity_score,
                            }
                            for a in s.anomalies
                        ],
                        "decision": (
                            {
                                "recommendation": s.decision.recommendation,
                                "confidence": s.decision.confidence,
                                "reason": s.decision.reason,
                                "regime": s.decision.regime,
                            }
                            if s.decision
                            else None
                        ),
                        "notes": s.notes,
                    }
                )

        return {
            "symbol": result.symbol,
            "interval": result.interval,
            "total_bars": result.total_bars,
            "summary": result.summary,
            "interesting_steps": steps_out[:40],
            "interesting_count": len(steps_out),
        }

    except Exception as e:
        log.error("Replay failed", symbol=symbol, error=str(e))
        return {"error": f"Replay failed: {str(e)}", "symbol": symbol}


@app.get("/api/events")
async def api_events():
    from app.analytics.events import get_active_events, is_high_impact_window

    now = datetime.now(timezone.utc)
    active = get_active_events(now)
    return {
        "high_impact_window": is_high_impact_window(now),
        "active_events": [
            {
                "name": e.name,
                "type": e.event_type,
                "impact": e.impact,
                "start": e.start.isoformat(),
                "end": e.end.isoformat(),
                "notes": e.notes,
            }
            for e in active
        ],
    }


@app.get("/api/whale/{symbol}")
async def api_whale(symbol: str):
    from app.analytics.whale import analyze_whale_flow, format_whale_note

    symbol = symbol.upper().strip()
    flow = await analyze_whale_flow(symbol)
    return {
        "symbol": flow.symbol,
        "bias": flow.bias,
        "net_usd": flow.net_usd,
        "buy_usd": flow.buy_usd,
        "sell_usd": flow.sell_usd,
        "trade_count": flow.trade_count,
        "largest_trade": (
            {
                "side": flow.largest_trade.side,
                "size_usd": flow.largest_trade.size_usd,
                "price": flow.largest_trade.price,
            }
            if flow.largest_trade
            else None
        ),
        "summary": format_whale_note(flow),
    }


@app.get("/api/quality-dips")
async def api_quality_dips():
    from app.services.quality_dip_scanner import quality_dip_scanner, _watchlist

    discounts = await quality_dip_scanner.current_discounts()
    return {
        "watchlist": _watchlist(),
        "in_discount_zone": discounts,
        "count": len(discounts),
    }


@app.get("/api/export/paper-trades")
async def export_paper_trades():
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.models.paper_trade import PaperTrade

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PaperTrade).order_by(PaperTrade.created_at.desc())
        )
        trades = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "symbol",
            "side",
            "status",
            "entry_price",
            "exit_price",
            "pnl_pct",
            "is_winner",
            "confidence",
            "reason",
            "mfe",
            "mae",
            "entry_time",
            "exit_time",
            "created_at",
        ]
    )

    for t in trades:
        writer.writerow(
            [
                t.id,
                t.symbol,
                t.side,
                t.status,
                t.entry_price,
                t.exit_price,
                t.pnl_pct,
                t.is_winner,
                t.confidence,
                t.reason,
                getattr(t, "mfe", None),
                getattr(t, "mae", None),
                t.entry_time.isoformat() if t.entry_time else "",
                t.exit_time.isoformat() if t.exit_time else "",
                t.created_at.isoformat() if t.created_at else "",
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=atlas_paper_trades_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
        },
    )