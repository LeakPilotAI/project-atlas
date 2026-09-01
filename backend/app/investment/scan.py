"""Opt-in investment research scanner. Independent of the Hyperliquid trading loop.

Manual:  `InvestmentScanner(...).run_once()`
Scheduled: `await scanner.start()` behind INVESTMENT_SCAN_ENABLED (default false).

Crashes here must never stop the trading engine. start() / the loop swallow errors.
No real orders. No ML. No look-ahead: scoring uses bars with session_date ≤ T.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional
from uuid import uuid4

from app.investment.alerts import AlertStore, commit_move, should_emit_move
from app.investment.blocking import blocking_pair, blocker_bucket, is_qualified
from app.investment.completeness import completeness_report
from app.investment.diagnostics import cycle_summary, format_data_health, save_last_cycle
from app.investment.engine import process_research
from app.investment.enums import DataQuality, EvidenceQuality, InvestmentAlertState, ThesisState
from app.investment.evaluation import classify_evaluation
from app.investment.freshness import restamp
from app.investment.history import load_bars
from app.investment.ingest import FetchPlan, InvestmentIngest
from app.investment.intelligence import evaluate_equity_move
from app.investment.lookahead import as_of_date, filter_bars_as_of
from app.investment.market_hours import session_status
from app.investment.models import MeasuredValue, PortfolioInput
from app.investment.move_store import append_move_event
from app.investment.notify import deliver_investment_alert, format_equity_move_alert
from app.investment.outcomes import empty_outcomes, enrich_observation
from app.investment.paper_book import PaperBook
from app.investment.portfolio import load_portfolio
from app.investment.provider_health import configure_provider_health, get_provider_health
from app.investment.research import InvestmentResearch
from app.investment.research_models import ResearchRecord
from app.investment.research_store import append_research
from app.investment.scan_models import SCAN_VERSION, ScanObservation, ScanReport
from app.investment.scan_settings import ScanSettings
from app.investment.scan_store import append_observation, append_scan_log, load_observations
from app.investment.snapshot import (
    InvestmentSnapshot,
    load_latest_snapshot,
    save_latest_snapshot,
)
from app.investment.storage import (
    FETCH_STATE_PATH,
    LATEST_DIR,
    LEDGER_PATH,
    OBSERVATIONS_PATH,
    OUTCOMES_PATH,
    PAPER_STATE_PATH,
    bootstrap_universe_if_missing,
    ensure_dirs,
)
from app.investment.tape import set_rows as set_equity_tape
from app.investment.thesis_trend import apply_deterioration, detect_deterioration
from app.investment.universe import InvestmentUniverse, UniverseEntry, load_universe
from app.investment.yfinance_client import ProviderCallError
from app.investment.blocking import blocking_pair, blocker_bucket, is_qualified
from app.investment.completeness import completeness_report
from app.investment.diagnostics import cycle_summary, format_data_health, save_last_cycle
from app.investment.engine import process_research
from app.investment.enums import DataQuality, EvidenceQuality, InvestmentAlertState, ThesisState
from app.investment.evaluation import classify_evaluation
from app.investment.freshness import restamp
from app.investment.history import load_bars
from app.investment.ingest import FetchPlan, InvestmentIngest
from app.investment.lookahead import as_of_date, filter_bars_as_of
from app.investment.market_hours import session_status
from app.investment.models import MeasuredValue, PortfolioInput
from app.investment.notify import deliver_investment_alert
from app.investment.outcomes import empty_outcomes, enrich_observation
from app.investment.paper_book import PaperBook
from app.investment.portfolio import load_portfolio
from app.investment.provider_health import configure_provider_health, get_provider_health
from app.investment.research import InvestmentResearch
from app.investment.research_models import ResearchRecord
from app.investment.research_store import append_research
from app.investment.scan_models import SCAN_VERSION, ScanObservation, ScanReport
from app.investment.scan_settings import ScanSettings
from app.investment.scan_store import append_observation, append_scan_log, load_observations
from app.investment.snapshot import (
    InvestmentSnapshot,
    load_latest_snapshot,
    save_latest_snapshot,
)
from app.investment.storage import (
    FETCH_STATE_PATH,
    LATEST_DIR,
    LEDGER_PATH,
    OBSERVATIONS_PATH,
    OUTCOMES_PATH,
    PAPER_STATE_PATH,
    bootstrap_universe_if_missing,
    ensure_dirs,
)
from app.investment.universe import InvestmentUniverse, UniverseEntry, load_universe
from app.investment.yfinance_client import ProviderCallError

try:
    import structlog

    log = structlog.get_logger("investment.scan")
except Exception:  # pragma: no cover
    class _Log:
        def info(self, *a, **k):
            return None

        def warning(self, *a, **k):
            return None

        def error(self, *a, **k):
            return None

    log = _Log()


ScoreFn = Callable[..., ResearchRecord]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(raw: object) -> Optional[datetime]:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def field_quality_map(snap: InvestmentSnapshot, *, history_quality: str = "") -> Dict[str, str]:
    out: Dict[str, str] = {"price": snap.price.quality.value}
    for k, mv in snap.fundamentals.items():
        out[f"fundamentals.{k}"] = mv.quality.value if isinstance(mv.quality, DataQuality) else str(mv.quality)
    for k, mv in snap.valuation.items():
        out[f"valuation.{k}"] = mv.quality.value if isinstance(mv.quality, DataQuality) else str(mv.quality)
    if history_quality:
        out["history"] = history_quality
    return out


def _iso(dt) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def known_at_payload(snap: InvestmentSnapshot, bars, as_of: datetime) -> Dict[str, object]:
    fund_ts = [mv.retrieved_at for mv in snap.fundamentals.values() if getattr(mv, "retrieved_at", None)]
    val_ts = [mv.retrieved_at for mv in snap.valuation.values() if getattr(mv, "retrieved_at", None)]
    cutoff = bars[-1].session_date if bars else None
    return {
        "as_of": as_of.isoformat(),
        "price_effective": _iso(snap.price.effective_timestamp or snap.price.timestamp),
        "price_retrieved": _iso(snap.price.retrieved_at),
        "fundamentals_retrieved": _iso(max(fund_ts) if fund_ts else None),
        "valuation_retrieved": _iso(max(val_ts) if val_ts else None),
        "history_cutoff": cutoff,
        "look_ahead_cutoff": as_of_date(as_of),
    }



def data_source_status(snap: InvestmentSnapshot, fetched: Dict[str, bool]) -> Dict[str, str]:
    status: Dict[str, str] = {}
    status["price"] = "FETCHED" if fetched.get("price") else "CACHED"
    if snap.price.quality in (DataQuality.MISSING, DataQuality.UNKNOWN):
        status["price"] = snap.price.quality.value
    status["fundamentals"] = "FETCHED" if fetched.get("fundamentals") else "CACHED"
    if not snap.fundamentals:
        status["fundamentals"] = "MISSING"
    status["valuation"] = "FETCHED" if fetched.get("valuation") else "CACHED"
    if not snap.valuation:
        status["valuation"] = "MISSING"
    status["history"] = "FETCHED" if fetched.get("history") else "CACHED"
    if snap.failures:
        status["provider_failures"] = str(len(snap.failures))
    return status


def restamp_snapshot(snap: InvestmentSnapshot, now: datetime) -> InvestmentSnapshot:
    snap.price = restamp(snap.price, kind="price", now=now)
    snap.fundamentals = {
        k: restamp(v, kind="fundamental", now=now) for k, v in snap.fundamentals.items()
    }
    snap.valuation = {k: restamp(v, kind="valuation", now=now) for k, v in snap.valuation.items()}
    return snap


class FetchState:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path
        self._by: Dict[str, dict] = {}
        self.load()

    def load(self) -> None:
        self._by = {}
        if not self.path or not Path(self.path).exists():
            return
        try:
            data = json.loads(Path(self.path).read_text(encoding="utf-8"))
        except Exception:
            return
        rows = data.get("symbols") if isinstance(data, dict) else {}
        if isinstance(rows, dict):
            self._by = {str(k).upper(): v for k, v in rows.items() if isinstance(v, dict)}

    def save(self) -> None:
        if not self.path:
            return
        ensure_dirs()
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.path).write_text(json.dumps({"symbols": self._by}, indent=2), encoding="utf-8")

    def last(self, symbol: str, key: str) -> Optional[datetime]:
        row = self._by.get(str(symbol).upper()) or {}
        return _parse_dt(row.get(key))

    def touch(self, symbol: str, **times: datetime) -> None:
        key = str(symbol).upper()
        row = dict(self._by.get(key) or {})
        for k, v in times.items():
            if v is not None:
                row[k] = v.isoformat()
        self._by[key] = row
        self.save()


def _age_ok(ts: Optional[datetime], ttl: float, now: datetime) -> bool:
    if ts is None:
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds() <= ttl


def plan_fetches(
    symbol: str,
    *,
    session: str,
    settings: ScanSettings,
    state: FetchState,
    now: datetime,
    has_prior: bool,
    has_history: bool,
) -> FetchPlan:
    """Skip provider calls when cached data is still within the refresh window.

    MARKET_CLOSED: last session close cannot get fresher — skip live price if we
    already have a prior snapshot. Fundamentals/valuation still refresh on their TTLs.
    """
    price_due = not _age_ok(state.last(symbol, "price"), settings.price_refresh_seconds, now)
    hist_due = not _age_ok(state.last(symbol, "history"), settings.history_refresh_seconds, now) or not has_history
    fund_due = not _age_ok(state.last(symbol, "fundamentals"), settings.fundamental_refresh_seconds, now)
    val_due = not _age_ok(state.last(symbol, "valuation"), settings.valuation_refresh_seconds, now)
    if session != "MARKET_OPEN" and has_prior:
        price_due = False
    if not has_prior:
        price_due = fund_due = val_due = True
        hist_due = True
    return FetchPlan(price=price_due, history=hist_due, fundamentals=fund_due, valuation=val_due)


def failed_record(symbol: str, name: str, reason: str, as_of: datetime) -> ResearchRecord:
    rec = ResearchRecord(
        symbol=symbol,
        name=name,
        timestamp=as_of,
        classification=InvestmentAlertState.NO_ACTION,
        opportunity_score=None,
        evidence_quality=EvidenceQuality.INSUFFICIENT,
        thesis=ThesisState.UNKNOWN,
        missing_critical=["price", "fundamentals", "valuation"],
        generational_blockers=[reason],
        data_risk=[reason],
        coverage_label="provider failure — no invented values",
    )
    rec.explain.data_quality_notes.append(reason)
    rec.explain.missing_data.extend(["price", "fundamentals", "valuation"])
    return rec


def format_scan_dashboard(report: ScanReport) -> str:
    counts = report.counts
    lines = [
        "**ATLAS INVESTMENT SCAN**",
        f"Session: `{report.session}`",
        f"scan_version: `{report.scan_version}`",
        "_Not a performance dashboard. Outcome data is not yet sufficient. "
        "Separate from Hyperliquid /paper /research._",
        "",
        "INVESTMENT SCAN",
        f"Universe: {report.universe}",
        f"Evaluated: {report.evaluated}",
        f"WATCH: {counts.get('WATCH', 0)}",
        f"ACCUMULATION: {counts.get('ACCUMULATION', 0)}",
        f"DEEP VALUE: {counts.get('DEEP_VALUE', 0)}",
        f"GENERATIONAL: {counts.get('GENERATIONAL_OPPORTUNITY', 0)}",
        f"THESIS BROKEN: {counts.get('THESIS_BROKEN', 0)}",
        f"NO ACTION: {counts.get('NO_ACTION', 0)}",
        "",
        "TOP OPPORTUNITIES",
        "Symbol | Price | Drawdown | Score | Classification | Thesis | Evidence",
    ]
    ranked = sorted(
        [o for o in report.observations if o.research is not None],
        key=lambda o: (o.research.opportunity_score is not None, o.research.opportunity_score or -1),
        reverse=True,
    )
    shown = [o for o in ranked if o.research and o.research.classification is not InvestmentAlertState.NO_ACTION][:8]
    if not shown:
        shown = ranked[:5]
    if not shown:
        lines.append("(none)")
    for o in shown:
        r = o.research
        dd = r.drawdown.current_drawdown
        dd_s = "n/a" if dd is None else f"{dd:.0%}"
        lines.append(
            f"{r.symbol} | {r.price} | {dd_s} | {r.opportunity_score}/100 | "
            f"{r.classification.value} | {r.thesis.value} | {r.evidence_quality.value}"
        )
    buckets: Dict[str, int] = {}
    for o in report.observations:
        if o.classification == InvestmentAlertState.GENERATIONAL_OPPORTUNITY.value:
            continue
        bucket = blocker_bucket(o.blocking_reason or "Other")
        buckets[bucket] = buckets.get(bucket, 0) + 1
    lines += ["", "TOP BLOCKERS"]
    if not buckets:
        lines.append("(none)")
    else:
        for k, v in sorted(buckets.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"{k}: {v}")
    if report.session == "MARKET_CLOSED":
        lines += ["", "Market is CLOSED. Research may update; last session prints are not live quotes."]
    elif report.session == "SYSTEM_OFFLINE":
        lines += ["", "SYSTEM OFFLINE — not the same as a closed market."]
    ev = report.evaluation_counts or {}
    lines += [
        "",
        "DATA QUALITY",
        f"VALID: {ev.get('VALID', 0)}  VALID_NO_ACTION: {ev.get('VALID_NO_ACTION', 0)}",
        f"INSUFFICIENT_DATA: {ev.get('INSUFFICIENT_DATA', 0)}  PROVIDER_ERROR: {ev.get('PROVIDER_ERROR', 0)}",
        f"RATE_LIMITED: {ev.get('RATE_LIMITED', 0)}  STALE_DATA: {ev.get('STALE_DATA', 0)}",
        "",
        "INVESTMENT OPPORTUNITY",
        "Classifications above are research calls, not fills and not alpha.",
        "",
        "PERFORMANCE",
        "Not available. No win rate. No alpha. Dataset size is not strategy success.",
        "",
        "Research rankings are not probabilities. No real orders. No alpha claim.",
    ]
    return "\n".join(lines)


class InvestmentScanner:
    """Independently startable/stoppable. Default off."""

    version = SCAN_VERSION

    def __init__(
        self,
        *,
        settings: Optional[ScanSettings] = None,
        universe: Optional[InvestmentUniverse] = None,
        ingest: Optional[InvestmentIngest] = None,
        research: Optional[InvestmentResearch] = None,
        alert_store: Optional[AlertStore] = None,
        portfolio: Optional[PortfolioInput] = None,
        paper: Optional[PaperBook] = None,
        history_root=None,
        observations_path: Optional[Path] = None,
        outcomes_path: Optional[Path] = None,
        fetch_state_path: Optional[Path] = None,
        persist: Optional[bool] = None,
        notify: Optional[Callable] = None,
        system_ok: bool = True,
    ) -> None:
        self.settings = settings
        self._universe_override = universe
        self.ingest = ingest
        self.research = research or InvestmentResearch()
        self.alert_store = alert_store
        self._portfolio_override = portfolio
        self.paper = paper
        self.history_root = history_root
        self.observations_path = observations_path
        self.outcomes_path = outcomes_path
        self.fetch_state_path = fetch_state_path
        self._persist_override = persist
        self._notify = notify
        self.system_ok = system_ok
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self.last_report: Optional[ScanReport] = None
        self._latest: Dict[str, InvestmentSnapshot] = {}

    @property
    def running(self) -> bool:
        return self._running

    def _cfg(self) -> ScanSettings:
        return self.settings or ScanSettings.from_env()

    def _persist(self, cfg: ScanSettings) -> bool:
        if self._persist_override is not None:
            return self._persist_override
        return cfg.persist

    def _universe(self) -> InvestmentUniverse:
        if self._universe_override is not None:
            return self._universe_override
        bootstrap_universe_if_missing()
        return load_universe()

    def _store(self, persist: bool) -> AlertStore:
        if self.alert_store is not None:
            return self.alert_store
        return AlertStore(persist=persist)

    def _ing(self, universe: InvestmentUniverse, persist: bool) -> InvestmentIngest:
        if self.ingest is not None:
            return self.ingest
        return InvestmentIngest(universe=universe, history_root=self.history_root, persist=persist)

    def _port(self) -> PortfolioInput:
        if self._portfolio_override is not None:
            return self._portfolio_override
        return load_portfolio()

    def _paper_book(self, port: PortfolioInput, persist: bool) -> Optional[PaperBook]:
        if self.paper is not None:
            return self.paper
        if not persist:
            if port.is_complete_for_personalized_plan() and port.available_cash is not None:
                return PaperBook(cash=float(port.available_cash), state_path=None, ledger_path=None)
            return None
        if PAPER_STATE_PATH.exists():
            return PaperBook.load(PAPER_STATE_PATH, ledger_path=LEDGER_PATH)
        if port.is_complete_for_personalized_plan() and port.available_cash is not None:
            return PaperBook(
                cash=float(port.available_cash),
                state_path=PAPER_STATE_PATH,
                ledger_path=LEDGER_PATH,
            )
        return None

    async def start(self) -> None:
        """Opt-in. Never raises into the trading lifespan."""
        try:
            if self._task and not self._task.done():
                return
            cfg = self._cfg()
            if not cfg.enabled:
                log.info("investment scanner disabled (opt-in)")
                return
            self._running = True
            self._task = asyncio.create_task(self._loop(), name="investment_scanner")
            log.info(
                "investment scanner started",
                interval_open=cfg.interval_open_seconds,
                interval_closed=cfg.interval_closed_seconds,
            )
        except Exception as e:
            self._running = False
            log.warning("investment scanner failed to start; trading continues", error=str(e)[:200])

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        log.info("investment scanner stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.warning("investment scan cycle failed; trading continues", error=str(e)[:200])
            cfg = self._cfg()
            session = session_status(system_ok=self.system_ok)
            delay = cfg.interval_open_seconds if session == "MARKET_OPEN" else cfg.interval_closed_seconds
            delay = max(60.0, float(delay))
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                break

    async def run_once(self, *, now: Optional[datetime] = None) -> ScanReport:
        now = now or _now()
        cfg = self._cfg()
        persist = self._persist(cfg)
        if persist:
            try:
                configure_provider_health(persist=True)
            except Exception:
                pass
        session = session_status(now, system_ok=self.system_ok)
        scan_id = f"scan-{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
        report = ScanReport(scan_id=scan_id, started_at=now, session=session)
        universe = self._universe()
        ordered = universe.scan_order()
        report.universe = len(ordered)
        ing = self._ing(universe, persist)
        store = self._store(persist)
        port = self._port()
        paper = self._paper_book(port, persist)
        fetch_state = FetchState(path=self.fetch_state_path if self.fetch_state_path is not None else (FETCH_STATE_PATH if persist else None))
        obs_path = self.observations_path if self.observations_path is not None else (OBSERVATIONS_PATH if persist else None)
        out_path = self.outcomes_path if self.outcomes_path is not None else (OUTCOMES_PATH if persist else None)

        counts = {s.value: 0 for s in InvestmentAlertState}
        tape_rows: List[dict] = []
        for entry in ordered:
            try:
                obs = await self._evaluate_one(
                    entry,
                    cfg=cfg,
                    now=now,
                    session=session,
                    scan_id=scan_id,
                    ing=ing,
                    universe=universe,
                    fetch_state=fetch_state,
                    store=store,
                    port=port,
                    paper=paper,
                    persist=persist,
                    obs_path=obs_path,
                    tape_rows=tape_rows,
                )
                report.observations.append(obs)
                report.evaluated += 1
                counts[obs.classification] = counts.get(obs.classification, 0) + 1
                if obs.evaluation:
                    report.evaluation_counts[obs.evaluation] = report.evaluation_counts.get(obs.evaluation, 0) + 1
                if obs.fetched.get("alert_emitted"):
                    report.alerts_emitted += 1
            except Exception as e:
                report.failed += 1
                log.warning("investment symbol failed", symbol=entry.symbol, error=str(e)[:200])
                rec = failed_record(entry.symbol, entry.name, f"scan exception: {str(e)[:160]}", now)
                first, factors = blocking_pair(rec)
                from app.investment.enums import EvaluationStatus

                obs = ScanObservation(
                    scan_id=scan_id,
                    as_of=now,
                    symbol=entry.symbol,
                    qualified=False,
                    classification=rec.classification.value,
                    blocking_reason=first,
                    blocking_factors=factors,
                    session=session,
                    research=rec,
                    outcomes=empty_outcomes(),
                    provider_failures=[{"code": "SCAN_EXCEPTION", "message": str(e)[:200]}],
                    evaluation=EvaluationStatus.PROVIDER_ERROR.value,
                    evaluation_reason=f"scan exception: {str(e)[:160]}",
                )
                report.observations.append(obs)
                counts[obs.classification] = counts.get(obs.classification, 0) + 1
                if persist and obs_path:
                    append_observation(obs, path=obs_path)
                    if self.observations_path is None:
                        append_research(rec)
                    else:
                        append_research(rec, path=Path(self.observations_path).with_name("opportunities.jsonl"))
            if cfg.inter_symbol_delay_seconds and entry is not ordered[-1]:
                await asyncio.sleep(max(0.0, float(cfg.inter_symbol_delay_seconds)))

        report.counts = counts
        report.finished_at = _now()
        report.dashboard = format_scan_dashboard(report)
        report.data_health = format_data_health(report)
        self.last_report = report
        try:
            set_equity_tape(tape_rows)
        except Exception as e:
            log.warning("equity tape update failed", error=str(e)[:160])
        if persist:
            append_scan_log(report)
            try:
                save_last_cycle(cycle_summary(report))
            except Exception as e:
                log.warning("last cycle persist failed", error=str(e)[:160])
            try:
                self._enrich_past(now=now, outcomes_path=out_path)
            except Exception as e:
                log.warning("outcome enrichment failed", error=str(e)[:200])
        return report

    async def _evaluate_one(
        self,
        entry: UniverseEntry,
        *,
        cfg: ScanSettings,
        now: datetime,
        session: str,
        scan_id: str,
        ing: InvestmentIngest,
        universe: InvestmentUniverse,
        fetch_state: FetchState,
        store: AlertStore,
        port: PortfolioInput,
        paper: Optional[PaperBook],
        persist: bool,
        obs_path: Optional[Path],
        tape_rows: Optional[List[dict]] = None,
    ) -> ScanObservation:
        prior = self._latest.get(entry.symbol)
        if prior is None:
            prior = load_latest_snapshot(entry.symbol)
            if prior is not None:
                self._latest[entry.symbol] = prior
        has_history = bool(load_bars(entry.symbol, root=self.history_root or getattr(ing, "history_root", None)))
        plan = plan_fetches(
            entry.symbol,
            session=session,
            settings=cfg,
            state=fetch_state,
            now=now,
            has_prior=prior is not None,
            has_history=has_history,
        )
        snap = await self._ingest_with_retry(ing, entry, cfg, plan, prior)
        snap = restamp_snapshot(snap, now)
        self._latest[entry.symbol] = snap
        if persist:
            try:
                save_latest_snapshot(snap)
            except Exception:
                pass
        if plan.price:
            fetch_state.touch(entry.symbol, price=now)
        if plan.history:
            fetch_state.touch(entry.symbol, history=now)
        if plan.fundamentals:
            fetch_state.touch(entry.symbol, fundamentals=now)
        if plan.valuation:
            fetch_state.touch(entry.symbol, valuation=now)

        raw_bars = load_bars(entry.symbol, root=self.history_root or getattr(ing, "history_root", None))
        bars = filter_bars_as_of(raw_bars, now)
        rec = self.research.score_snapshot(snap, bars, as_of=now)
        rec.timestamp = now
        deteriorating, dnotes = detect_deterioration(
            snap.fundamentals, prior.fundamentals if prior is not None else None
        )
        if deteriorating:
            rec.thesis = apply_deterioration(rec.thesis, True)
            rec.explain.weakens_thesis.extend(dnotes)
            rec.explain.invalidation.extend(dnotes)

        headlines: List[dict] = []
        intel = evaluate_equity_move(
            entry,
            rec,
            universe=universe,
            history_root=self.history_root or getattr(ing, "history_root", None),
            headlines=headlines,
            deteriorating=deteriorating,
        )
        mv_score = intel["move"].score
        if mv_score is not None and mv_score >= 65:
            try:
                from app.investment.cause import fetch_yahoo_headlines

                headlines = await fetch_yahoo_headlines(entry.symbol)
                intel = evaluate_equity_move(
                    entry,
                    rec,
                    universe=universe,
                    history_root=self.history_root or getattr(ing, "history_root", None),
                    headlines=headlines,
                    deteriorating=deteriorating,
                )
            except Exception:
                pass
        if tape_rows is not None:
            tape_rows.append(intel["tape_row"])
        if persist and mv_score is not None and mv_score >= 40:
            try:
                append_move_event(
                    {
                        "symbol": entry.symbol,
                        "as_of": now.isoformat(),
                        "price": rec.price,
                        "move": intel["move"].as_dict(),
                        "relative": intel["relative"].as_dict(),
                        "cause": intel["cause"].as_dict(),
                        "thesis": rec.thesis.value,
                        "evidence": rec.evidence_quality.value,
                        "classification": intel["move"].classification.value,
                    }
                )
            except Exception as e:
                log.warning("move event persist failed", symbol=entry.symbol, error=str(e)[:160])

        first, factors = blocking_pair(rec)
        fetched = {
            "price": plan.price,
            "history": plan.history,
            "fundamentals": plan.fundamentals,
            "valuation": plan.valuation,
        }
        hist_q = "MISSING"
        if bars:
            last_q = getattr(bars[-1], "quality", "") or "FRESH"
            hist_q = last_q if isinstance(last_q, str) else str(last_q)
        status, eval_reason = classify_evaluation(snap, rec, failures=snap.failures)
        complete = completeness_report(snap, evidence=rec.evidence_quality)
        obs = ScanObservation(
            scan_id=scan_id,
            as_of=now,
            symbol=entry.symbol,
            qualified=is_qualified(rec),
            classification=rec.classification.value,
            blocking_reason=first,
            blocking_factors=factors,
            field_quality=field_quality_map(snap, history_quality=hist_q),
            data_source_status=data_source_status(snap, fetched),
            provider_failures=list(snap.failures),
            session=session,
            research=rec,
            outcomes=empty_outcomes(),
            fetched=fetched,
            evaluation=status.value,
            evaluation_reason=eval_reason,
            completeness=complete,
            known_at=known_at_payload(snap, bars, now),
        )
        if persist:
            if obs_path:
                append_observation(obs, path=obs_path)
            if self.observations_path is None:
                append_research(rec)
            else:
                append_research(rec, path=Path(self.observations_path).with_name("opportunities.jsonl"))

        result = process_research(
            rec,
            portfolio=port,
            store=store,
            paper=paper,
            now=now,
            system_ok=self.system_ok,
            persist=persist,
        )
        if result.get("decision") is not None and getattr(result["decision"], "emit", False):
            # counted on the report after return; stash on obs via side channel
            obs.fetched["alert_emitted"] = True
        if result.get("alert_text") and cfg.notify_discord:
            try:
                if self._notify is not None:
                    self._notify(result["alert_text"], rec.symbol, result["decision"].priority)
                else:
                    await deliver_investment_alert(
                        result["alert_text"],
                        symbol=rec.symbol,
                        priority=result["decision"].priority,
                    )
            except Exception as e:
                log.warning("investment notify failed", symbol=rec.symbol, error=str(e)[:160])
        try:
            move_cls = intel["move"].classification
            mdec = should_emit_move(store, entry.symbol, move_cls)
            if mdec.emit:
                commit_move(store, entry.symbol, move_cls, now=now)
                plan = result.get("plan")
                if intel.get("review") is not None and plan is not None:
                    plan.review_levels = intel["review"].as_dict()
                text = format_equity_move_alert(
                    symbol=entry.symbol,
                    tape_row=intel["tape_row"],
                    plan=plan,
                    review=None if intel.get("review") is None else intel["review"].as_dict(),
                    why=rec.explain.why_now or rec.explain.why_interesting,
                    risks=rec.explain.risks,
                )
                if cfg.notify_discord:
                    if self._notify is not None:
                        self._notify(text, rec.symbol, mdec.priority)
                    else:
                        await deliver_investment_alert(text, symbol=rec.symbol, priority=mdec.priority)
                obs.fetched["move_alert_emitted"] = True
        except Exception as e:
            log.warning("equity move alert failed", symbol=entry.symbol, error=str(e)[:160])
        return obs

    async def _ingest_with_retry(
        self,
        ing: InvestmentIngest,
        entry: UniverseEntry,
        cfg: ScanSettings,
        plan: FetchPlan,
        prior: Optional[InvestmentSnapshot],
    ) -> InvestmentSnapshot:
        last_exc: Optional[BaseException] = None
        attempts = max(1, int(cfg.max_retries) + 1)
        for i in range(attempts):
            try:
                return await ing.ingest_symbol(
                    entry,
                    history_period=cfg.history_period,
                    fetch=plan,
                    prior=prior,
                )
            except ProviderCallError as e:
                last_exc = e
                if not getattr(e, "failure", None) or not e.failure.retryable:
                    break
                delay = float(cfg.retry_base_seconds) * (2 ** i)
                if e.failure.code == "RATE_LIMIT":
                    delay *= 2
                await asyncio.sleep(delay)
            except Exception as e:
                last_exc = e
                await asyncio.sleep(float(cfg.retry_base_seconds) * (2 ** i))
        # Graceful partial: never invent values.
        if prior is not None:
            log.warning("provider failed; using prior snapshot labeled stale/unknown", symbol=entry.symbol)
            return prior
        from app.investment.snapshot import snapshot_from_parts

        reason = f"provider failure: {str(last_exc)[:160] if last_exc else 'unknown'}"
        return snapshot_from_parts(
            entry,
            price=MeasuredValue.unknown("yfinance", reason),
            fundamentals={},
            valuation={},
            failures=[{"symbol": entry.symbol, "code": "PROVIDER_FAIL", "message": reason}],
        )

    def _enrich_past(self, *, now: datetime, outcomes_path: Optional[Path]) -> None:
        """Separate process: fill outcome fields for *prior* observations only.

        Never feeds those prices back into score / classification / alerts.
        Never overwrites observations.jsonl.
        """
        if outcomes_path is None:
            return
        from app.investment.outcomes import load_outcomes

        obs_path = self.observations_path or OBSERVATIONS_PATH
        rows = load_observations(obs_path)
        already = {r.get("observation_id") for r in load_outcomes(outcomes_path)}
        for row in rows:
            oid = row.get("observation_id")
            if not oid or oid in already:
                continue
            as_of_raw = row.get("as_of") or row.get("timestamp")
            if not as_of_raw:
                continue
            try:
                as_of = datetime.fromisoformat(str(as_of_raw).replace("Z", "+00:00"))
            except Exception:
                continue
            if as_of >= now:
                continue  # current cycle — leave outcomes NULL
            symbol = str(row.get("symbol") or "")
            if not symbol:
                continue
            bars = load_bars(symbol, root=self.history_root)
            try:
                written = enrich_observation(row, bars, now=now, outcomes_path=outcomes_path)
                if written:
                    already.add(oid)
            except Exception:
                continue


investment_scanner = InvestmentScanner()


async def start_investment_scanner() -> None:
    """Lifespan helper. Swallows all errors so trading continues."""
    try:
        await investment_scanner.start()
    except Exception as e:
        log.warning("investment scanner start wrapper caught error; trading continues", error=str(e)[:200])


async def stop_investment_scanner() -> None:
    try:
        await investment_scanner.stop()
    except Exception:
        pass
