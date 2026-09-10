from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.adapters.registry import registry
from app.core.logging import get_logger
from app.trading_core.models import Side
from app.trading_core.perp_discovery import analyze_candles, rank_setup, shortlist_markets
from app.trading_core.perp_manual_planner import build_manual_perp_plan
from app.trading_core.perp_manual_trade_lifecycle import close_plan, enter_setup
from app.trading_core.perp_setup_lifecycle import reconcile_setups
from app.trading_core.perp_setup_state import classify_setup_state

log = get_logger("perp_manual")


class PerpManualService:
    """Read-only/manual Hyperliquid planning and lifecycle service.

    Atlas never places brokerage/exchange orders. Entry/close state is changed only
    by explicit user/API lifecycle actions; price movement alone cannot invent a fill.
    """

    def __init__(self) -> None:
        self.running = False
        self.last_error: Optional[str] = None
        self.last_refresh_at: Optional[str] = None
        self.last_snapshot: Dict[str, Any] = {
            "source": "hyperliquid",
            "mode": "MANUAL_ONLY",
            "markets": [],
            "setups": [],
            "plans": [],
        }
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._loop(), name="perp_manual_service")
        log.info("Manual Hyperliquid perp planner started")

    async def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log.info("Manual Hyperliquid perp planner stopped")

    def _adapter(self):
        try:
            if hasattr(registry, "get"):
                return registry.get("hyperliquid")
        except Exception:
            pass
        for attr in ("adapters", "_adapters"):
            try:
                mapping = getattr(registry, attr)
                if isinstance(mapping, dict) and "hyperliquid" in mapping:
                    return mapping["hyperliquid"]
            except Exception:
                pass
        return None

    async def _loop(self) -> None:
        await asyncio.sleep(3)
        while self.running:
            try:
                await self.refresh()
            except Exception as e:
                self.last_error = f"{type(e).__name__}: {str(e)[:180]}"
                log.warning("Manual perp refresh failed", error=self.last_error)
            await asyncio.sleep(20)

    async def _discover_setups(
        self,
        adapter: Any,
        rows: list[Dict[str, Any]],
        live_universe: list[str],
    ) -> list[Dict[str, Any]]:
        if not hasattr(adapter, "get_candles"):
            return []

        candidates = shortlist_markets(rows, limit=8)

        async def inspect(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            symbol = str(row["symbol"])
            try:
                candles = await adapter.get_candles(symbol, interval="5m", lookback=48)
                structure = analyze_candles(candles)
                ranked = rank_setup(
                    symbol=symbol,
                    price=float(row["price"]),
                    volume_24h=float(row.get("volume_24h") or 0.0),
                    open_interest=float(row.get("open_interest") or 0.0),
                    funding_rate=row.get("funding_rate"),
                    structure=structure,
                )
                if ranked is None:
                    return None
                plan = build_manual_perp_plan(
                    symbol=ranked.symbol,
                    side=ranked.side,
                    reference_price=ranked.price,
                    hyperliquid_symbols=live_universe,
                    volatility_pct=max(0.15, ranked.volatility_pct),
                    target_rr=1.8,
                    secondary_rr=3.0,
                )
                state = classify_setup_state(
                    side=ranked.side,
                    mark=ranked.price,
                    l1=plan.l1,
                    l2=plan.l2,
                    l3=plan.l3,
                    stop=plan.stop,
                    tp1=plan.tp1,
                    tp2=plan.tp2,
                )
                out = asdict(ranked)
                out["side"] = ranked.side.value
                out["state"] = state.state.value
                out["next_action"] = state.next_action
                out["distance_to_l1_pct"] = round(float(state.distance_to_l1_pct), 4)
                out["levels"] = {
                    "l1": plan.l1,
                    "l2": plan.l2,
                    "l3": plan.l3,
                    "stop": plan.stop,
                    "tp1": plan.tp1,
                    "tp2": plan.tp2,
                    "target_rr": plan.target_rr,
                }
                return out
            except Exception as e:
                log.debug("Manual perp discovery symbol skipped", symbol=symbol, error=str(e)[:120])
                return None

        inspected = await asyncio.gather(*(inspect(row) for row in candidates))
        setups = [s for s in inspected if s is not None]
        setups.sort(key=lambda s: float(s.get("score") or 0.0), reverse=True)
        return setups[:8]

    async def refresh(self) -> Dict[str, Any]:
        adapter = self._adapter()
        if adapter is None:
            raise RuntimeError("Hyperliquid adapter unavailable")

        tickers = await adapter.get_all_tickers()
        live_universe = list(adapter.universe_names())
        if not live_universe:
            live_universe = [str(getattr(t, "symbol", "")) for t in tickers if getattr(t, "symbol", None)]

        rows = []
        price_map: Dict[str, float] = {}
        for t in tickers:
            symbol = str(getattr(t, "symbol", "") or "").upper()
            price = float(getattr(t, "price", 0.0) or 0.0)
            vol = float(getattr(t, "volume_24h", 0.0) or 0.0)
            oi = float(getattr(t, "open_interest", 0.0) or 0.0)
            funding = getattr(t, "funding_rate", None)
            if not symbol or price <= 0:
                continue
            price_map[symbol] = price
            rows.append({
                "symbol": symbol,
                "price": price,
                "volume_24h": vol,
                "open_interest": oi,
                "funding_rate": funding,
            })

        rows.sort(key=lambda r: (float(r["volume_24h"]), float(r["open_interest"])), reverse=True)
        plans = list(self.last_snapshot.get("plans") or [])
        for plan in plans:
            if str(plan.get("status") or "").upper() == "CLOSED":
                continue
            mark = price_map.get(str(plan.get("symbol") or "").upper())
            if mark is None:
                plan["state"] = "WAIT"
                plan["next_action"] = "No current Hyperliquid mark; wait for fresh data."
                plan["mark"] = None
                continue
            try:
                side_enum = Side[str(plan.get("side") or "").upper()]
                state = classify_setup_state(
                    side=side_enum,
                    mark=mark,
                    l1=float(plan["l1"]),
                    l2=float(plan["l2"]),
                    l3=float(plan["l3"]),
                    stop=float(plan["stop"]),
                    tp1=float(plan["tp1"]),
                    tp2=float(plan["tp2"]),
                    entered=bool(plan.get("entered", False)),
                )
                plan["mark"] = mark
                plan["state"] = state.state.value
                plan["next_action"] = state.next_action
                plan["distance_to_l1_pct"] = round(float(state.distance_to_l1_pct), 4)
            except Exception as e:
                plan["state"] = "WAIT"
                plan["next_action"] = f"State unavailable: {str(e)[:120]}"
                plan["mark"] = mark

        raw_setups = await self._discover_setups(adapter, rows, live_universe)
        now_dt = datetime.now(timezone.utc)
        setups = reconcile_setups(
            raw_setups,
            previous=list(self.last_snapshot.get("setups") or []),
            now=now_dt,
            cooldown_minutes=30,
        )
        setups.sort(
            key=lambda s: (
                bool(s.get("alert_eligible")),
                str(s.get("tier") or "") == "PRIME",
                float(s.get("score") or 0.0),
            ),
            reverse=True,
        )

        active_by_key = {
            str(p.get("setup_key") or ""): p
            for p in plans
            if str(p.get("status") or "").upper() == "ENTERED"
        }
        for setup in setups:
            active = active_by_key.get(str(setup.get("setup_key") or ""))
            setup["trade_status"] = "ENTERED" if active else "NOT_ENTERED"
            setup["entry_price"] = active.get("entry_price") if active else None
            setup["entered_at"] = active.get("entered_at") if active else None

        now = now_dt.isoformat()
        self.last_snapshot = {
            "source": "hyperliquid",
            "mode": "MANUAL_ONLY",
            "updated_at": now,
            "market_count": len(rows),
            "markets": rows,
            "setups": setups,
            "alert_candidates": [s for s in setups if bool(s.get("alert_eligible"))],
            "plans": plans,
            "note": "Hyperliquid markets only. Ranked setups are research guidance; Atlas never places orders.",
        }
        self.last_refresh_at = now
        self.last_error = None
        return self.snapshot()

    def acknowledge_alert(self, setup_key: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        changed = False
        for setup in self.last_snapshot.get("setups") or []:
            if str(setup.get("setup_key") or "") == str(setup_key):
                setup["last_alert_at"] = now
                setup["alert_eligible"] = False
                setup["alert_reason"] = "alert acknowledged; cooldown active"
                changed = True
        self.last_snapshot["alert_candidates"] = [
            s for s in self.last_snapshot.get("setups") or [] if bool(s.get("alert_eligible"))
        ]
        return changed

    def enter_discovered_setup(self, setup_key: str, *, fill_price: float | None = None) -> Dict[str, Any]:
        key = str(setup_key or "")
        setups = list(self.last_snapshot.get("setups") or [])
        setup = next((s for s in setups if str(s.get("setup_key") or "") == key), None)
        if setup is None:
            raise ValueError("manual perp setup not found")

        plans = list(self.last_snapshot.get("plans") or [])
        existing = next(
            (
                p
                for p in plans
                if str(p.get("setup_key") or "") == key
                and str(p.get("status") or "").upper() == "ENTERED"
            ),
            None,
        )
        if existing is not None:
            return dict(existing)

        plan = enter_setup(setup, fill_price=fill_price)
        plans = [
            p
            for p in plans
            if not (
                str(p.get("setup_key") or "") == key
                and str(p.get("status") or "").upper() != "CLOSED"
            )
        ]
        plans.insert(0, plan)
        self.last_snapshot["plans"] = plans[:100]
        setup["trade_status"] = "ENTERED"
        setup["entry_price"] = plan["entry_price"]
        setup["entered_at"] = plan["entered_at"]
        return dict(plan)

    def close_entered_plan(
        self,
        setup_key: str,
        *,
        exit_price: float,
        reason: str = "MANUAL_EXIT",
    ) -> Dict[str, Any]:
        key = str(setup_key or "")
        plans = list(self.last_snapshot.get("plans") or [])
        idx = next(
            (
                i
                for i, p in enumerate(plans)
                if str(p.get("setup_key") or "") == key
                and str(p.get("status") or "").upper() == "ENTERED"
            ),
            None,
        )
        if idx is None:
            raise ValueError("entered manual perp plan not found")
        closed = close_plan(plans[idx], exit_price=exit_price, reason=reason)
        plans[idx] = closed
        self.last_snapshot["plans"] = plans
        for setup in self.last_snapshot.get("setups") or []:
            if str(setup.get("setup_key") or "") == key:
                setup["trade_status"] = "CLOSED"
                setup["entry_price"] = closed.get("entry_price")
                setup["entered_at"] = closed.get("entered_at")
        return dict(closed)

    def create_plan(
        self,
        *,
        symbol: str,
        side: str,
        reference_price: float,
        risk_pct: float = 1.0,
        layer_spacing_pct: float = 0.35,
        tp1_r: float = 1.5,
        tp2_r: float = 2.5,
    ) -> Dict[str, Any]:
        if float(risk_pct) <= 0:
            raise ValueError("risk_pct must be positive")
        try:
            side_enum = Side[str(side).strip().upper()]
        except KeyError as exc:
            raise ValueError("side must be LONG or SHORT") from exc

        markets = self.last_snapshot.get("markets") or []
        live_universe = [str(r.get("symbol") or "") for r in markets]
        plan = build_manual_perp_plan(
            symbol=symbol,
            side=side_enum,
            reference_price=reference_price,
            hyperliquid_symbols=live_universe,
            layer_spacing_pct=layer_spacing_pct,
            target_rr=tp1_r,
            secondary_rr=tp2_r,
        )
        out = asdict(plan)
        out["side"] = plan.side.value
        out["risk_pct"] = float(risk_pct)
        out["tp2_rr"] = float(tp2_r)
        out["entered"] = False
        out["status"] = "PLANNED"
        out["setup_key"] = f"{out['symbol']}:{out['side']}"

        mark = None
        for row in markets:
            if str(row.get("symbol") or "").upper() == out["symbol"]:
                mark = float(row.get("price") or 0.0)
                break
        if mark and mark > 0:
            state = classify_setup_state(
                side=plan.side,
                mark=mark,
                l1=plan.l1,
                l2=plan.l2,
                l3=plan.l3,
                stop=plan.stop,
                tp1=plan.tp1,
                tp2=plan.tp2,
                entered=False,
            )
            out["mark"] = mark
            out["state"] = state.state.value
            out["next_action"] = state.next_action
            out["distance_to_l1_pct"] = round(float(state.distance_to_l1_pct), 4)
        else:
            out["mark"] = None
            out["state"] = "WAIT"
            out["next_action"] = "No current Hyperliquid mark; wait for fresh data."
            out["distance_to_l1_pct"] = None

        plans = list(self.last_snapshot.get("plans") or [])
        plans = [p for p in plans if not (p.get("symbol") == out["symbol"] and p.get("side") == out["side"])]
        plans.insert(0, out)
        self.last_snapshot["plans"] = plans[:100]
        return out

    def snapshot(self) -> Dict[str, Any]:
        return {
            **self.last_snapshot,
            "running": self.running,
            "last_refresh_at": self.last_refresh_at,
            "last_error": self.last_error,
        }


perp_manual_service = PerpManualService()
