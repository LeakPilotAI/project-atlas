from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.adapters.registry import registry
from app.core.logging import get_logger
from app.trading_core.models import Side
from app.trading_core.perp_manual_planner import build_manual_perp_plan
from app.trading_core.perp_setup_state import classify_setup_state

log = get_logger("perp_manual")


class PerpManualService:
    """Read-only manual perp planner sourced strictly from Hyperliquid.

    No brokerage/exchange orders are placed. Atlas only publishes a manual plan for
    symbols that are present in the live Hyperliquid universe exposed by the adapter.
    """

    def __init__(self) -> None:
        self.running = False
        self.last_error: Optional[str] = None
        self.last_refresh_at: Optional[str] = None
        self.last_snapshot: Dict[str, Any] = {
            "source": "hyperliquid",
            "mode": "MANUAL_ONLY",
            "markets": [],
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
                )
                plan["mark"] = mark
                plan["state"] = state.state.value
                plan["next_action"] = state.next_action
                plan["distance_to_l1_pct"] = round(float(state.distance_to_l1_pct), 4)
            except Exception as e:
                plan["state"] = "WAIT"
                plan["next_action"] = f"State unavailable: {str(e)[:120]}"
                plan["mark"] = mark

        now = datetime.now(timezone.utc).isoformat()
        self.last_snapshot = {
            "source": "hyperliquid",
            "mode": "MANUAL_ONLY",
            "updated_at": now,
            "market_count": len(rows),
            "markets": rows,
            "plans": plans,
            "note": "Hyperliquid markets only. Atlas never places orders.",
        }
        self.last_refresh_at = now
        self.last_error = None
        return self.snapshot()

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
        self.last_snapshot["plans"] = plans[:50]
        return out

    def snapshot(self) -> Dict[str, Any]:
        return {
            **self.last_snapshot,
            "running": self.running,
            "last_refresh_at": self.last_refresh_at,
            "last_error": self.last_error,
        }


perp_manual_service = PerpManualService()
