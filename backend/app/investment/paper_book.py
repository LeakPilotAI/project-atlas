"""Simulated long-term book. Separate from Hyperliquid paper. No real orders."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from app.investment.allocation import money
from app.investment.models import AllocationPlan, PaperInvestmentAccount
from app.investment.storage import LEDGER_PATH, PAPER_STATE_PATH, ensure_dirs


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PaperPosition:
    symbol: str
    shares: float = 0.0
    avg_cost: float = 0.0
    market_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.shares * self.market_price

    @property
    def cost_basis(self) -> float:
        return self.shares * self.avg_cost

    @property
    def unrealized(self) -> float:
        return self.market_value - self.cost_basis


@dataclass
class PaperOrder:
    order_id: str
    symbol: str
    limit_price: float
    shares: float
    status: str = "OPEN"  # OPEN · FILLED · CANCELLED
    filled_shares: float = 0.0
    filled_price: Optional[float] = None


@dataclass
class Benchmark:
    symbol: str = "SPY"
    shares: float = 0.0
    start_price: float = 0.0
    start_value: float = 0.0

    def value(self, last: Optional[float]) -> Optional[float]:
        if last is None or self.shares <= 0:
            return None
        return self.shares * last


class PaperBook:
    def __init__(
        self,
        *,
        cash: float = 0.0,
        benchmark_symbol: str = "SPY",
        state_path: Optional[Path] = None,
        ledger_path: Optional[Path] = None,
    ) -> None:
        self.cash = float(cash)
        self.positions: Dict[str, PaperPosition] = {}
        self.orders: List[PaperOrder] = []
        self.fills: List[dict] = []
        self.realized_pnl = 0.0
        self.peak_equity = float(cash)
        self.benchmark = Benchmark(symbol=benchmark_symbol)
        self.state_path = state_path if state_path is not None else PAPER_STATE_PATH
        self.ledger_path = ledger_path if ledger_path is not None else LEDGER_PATH

    def research_buy(
        self,
        symbol: str,
        price: float,
        usd: float,
        *,
        reason: str = "",
        seed_cash: float = 10_000.0,
    ) -> Optional[dict]:
        """Simulated market buy. Stocks/ETFs only. Never a brokerage order."""
        symbol = symbol.upper()
        price = float(price)
        usd = float(usd)
        if price <= 0 or usd <= 0:
            return None
        if symbol in self.positions and self.positions[symbol].shares > 0:
            return None
        if self.cash <= 0 and not self.positions:
            self.cash = float(seed_cash)
        shares = usd / price
        cost = shares * price
        if cost > self.cash + 1e-9:
            shares = self.cash / price
            cost = shares * price
        if shares <= 0 or cost <= 0:
            return None
        self.cash = float(money(Decimal(str(self.cash)) - Decimal(str(cost))))
        pos = self.positions.get(symbol) or PaperPosition(symbol=symbol)
        new_shares = pos.shares + shares
        pos.avg_cost = (pos.cost_basis + cost) / new_shares if new_shares else price
        pos.shares = new_shares
        pos.market_price = price
        self.positions[symbol] = pos
        row = {
            "symbol": symbol,
            "shares": shares,
            "price": price,
            "usd": cost,
            "reason": reason,
            "session": "RESEARCH_PAPER",
            "at": _now().isoformat(),
        }
        self.fills.append(row)
        self._ledger("research_buy", row)
        self._touch_peak()
        self.save()
        return row

    def execute_broker_order(self, *_a, **_k) -> None:
        raise RuntimeError("No real brokerage execution. Investment engine is research/paper only.")

    def equity(self) -> float:
        return self.cash + sum(p.market_value for p in self.positions.values())

    def invested(self) -> float:
        return sum(p.market_value for p in self.positions.values())

    def unrealized_pnl(self) -> float:
        return sum(p.unrealized for p in self.positions.values())

    def drawdown(self) -> float:
        eq = self.equity()
        if self.peak_equity <= 0:
            return 0.0
        return min(0.0, eq / self.peak_equity - 1.0)

    def seed_benchmark(self, price: float) -> None:
        if price <= 0 or self.benchmark.shares > 0:
            return
        eq = self.equity()
        self.benchmark.start_price = float(price)
        self.benchmark.start_value = eq
        self.benchmark.shares = eq / float(price) if price else 0.0

    def submit_from_plan(self, plan: AllocationPlan) -> List[PaperOrder]:
        created: List[PaperOrder] = []
        if not plan.is_actionable():
            return created
        for t in plan.tiers:
            if not t.price or not t.share_quantity or t.share_quantity <= 0:
                continue
            o = PaperOrder(
                order_id=uuid4().hex[:12],
                symbol=plan.symbol,
                limit_price=float(t.price),
                shares=float(t.share_quantity),
            )
            self.orders.append(o)
            created.append(o)
            self._ledger("order", {"order_id": o.order_id, "symbol": o.symbol, "limit": o.limit_price, "shares": o.shares})
        self.save()
        return created

    def cancel_open(self, symbol: str, *, reason: str = "") -> int:
        n = 0
        for o in self.orders:
            if o.symbol == symbol and o.status == "OPEN":
                o.status = "CANCELLED"
                n += 1
        if n:
            self._ledger("cancel", {"symbol": symbol, "count": n, "reason": reason})
            self.save()
        return n

    def try_fill(self, symbol: str, market_price: float, *, session: str) -> List[dict]:
        """Fill open limits only while the cash session is open. Never invent weekend prints."""
        if session != "MARKET_OPEN":
            return []
        if market_price <= 0:
            return []
        filled: List[dict] = []
        for o in self.orders:
            if o.symbol != symbol or o.status != "OPEN":
                continue
            if market_price > o.limit_price + 1e-12:
                continue
            cost = o.shares * o.limit_price
            if cost > self.cash + 1e-9:
                continue
            self.cash = float(money(Decimal(str(self.cash)) - Decimal(str(cost))))
            pos = self.positions.get(symbol) or PaperPosition(symbol=symbol)
            new_shares = pos.shares + o.shares
            if new_shares > 0:
                pos.avg_cost = (pos.cost_basis + cost) / new_shares
            pos.shares = new_shares
            pos.market_price = market_price
            self.positions[symbol] = pos
            o.status = "FILLED"
            o.filled_shares = o.shares
            o.filled_price = o.limit_price
            row = {
                "order_id": o.order_id,
                "symbol": symbol,
                "shares": o.shares,
                "price": o.limit_price,
                "session": session,
                "at": _now().isoformat(),
            }
            self.fills.append(row)
            filled.append(row)
            self._ledger("fill", row)
        if filled:
            self._touch_peak()
            self.save()
        return filled

    def mark(self, prices: Dict[str, float]) -> None:
        for sym, px in prices.items():
            if sym in self.positions and px and px > 0:
                self.positions[sym].market_price = float(px)
        self._touch_peak()
        self.save()

    def _touch_peak(self) -> None:
        eq = self.equity()
        if eq > self.peak_equity:
            self.peak_equity = eq

    def snapshot(self, *, spy_price: Optional[float] = None) -> dict:
        bmv = self.benchmark.value(spy_price)
        return {
            "cash": self.cash,
            "invested": self.invested(),
            "portfolio_value": self.equity(),
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl(),
            "drawdown": self.drawdown(),
            "benchmark": self.benchmark.symbol,
            "benchmark_value": bmv,
            "positions": {
                s: {"shares": p.shares, "avg_cost": p.avg_cost, "market_price": p.market_price, "value": p.market_value}
                for s, p in self.positions.items()
            },
            "open_orders": sum(1 for o in self.orders if o.status == "OPEN"),
            "disclaimer": "Paper investment book. Not Hyperliquid paper. Not a live brokerage account. No alpha claim.",
        }

    def as_legacy_account(self) -> PaperInvestmentAccount:
        return PaperInvestmentAccount(
            cash=self.cash,
            shares={s: p.shares for s, p in self.positions.items()},
            orders=[o.__dict__ for o in self.orders],
            fills=list(self.fills),
            portfolio_value=self.equity(),
            realized_pnl=self.realized_pnl,
            unrealized_pnl=self.unrealized_pnl(),
            drawdown=self.drawdown(),
            benchmark=self.benchmark.symbol,
        )

    def _ledger(self, kind: str, payload: dict) -> None:
        if self.ledger_path is None:
            return
        ensure_dirs()
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        row = {"kind": kind, "at": _now().isoformat(), **payload}
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")

    def save(self) -> None:
        if self.state_path is None:
            return
        ensure_dirs()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "cash": self.cash,
            "realized_pnl": self.realized_pnl,
            "peak_equity": self.peak_equity,
            "positions": {s: p.__dict__ for s, p in self.positions.items()},
            "orders": [o.__dict__ for o in self.orders],
            "fills": self.fills,
            "benchmark": self.benchmark.__dict__,
        }
        self.state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Optional[Path] = None, **kwargs) -> "PaperBook":
        p = path if path is not None else PAPER_STATE_PATH
        book = cls(state_path=p, **kwargs)
        if not p.exists():
            return book
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return book
        book.cash = float(data.get("cash") or 0)
        book.realized_pnl = float(data.get("realized_pnl") or 0)
        book.peak_equity = float(data.get("peak_equity") or book.cash)
        for s, row in (data.get("positions") or {}).items():
            book.positions[s] = PaperPosition(**row)
        for row in data.get("orders") or []:
            book.orders.append(PaperOrder(**row))
        book.fills = list(data.get("fills") or [])
        b = data.get("benchmark") or {}
        book.benchmark = Benchmark(
            symbol=str(b.get("symbol") or "SPY"),
            shares=float(b.get("shares") or 0),
            start_price=float(b.get("start_price") or 0),
            start_value=float(b.get("start_value") or 0),
        )
        return book
