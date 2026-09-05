"""Project Atlas — FastAPI entrypoint."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.adapters.hyperliquid import HyperliquidAdapter
from app.adapters.registry import registry
from app.alerts.discord import is_discord_ready, start_discord_bot, stop_discord_bot
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.core.redis import close_redis, get_redis_client
from app.db.session import Base, engine

import app.models  # noqa: F401

from app.services.scanner import scanner
from app.services.opportunity_tracker import opportunity_tracker
from app.services.paper_trade_tracker import paper_trade_tracker
from app.services.weekly_summary import weekly_summary_service
from app.services.quality_dip_scanner import quality_dip_scanner
from app.services.day_trade_assistant import day_trade_assistant
from app.services.perp_micro_coach import perp_micro_coach
from app.services.robinhood_brief import robinhood_brief_service
from app.services.command_center import command_center
from app.services.daily_paper_recap import daily_paper_recap
from app.services.micro_heartbeat import micro_heartbeat
from app.api.diagnostics import router as diagnostics_router
from app.api.live import router as live_router
from app.api.validation import router as validation_router
from app.services.performance import router as performance_router


async def _announce_session(info: Dict[str, Any]) -> None:
    await asyncio.sleep(12)
    try:
        from app.alerts.discord import is_discord_ready, send_discord_alert

        if not is_discord_ready():
            return
        prior = int(info.get("prior_closed_archived") or 0)
        desc = (
            f"**New paper testing window** `{info.get('session_id')}`\n\n"
            f"Session stats (WR, closed, avg R) start at zero.\n"
            f"`{prior}` prior PAPER closes stay in the journal for research.\n"
            f"Nothing was deleted.\n\n"
            f"Concurrent paper cap: unlimited (safety 80).\n"
            f"Entry gates unchanged: RSI 28/72 · ext 1.4% · R:R 1.8.\n"
            f"Dashboard: http://127.0.0.1:8000/dashboard\n"
            f"Not live capital."
        )
        await send_discord_alert(
            symbol="ATLAS",
            title="Paper session reset — data kept",
            description=desc,
            severity="LOW",
            opportunity=10,
            confidence=10,
            risk=10,
        )
    except Exception:
        pass

try:
    from app.services.accumulation_ladder import accumulation_ladder
except Exception:
    accumulation_ladder = None  # type: ignore

try:
    from app.services.btc_accumulation import btc_accumulation
except Exception:
    btc_accumulation = None  # type: ignore

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    log.info("Project Atlas starting", env=settings.app_env)
    log.info("Database URL host check", database_url=settings.database_url_safe)

    try:
        from app.services.paper_pipeline import paper_pipeline
        from app.services.paper_pipeline_hooks import apply as apply_pipeline_hooks

        apply_pipeline_hooks()
        log.info("Effective micro config", **paper_pipeline.effective_config())
    except Exception as e:
        log.warning("Could not log effective micro config", error=str(e)[:200])

    try:
        r = await get_redis_client()
        if r is not None:
            await r.ping()
            log.info("Redis connected successfully", url=settings.redis_url)
    except Exception as e:
        log.warning("Redis connection failed", error=str(e))

    last_err: Exception | None = None
    for attempt in range(1, 16):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            log.info("Database tables created/verified", attempt=attempt)
            last_err = None
            break
        except Exception as e:
            last_err = e
            log.warning("Database not ready, retrying", attempt=attempt, error=str(e)[:200])
            await asyncio.sleep(2)
    if last_err is not None:
        log.error("Database init failed", error=str(last_err))
        raise last_err

    async def _boot_services() -> None:
        try:
            hl = HyperliquidAdapter()
            registry.register(hl)
            await hl.connect()
            log.info("Adapter connected", name="hyperliquid")
        except Exception as e:
            log.error("Hyperliquid adapter failed", error=str(e))

        for name, starter in [
            ("scanner", scanner.start),
            ("opportunity_tracker", opportunity_tracker.start),
            ("paper_trade_tracker", paper_trade_tracker.start),
            ("weekly_summary", weekly_summary_service.start),
            ("quality_dip", quality_dip_scanner.start),
            ("day_trade", day_trade_assistant.start),
            ("robinhood_brief", robinhood_brief_service.start),
            ("command_center", command_center.start),
            ("perp_micro_coach", perp_micro_coach.start),
            ("daily_paper_recap", daily_paper_recap.start),
            ("micro_heartbeat", micro_heartbeat.start),
        ]:
            try:
                await starter()
            except Exception as e:
                log.warning(f"{name} start failed", error=str(e))

        if accumulation_ladder is not None:
            try:
                await accumulation_ladder.start()
            except Exception as e:
                log.warning("accumulation start failed", error=str(e))
        if btc_accumulation is not None:
            try:
                await btc_accumulation.start()
            except Exception as e:
                log.warning("btc accumulation start failed", error=str(e))

        asyncio.create_task(start_discord_bot(), name="discord_bot")
        log.info("Discord bot task scheduled (DM-only alerts)")
        try:
            from app.services.paper_journal import paper_journal

            session_info = paper_journal.bootstrap_session()
            log.info("paper session bootstrap", **{k: session_info.get(k) for k in ("created", "session_id", "started_at", "prior_closed_archived")})
            if session_info.get("created"):
                asyncio.create_task(_announce_session(session_info), name="paper_session_announce")
        except Exception as e:
            log.warning("paper session bootstrap failed", error=str(e)[:200])
        try:
            from app.investment.scan import start_investment_scanner

            await start_investment_scanner()
        except Exception as e:
            log.warning("investment scanner start failed; trading continues", error=str(e)[:200])
        log.info("Background services booted")

    boot_task = asyncio.create_task(_boot_services(), name="atlas_boot")
    log.info("API is serving /health; services starting in background")

    yield

    log.info("Project Atlas shutting down")
    if not boot_task.done():
        boot_task.cancel()
        try:
            await boot_task
        except (asyncio.CancelledError, Exception):
            pass
    try:
        from app.investment.scan import stop_investment_scanner

        await stop_investment_scanner()
    except Exception:
        pass
    try:
        await stop_discord_bot()
    except Exception:
        pass
    for name, stopper in [
        ("micro_heartbeat", micro_heartbeat.stop),
        ("daily_paper_recap", daily_paper_recap.stop),
        ("perp_micro_coach", perp_micro_coach.stop),
        ("command_center", command_center.stop),
        ("robinhood_brief", robinhood_brief_service.stop),
        ("day_trade", day_trade_assistant.stop),
        ("quality_dip", quality_dip_scanner.stop),
        ("weekly_summary", weekly_summary_service.stop),
        ("paper_trade_tracker", paper_trade_tracker.stop),
        ("opportunity_tracker", opportunity_tracker.stop),
        ("scanner", scanner.stop),
    ]:
        try:
            await stopper()
        except Exception as e:
            log.warning(f"{name} stop failed", error=str(e))

    if accumulation_ladder is not None:
        try:
            await accumulation_ladder.stop()
        except Exception:
            pass
    if btc_accumulation is not None:
        try:
            await btc_accumulation.stop()
        except Exception:
            pass

    try:
        await close_redis()
    except Exception:
        pass
    try:
        await engine.dispose()
    except Exception:
        pass
    log.info("Project Atlas shutdown complete")


app = FastAPI(title="Project Atlas", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(diagnostics_router)
app.include_router(performance_router)
app.include_router(live_router)
app.include_router(validation_router)

DASHBOARD_HTML = Path(__file__).resolve().parent / "static" / "dashboard.html"


@app.get("/dashboard")
async def dashboard_page() -> FileResponse:
    return FileResponse(DASHBOARD_HTML, media_type="text/html")


@app.get("/api/research")
async def api_research() -> Dict[str, Any]:
    from app.api.diagnostics import diagnostics_research

    return await diagnostics_research()


@app.get("/api/funnel")
async def api_funnel() -> Dict[str, Any]:
    from app.api.diagnostics import diagnostics_funnel

    return await diagnostics_funnel()


@app.get("/health")
async def health() -> Dict[str, Any]:
    settings = get_settings()
    redis_ok = "unknown"
    try:
        r = await get_redis_client()
        if r is not None:
            await r.ping()
            redis_ok = "ok"
        else:
            redis_ok = "missing"
    except Exception:
        redis_ok = "error"

    adapters: list[str] = []
    try:
        if hasattr(registry, "names") and callable(registry.names):
            adapters = list(registry.names())
        elif hasattr(registry, "adapters"):
            adapters = list(registry.adapters.keys())
        elif hasattr(registry, "_adapters"):
            adapters = list(registry._adapters.keys())
    except Exception:
        adapters = ["hyperliquid"]

    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.app_env,
        "redis": redis_ok,
        "adapters": adapters or ["hyperliquid"],
        "scanner_running": bool(getattr(scanner, "running", False)),
        "opportunity_tracker_running": bool(getattr(opportunity_tracker, "running", False)),
        "paper_trade_tracker_running": bool(getattr(paper_trade_tracker, "running", False)),
        "weekly_summary_running": bool(getattr(weekly_summary_service, "running", False)),
        "quality_dip_running": bool(getattr(quality_dip_scanner, "running", False)),
        "day_trade_running": bool(getattr(day_trade_assistant, "running", False)),
        "robinhood_brief_running": bool(getattr(robinhood_brief_service, "running", False)),
        "command_center_running": bool(getattr(command_center, "running", False)),
        "perp_micro_running": bool(getattr(perp_micro_coach, "running", False)),
        "daily_paper_recap_running": bool(getattr(daily_paper_recap, "running", False)),
        "micro_heartbeat_running": bool(getattr(micro_heartbeat, "running", False)),
        "discord_ready": is_discord_ready(),
        "perp_allowlist_enabled": bool(settings.perp_allowlist_enabled),
        "liquid_count": int(getattr(perp_micro_coach, "liquid_count", 0) or 0),
    }


@app.get("/")
async def root() -> Dict[str, str]:
    return {
        "service": "Project Atlas",
        "docs": "/docs",
        "health": "/health",
        "dashboard": "/dashboard",
        "diagnostics": "/diagnostics/paper",
        "research": "/api/research",
        "funnel": "/api/funnel",
    }
