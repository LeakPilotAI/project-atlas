"""End-to-end paper pipeline observability. Does not change strategy thresholds."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

import structlog

log = structlog.get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
FUNNEL_PATH = DATA_DIR / "pipeline_funnel.jsonl"
WINDOW_HOURS = 24.0

# Keys that are latest-cycle snapshots, not 24h sums.
SNAPSHOT_KEYS = ("tickers_received", "valid_prices", "liquid_set", "passed_volume_oi")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or _now()).isoformat()


def _parse_iso(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return _now()


class PaperPipeline:
    """In-memory funnel + rolling 24h window for micro-coach scans."""

    def __init__(self) -> None:
        self.last_error: Optional[str] = None
        self.last_cycle_at: Optional[str] = None
        self.last_market_data_ok_at: Optional[str] = None
        self.last_candle_ok_at: Optional[str] = None
        self.last_evaluation_at: Optional[str] = None
        self.last_qualified_at: Optional[str] = None
        self.last_paper_open_at: Optional[str] = None
        self.last_discord_alert_at: Optional[str] = None
        self.last_reject_reason: Optional[str] = None
        self.session_started_at: str = _iso()
        self.cycle_count: int = 0
        self._session: Dict[str, int] = defaultdict(int)
        self._cycle: Dict[str, int] = defaultdict(int)
        self._reject_24: Dict[str, int] = defaultdict(int)
        # Rolling 24h cycle snapshots: (ts, counts)
        self._window: Deque[Tuple[datetime, Dict[str, int]]] = deque()
        self._latest_universe: Dict[str, int] = {"markets": 0, "liquid": 0}
        self._load_window()

    def _load_window(self) -> None:
        path = FUNNEL_PATH
        if not path.exists():
            return
        cutoff = _now() - timedelta(hours=WINDOW_HOURS)
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    if row.get("event") != "cycle":
                        continue
                    ts = _parse_iso(str(row.get("ts") or ""))
                    if ts < cutoff:
                        continue
                    counts = {
                        k: int(v)
                        for k, v in row.items()
                        if k not in ("event", "ts") and isinstance(v, (int, float))
                    }
                    self._window.append((ts, counts))
                    if counts.get("tickers_received"):
                        self._latest_universe["markets"] = int(counts["tickers_received"])
                    if counts.get("liquid_set"):
                        self._latest_universe["liquid"] = int(counts["liquid_set"])
        except Exception as e:
            log.warning("funnel window load failed", error=str(e)[:200])

    def _prune_window(self, now: Optional[datetime] = None) -> None:
        cutoff = (now or _now()) - timedelta(hours=WINDOW_HOURS)
        while self._window and self._window[0][0] < cutoff:
            self._window.popleft()

    def _flush_cycle(self) -> None:
        if not self._cycle:
            return
        ts = _now()
        counts = {k: int(v) for k, v in self._cycle.items() if v}
        self._window.append((ts, counts))
        self._prune_window(ts)
        if counts.get("tickers_received"):
            self._latest_universe["markets"] = int(counts["tickers_received"])
        if counts.get("liquid_set"):
            self._latest_universe["liquid"] = int(counts["liquid_set"])
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with FUNNEL_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"event": "cycle", "ts": _iso(ts), **counts}) + "\n")
        except Exception as e:
            log.debug("funnel persist failed", error=str(e)[:160])

    def reset_cycle(self) -> None:
        self._flush_cycle()
        self._cycle = defaultdict(int)
        self.last_cycle_at = _iso()
        self.cycle_count += 1

    def inc(self, key: str, n: int = 1) -> None:
        self._cycle[key] += n
        self._session[key] += n

    def inc_reject(self, code: str, n: int = 1) -> None:
        code = (code or "OTHER").upper()
        self.inc(f"reject_{code.lower()}", n)
        self._reject_24[code] += n
        self.last_reject_reason = code

    def mark_error(self, err: str) -> None:
        self.last_error = str(err)[:400]
        log.warning("paper pipeline error", error=self.last_error)

    def snapshot_cycle(self) -> Dict[str, int]:
        return dict(self._cycle)

    def snapshot_session(self) -> Dict[str, int]:
        return dict(self._session)

    def last_24h(self) -> Dict[str, Any]:
        """Rolling 24h funnel. Markets/Liquid are latest-cycle snapshots."""
        self._prune_window()
        summed: Dict[str, int] = defaultdict(int)
        for _, counts in self._window:
            for k, v in counts.items():
                if k in SNAPSHOT_KEYS:
                    continue
                summed[k] += int(v)
        for k, v in self._cycle.items():
            if k in SNAPSHOT_KEYS:
                continue
            summed[k] += int(v)

        markets = int(self._cycle.get("tickers_received") or 0) or int(
            self._latest_universe.get("markets") or 0
        )
        liquid = int(self._cycle.get("liquid_set") or 0) or int(
            self._latest_universe.get("liquid") or 0
        )
        evaluated = int(summed.get("evaluated", 0))
        extension = int(summed.get("extension_pass", 0))
        rsi = int(summed.get("rsi_extreme", 0))
        quality = int(summed.get("quality_pass", 0))
        rr = int(summed.get("rr_pass", 0))
        qualified = int(summed.get("qualified", 0))
        paper = int(summed.get("paper_open_succeeded", 0))
        shadow = int(summed.get("shadow_candidates_recorded", 0))
        candle_success = int(summed.get("candle_success", 0))
        candle_fail = int(summed.get("candle_fail", 0))
        extension_evaluated = int(summed.get("extension_evaluated", 0)) or candle_success
        rsi_evaluated = int(summed.get("rsi_evaluated", 0))
        rr_evaluated = int(summed.get("rr_evaluated", 0))
        paper_closed = int(summed.get("paper_closed", 0))
        shadow_open = int(summed.get("shadow_open", 0))
        return {
            "hours": WINDOW_HOURS,
            "markets": markets,
            "liquid": liquid,
            "evaluated": evaluated,
            "extension_passed": extension,
            "rsi_passed": rsi,
            "quality_passed": quality,
            "rr_passed": rr,
            "qualified": qualified,
            "paper_trades": paper,
            "shadow_candidates": shadow,
            "candle_success": candle_success,
            "candle_fail": candle_fail,
            "extension_evaluated": extension_evaluated,
            "rsi_evaluated": rsi_evaluated,
            "quality_evaluated": int(summed.get("quality_evaluated", 0)),
            "rr_evaluated": rr_evaluated,
            "rejected_score": int(summed.get("rejected_score", 0)),
            "rejected_rr": int(summed.get("rejected_rr", 0)),
            "rejected_atr": int(summed.get("rejected_atr", 0)),
            "rejected_liquidity": int(summed.get("rejected_liquidity", 0)),
            "rsi_not_extreme": int(summed.get("reject_rsi_not_extreme", 0)),
            "extension_too_small": int(summed.get("reject_extension_too_small", 0)),
            "shadow_evals": int(summed.get("shadow_evaluation_attempts", 0)),
            "shadow_open": shadow_open,
            "paper_open_attempted": int(summed.get("paper_open_attempted", 0)),
            "paper_open_failed": int(summed.get("paper_open_failed", 0)),
            "paper_closed": paper_closed,
            "independent_extension_pass": int(summed.get("independent_extension_pass", 0)),
            "independent_rsi_pass": int(summed.get("independent_rsi_pass", 0)),
            "independent_rsi_long": int(summed.get("independent_rsi_long", 0)),
            "independent_rsi_short": int(summed.get("independent_rsi_short", 0)),
            "independent_quality_pass": int(summed.get("independent_quality_pass", 0)),
            "independent_rr_pass": int(summed.get("independent_rr_pass", 0)),
            "cycles": len(self._window) + (1 if self._cycle else 0),
            "bottleneck": self._bottleneck_code(
                evaluated, extension, rsi, quality, rr, qualified, paper
            ),
            "pct": {
                "liquid_of_markets": round(100.0 * liquid / markets, 1) if markets else 0.0,
                "evaluated_of_liquid": round(100.0 * evaluated / liquid, 1) if liquid else 0.0,
                "extension_of_evaluated": round(100.0 * extension / (extension_evaluated or evaluated), 1) if (extension_evaluated or evaluated) else 0.0,
                "rsi_of_extension": round(100.0 * rsi / extension, 1) if extension else 0.0,
                "quality_of_rsi": round(100.0 * quality / rsi, 1) if rsi else 0.0,
                "rr_of_quality": round(100.0 * rr / quality, 1) if quality else 0.0,
                "qualified_of_rr": round(100.0 * qualified / rr, 1) if rr else 0.0,
            },
        }

    def _bottleneck_code(
        self,
        evaluated: int,
        extension: int,
        rsi: int,
        quality: int,
        rr: int,
        qualified: int,
        paper: int,
    ) -> str:
        if evaluated == 0:
            return "evaluated"
        if extension == 0:
            return "extension"
        if rsi == 0:
            return "rsi"
        if quality == 0:
            return "quality"
        if rr == 0:
            return "rr"
        if qualified == 0:
            return "qualified"
        if paper == 0:
            return "paper_open"
        return "producing"

    def bottleneck_text(self, h: Optional[Dict[str, Any]] = None) -> str:
        h = h or self.last_24h()
        code = h.get("bottleneck") or "producing"
        e, x, r, q = h["evaluated"], h["extension_passed"], h["rsi_passed"], h["quality_passed"]
        rr, qd, p = h["rr_passed"], h["qualified"], h["paper_trades"]
        if code == "evaluated":
            return "No symbols evaluated. Data, liquid set, or gates."
        if code == "extension":
            return f"Extension is the bottleneck. {e} evaluated → {x} extension."
        if code == "rsi":
            return f"RSI is the bottleneck. {x} extension → {r} RSI."
        if code == "quality":
            return f"Quality scoring is the bottleneck. {r} RSI → {q} quality."
        if code == "rr":
            return f"R:R is the bottleneck. {q} quality → {rr} R:R."
        if code == "qualified":
            return f"Setups stall after R:R. {rr} R:R → {qd} qualified."
        if code == "paper_open":
            return f"Qualified but paper open failed. {qd} qualified → {p} paper."
        return f"Pipeline is producing paper trades. {p} in the last 24h."

    def log_cycle_funnel(self) -> None:
        c = self._cycle
        log.info(
            "ATLAS MICRO PIPELINE",
            markets_received=c.get("tickers_received", 0),
            valid_prices=c.get("valid_prices", 0),
            passed_volume_oi=c.get("passed_volume_oi", 0),
            liquid_set=c.get("liquid_set", 0),
            evaluated=c.get("evaluated", 0),
            cooldown_skipped=c.get("skip_cooldown", 0),
            already_open=c.get("skip_already_open", 0),
            candle_success=c.get("candle_success", 0),
            candle_failures=c.get("candle_fail", 0),
            extension_pass=c.get("extension_pass", 0),
            rsi_extreme=c.get("rsi_extreme", 0),
            long_candidates=c.get("long_candidates", 0),
            short_candidates=c.get("short_candidates", 0),
            quality_evaluated=c.get("quality_evaluated", 0),
            quality_pass=c.get("quality_pass", 0),
            rejected_score=c.get("rejected_score", 0),
            rejected_atr=c.get("rejected_atr", 0),
            rejected_rr=c.get("rejected_rr", 0),
            rr_pass=c.get("rr_pass", 0),
            qualified=c.get("qualified", 0),
            paper_open_attempted=c.get("paper_open_attempted", 0),
            paper_open_succeeded=c.get("paper_open_succeeded", 0),
            paper_open_failed=c.get("paper_open_failed", 0),
            discord_attempted=c.get("discord_trigger_attempted", 0),
            discord_delivered=c.get("discord_trigger_delivered", 0),
            shadow_evals=c.get("shadow_evaluation_attempts", 0),
        )

    def why_no_trade(self) -> Dict[str, Any]:
        h = self.last_24h()
        s = self._session
        qualified = int(h.get("qualified", 0) or s.get("qualified", 0))
        attempted = int(h.get("paper_open_attempted", 0) or s.get("paper_open_attempted", 0))
        succeeded = int(h.get("paper_trades", 0) or s.get("paper_open_succeeded", 0))
        evaluated = int(h.get("evaluated", 0) or s.get("evaluated", 0))
        quality = int(h.get("quality_evaluated", 0) or s.get("quality_evaluated", 0))
        if attempted > 0 and succeeded == 0:
            headline = "CRITICAL: Paper execution path is failing."
        elif qualified == 0 and evaluated > 0:
            headline = "No setups passed RSI + extension + quality + R:R."
        elif evaluated == 0:
            headline = "No symbols reached evaluation (data, liquid set, or gates)."
        elif quality == 0:
            headline = "Candidates never reached quality scoring."
        else:
            headline = "Pipeline is moving; waiting on a qualified setup."
        return {
            "headline": headline,
            "bottleneck": self.bottleneck_text(h),
            "session": {
                "evaluated": evaluated,
                "extension_too_small": int(h.get("extension_too_small", 0) or s.get("reject_extension_too_small", 0)),
                "rsi_not_extreme": int(h.get("rsi_not_extreme", 0) or s.get("reject_rsi_not_extreme", 0)),
                "rejected_score": int(h.get("rejected_score", 0) or s.get("rejected_score", 0)),
                "rejected_liquidity": int(h.get("rejected_liquidity", 0) or s.get("rejected_liquidity", 0)),
                "rejected_atr": int(h.get("rejected_atr", 0) or s.get("rejected_atr", 0)),
                "rejected_rr": int(h.get("rejected_rr", 0) or s.get("rejected_rr", 0)),
                "qualified": qualified,
                "paper_open_attempted": attempted,
                "paper_open_succeeded": succeeded,
            },
        }

    def stuck_warnings(self) -> List[str]:
        warnings: List[str] = []
        now = _now()
        s = self._session
        h = self.last_24h()
        last_eval = self.last_evaluation_at
        last_data = self.last_market_data_ok_at
        data_ok = False
        if last_data:
            try:
                dt = datetime.fromisoformat(last_data.replace("Z", "+00:00"))
                data_ok = (now - dt).total_seconds() < 300
            except Exception:
                data_ok = False
        eval_age = None
        if last_eval:
            try:
                dt = datetime.fromisoformat(last_eval.replace("Z", "+00:00"))
                eval_age = (now - dt).total_seconds()
            except Exception:
                eval_age = None
        if data_ok and (eval_age is None or eval_age > 30 * 60) and self.cycle_count >= 3:
            warnings.append("Market data is healthy but no evaluations in 30+ minutes.")
        if data_ok and int(s.get("shadow_evaluation_attempts", 0)) == 0 and self.cycle_count >= 3:
            warnings.append("Zero shadow evaluations this session — research hook may be dead.")
        if data_ok and int(h.get("quality_evaluated", 0) or s.get("quality_evaluated", 0)) == 0 and self.cycle_count >= 20:
            warnings.append("No candidates reached quality evaluation. Possible RSI/extension bottleneck.")
        if int(s.get("paper_open_attempted", 0)) > 0 and int(s.get("paper_open_succeeded", 0)) == 0:
            warnings.append("Paper opens attempted but none succeeded.")
        bn = h.get("bottleneck")
        if bn and bn not in ("producing", "evaluated") and int(h.get("evaluated", 0)) > 0:
            warnings.append(self.bottleneck_text(h))
        return warnings

    def effective_config(self) -> Dict[str, Any]:
        from app.core.config import get_settings

        s = get_settings()
        return {
            "perp_micro_enabled": bool(s.perp_micro_enabled),
            "perp_micro_paper_enabled": bool(s.perp_micro_paper_enabled),
            "perp_micro_all_markets": bool(s.perp_micro_all_markets),
            "min_volume": float(s.perp_micro_min_vol),
            "min_oi": float(s.perp_micro_min_oi),
            "rsi_long": float(s.perp_micro_rsi_long),
            "rsi_short": float(s.perp_micro_rsi_short),
            "extension": float(s.perp_micro_min_extension_pct),
            "minimum_rr": float(s.perp_micro_min_rr),
            "scalp_enabled": bool(getattr(s, "perp_micro_scalp_enabled", True)),
            "scalp_tp_r": float(getattr(s, "perp_micro_scalp_tp_r", 1.0)),
            "be_after_r": float(getattr(s, "perp_micro_be_after_r", 0.5)),
            "max_open": int(s.effective_max_open),
            "max_open_configured": int(s.perp_micro_max_open),
            "max_open_unlimited": int(s.perp_micro_max_open) <= 0,
            "max_daily_triggers": int(s.perp_micro_max_triggers_per_day),
            "scan_seconds": float(s.perp_micro_scan_seconds),
        }

    def funnel_24h_text(self) -> str:
        h = self.last_24h()
        p = h.get("pct") or {}

        def row(label: str, value: Any, extra: str = "", width: int = 20) -> str:
            return f"{label:<{width}}{value}{extra}"

        lines = [
            "**LAST 24 HOURS**",
            "",
            row("Markets:", h["markets"]),
            row("Liquid:", h["liquid"]),
            row("Evaluated:", h["evaluated"]),
            "",
            row("Extension passed:", h["extension_passed"], f"  ({p.get('extension_of_evaluated', 0)}%)"),
            row("RSI passed:", h["rsi_passed"], f"  ({p.get('rsi_of_extension', 0)}%)"),
            row("Quality passed:", h["quality_passed"], f"  ({p.get('quality_of_rsi', 0)}%)"),
            row("R:R passed:", h["rr_passed"], f"  ({p.get('rr_of_quality', 0)}%)"),
            row("Qualified:", h["qualified"]),
            "",
            row("Paper trades:", h["paper_trades"]),
            row("Shadow candidates:", h["shadow_candidates"]),
            "",
            f"Bottleneck: {self.bottleneck_text(h)}",
        ]
        return "\n".join(lines)

    def as_json(self) -> Dict[str, Any]:
        from app.alerts.discord import get_subscriber_ids, is_discord_ready

        c = self._cycle
        s = self._session
        why = self.why_no_trade()
        h = self.last_24h()
        return {
            "hyperliquid_data": "OK" if self.last_market_data_ok_at else "UNKNOWN",
            "ticker_count": int(c.get("tickers_received", 0) or s.get("tickers_received", 0) or h.get("markets", 0)),
            "valid_prices": int(c.get("valid_prices", 0)),
            "liquid_count": int(c.get("liquid_set", 0) or h.get("liquid", 0)),
            "symbols_evaluated": int(c.get("evaluated", 0)),
            "candle_success": int(c.get("candle_success", 0)),
            "candle_failures": int(c.get("candle_fail", 0)),
            "extension_pass": int(c.get("extension_pass", 0)),
            "rsi_extreme": int(c.get("rsi_extreme", 0)),
            "quality_evaluated": int(c.get("quality_evaluated", 0)),
            "quality_pass": int(c.get("quality_pass", 0)),
            "rr_pass": int(c.get("rr_pass", 0)),
            "qualified": int(c.get("qualified", 0)),
            "paper_open_attempts": int(c.get("paper_open_attempted", 0)),
            "paper_open_success": int(c.get("paper_open_succeeded", 0)),
            "discord_ready": bool(is_discord_ready()),
            "discord_subscribers": len(get_subscriber_ids()),
            "discord_trigger_attempts": int(c.get("discord_trigger_attempted", 0)),
            "discord_trigger_delivered": int(c.get("discord_trigger_delivered", 0)),
            "shadow_evaluation_attempts": int(c.get("shadow_evaluation_attempts", 0)),
            "shadow_candidates_recorded": int(c.get("shadow_candidates_recorded", 0)),
            "shadow_candidates_deduped": int(c.get("shadow_candidates_deduped", 0)),
            "last_cycle_at": self.last_cycle_at,
            "last_successful_market_data_fetch": self.last_market_data_ok_at,
            "last_successful_candle_fetch": self.last_candle_ok_at,
            "last_candidate_evaluation": self.last_evaluation_at,
            "last_qualified_setup": self.last_qualified_at,
            "last_paper_open": self.last_paper_open_at,
            "last_discord_alert": self.last_discord_alert_at,
            "last_error": self.last_error,
            "last_reject_reason": self.last_reject_reason,
            "session": dict(s),
            "cycle": dict(c),
            "last_24h": h,
            "bottleneck": self.bottleneck_text(h),
            "why_no_trade": why,
            "warnings": self.stuck_warnings(),
            "effective_config": self.effective_config(),
            "cycle_count": self.cycle_count,
            "session_started_at": self.session_started_at,
        }

    def summary_text(self) -> str:
        try:
            from app.services.funnel_research import funnel_research

            return funnel_research.diagnostics_text()
        except Exception:
            pass
        j = self.as_json()
        why = j["why_no_trade"]
        lines = [
            "**ATLAS DIAGNOSTICS**",
            f"Data: `{j['hyperliquid_data']}`",
            f"Last scan: `{j['last_cycle_at'] or 'n/a'}`",
            f"Discord: `{'READY' if j['discord_ready'] else 'NOT READY'}` · subs `{j['discord_subscribers']}`",
            f"Last error: `{j['last_error'] or 'NONE'}`",
            "",
            self.funnel_24h_text(),
            "",
            f"**WHY NO TRADE?** {why['headline']}",
        ]
        sess = why["session"]
        lines.append(
            f"24h rejects — RSI `{sess['rsi_not_extreme']}` · "
            f"ext `{sess['extension_too_small']}` · score `{sess['rejected_score']}` · "
            f"liq `{sess['rejected_liquidity']}` · ATR `{sess['rejected_atr']}` · "
            f"R:R `{sess['rejected_rr']}`"
        )
        for w in j["warnings"]:
            lines.append(f"⚠ {w}")
        cfg = j.get("effective_config") or {}
        if cfg:
            lines.append(
                f"Gates locked: RSI `{cfg.get('rsi_long')}/{cfg.get('rsi_short')}` · "
                f"ext `{cfg.get('extension')}%` · R:R `{cfg.get('minimum_rr')}`"
            )
        text = "\n".join(lines)
        if len(text) > 1900:
            text = text[:1900] + "…"
        return text


paper_pipeline = PaperPipeline()
