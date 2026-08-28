"""Non-invasive funnel hooks. Does not change strategy thresholds."""

from __future__ import annotations

from datetime import datetime, timezone


def apply() -> None:
    from app.services.paper_pipeline import paper_pipeline
    from app.services.perp_micro_coach import PerpMicroCoach

    if getattr(PerpMicroCoach, "_atlas_pipeline_hooked", False):
        return

    orig_cycle = PerpMicroCoach._cycle
    orig_try = PerpMicroCoach._try_symbol
    orig_fetch = PerpMicroCoach._fetch_tickers

    async def _fetch(self):
        data = await orig_fetch(self)
        paper_pipeline.inc("tickers_received", len(data or []))
        if data:
            paper_pipeline.last_market_data_ok_at = datetime.now(timezone.utc).isoformat()
            valid = 0
            try:
                from app.services.perp_micro_coach import _f, _sym, _to_dict

                for raw in data:
                    t = _to_dict(raw)
                    px = _f(t, "price", "markPx", "midPx", "mark_px", "mid", "last")
                    if _sym(t) and px > 0:
                        valid += 1
            except Exception:
                valid = 0
            if valid:
                paper_pipeline.inc("valid_prices", valid)
        return data

    async def _cycle(self):
        paper_pipeline.reset_cycle()
        try:
            await orig_cycle(self)
        finally:
            n = int(getattr(self, "liquid_count", 0) or 0)
            paper_pipeline.inc("liquid_set", n)
            paper_pipeline.inc("passed_volume_oi", n)
            paper_pipeline.log_cycle_funnel()

    async def _try(self, symbol: str, price: float) -> bool:
        paper_pipeline.inc("evaluated")
        paper_pipeline.last_evaluation_at = datetime.now(timezone.utc).isoformat()
        ok = await orig_try(self, symbol, price)
        if ok:
            paper_pipeline.inc("qualified")
            paper_pipeline.inc("paper_open_attempted")
            paper_pipeline.inc("paper_open_succeeded")
            paper_pipeline.last_qualified_at = datetime.now(timezone.utc).isoformat()
            paper_pipeline.last_paper_open_at = datetime.now(timezone.utc).isoformat()
        return ok

    PerpMicroCoach._fetch_tickers = _fetch
    PerpMicroCoach._cycle = _cycle
    PerpMicroCoach._try_symbol = _try
    PerpMicroCoach._atlas_pipeline_hooked = True
