from __future__ import annotations

from functools import wraps
from typing import Any, Callable

import structlog

from app.services.v4_journal_observer import observe_paper_mark, observe_paper_open

log = structlog.get_logger(__name__)

_APPLIED_ATTR = "_atlas_v4_shadow_patch_applied"


def apply(paper_journal: Any) -> bool:
    """Install one-way V4 shadow observers on the legacy paper journal.

    The patch is intentionally fail-contained and idempotent. Legacy journal writes
    complete first; V4 observation happens afterward and can never change the legacy
    return value or raise into the caller.
    """
    if getattr(paper_journal, _APPLIED_ATTR, False):
        return False

    original_open: Callable[..., Any] = paper_journal.open_trade
    original_mark: Callable[..., Any] = paper_journal.update_excursion

    @wraps(original_open)
    async def open_trade_with_v4_shadow(*args: Any, **kwargs: Any) -> Any:
        trade_id = await original_open(*args, **kwargs)
        try:
            if str(kwargs.get("trade_type") or "PAPER").upper() == "PAPER" and trade_id:
                row = paper_journal._open.get(trade_id)
                if row:
                    observe_paper_open(row)
        except Exception as exc:
            log.warning("v4 shadow open observer failed", error=str(exc)[:160])
        return trade_id

    @wraps(original_mark)
    def update_excursion_with_v4_shadow(trade_id: str, mark: float, *args: Any, **kwargs: Any) -> Any:
        result = original_mark(trade_id, mark, *args, **kwargs)
        try:
            row = paper_journal._open.get(trade_id)
            if row and str(row.get("trade_type") or "PAPER").upper() == "PAPER":
                observe_paper_mark(row, mark)
        except Exception as exc:
            log.warning("v4 shadow mark observer failed", error=str(exc)[:160])
        return result

    paper_journal.open_trade = open_trade_with_v4_shadow
    paper_journal.update_excursion = update_excursion_with_v4_shadow
    setattr(paper_journal, _APPLIED_ATTR, True)
    return True
