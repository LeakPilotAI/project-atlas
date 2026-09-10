from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.adapters.registry import registry
from app.core.logging import get_logger
from app.trading_core.perp_manual_planner import build_manual_perp_plan

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
        for t in tickers:
            symbol = str(getattr(t, "symbol", "") or "").upper()
            price = float(getattr(t, "price", 0.0) or 0.0)
            vol = float(getattr(t, "volume_24h", 0.0) or 0.0)
            oi = float(getattr(t, "open_interest", 0.0) or 0.0)
            funding = getattr(t, "funding_rate", None)
            if not symbol or price <= 0:
                continue
            rows.append({
                "symbol": symbol,
                "price": price,
                "volume_24h": vol,
                "open_interest": oi,
                "funding_rate": funding,
            })

        rows.sort(key=lambda r: (float(r["volume_24h"]), float(r["open_interest"])), reverse=True)
        now = datetime.now(timezone.utc).isoformat()
        self.last_snapshot = {
            "source": "hyperliquid",
            "mode": "MANUAL_ONLY",
            "updated_at": now,
            "market_count": len(rows),
            "markets": rows,
            "plans": list(self.last_snapshot.get("plans") or []),
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
        markets = self.last_snapshot.get("markets") or []
        live_universe = [str(r.get("symbol") or "") for r in markets]
        plan = build_manual_perp_plan(
            symbol=symbol,
            side=side,
            reference_price=reference_price,
            live_universe=live_universe,
            risk_pct=risk_pct,
            layer_spacing_pct=layer_spacing_pct,
            tp1_r=tp1_r,
            tp2_r=tp2_r,
        )
        out = asdict(plan)
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
