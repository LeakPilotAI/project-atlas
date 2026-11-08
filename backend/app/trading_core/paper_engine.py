from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from .models import (
    ExitReason,
    MarketQuote,
    PaperExecutionConfig,
    PaperPosition,
    PositionStatus,
    Side,
    TradeIntent,
)


@dataclass(frozen=True)
class EngineStep:
    position: PaperPosition
    event: str


class PaperEngine:
    """Pure deterministic paper execution.

    No networking, storage, clocks, randomness, or global mutable state. The same
    TradeIntent + quote sequence always produces the same position history.
    """

    def __init__(self, config: PaperExecutionConfig | None = None) -> None:
        self.config = config or PaperExecutionConfig()

    @staticmethod
    def _slip(price: float, side: Side, bps: float, *, entry: bool) -> float:
        # Adverse slippage: LONG entry/SHORT exit pay up; SHORT entry/LONG exit sell lower.
        direction = side.direction
        sign = direction if entry else -direction
        return price * (1.0 + sign * bps / 10_000.0)

    def open(self, intent: TradeIntent, quote: MarketQuote) -> PaperPosition:
        if quote.symbol.upper() != intent.symbol.upper():
            raise ValueError("quote symbol does not match intent")
        if quote.timestamp < intent.signal_timestamp:
            raise ValueError("entry quote predates signal")

        entry = self._slip(
            quote.price,
            intent.side,
            self.config.entry_slippage_bps,
            entry=True,
        )
        risk_price = abs(entry - intent.stop_price)
        if risk_price <= 0:
            raise ValueError("entry and stop produce zero risk")
        if intent.side is Side.LONG and intent.stop_price >= entry:
            raise ValueError("LONG stop must remain below slipped entry")
        if intent.side is Side.SHORT and intent.stop_price <= entry:
            raise ValueError("SHORT stop must remain above slipped entry")

        quantity = intent.risk_usd / risk_price
        target = entry + intent.side.direction * risk_price * intent.target_r
        return PaperPosition(
            trade_id=intent.trade_id,
            symbol=intent.symbol.upper(),
            side=intent.side,
            strategy_version=intent.strategy_version,
            opened_at=quote.timestamp,
            signal_price=intent.signal_price,
            entry_price=entry,
            initial_stop=intent.stop_price,
            working_stop=intent.stop_price,
            target_price=target,
            target_r=intent.target_r,
            risk_price=risk_price,
            risk_usd=intent.risk_usd,
            quantity=quantity,
            last_price=quote.price,
            last_timestamp=quote.timestamp,
        )

    def mark(self, position: PaperPosition, quote: MarketQuote) -> EngineStep:
        if not position.is_open:
            return EngineStep(position=position, event="ALREADY_CLOSED")
        if quote.symbol.upper() != position.symbol.upper():
            raise ValueError("quote symbol does not match position")
        if position.last_timestamp is not None and quote.timestamp < position.last_timestamp:
            raise ValueError("quotes must be chronological")

        signed_move = position.side.direction * (quote.price - position.entry_price)
        current_r = signed_move / position.risk_price
        mfe_r = max(position.mfe_r, current_r)
        mae_r = max(position.mae_r, -current_r)

        working_stop = position.working_stop
        be_armed = position.be_armed
        lock_armed = position.lock_armed

        if self.config.breakeven_after_r is not None and mfe_r >= self.config.breakeven_after_r:
            be_armed = True
            if position.side is Side.LONG:
                working_stop = max(working_stop, position.entry_price)
            else:
                working_stop = min(working_stop, position.entry_price)

        if self.config.lock_after_r is not None and mfe_r >= self.config.lock_after_r:
            lock_armed = True
            locked = position.entry_price + position.side.direction * position.risk_price * self.config.lock_r
            if position.side is Side.LONG:
                working_stop = max(working_stop, locked)
            else:
                working_stop = min(working_stop, locked)

        updated = position.evolve(
            mfe_r=mfe_r,
            mae_r=mae_r,
            working_stop=working_stop,
            be_armed=be_armed,
            lock_armed=lock_armed,
            last_price=quote.price,
            last_timestamp=quote.timestamp,
        )

        stop_hit = quote.price <= working_stop if position.side is Side.LONG else quote.price >= working_stop
        target_hit = quote.price >= position.target_price if position.side is Side.LONG else quote.price <= position.target_price

        # With mark-only data a single quote cannot honestly establish intrabar order.
        # If both conditions are somehow true due to invalid geometry, fail closed.
        if stop_hit and target_hit:
            raise RuntimeError("ambiguous stop/target geometry")
        if stop_hit:
            reason = ExitReason.LOCKED_STOP if lock_armed else (ExitReason.BREAKEVEN if be_armed else ExitReason.STOP)
            return EngineStep(position=self._close(updated, quote, reason, working_stop), event=reason.value)
        if target_hit:
            return EngineStep(position=self._close(updated, quote, ExitReason.TARGET, position.target_price), event="TARGET")
        return EngineStep(position=updated, event="MARK")

    def _close(
        self,
        position: PaperPosition,
        quote: MarketQuote,
        reason: ExitReason,
        trigger_price: float,
    ) -> PaperPosition:
        exit_fill = self._slip(
            trigger_price,
            position.side,
            self.config.exit_slippage_bps,
            entry=False,
        )
        gross_pnl = position.side.direction * (exit_fill - position.entry_price) * position.quantity
        gross_r = gross_pnl / position.risk_usd
        entry_notional = position.entry_price * position.quantity
        exit_notional = exit_fill * position.quantity
        fees = (entry_notional + exit_notional) * self.config.fee_bps_per_side / 10_000.0
        net_r = (gross_pnl - fees) / position.risk_usd
        return position.evolve(
            status=PositionStatus.CLOSED,
            closed_at=quote.timestamp,
            exit_price=exit_fill,
            exit_reason=reason,
            gross_r=gross_r,
            net_r=net_r,
            fees_usd=fees,
            last_price=quote.price,
            last_timestamp=quote.timestamp,
        )

    def replay(self, intent: TradeIntent, quotes: Iterable[MarketQuote]) -> List[EngineStep]:
        seq = list(quotes)
        if not seq:
            raise ValueError("replay requires at least one quote")
        pos = self.open(intent, seq[0])
        out = [EngineStep(position=pos, event="OPEN")]
        for quote in seq[1:]:
            step = self.mark(pos, quote)
            out.append(step)
            pos = step.position
            if not pos.is_open:
                break
        return out
