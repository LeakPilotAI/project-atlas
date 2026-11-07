from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .models import MarketQuote, PaperExecutionConfig
from .persistent_runtime import PersistentPaperRuntime
from .runtime import LegacySignalAdapter


_DEFAULT_EVENT_PATH = Path(__file__).resolve().parents[2] / "data" / "trading_v4_shadow.jsonl"


class V4ShadowCoordinator:
    """Shadow-only bridge from legacy Atlas paper signals into the V4 runtime.

    This coordinator never creates legacy trades, changes legacy state, or places live
    orders. It mirrors accepted legacy paper opens into V4 and feeds the same live mark
    prices into V4 for deterministic side-by-side research.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _DEFAULT_EVENT_PATH
        self._runtime: Optional[PersistentPaperRuntime] = None
        self.last_error: Optional[str] = None
        self.last_open_at: Optional[str] = None
        self.last_mark_at: Optional[str] = None

    def _config(self) -> PaperExecutionConfig:
        from app.core.config import get_settings

        s = get_settings()
        return PaperExecutionConfig(
            entry_slippage_bps=1.0,
            exit_slippage_bps=1.0,
            fee_bps_per_side=2.0,
            breakeven_after_r=float(getattr(s, "perp_micro_be_after_r", 0.3)),
            lock_after_r=float(getattr(s, "perp_micro_lock_after_r", 0.5)),
            lock_r=float(getattr(s, "perp_micro_lock_r", 0.2)),
        )

    @property
    def runtime(self) -> PersistentPaperRuntime:
        if self._runtime is None:
            self._runtime = PersistentPaperRuntime(self.path, self._config())
        return self._runtime

    def recover(self) -> int:
        try:
            return self.runtime.recover()
        except Exception as e:
            self.last_error = f"recover: {type(e).__name__}: {str(e)[:180]}"
            return 0

    def mirror_legacy_open(self, row: Dict[str, Any], *, trade_id: str, price: float) -> bool:
        """Mirror one accepted legacy PAPER trade into V4 using the same trade_id."""
        try:
            payload = dict(row)
            payload["trade_id"] = trade_id
            intent = LegacySignalAdapter().to_intent(payload)
            quote = MarketQuote(
                symbol=intent.symbol,
                price=float(price),
                timestamp=datetime.now(timezone.utc),
            )
            self.runtime.open(intent, quote)
            self.last_open_at = quote.timestamp.isoformat()
            self.last_error = None
            return True
        except Exception as e:
            self.last_error = f"open: {type(e).__name__}: {str(e)[:180]}"
            return False

    def mark_prices(self, price_map: Dict[str, float]) -> int:
        """Feed current live marks into all open V4 shadow positions."""
        if not price_map:
            return 0
        now = datetime.now(timezone.utc)
        quotes = {
            str(symbol).upper(): MarketQuote(symbol=str(symbol).upper(), price=float(price), timestamp=now)
            for symbol, price in price_map.items()
            if float(price) > 0
        }
        try:
            updated = self.runtime.mark_many(quotes)
            if updated:
                self.last_mark_at = now.isoformat()
            self.last_error = None
            return len(updated)
        except Exception as e:
            self.last_error = f"mark: {type(e).__name__}: {str(e)[:180]}"
            return 0

    def snapshot(self) -> Dict[str, Any]:
        try:
            rt = self.runtime
            opens = rt.book.list_open()
            closed = rt.book.list_closed()
            return {
                "enabled": True,
                "mode": "SHADOW_ONLY",
                "event_path": str(self.path),
                "open": len(opens),
                "closed": len(closed),
                "recovered_open": len(opens),
                "last_open_at": self.last_open_at,
                "last_mark_at": self.last_mark_at,
                "last_error": self.last_error,
                "open_positions": [
                    {
                        "trade_id": p.trade_id,
                        "symbol": p.symbol,
                        "side": p.side.value,
                        "entry": p.entry_price,
                        "working_stop": p.working_stop,
                        "target": p.target_price,
                        "mfe_r": p.mfe_r,
                        "mae_r": p.mae_r,
                    }
                    for p in opens
                ],
                "closed_positions": [
                    {
                        "trade_id": p.trade_id,
                        "symbol": p.symbol,
                        "side": p.side.value,
                        "exit_reason": p.exit_reason.value if p.exit_reason else None,
                        "gross_r": p.gross_r,
                        "net_r": p.net_r,
                        "fees_usd": p.fees_usd,
                    }
                    for p in closed[-50:]
                ],
                "note": "Research only. V4 shadow cannot alter legacy paper state or place live orders.",
            }
        except Exception as e:
            return {
                "enabled": True,
                "mode": "SHADOW_ONLY",
                "open": 0,
                "closed": 0,
                "last_error": f"snapshot: {type(e).__name__}: {str(e)[:180]}",
            }


v4_shadow_coordinator = V4ShadowCoordinator()
