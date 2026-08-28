"""Signal-intelligence / funnel research.

RESEARCH ONLY. Never changes production RSI/extension/quality/R:R gates.
Never mixes shadow PnL with paper PnL.
Persists across restarts via data/funnel_research.jsonl.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

import structlog

log = structlog.get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
RESEARCH_PATH = DATA_DIR / "funnel_research.jsonl"
WINDOW_HOURS = 24.0
MAX_IN_MEMORY = 25000

EXT_LOCK = 1.4
RSI_LONG_LOCK = 28.0
RSI_SHORT_LOCK = 72.0
RR_LOCK = 1.8

EXT_SENSITIVITY = (0.5, 0.75, 1.0, 1.25, 1.4, 1.5, 2.0, 2.5)
RSI_LONG_SENSITIVITY = (20.0, 25.0, 28.0, 30.0, 35.0)
RSI_SHORT_SENSITIVITY = (65.0, 70.0, 72.0, 75.0, 80.0)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or _now()).isoformat()


def _parse_iso(s: str) -> datetime:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return _now()


def _pct(n: float, d: float) -> float:
    if d <= 0:
        return 0.0
    return round(100.0 * float(n) / float(d), 1)


def _percentile(xs: List[float], p: float) -> Optional[float]:
    if not xs:
        return None
    s = sorted(float(x) for x in xs)
    if len(s) == 1:
        return round(s[0], 6)
    k = (len(s) - 1) * (p / 100.0)
    f = int(math.floor(k))
    c = min(f + 1, len(s) - 1)
    if f == c:
        return round(s[f], 6)
    return round(s[f] + (s[c] - s[f]) * (k - f), 6)


def _stats(xs: List[float]) -> Dict[str, Any]:
    if not xs:
        return {
            "n": 0,
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "p5": None,
            "p10": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "p99": None,
        }
    n = len(xs)
    mean = sum(xs) / n
    return {
        "n": n,
        "min": round(min(xs), 6),
        "max": round(max(xs), 6),
        "mean": round(mean, 6),
        "median": _percentile(xs, 50),
        "p5": _percentile(xs, 5),
        "p10": _percentile(xs, 10),
        "p75": _percentile(xs, 75),
        "p90": _percentile(xs, 90),
        "p95": _percentile(xs, 95),
        "p99": _percentile(xs, 99),
    }


def _stage(label: str, count: int, prev: int) -> Dict[str, Any]:
    return {
        "label": label,
        "count": int(count),
        "pct_of_previous": _pct(count, prev),
    }


class FunnelResearch:
    """Persistent 24h research observations. Production strategy untouched."""

    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._rows: Deque[Tuple[datetime, Dict[str, Any]]] = deque()
        self._load()

    def _load(self) -> None:
        path = RESEARCH_PATH
        if not path.exists():
            return
        cutoff = _now() - timedelta(hours=WINDOW_HOURS)
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    if row.get("event") != "observe":
                        continue
                    ts = _parse_iso(str(row.get("ts") or ""))
                    if ts < cutoff:
                        continue
                    self._rows.append((ts, row))
            while len(self._rows) > MAX_IN_MEMORY:
                self._rows.popleft()
        except Exception as e:
            log.warning("funnel research load failed", error=str(e)[:200])

    def _prune(self) -> None:
        cutoff = _now() - timedelta(hours=WINDOW_HOURS)
        while self._rows and self._rows[0][0] < cutoff:
            self._rows.popleft()
        while len(self._rows) > MAX_IN_MEMORY:
            self._rows.popleft()

    def _append(self, row: Dict[str, Any]) -> None:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with RESEARCH_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, default=str) + "\n")
        except Exception as e:
            log.debug("funnel research persist failed", error=str(e)[:160])

    def observe(
        self,
        *,
        symbol: str,
        price: float,
        ext_pct: float,
        rsi: float,
        quality_score: float,
        quality_min: float,
        rr: float,
        atr: float,
        volume: float = 0.0,
        open_interest: float = 0.0,
        regime: str = "UNKNOWN",
        side_hyp: str = "NONE",
        sequential_stage: str = "evaluated",
        features: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record one evaluated market. Independent gates — not sequential."""
        from app.services.paper_pipeline import paper_pipeline

        ts = _now()
        ext_ok = float(ext_pct) >= EXT_LOCK
        rsi_long = float(rsi) <= RSI_LONG_LOCK
        rsi_short = float(rsi) >= RSI_SHORT_LOCK
        rsi_ok = rsi_long or rsi_short
        quality_ok = float(quality_score) >= float(quality_min) if quality_min else False
        rr_ok = float(rr) >= RR_LOCK if rr == rr else False  # NaN guard

        paper_pipeline.inc("extension_evaluated")
        paper_pipeline.inc("rsi_evaluated")
        paper_pipeline.inc("quality_research_evaluated")
        paper_pipeline.inc("rr_evaluated")
        if ext_ok:
            paper_pipeline.inc("independent_extension_pass")
        if rsi_long:
            paper_pipeline.inc("independent_rsi_long")
        if rsi_short:
            paper_pipeline.inc("independent_rsi_short")
        if rsi_ok:
            paper_pipeline.inc("independent_rsi_pass")
        if quality_ok:
            paper_pipeline.inc("independent_quality_pass")
        if rr_ok:
            paper_pipeline.inc("independent_rr_pass")

        row: Dict[str, Any] = {
            "event": "observe",
            "ts": _iso(ts),
            "symbol": str(symbol).upper(),
            "price": float(price),
            "ext_pct": round(float(ext_pct), 6),
            "rsi": round(float(rsi), 4),
            "quality_score": round(float(quality_score), 4),
            "quality_min": round(float(quality_min), 4),
            "rr": round(float(rr), 4),
            "atr": round(float(atr), 8),
            "volume": float(volume or 0),
            "open_interest": float(open_interest or 0),
            "regime": regime or "UNKNOWN",
            "side_hyp": (side_hyp or "NONE").upper(),
            "sequential_stage": sequential_stage,
            "ind_ext": bool(ext_ok),
            "ind_rsi_long": bool(rsi_long),
            "ind_rsi_short": bool(rsi_short),
            "ind_rsi": bool(rsi_ok),
            "ind_quality": bool(quality_ok),
            "ind_rr": bool(rr_ok),
            "features": features or {},
        }
        self._rows.append((ts, row))
        self._prune()
        self._append(row)
        return row

    def _window_rows(self) -> List[Dict[str, Any]]:
        self._prune()
        return [r for _, r in self._rows]

    def independent_gates(self) -> Dict[str, Any]:
        rows = self._window_rows()
        n = len(rows)
        ext = sum(1 for r in rows if r.get("ind_ext"))
        rsi_l = sum(1 for r in rows if r.get("ind_rsi_long"))
        rsi_s = sum(1 for r in rows if r.get("ind_rsi_short"))
        rsi = sum(1 for r in rows if r.get("ind_rsi"))
        q = sum(1 for r in rows if r.get("ind_quality"))
        rr = sum(1 for r in rows if r.get("ind_rr"))
        return {
            "n": n,
            "extension_ge_1_4": {"count": ext, "pct": _pct(ext, n)},
            "rsi_long_le_28": {"count": rsi_l, "pct": _pct(rsi_l, n)},
            "rsi_short_ge_72": {"count": rsi_s, "pct": _pct(rsi_s, n)},
            "rsi_either": {"count": rsi, "pct": _pct(rsi, n)},
            "quality_ge_threshold": {"count": q, "pct": _pct(q, n)},
            "rr_ge_1_8": {"count": rr, "pct": _pct(rr, n)},
            "note": "Independent of sequential production gates. Research only.",
        }

    def distributions(self) -> Dict[str, Any]:
        rows = self._window_rows()
        ext = [float(r["ext_pct"]) for r in rows if r.get("ext_pct") is not None]
        rsi = [float(r["rsi"]) for r in rows if r.get("rsi") is not None]
        quality = [float(r["quality_score"]) for r in rows if r.get("quality_score") is not None]
        rr = [float(r["rr"]) for r in rows if r.get("rr") is not None]
        return {
            "extension": _stats(ext),
            "rsi": _stats(rsi),
            "quality": _stats(quality),
            "rr": _stats(rr),
        }

    def sensitivity(self) -> Dict[str, Any]:
        rows = self._window_rows()
        n = len(rows)
        ext_counts = {}
        for t in EXT_SENSITIVITY:
            c = sum(1 for r in rows if float(r.get("ext_pct") or 0) >= t)
            ext_counts[str(t)] = {"count": c, "pct": _pct(c, n)}
        rsi_long = {}
        for t in RSI_LONG_SENSITIVITY:
            c = sum(1 for r in rows if float(r.get("rsi") or 100) <= t)
            rsi_long[f"long_le_{t:g}"] = {"count": c, "pct": _pct(c, n)}
        rsi_short = {}
        for t in RSI_SHORT_SENSITIVITY:
            c = sum(1 for r in rows if float(r.get("rsi") or 0) >= t)
            rsi_short[f"short_ge_{t:g}"] = {"count": c, "pct": _pct(c, n)}
        return {
            "n": n,
            "extension": ext_counts,
            "rsi_long": rsi_long,
            "rsi_short": rsi_short,
            "locked_production": {
                "rsi_long": RSI_LONG_LOCK,
                "rsi_short": RSI_SHORT_LOCK,
                "extension": EXT_LOCK,
                "rr": RR_LOCK,
            },
            "note": "Does not change production thresholds.",
        }

    def sequential_funnel(self) -> Dict[str, Any]:
        from app.services.paper_pipeline import paper_pipeline
        from app.services.shadow_research import shadow_research
        from app.services.paper_journal import paper_journal

        h = paper_pipeline.last_24h()
        markets = int(h.get("markets") or 0)
        liquid = int(h.get("liquid") or 0)
        evaluated = int(h.get("evaluated") or 0)
        candle_ok = int(h.get("candle_success") or 0)
        candle_fail = int(h.get("candle_fail") or 0)
        ext_eval = int(h.get("extension_evaluated") or candle_ok)
        ext_pass = int(h.get("extension_passed") or 0)
        rsi_eval = int(h.get("rsi_evaluated") or ext_pass)
        rsi_pass = int(h.get("rsi_passed") or 0)
        q_eval = int(h.get("quality_evaluated") or 0)
        q_pass = int(h.get("quality_passed") or 0)
        rr_eval = int(h.get("rr_evaluated") or q_pass)
        rr_pass = int(h.get("rr_passed") or 0)
        qualified = int(h.get("qualified") or 0)
        paper_att = int(h.get("paper_open_attempted") or 0)
        paper_open = int(h.get("paper_trades") or 0)
        paper_closed = int(h.get("paper_closed") or 0)
        shadow_eval = int(h.get("shadow_evals") or 0)
        shadow_open = int(h.get("shadow_open") or 0)
        try:
            sh = shadow_research.funnel_stats(24.0)
            shadow_closed = int(sh.get("resolved") or 0)
            if not shadow_open:
                shadow_open = int(sh.get("shadow_tracked") or 0)
        except Exception:
            shadow_closed = 0

        stages = [
            _stage("markets", markets, markets or 1),
            _stage("liquid", liquid, markets),
            _stage("evaluated", evaluated, liquid),
            _stage("candle_success", candle_ok, evaluated),
            _stage("candle_failure", candle_fail, evaluated),
            _stage("extension_evaluated", ext_eval, candle_ok or evaluated),
            _stage("extension_passed", ext_pass, ext_eval or candle_ok or evaluated),
            _stage("rsi_evaluated", rsi_eval, ext_pass or ext_eval),
            _stage("rsi_passed", rsi_pass, rsi_eval or ext_pass),
            _stage("quality_evaluated", q_eval, rsi_pass),
            _stage("quality_passed", q_pass, q_eval or rsi_pass),
            _stage("rr_evaluated", rr_eval, q_pass or q_eval),
            _stage("rr_passed", rr_pass, rr_eval or q_pass),
            _stage("qualified", qualified, rr_pass or q_pass),
            _stage("paper_open_attempted", paper_att, qualified),
            _stage("paper_opened", paper_open, paper_att or qualified),
            _stage("paper_closed", paper_closed, paper_open or 1),
            _stage("shadow_evaluated", shadow_eval, evaluated),
            _stage("shadow_opened", shadow_open, shadow_eval or evaluated),
            _stage("shadow_closed", shadow_closed, shadow_open or 1),
        ]
        return {
            "hours": WINDOW_HOURS,
            "stages": stages,
            "by_name": {s["label"]: s for s in stages},
        }

    def bottleneck(self) -> Dict[str, Any]:
        """First meaningful sequential bottleneck + independent confirmation."""
        from app.services.paper_pipeline import paper_pipeline

        h = paper_pipeline.last_24h()
        ind = self.independent_gates()
        n = int(ind.get("n") or 0)
        evaluated = int(h.get("evaluated") or 0)
        candle_ok = int(h.get("candle_success") or 0)
        candle_fail = int(h.get("candle_fail") or 0)
        ext = int(h.get("extension_passed") or 0)
        rsi = int(h.get("rsi_passed") or 0)
        quality = int(h.get("quality_passed") or 0)
        rr = int(h.get("rr_passed") or 0)
        qualified = int(h.get("qualified") or 0)
        paper = int(h.get("paper_trades") or 0)
        attempted = int(h.get("paper_open_attempted") or 0)

        ind_ext = int((ind.get("extension_ge_1_4") or {}).get("count") or 0)
        ind_rsi = int((ind.get("rsi_either") or {}).get("count") or 0)
        ind_q = int((ind.get("quality_ge_threshold") or {}).get("count") or 0)

        if evaluated == 0:
            code, reason = "EVALUATED", "0 markets evaluated. Data, liquid set, or scan idle."
        elif candle_ok == 0 and candle_fail > 0:
            code, reason = "CANDLES", f"{candle_fail}/{evaluated} candle fetches failed. Cannot measure extension/RSI."
        elif candle_ok == 0 and n == 0:
            code, reason = "CANDLES", f"0/{evaluated} markets produced usable candles."
        elif ext == 0:
            code = "EXTENSION"
            reason = (
                f"{ext}/{candle_ok or n or evaluated} markets currently exceed {EXT_LOCK}% extension "
                f"(sequential). Independent: {ind_ext}/{n} would pass extension ≥ {EXT_LOCK}%."
            )
        elif rsi == 0:
            code = "RSI"
            reason = (
                f"{ext} passed extension, {rsi} passed RSI {RSI_LONG_LOCK}/{RSI_SHORT_LOCK} "
                f"(sequential). Independent RSI either: {ind_rsi}/{n}."
            )
        elif quality == 0:
            code = "QUALITY"
            reason = (
                f"{rsi} passed extension and RSI, but {quality} passed quality "
                f"(sequential). Independent quality: {ind_q}/{n}."
            )
        elif rr == 0:
            code, reason = "RR", f"{quality} passed quality, {rr} passed R:R ≥ {RR_LOCK} (sequential)."
        elif qualified == 0:
            code, reason = "QUALIFIED", f"{rr} passed R:R, {qualified} qualified."
        elif attempted > 0 and paper == 0:
            code, reason = "PAPER_EXECUTION", f"{qualified} qualified but {paper} paper trades opened."
        elif qualified > 0 and paper == 0:
            code, reason = "PAPER_EXECUTION", f"{qualified} markets qualified but 0 paper trades opened."
        else:
            code, reason = "PRODUCING", f"{paper} paper trades opened in the last 24h."

        return {
            "code": code,
            "reason": reason,
            "sequential": {
                "evaluated": evaluated,
                "candle_success": candle_ok,
                "extension": ext,
                "rsi": rsi,
                "quality": quality,
                "rr": rr,
                "qualified": qualified,
                "paper": paper,
            },
            "independent": ind,
        }

    def why_no_paper_trades(self) -> Dict[str, Any]:
        b = self.bottleneck()
        return {
            "headline": f"Bottleneck: {b['code']}",
            "reason": b["reason"],
            "bottleneck": b["code"],
            **b,
        }

    def research_payload(self) -> Dict[str, Any]:
        from app.services.paper_pipeline import paper_pipeline
        from app.services.shadow_research import shadow_research

        funnel = self.sequential_funnel()
        dist = self.distributions()
        bn = self.bottleneck()
        sh = shadow_research.funnel_stats(24.0)
        return {
            "hours": WINDOW_HOURS,
            "funnel": funnel,
            "independent_gates": self.independent_gates(),
            "distributions": dist,
            "sensitivity": self.sensitivity(),
            "bottleneck": bn,
            "why_no_paper_trades": self.why_no_paper_trades(),
            "shadow": {
                "evaluated": sh.get("raw_candidates"),
                "open": sh.get("shadow_open_now"),
                "resolved": sh.get("resolved"),
                "wins": sh.get("shadow_wins"),
                "losses": sh.get("shadow_losses"),
                "avg_r": sh.get("shadow_expectancy_r"),
                "avg_mfe": sh.get("avg_mfe_r"),
                "avg_mae": sh.get("avg_mae_r"),
            },
            "paper_24h": {
                "opened": int(paper_pipeline.last_24h().get("paper_trades") or 0),
                "closed": int(paper_pipeline.last_24h().get("paper_closed") or 0),
            },
            "locked_gates": {
                "rsi_long": RSI_LONG_LOCK,
                "rsi_short": RSI_SHORT_LOCK,
                "extension": EXT_LOCK,
                "rr": RR_LOCK,
            },
            "observations": len(self._window_rows()),
        }

    def research_summary_text(self) -> str:
        p = self.research_payload()
        f = p["funnel"]["by_name"]
        d = p["distributions"]
        sh = p["shadow"]
        bn = p["bottleneck"]

        def c(name: str) -> int:
            return int((f.get(name) or {}).get("count") or 0)

        def pct(name: str) -> float:
            return float((f.get(name) or {}).get("pct_of_previous") or 0)

        ext_p95 = (d.get("extension") or {}).get("p95")
        rsi_p5 = (d.get("rsi") or {}).get("p5")
        rsi_p95 = (d.get("rsi") or {}).get("p95")
        q_p95 = (d.get("quality") or {}).get("p95")
        rr_p95 = (d.get("rr") or {}).get("p95")
        ind = p["independent_gates"]

        lines = [
            "**ATLAS RESEARCH**",
            "",
            "**24H FUNNEL**",
            f"Evaluated: `{c('evaluated')}`",
            f"Extension: `{c('extension_passed')}` ({pct('extension_passed')}%)",
            f"RSI: `{c('rsi_passed')}` ({pct('rsi_passed')}%)",
            f"Quality: `{c('quality_passed')}` ({pct('quality_passed')}%)",
            f"R:R: `{c('rr_passed')}` ({pct('rr_passed')}%)",
            f"Qualified: `{c('qualified')}`",
            f"Paper: `{c('paper_opened')}`",
            f"Shadow: `{sh.get('resolved') or 0}` resolved / `{sh.get('open') or 0}` open",
            "",
            f"**BOTTLENECK:** `{bn['code']}`",
            str(bn.get("reason") or ""),
            "",
            "**INDEPENDENT GATES** (research, not sequential)",
            f"Ext≥1.4%: `{ind['extension_ge_1_4']['count']}/{ind['n']}` ({ind['extension_ge_1_4']['pct']}%)",
            f"RSI≤28: `{ind['rsi_long_le_28']['count']}` · RSI≥72: `{ind['rsi_short_ge_72']['count']}`",
            f"Quality: `{ind['quality_ge_threshold']['count']}` · R:R≥1.8: `{ind['rr_ge_1_8']['count']}`",
            "",
            "**FEATURE DISTRIBUTIONS**",
            f"Extension P95: `{ext_p95 if ext_p95 is not None else 'n/a'}%`",
            f"RSI P5/P95: `{rsi_p5 if rsi_p5 is not None else 'n/a'} / {rsi_p95 if rsi_p95 is not None else 'n/a'}`",
            f"Quality P95: `{q_p95 if q_p95 is not None else 'n/a'}`",
            f"R:R P95: `{rr_p95 if rr_p95 is not None else 'n/a'}`",
            "",
            "**SHADOW PERFORMANCE** (not paper)",
            f"Shadow resolved: `{sh.get('resolved') or 0}`",
            f"Hypothetical winners: `{sh.get('wins') or 0}`",
            f"Hypothetical losers: `{sh.get('losses') or 0}`",
            f"Average shadow R: `{(sh.get('avg_r') or 0):+.2f}`",
            f"Average MFE: `{(sh.get('avg_mfe') or 0):+.2f}`",
            f"Average MAE: `{(sh.get('avg_mae') or 0):+.2f}`",
            "",
            "_Gates locked: RSI 28/72 · ext 1.4% · R:R 1.8. Not financial advice._",
        ]
        text = "\n".join(lines)
        if len(text) > 1900:
            text = text[:1900] + "…"
        return text

    def diagnostics_text(self) -> str:
        why = self.why_no_paper_trades()
        from app.services.paper_pipeline import paper_pipeline

        h = paper_pipeline.last_24h()
        lines = [
            "**ATLAS DIAGNOSTICS**",
            "",
            f"**WHY ARE THERE NO PAPER TRADES?**",
            f"Bottleneck: `{why['bottleneck']}`",
            f"Reason: {why['reason']}",
            "",
            paper_pipeline.funnel_24h_text(),
            "",
            "_Production gates unchanged. Research layer only._",
        ]
        text = "\n".join(lines)
        if len(text) > 1900:
            text = text[:1900] + "…"
        return text


funnel_research = FunnelResearch()
