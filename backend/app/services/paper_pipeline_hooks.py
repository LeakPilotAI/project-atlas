"""Non-invasive funnel hooks. Does not change strategy thresholds."""

from __future__ import annotations

from datetime import datetime, timezone


def apply() -> None:
    from app.services.paper_pipeline import paper_pipeline
    from app.services.paper_try_symbol import instrumented_try_symbol
    from app.services.perp_micro_coach import PerpMicroCoach
    from app.services.shadow_research import ShadowResearch
    from app.services.paper_journal import JOURNAL_PATH, iter_jsonl, paper_journal
    from app.services.perp_manual_service import PerpManualService
    from app.services.perp_setup_paper_mirror import SOURCE as AUTO_PAPER_SOURCE
    from app.services.perp_setup_paper_mirror import perp_setup_paper_mirror
    from app.services.v4_journal_observer import install_paper_journal_observer

    # V4 shadow observation is independent of the legacy coach hook. Install it
    # first so a previously-hooked coach cannot accidentally skip activation.
    install_paper_journal_observer(paper_journal)

    # Manual-perp setups automatically mirror into the common append-only paper
    # journal only after price actually reaches an active L1/L2/L3 state. PREPARE
    # means a resting manual order can be staged; it is NOT counted as a paper fill.
    # This keeps paper evidence honest while requiring no user click.
    if not getattr(PerpManualService, "_atlas_auto_paper_hooked", False):
        orig_manual_refresh = PerpManualService.refresh

        def _auto_paper_stats() -> dict:
            opened_ids: set[str] = set()
            closed_ids: set[str] = set()
            for row in iter_jsonl(JOURNAL_PATH):
                if str(row.get("source") or "") != AUTO_PAPER_SOURCE:
                    continue
                tid = str(row.get("trade_id") or "")
                if not tid:
                    continue
                if row.get("event") == "open":
                    opened_ids.add(tid)
                elif row.get("event") == "close":
                    closed_ids.add(tid)
            return {
                "source": AUTO_PAPER_SOURCE,
                "opened_total": len(opened_ids),
                "closed_total": len(closed_ids),
                "open_count": len(opened_ids - closed_ids),
                "included_in_paper_journal": True,
                "counts_for_live": False,
            }

        async def _manual_refresh(self):
            snap = await orig_manual_refresh(self)
            markets = list(snap.get("markets") or [])
            price_map = {
                str(row.get("symbol") or "").upper(): float(row.get("price") or 0.0)
                for row in markets
                if str(row.get("symbol") or "").strip() and float(row.get("price") or 0.0) > 0
            }
            try:
                sync = await perp_setup_paper_mirror.sync(list(snap.get("setups") or []), price_map)
                stats = _auto_paper_stats()
                stats["last_sync"] = dict(sync)
                stats["updated_at"] = datetime.now(timezone.utc).isoformat()
                self.last_snapshot["auto_paper"] = stats
            except Exception as exc:
                self.last_snapshot["auto_paper"] = {
                    **_auto_paper_stats(),
                    "error": f"{type(exc).__name__}: {str(exc)[:180]}",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            return self.snapshot()

        PerpManualService.refresh = _manual_refresh
        PerpManualService._atlas_auto_paper_hooked = True

    if getattr(PerpMicroCoach, "_atlas_pipeline_hooked", False):
        return

    orig_cycle = PerpMicroCoach._cycle
    orig_fetch = PerpMicroCoach._fetch_tickers
    orig_research = ShadowResearch.research_summary_text

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
        return await instrumented_try_symbol(self, symbol, price)

    def _research(self, hours: float = 24.0) -> str:
        head = paper_pipeline.funnel_24h_text()
        rest = orig_research(self, hours)
        text = f"{head}\n\n{rest}"
        if len(text) > 1900:
            text = text[:1900] + "\u2026"
        return text

    PerpMicroCoach._fetch_tickers = _fetch
    PerpMicroCoach._cycle = _cycle
    PerpMicroCoach._try_symbol = _try
    PerpMicroCoach._atlas_pipeline_hooked = True
    ShadowResearch.research_summary_text = _research
