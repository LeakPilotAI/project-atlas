from __future__ import annotations

from typing import Any, Dict

import structlog

from app.trading_core.live_shadow_hooks import mirror_marks_from_legacy, mirror_open_from_legacy

log = structlog.get_logger(__name__)


def on_paper_open(*, trade_id: str, symbol: str, side: str, entry: float, stop: float, setup_rr: float, risk_usd: float) -> None:
    try:
        mirror_open_from_legacy(
            trade_id=trade_id,
            symbol=symbol,
            side=side,
            price=float(entry),
            stop=float(stop),
            setup_rr=float(setup_rr),
            risk_usd=float(risk_usd),
        )
    except Exception as e:
        log.debug("v4 shadow open observer failed", trade_id=trade_id, error=str(e)[:160])


def on_paper_mark(*, symbol: str, mark: float) -> None:
    try:
        mirror_marks_from_legacy({str(symbol).upper(): float(mark)})
    except Exception as e:
        log.debug("v4 shadow mark observer failed", symbol=symbol, error=str(e)[:160])


def install_paper_journal_observer(journal: Any) -> bool:
    """Wrap one PaperJournal instance without changing legacy class behavior.

    Legacy persistence/execution always runs first. V4 receives PAPER opens and
    marks afterward on a best-effort basis. Repeated installation is idempotent.
    """
    if getattr(journal, "_atlas_v4_shadow_observer_installed", False):
        return False

    original_open = journal.open_trade
    original_mark = journal.update_excursion

    async def observed_open_trade(*args: Any, **kwargs: Any) -> str:
        trade_id = await original_open(*args, **kwargs)
        try:
            row: Dict[str, Any] = dict(getattr(journal, "_open", {}).get(trade_id) or {})
            if row and str(row.get("trade_type") or "PAPER").upper() == "PAPER":
                on_paper_open(
                    trade_id=str(trade_id),
                    symbol=str(row.get("symbol") or ""),
                    side=str(row.get("side") or ""),
                    entry=float(row.get("actual_entry_price")),
                    stop=float(row.get("initial_stop") or row.get("stop_price")),
                    setup_rr=float(row.get("setup_rr") or 1.8),
                    risk_usd=float(row.get("risk_dollars") or 1.0),
                )
        except Exception as e:
            log.debug("v4 shadow journal-open bridge failed", trade_id=trade_id, error=str(e)[:160])
        return trade_id

    def observed_update_excursion(trade_id: str, mark: float, *, force: bool = False) -> None:
        original_mark(trade_id, mark, force=force)
        try:
            row: Dict[str, Any] = dict(getattr(journal, "_open", {}).get(trade_id) or {})
            if row and str(row.get("trade_type") or "PAPER").upper() == "PAPER":
                on_paper_mark(symbol=str(row.get("symbol") or ""), mark=float(mark))
        except Exception as e:
            log.debug("v4 shadow journal-mark bridge failed", trade_id=trade_id, error=str(e)[:160])

    journal.open_trade = observed_open_trade
    journal.update_excursion = observed_update_excursion
    journal._atlas_v4_shadow_observer_installed = True
    return True
