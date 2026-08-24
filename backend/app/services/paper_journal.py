"""Persist paper TRIGGER / TP / STOP rows + query helpers for /paper and recaps."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import desc, select

from app.db.session import AsyncSessionLocal
from app.models.paper_trade import PaperTrade

log = structlog.get_logger(__name__)


def _uid() -> str:
    return uuid.uuid4().hex[:12]


class PaperJournal:
    async def open_trade(
        self,
        *,
        symbol: str,
        side: str,
        entry: float,
        stop: Optional[float],
        tp1: Optional[float],
        tp2: Optional[float] = None,
        risk_usd: float = 1.0,
        regime: Optional[str] = None,
        notes: Optional[str] = None,
        source: str = "perp_micro",
        trade_id: Optional[str] = None,
    ) -> str:
        tid = trade_id or _uid()
        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            row = PaperTrade(
                trade_id=tid,
                symbol=symbol.upper(),
                side=side.upper(),
                status="OPEN",
                entry=float(entry),
                stop=float(stop) if stop is not None else None,
                tp1=float(tp1) if tp1 is not None else None,
                tp2=float(tp2) if tp2 is not None else None,
                risk_usd=float(risk_usd),
                regime=regime,
                notes=notes,
                source=source,
                opened_at=now,
            )
            session.add(row)
            await session.commit()
        log.info("Paper journal OPEN", trade_id=tid, symbol=symbol, side=side, entry=entry)
        return tid

    async def close_trade(
        self,
        trade_id: str,
        *,
        exit_price: float,
        result: str,
        pnl_r: float,
        pnl_usd: Optional[float] = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            q = await session.execute(
                select(PaperTrade).where(PaperTrade.trade_id == trade_id)
            )
            row = q.scalar_one_or_none()
            if row is None:
                log.warning("Paper journal close miss", trade_id=trade_id)
                return
            row.status = "CLOSED"
            row.exit_price = float(exit_price)
            row.result = result.upper()
            row.pnl_r = float(pnl_r)
            row.pnl_usd = float(pnl_usd) if pnl_usd is not None else float(pnl_r) * float(row.risk_usd)
            row.closed_at = now
            await session.commit()
        log.info(
            "Paper journal CLOSE",
            trade_id=trade_id,
            result=result,
            pnl_r=pnl_r,
        )

    async def list_open(self, limit: int = 20) -> List[Dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            q = await session.execute(
                select(PaperTrade)
                .where(PaperTrade.status == "OPEN")
                .order_by(desc(PaperTrade.opened_at))
                .limit(limit)
            )
            rows = q.scalars().all()
        return [self._to_dict(r) for r in rows]

    async def list_closed(self, limit: int = 30) -> List[Dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            q = await session.execute(
                select(PaperTrade)
                .where(PaperTrade.status == "CLOSED")
                .order_by(desc(PaperTrade.closed_at))
                .limit(limit)
            )
            rows = q.scalars().all()
        return [self._to_dict(r) for r in rows]

    async def stats(self) -> Dict[str, Any]:
        async with AsyncSessionLocal() as session:
            closed_q = await session.execute(
                select(PaperTrade).where(PaperTrade.status == "CLOSED")
            )
            closed = list(closed_q.scalars().all())
            open_q = await session.execute(
                select(PaperTrade).where(PaperTrade.status == "OPEN")
            )
            opens = list(open_q.scalars().all())

        wins = [t for t in closed if (t.pnl_r or 0) > 0]
        losses = [t for t in closed if (t.pnl_r or 0) <= 0]
        sum_r = sum(float(t.pnl_r or 0) for t in closed)
        n = len(closed)
        wr = (len(wins) / n * 100.0) if n else 0.0
        return {
            "wins": len(wins),
            "losses": len(losses),
            "closed": n,
            "open": len(opens),
            "win_rate_pct": round(wr, 1),
            "sum_r": round(sum_r, 2),
        }

    async def stats_since(self, since: datetime) -> Dict[str, Any]:
        async with AsyncSessionLocal() as session:
            q = await session.execute(
                select(PaperTrade).where(
                    PaperTrade.status == "CLOSED",
                    PaperTrade.closed_at >= since,
                )
            )
            closed = list(q.scalars().all())
            oq = await session.execute(
                select(PaperTrade).where(PaperTrade.status == "OPEN")
            )
            opens = list(oq.scalars().all())
        wins = [t for t in closed if (t.pnl_r or 0) > 0]
        losses = [t for t in closed if (t.pnl_r or 0) <= 0]
        sum_r = sum(float(t.pnl_r or 0) for t in closed)
        n = len(closed)
        wr = (len(wins) / n * 100.0) if n else 0.0
        return {
            "wins": len(wins),
            "losses": len(losses),
            "closed": n,
            "open": len(opens),
            "win_rate_pct": round(wr, 1),
            "sum_r": round(sum_r, 2),
            "trades": [self._to_dict(t) for t in closed[-10:]],
        }

    @staticmethod
    def _to_dict(r: PaperTrade) -> Dict[str, Any]:
        return {
            "id": r.trade_id,
            "symbol": r.symbol,
            "side": r.side,
            "status": r.status,
            "entry": r.entry,
            "stop": r.stop,
            "tp1": r.tp1,
            "tp2": r.tp2,
            "exit_price": r.exit_price,
            "pnl_r": r.pnl_r,
            "pnl_usd": r.pnl_usd,
            "result": r.result,
            "regime": r.regime,
            "opened_at": r.opened_at.isoformat() if r.opened_at else None,
            "closed_at": r.closed_at.isoformat() if r.closed_at else None,
        }


paper_journal = PaperJournal()