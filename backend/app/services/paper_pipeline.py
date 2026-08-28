"""End-to-end paper pipeline observability. Does not change strategy thresholds."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or _now()).isoformat()


class PaperPipeline:
    """In-memory funnel + timestamps for micro-coach scans."""

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
        self._session = defaultdict(int)
        self._cycle = defaultdict(int)
        self._reject_24: Dict[str, int] = defaultdict(int)

    def reset_cycle(self) -> None:
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
            rejected_score=c.get("rejected_score", 0),
            rejected_atr=c.get("rejected_atr", 0),
            rejected_rr=c.get("rejected_rr", 0),
            qualified=c.get("qualified", 0),
            paper_open_attempted=c.get("paper_open_attempted", 0),
            paper_open_succeeded=c.get("paper_open_succeeded", 0),
            paper_open_failed=c.get("paper_open_failed", 0),
            discord_attempted=c.get("discord_trigger_attempted", 0),
            discord_delivered=c.get("discord_trigger_delivered", 0),
            shadow_evals=c.get("shadow_evaluation_attempts", 0),
        )

    def why_no_trade(self) -> Dict[str, Any]:
        s = self._session
        qualified = int(s.get("qualified", 0))
        attempted = int(s.get("paper_open_attempted", 0))
        succeeded = int(s.get("paper_open_succeeded", 0))
        evaluated = int(s.get("evaluated", 0))
        quality = int(s.get("quality_evaluated", 0))
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
            "session": {
                "evaluated": evaluated,
                "extension_too_small": int(s.get("reject_extension_too_small", 0)),
                "rsi_not_extreme": int(s.get("reject_rsi_not_extreme", 0)),
                "rejected_score": int(s.get("rejected_score", 0)),
                "rejected_liquidity": int(s.get("rejected_liquidity", 0)),
                "rejected_atr": int(s.get("rejected_atr", 0)),
                "rejected_rr": int(s.get("rejected_rr", 0)),
                "qualified": qualified,
                "paper_open_attempted": attempted,
                "paper_open_succeeded": succeeded,
            },
        }

    def stuck_warnings(self) -> List[str]:
        warnings: List[str] = []
        now = _now()
        s = self._session
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
        if data_ok and int(s.get("quality_evaluated", 0)) == 0 and self.cycle_count >= 20:
            warnings.append("No candidates reached quality evaluation. Possible RSI/extension bottleneck.")
        if int(s.get("paper_open_attempted", 0)) > 0 and int(s.get("paper_open_succeeded", 0)) == 0:
            warnings.append("Paper opens attempted but none succeeded.")
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
            "max_open": int(s.perp_micro_max_open),
            "max_daily_triggers": int(s.perp_micro_max_triggers_per_day),
            "scan_seconds": float(s.perp_micro_scan_seconds),
        }

    def as_json(self) -> Dict[str, Any]:
        from app.alerts.discord import get_subscriber_ids, is_discord_ready

        c = self._cycle
        s = self._session
        why = self.why_no_trade()
        return {
            "hyperliquid_data": "OK" if self.last_market_data_ok_at else "UNKNOWN",
            "ticker_count": int(c.get("tickers_received", 0) or s.get("tickers_received", 0)),
            "valid_prices": int(c.get("valid_prices", 0)),
            "liquid_count": int(c.get("liquid_set", 0)),
            "symbols_evaluated": int(c.get("evaluated", 0)),
            "candle_success": int(c.get("candle_success", 0)),
            "candle_failures": int(c.get("candle_fail", 0)),
            "extension_pass": int(c.get("extension_pass", 0)),
            "rsi_extreme": int(c.get("rsi_extreme", 0)),
            "quality_evaluated": int(c.get("quality_evaluated", 0)),
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
            "why_no_trade": why,
            "warnings": self.stuck_warnings(),
            "effective_config": self.effective_config(),
            "cycle_count": self.cycle_count,
            "session_started_at": self.session_started_at,
        }

    def summary_text(self) -> str:
        j = self.as_json()
        why = j["why_no_trade"]
        lines = [
            "**ATLAS DIAGNOSTICS**",
            f"Data: `{j['hyperliquid_data']}`",
            f"Hyperliquid tickers (last cycle): `{j['ticker_count']}`",
            f"Liquid markets: `{j['liquid_count']}`",
            f"Last scan: `{j['last_cycle_at'] or 'n/a'}`",
            f"Evaluated: `{j['symbols_evaluated']}`",
            f"Candle failures: `{j['candle_failures']}`",
            f"Extension passed: `{j['extension_pass']}`",
            f"RSI extreme: `{j['rsi_extreme']}`",
            f"Quality evaluated: `{j['quality_evaluated']}`",
            f"Qualified: `{j['qualified']}`",
            f"Shadow evals (cycle): `{j['shadow_evaluation_attempts']}`",
            f"Paper opens: `{j['paper_open_success']}/{j['paper_open_attempts']}`",
            f"Discord: `{'READY' if j['discord_ready'] else 'NOT READY'}` · subs `{j['discord_subscribers']}`",
            f"Trigger DMs (cycle): `{j['discord_trigger_delivered']}`",
            f"Last error: `{j['last_error'] or 'NONE'}`",
            "",
            f"**WHY NO TRADE?** {why['headline']}",
        ]
        sess = why["session"]
        lines.append(
            f"Session rejects — RSI `{sess['rsi_not_extreme']}` · "
            f"ext `{sess['extension_too_small']}` · score `{sess['rejected_score']}` · "
            f"liq `{sess['rejected_liquidity']}` · ATR `{sess['rejected_atr']}` · "
            f"R:R `{sess['rejected_rr']}`"
        )
        for w in j["warnings"]:
            lines.append(f"⚠ {w}")
        text = "\n".join(lines)
        if len(text) > 1900:
            text = text[:1900] + "…"
        return text


paper_pipeline = PaperPipeline()
